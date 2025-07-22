# 🌐 Network of Assistants (NoA)

[![Release](https://img.shields.io/github/v/release/agntcy/network-of-assistants?display_name=tag)](CHANGELOG.md)
[![Lint](https://github.com/agntcy/network-of-assistants/actions/workflows/lint.yml/badge.svg?branch=main)](https://github.com/marketplace/actions/super-linter)
[![Contributor-Covenant](https://img.shields.io/badge/Contributor%20Covenant-2.1-fbab2c.svg)](CODE_OF_CONDUCT.md)

Welcome to Network of Assistants (NoA), a sample multi-agent multi-framework application designed to orchestrate specialized AI assistants to answer general queries. Think of it as an intelligent network of AI minds working collaboratively to get the job done! 🤖✨

At the heart of NoA is a moderator agent that orchestrates conversations between specialized assistants in a chat-like environment. Here's how it works:

1. 🗨️ User Interaction: Users interact with the moderator agent which starts a discussion with specialized assistants.
2. 📡 Agentic Communication: The chat environment is powered by the [Secure Low-Latency Interactive Messaging (SLIM)](https://github.com/agntcy/slim) protocol for broadcasting.
3. 📖 Agent Discovery: The moderator leverages the [Agent Directory Service](https://github.com/agntcy/dir) to discover and invite specialized agents to the conversation.
4. 🛠️ Capabilities Framework: Agent capabilities are described using the [Open Agentic Schema Framework (OASF)](https://github.com/agntcy/oasf).
5. 🔄 Framework & LLM Support: NoA supports multiple frameworks and works with various LLM APIs.
    - Agentic frameworks: LangChain, LangGraph, Llama-Index, Autogen
    - LLMs: OpenAI, Azure, Mistral, Ollama


## 🚀 Getting Started

Follow these steps to deploy and run your own Network of Assistants! 🌟

1. Build the Docker Images

    From the project's root directory, start by building the required Docker images:

    ```bash
    docker compose build
    ```

2. Configure Your Environment

    Create a .env file based on the provided .env-example. Add your credentials for accessing the supported LLMs.

3. Start the NoA App

    Run the following command to launch the application:

    ```bash
    docker compose up
    ```

4. Verify Your Deployment

    Check if your NoA app is up and running by using the health check endpoint:

    ```bash 
    curl 0.0.0.0:8000/health
    ```

    You should see a response indicating the app is healthy! ✅

5. Ask NoA a Question

    Engage with NoA by sending a query:

    ```bash
    curl -X POST 0.0.0.0:8000/ask -H "Content-Type: application/json" -d '{"message": "Hello, what can you do?"}'
    ```

    And that's all! 🪄 Watch as NoA responds with its capabilities.

## Roadmap

See the [open issues](https://github.com/agntcy/network-of-assistants/issues) for a list
of proposed features (and known issues).

## Contributing

Contributions are what make the open source community such an amazing place to
learn, inspire, and create. Any contributions you make are **greatly
appreciated**. For detailed contributing guidelines, please see
[CONTRIBUTING.md](CONTRIBUTING.md)

## License

Distributed under the Apache 2.0 License. See [LICENSE](LICENSE) for more
information.

## Contact

Thomas Feltin - [@tfeltin](https://github.com/tfeltin) - tfeltin@cisco.com

