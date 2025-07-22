# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import os
import re
import json
import logging
import argparse
import requests

from llama_index.core import SimpleDirectoryReader, VectorStoreIndex
from llama_index.core.agent.workflow import ReActAgent
from llama_index.core.llms import ChatMessage
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.tools import QueryEngineTool
from llama_index.llms.ollama import Ollama
from llama_index.llms.azure_openai import AzureOpenAI
from llama_index.llms.openai_like import OpenAILike

from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core import Settings

from slim import SLIM
from util import take_step

from ioa_observe.sdk import Observe
from ioa_observe.sdk.instrumentations.slim import SLIMInstrumentor
from ioa_observe.sdk.connectors.slim import SLIMConnector, process_slim_msg


ReActAgent.take_step = take_step


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s",  # Log message format
)
log = logging.getLogger(__name__)


def ensure_directory_exists(save_dir):
    if not os.path.exists(save_dir):
        try:
            os.makedirs(save_dir, exist_ok=True)
            log.info(f"Directory created: {save_dir}")
        except PermissionError as e:
            log.error(f"Permission denied while creating directory {save_dir}: {e}")
            raise
        except Exception as e:
            log.error(f"An error occurred while creating directory {save_dir}: {e}")
            raise
    else:
        log.info(f"Directory already exists: {save_dir}")


def download_pdf(url, save_dir):
    ensure_directory_exists(save_dir)

    filename = re.sub(r'[<>:"/\\|?*]', "_", os.path.basename(url))
    save_path = os.path.join(save_dir, f"{filename}.pdf")

    if os.path.exists(save_path):
        log.info(f"The file '{save_path}' already exists. Skipping download.")
        return

    try:
        # Send a GET request to the URL
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Raise an error for HTTP errors (e.g., 404, 403)

        # Write the content to a file
        with open(save_path, "wb") as pdf_file:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:  # Write only non-empty chunks
                    pdf_file.write(chunk)
        log.info(f"PDF successfully downloaded and saved to: {save_path}")
    except requests.exceptions.RequestException as e:
        log.info(f"An error occurred while downloading the PDF: {e}")


async def amain(args):
    with_obs = os.getenv("WITH_OBS", "False").lower() == "true"
    if with_obs:
        Observe.init(args.assistant_id, api_endpoint=os.getenv("OTLP_HTTP_ENDPOINT"))
        SLIMInstrumentor().instrument()

    if args.llm_type == "azure":
        kwargs = {
            "engine": args.llm_model,
            "model": args.llm_model,
            "is_chat_model": True,
            "azure_endpoint": args.llm_base_url,
            "api_key": args.llm_api_key,
            "api_version": "2024-08-01-preview",
        }
        llm = AzureOpenAI(**kwargs)
    elif args.llm_type == "openai":
        kwargs = {
            "model": args.llm_model,
            "is_chat_model": True,
            "api_key": args.llm_api_key,
            "api_base": args.llm_base_url,
            "streaming": False,
        }
        llm = OpenAILike(**kwargs)
    elif args.llm_type == "ollama":
        kwargs = {
            "model": args.llm_model,
        }
        llm = Ollama(**kwargs)
    else:
        raise Exception(f"LLM type {args.llm_type} is not supported. Must be azure, openai, or ollama.")

    if args.rag_type == "openai":
        embed_model = OpenAIEmbedding(
            model=args.rag_model,
            api_key=args.rag_api_key,
            api_base=args.rag_base_url,
        )
    else:
        raise Exception(f"RAG type {args.rag_type} is not supported. Only supported type is openai.")

    Settings.embed_model = embed_model

    download_pdf(args.file_url, args.doc_dir)

    docs = SimpleDirectoryReader(input_dir=args.doc_dir).load_data()
    index = VectorStoreIndex.from_documents(docs, show_progress=True, streaming=False)

    qet = QueryEngineTool.from_defaults(
        index.as_query_engine(llm=llm, streaming=False),
        name="documentation_search",
        description="Searches the available documentation",
    )
    agent = ReActAgent(llm=llm, tools=[qet])

    slim = SLIM(
        slim_endpoint=args.slim_endpoint,
        local_id=args.assistant_id,
        shared_space="chat",
        opentelemetry_endpoint=os.getenv("OTLP_GRPC_ENDPOINT"),
    )

    await slim.init()

    with_obs = os.getenv("WITH_OBS", "False").lower() == "true"
    if with_obs:
        # initialize the SLIM connector
        slim_connector = SLIMConnector(
            remote_org="organization",
            remote_namespace="namespace",
            shared_space="chat",
        )
        # register the agent with the SLIM connector
        slim_connector.register("file_assistant")

    memory = ChatMemoryBuffer.from_defaults(token_limit=40000)

    log.info("File reader assistant is ready.")

    @process_slim_msg("noa-file-assistant")
    async def on_message_received(message: bytes):
        decoded_message = message.decode("utf-8")
        data = json.loads(decoded_message)

        if data["type"] == "ChatMessage":
            memory.put(ChatMessage(role="user", content=f"{data['author']}: {data['message']}"))

        elif data["type"] == "RequestToSpeak" and data["target"] == args.assistant_id:
            log.info("Moderator requested me to speak")
            handler = agent.run(user_msg=decoded_message, memory=memory)
            response = await handler
            # Publish a message to the SLIM server
            message = {
                "type": "ChatMessage",
                "author": args.assistant_id,
                "message": str(response),
            }
            message_json = json.dumps(message)
            log.info(f"Responding with: {str(response)}")
            await slim.publish(msg=message_json.encode("utf-8"))

        elif data["type"] == "RequestToSpeak" and data["target"] == "noa-user-proxy":
            memory.reset()

    # Connect to the SLIM server and start receiving messages
    await slim.receive(callback=on_message_received)
    await slim.receive_task


def run():
    parser = argparse.ArgumentParser(description="File reader assistant.")
    parser.add_argument(
        "--slim-endpoint", type=str, default=os.getenv("SLIM_ENDPOINT", "http://localhost:12345"), help="SLIM endpoint"
    )
    parser.add_argument(
        "--assistant-id", type=str, default=os.getenv("ASSISTANT_ID", "noa-file-assistant"), help="Assistant ID"
    )
    parser.add_argument("--llm-api-key", type=str, default=os.getenv("ASSISTANT_LLM_API_KEY"), help="Assistant LLM key")
    parser.add_argument("--llm-model", type=str, default=os.getenv("ASSISTANT_LLM_MODEL"), help="Assistant LLM model")
    parser.add_argument(
        "--doc-dir", type=str, default=os.getenv("ASSISTANT_DOC_DIR"), help="Assistant documentation directory"
    )
    parser.add_argument(
        "--llm-type", type=str, default=os.getenv("ASSISTANT_LLM_TYPE", "openai"), help="Assistant LLM type"
    )
    parser.add_argument(
        "--llm-base-url", type=str, default=os.getenv("ASSISTANT_LLM_BASE_URL"), help="Assistant LLM base URL"
    )
    parser.add_argument("--rag-type", type=str, default=os.getenv("ASSISTANT_RAG_TYPE", "openai"), help="RAG type")
    parser.add_argument(
        "--rag-model", type=str, default=os.getenv("ASSISTANT_RAG_MODEL", "text-embedding-3-large"), help="RAG model"
    )
    parser.add_argument("--rag-api-key", type=str, default=os.getenv("ASSISTANT_RAG_API_KEY"), help="RAG API key")
    parser.add_argument("--rag-base-url", type=str, default=os.getenv("ASSISTANT_RAG_BASE_URL"), help="RAG base URL")

    parser.add_argument("--file-url", type=str, default=os.getenv("FILE_URL"), help="File URL to download and analyze")

    args = parser.parse_args()

    import asyncio

    asyncio.run(amain(args))


if __name__ == "__main__":
    run()
