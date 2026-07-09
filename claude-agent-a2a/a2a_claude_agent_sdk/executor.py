"""AgentExecutor implementation bridging A2A requests to Claude Agent SDK sessions."""

from typing import Any

from a2a.server.agent_execution.agent_executor import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types import Part, Task, TaskState, TaskStatus

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    list_sessions,
)

from .tools import create_artifact_mcp_server


class ClaudeAgentExecutor(AgentExecutor):
    """Executes A2A tasks by running a Claude Agent SDK session.

    A2A context_id is used directly as the Claude session_id, enabling
    multi-turn conversations across tasks in the same A2A context.
    """

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task_id = context.task_id or ""
        context_id = context.context_id or ""
        user_input = context.get_user_input() or ""

        updater = TaskUpdater(
            event_queue=event_queue,
            task_id=task_id,
            context_id=context_id,
        )

        # Publish initial submitted task so the framework has something to track.
        await event_queue.enqueue_event(
            Task(
                id=task_id,
                context_id=context_id,
                status=TaskStatus(state=TaskState.TASK_STATE_SUBMITTED),
                history=[context.message] if context.message else [],
            )
        )
        await updater.start_work()

        artifact_collector: list[dict[str, Any]] = []
        artifact_server = create_artifact_mcp_server(artifact_collector)

        # Determine whether to resume an existing Claude session or start a new one
        # with the A2A context_id as the session UUID.
        existing_ids = {s.session_id for s in list_sessions()}
        if context_id in existing_ids:
            options = ClaudeAgentOptions(
                resume=context_id,
                mcp_servers={"a2a_artifacts": artifact_server},
                allowed_tools=["mcp__a2a_artifacts__add_artifact"],
            )
        else:
            options = ClaudeAgentOptions(
                session_id=context_id,
                mcp_servers={"a2a_artifacts": artifact_server},
                allowed_tools=["mcp__a2a_artifacts__add_artifact"],
            )

        try:
            async with ClaudeSDKClient(options=options) as client:
                await client.query(user_input)
                async for message in client.receive_response():
                    if isinstance(message, AssistantMessage):
                        # Stream partial text back as a working-state status message.
                        text_parts = [
                            b.text
                            for b in message.content
                            if isinstance(b, TextBlock)
                        ]
                        if text_parts:
                            status_msg = updater.new_agent_message(
                                parts=[Part(text="\n".join(text_parts))]
                            )
                            await updater.update_status(
                                TaskState.TASK_STATE_WORKING, message=status_msg
                            )
                    elif isinstance(message, ResultMessage):
                        break

        except Exception as exc:
            await updater.update_status(
                TaskState.TASK_STATE_FAILED,
                message=updater.new_agent_message(
                    parts=[Part(text=f"Error: {exc}")]
                ),
            )
            return

        # Publish any artifacts Claude attached via add_artifact.
        for artifact in artifact_collector:
            await updater.add_artifact(
                parts=[Part(text=artifact["content"])],
                name=artifact["name"],
                last_chunk=True,
            )

        await updater.complete()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(
            event_queue=event_queue,
            task_id=context.task_id or "",
            context_id=context.context_id or "",
        )
        await updater.cancel()
