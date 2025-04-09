import click
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core import SimpleKeywordTableIndex
from llama_index.llms.ollama import Ollama
from llama_index.llms.azure_openai import AzureOpenAI
from llama_index.core.agent.workflow import ReActAgent
from llama_index.core.tools import QueryEngineTool
from llama_index.core.agent.workflow import AgentStream, ToolCallResult
from llama_index.core import SimpleDirectoryReader


async def amain(doc_dir, llm_type, llm_endpoint, llm_key):
    if llm_type == "azure":
        kwargs = {
            "engine": "gpt-4o-mini",
            "model": "gpt-4o-mini",
            "is_chat_model": True,
            "azure_endpoint": llm_endpoint,
            "api_key": llm_key,
            "api_version": "2024-08-01-preview",
        }
        llm = AzureOpenAI(**kwargs)
    elif llm_type == "ollama":
        kwargs = {
            "model": "llama3.2",
        }
        llm = Ollama(**kwargs)
    else:
        raise Exception("LLM type must be azure or ollama")

    reader = SimpleDirectoryReader(input_dir=doc_dir)
    docs = reader.load_data()

    splitter = SentenceSplitter(chunk_size=1024, chunk_overlap=20)
    index = SimpleKeywordTableIndex.from_documents(
        docs, transformations=[splitter], llm=llm, show_progress=True
    )

    qet = QueryEngineTool.from_defaults(
        index.as_query_engine(llm=llm),
        name="documentation_search",
        description="Searches the available documentation",
    )
    agent = ReActAgent(llm=llm, tools=[qet])

    # TODO(sambetts) Replace this with AGP chat room logic
    while True:
        i = input("Question: ")
        handler = agent.run(user_msg=i)
        async for ev in handler.stream_events():
            if isinstance(ev, ToolCallResult):
                print(f"{ev}")
            if isinstance(ev, AgentStream):
                print(f"{ev.delta}", end="", flush=True)
        response = await handler
        print(str(response))


@click.command(context_settings={"auto_envvar_prefix": "ASSISTANT"})
@click.option("--doc-dir", prompt="directory of documentation to load")
@click.option("--llm-type", default="azure")
@click.option("--llm-endpoint", default=None)
@click.option("--llm-key", default=None)
def main(doc_dir, llm_type, llm_endpoint, llm_key):
    import asyncio

    asyncio.run(amain(doc_dir, llm_type, llm_endpoint, llm_key))


if __name__ == "__main__":
    main()
