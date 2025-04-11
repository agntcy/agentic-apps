import click
import json
import os
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core import SimpleKeywordTableIndex
from llama_index.llms.ollama import Ollama
from llama_index.llms.azure_openai import AzureOpenAI
from llama_index.core.agent.workflow import ReActAgent
from llama_index.core.tools import QueryEngineTool
from llama_index.core import SimpleDirectoryReader
from llama_index.core.llms import ChatMessage
from llama_index.core.memory import ChatMemoryBuffer
from agp import AGP


async def amain(doc_dir, llm_type, llm_endpoint, llm_key, assistant_id):
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

    agp = AGP(
        agp_endpoint=os.getenv("AGP_ENDPOINT", "http://localhost:12345"),
        local_id=assistant_id,
        shared_space="chat",
    )

    await agp.init()

    memory = ChatMemoryBuffer.from_defaults(token_limit=40000)

    async def on_message_received(message: bytes):
        decoded_message = message.decode("utf-8")
        data = json.loads(decoded_message)

        if data["type"] == "ChatMessage":
            print(f"{data['author']}: {data['message']}")
            memory.put(
                ChatMessage(role="user", content=f"{data['author']}: {data['message']}")
            )

        elif data["type"] == "RequestToSpeak" and data["target"] == assistant_id:
            print("Moderator requested me to speak")
            handler = agent.run(user_msg=decoded_message, memory=memory)
            response = await handler
            # Publish a message to the AGP server
            message = {
                "type": "ChatMessage",
                "author": assistant_id,
                "message": str(response),
            }
            message_json = json.dumps(message)
            print(f"Responding with: {str(response)}")
            await agp.publish(msg=message_json.encode("utf-8"))

    # Connect to the AGP server and start receiving messages
    await agp.receive(callback=on_message_received)
    await agp.receive_task


@click.command(context_settings={"auto_envvar_prefix": "ASSISTANT"})
@click.option("--doc-dir", prompt="directory of documentation to load", required=True)
@click.option("--llm-type", default="azure")
@click.option("--llm-endpoint", default=None)
@click.option("--llm-key", default=None)
@click.option("--assistant-id", required=True)
def main(doc_dir, llm_type, llm_endpoint, llm_key, assistant_id):
    import asyncio

    asyncio.run(amain(doc_dir, llm_type, llm_endpoint, llm_key, assistant_id))


def run():
    main()

if __name__ == "__main__":
    run()
