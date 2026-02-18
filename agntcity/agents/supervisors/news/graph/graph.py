# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
import logging
import uuid
import asyncio
import re
from typing import Optional, List, Dict

from pydantic import BaseModel, Field
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.graph import MessagesState
from langgraph.graph import StateGraph, END
from ioa_observe.sdk.decorators import agent, graph

from agents.supervisors.news.graph.tools import assign_url_to_worker
from common.llm import get_llm

logger = logging.getLogger("lungo.news.supervisor.graph")

class NodeStates:
    SUPERVISOR = "news_supervisor"
    ASSIGN_URLS = "assign_urls"
    COLLECT_RESULTS = "collect_results"
    RETRY_FAILED = "retry_failed"

class GraphState(MessagesState):
    """
    Represents the state of our graph, passed between nodes.
    """
    next_node: str
    urls_to_scrape: List[str] = []
    urls_in_progress: Dict[str, str] = {}  # url -> worker_id
    completed_urls: Dict[str, str] = {}   # url -> result
    failed_urls: Dict[str, int] = {}        # url -> retry_count
    all_results: List[Dict] = []

@agent(name="news_agent")
class NewsGraph:
    def __init__(self):
        self.graph = self.build_graph()
        self.max_retries = 3
        self.rate_limit_delay = 1.0  # seconds between requests

    @graph(name="news_graph")
    def build_graph(self) -> CompiledStateGraph:
        """
        Constructs and compiles a LangGraph instance for news scraping orchestration.

        Agent Flow:
        - supervisor: Extract URLs from prompt, initialize tracking
        - assign_urls: Assign URLs to worker agents with rate limiting
        - collect_results: Aggregate all completed results
        - retry_failed: Handle retries for failed URLs

        Returns:
        CompiledGraph: A fully compiled LangGraph instance ready for execution.
        """
        workflow = StateGraph(GraphState)

        # Define nodes
        workflow.add_node(NodeStates.SUPERVISOR, self._supervisor_node)
        workflow.add_node(NodeStates.ASSIGN_URLS, self._assign_urls_node)
        workflow.add_node(NodeStates.COLLECT_RESULTS, self._collect_results_node)
        workflow.add_node(NodeStates.RETRY_FAILED, self._retry_failed_node)
        
        # Define flow
        workflow.set_entry_point(NodeStates.SUPERVISOR)
        workflow.add_edge(NodeStates.SUPERVISOR, NodeStates.ASSIGN_URLS)
        workflow.add_edge(NodeStates.ASSIGN_URLS, NodeStates.COLLECT_RESULTS)
        workflow.add_conditional_edges(
            NodeStates.COLLECT_RESULTS,
            self._should_retry,
            {
                "retry": NodeStates.RETRY_FAILED,
                "done": END
            }
        )
        workflow.add_edge(NodeStates.RETRY_FAILED, NodeStates.ASSIGN_URLS)
        
        return workflow.compile()
    
    async def _supervisor_node(self, state: GraphState) -> dict:
        """
        YOUR RESPONSIBILITY #1: Track list of URLs to scrape
        - Extract URLs from user prompt or provided URLs
        - Initialize URL queue
        - Validate URLs
        """
        user_message = state["messages"][-1].content if state["messages"] else ""
        
        # Extract URLs from prompt
        urls = self._extract_urls(user_message)
        
        # If no URLs found in prompt, check if provided in state
        if not urls and state.get("urls_to_scrape"):
            urls = state["urls_to_scrape"]
        
        # Validate and deduplicate URLs
        valid_urls = self._validate_urls(urls)
        
        if not valid_urls:
            return {
                "messages": [AIMessage(content="⚠️ FALLBACK: No valid URLs found. Please provide URLs to scrape.")],
                "next_node": END
            }

        logger.info(f"Supervisor initialized with {len(valid_urls)} URLs to scrape")

        # Initialize tracking
        return {
            "urls_to_scrape": valid_urls,
            "urls_in_progress": {},
            "completed_urls": {},
            "failed_urls": {},
            "all_results": [],
            "next_node": NodeStates.ASSIGN_URLS
        }
    
    async def _assign_urls_node(self, state: GraphState) -> dict:
        """
        YOUR RESPONSIBILITY #2: Assign pages to worker agents
        - Get available URLs from queue
        - Send URLs to workers (with rate limiting)
        - Track which URLs are in progress
        """
        # Safely get urls_to_scrape, defaulting to empty list
        urls_to_scrape = state.get("urls_to_scrape", [])
        completed_urls = state.get("completed_urls", {})
        urls_in_progress = state.get("urls_in_progress", {})
        failed_urls = state.get("failed_urls", {})
        
        urls_to_process = [
            url for url in urls_to_scrape
            if url not in completed_urls
            and url not in urls_in_progress
            and failed_urls.get(url, 0) < self.max_retries
        ]
        
        if not urls_to_process:
            logger.info("No URLs to process")
            return {
                "urls_in_progress": urls_in_progress,
                "completed_urls": completed_urls
            }
        
        in_progress = urls_in_progress.copy()
        completed = completed_urls.copy()
        failed = failed_urls.copy()
        
        # Assign URLs to workers with rate limiting
        for idx, url in enumerate(urls_to_process):
            # Rate limiting: wait between requests
            if idx > 0:
                await asyncio.sleep(self.rate_limit_delay)
            
            # Mark as in progress
            worker_id = f"worker_{len(in_progress)}"
            in_progress[url] = worker_id
            
            logger.info(f"Assigning URL {url} to {worker_id}")
            
            # Send to worker
            try:
                result = await assign_url_to_worker(url, worker_id)
                # If successful, mark as completed
                completed[url] = result
                del in_progress[url]
                logger.info(f"Successfully processed {url}")
            except Exception as e:
                logger.error(f"Failed to assign {url}: {e}")
                # Mark for retry
                failed[url] = failed.get(url, 0) + 1
                del in_progress[url]
        
        return {
            "urls_in_progress": in_progress,
            "completed_urls": completed,
            "failed_urls": failed
        }
    
    async def _collect_results_node(self, state: GraphState) -> dict:
        """
        Collect all completed results and prepare aggregated report.
        
        The worker returns markdown-formatted summaries with JSON analysis.
        This node aggregates multiple community summaries into a final report.
        """
        results = []
        completed_urls = state.get("completed_urls", {})
        failed_urls = state.get("failed_urls", {})
        
        for url, result in completed_urls.items():
            results.append({
                "url": url,
                "content": result,
                "status": "success"
            })
        
        # Format results for response
        if results:
            # Build aggregated report header
            report_parts = [
                "# Moltbook News Service - Aggregated Report",
                "",
                f"**Communities Analyzed:** {len(results)}",
                f"**Time Period:** Past 24 hours",
                "",
                "---",
                ""
            ]
            
            # Add each community summary
            for idx, r in enumerate(results, 1):
                report_parts.append(f"## Community {idx}: {r['url']}")
                report_parts.append("")
                report_parts.append(r['content'])
                report_parts.append("")
                report_parts.append("---")
                report_parts.append("")
            
            # Add footer
            report_parts.append("*Aggregated report generated by Moltbook AI Agent News Service*")
            
            response_message = "\n".join(report_parts)
            
            # Add failed URLs info if any
            if failed_urls:
                failed_info = "\n\n⚠️ **Failed to process:**\n" + "\n".join([
                    f"- {url} (attempts: {count})" 
                    for url, count in failed_urls.items()
                ])
                response_message += failed_info
        else:
            response_message = "⚠️ No URLs were successfully processed. Please check if the Moltbook URLs are valid and the scraper service is running."
        
        return {
            "all_results": results,
            "messages": [AIMessage(content=response_message)]
        }
    
    async def _retry_failed_node(self, state: GraphState) -> dict:
        """
        YOUR RESPONSIBILITY #3: Handle retries
        - Identify failed URLs
        - Increment retry count
        - Re-add to queue if under max retries
        """
        failed = state.get("failed_urls", {}).copy()
        urls_to_scrape = state.get("urls_to_scrape", [])
        
        # Find URLs that failed but can be retried
        urls_to_retry = [
            url for url, count in failed.items()
            if count < self.max_retries
        ]
        
        if not urls_to_retry:
            logger.info("No URLs to retry")
            return {"failed_urls": failed}
        
        logger.info(f"Retrying {len(urls_to_retry)} failed URLs")
        
        # Re-add to queue (they'll be picked up in next assign_urls cycle)
        urls_to_scrape = urls_to_scrape + urls_to_retry
        
        return {
            "failed_urls": failed,
            "urls_to_scrape": urls_to_scrape
        }
    
    def _should_retry(self, state: GraphState) -> str:
        """Determine if we should retry failed URLs"""
        has_failures = any(
            count < self.max_retries
            for count in state["failed_urls"].values()
        )
        return "retry" if has_failures else "done"
    
    def _extract_urls(self, text: str) -> List[str]:
        """Extract URLs from text using regex"""
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        return re.findall(url_pattern, text)
    
    def _validate_urls(self, urls: List[str]) -> List[str]:
        """Validate and deduplicate URLs"""
        valid = []
        seen = set()
        for url in urls:
            if url.startswith(('http://', 'https://')) and url not in seen:
                valid.append(url)
                seen.add(url)
        return valid
    
    async def serve(self, prompt: str, urls: Optional[List[str]] = None) -> str:
        """
        Processes the input prompt and returns a complete response from the graph execution.

        Args:
            prompt (str): The input prompt to be processed by the graph.
            urls (Optional[List[str]]): Optional list of URLs to scrape.

        Returns:
            str: The final response content from the last AIMessage in the graph execution.
        """
        try:
            logger.debug(f"Received prompt: {prompt}, URLs: {urls}")
            
            # Validate input prompt
            if not isinstance(prompt, str) or not prompt.strip():
                raise ValueError("Prompt must be a non-empty string.")
            
            # Prepare initial state with all required keys
            initial_state = {
                "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
                ],
                "urls_to_scrape": self._validate_urls(urls) if urls else [],
                "urls_in_progress": {},
                "completed_urls": {},
                "failed_urls": {},
                "all_results": [],
            }
            
            # Execute the graph
            result = await self.graph.ainvoke(
                initial_state,
                {"configurable": {"thread_id": uuid.uuid4()}}
            )

            # Extract messages from the final state
            messages = result.get("messages", [])
            if not messages:
                raise RuntimeError("No messages found in the graph response.")

            # Find the last AIMessage with non-empty content
            for message in reversed(messages):
                if isinstance(message, AIMessage) and message.content.strip():
                    logger.debug(f"Valid AIMessage found: {message.content.strip()}")
                    return message.content.strip()

            raise RuntimeError("No valid AIMessage found in the graph response.")
        except ValueError as ve:
            logger.error(f"ValueError in serve method: {ve}")
            raise ValueError(str(ve))
        except Exception as e:
            logger.error(f"Error in serve method: {e}")
            raise Exception(str(e))

    async def streaming_serve(self, prompt: str, urls: Optional[List[str]] = None):
        """
        Streams the graph execution using LangGraph's astream_events API.

        Args:
            prompt (str): The input prompt to be processed by the graph.
            urls (Optional[List[str]]): Optional list of URLs to scrape.

        Yields:
            str: Message content chunks as they arrive from nodes during graph execution.
        """
        try:
            logger.debug(f"Received streaming prompt: {prompt}, URLs: {urls}")
            
            # Validate input prompt
            if not isinstance(prompt, str) or not prompt.strip():
                raise ValueError("Prompt must be a non-empty string.")

            # Prepare initial state with all required keys
            state = {
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "urls_to_scrape": self._validate_urls(urls) if urls else [],
                "urls_in_progress": {},
                "completed_urls": {},
                "failed_urls": {},
                "all_results": [],
            }

            # Track seen content to prevent duplicate yields
            seen_contents = set()
            
            # Stream events from the graph
            async for event in self.graph.astream_events(
                state, 
                {"configurable": {"thread_id": uuid.uuid4()}}, 
                version="v2"
            ):
                logger.debug(f"Event: {event}")
                
                # Filter for "on_chain_stream" events
                if event["event"] == "on_chain_stream":
                    node_name = event.get("name", "")
                    data = event.get("data", {})
                    
                    if "chunk" in data:
                        chunk = data["chunk"]
                        
                        if "messages" in chunk and chunk["messages"]:
                            logger.info(f"Streaming chunk from node '{node_name}': {chunk}")
                            
                            # Process and yield all messages from this chunk
                            for message in chunk["messages"]:
                                if isinstance(message, AIMessage) and message.content:
                                    content = message.content.strip()
                                    
                                    # Deduplicate
                                    if content in seen_contents:
                                        logger.info(f"Skipping duplicate content from '{node_name}'")
                                        continue
                                    
                                    seen_contents.add(content)
                                    logger.info(f"Yielding message from '{node_name}': {content}")
                                    yield message.content

        except ValueError as ve:
            logger.error(f"ValueError in streaming_serve method: {ve}")
            raise ValueError(str(ve))
        except Exception as e:
            logger.error(f"Error in streaming_serve method: {e}")
            raise Exception(str(e))
