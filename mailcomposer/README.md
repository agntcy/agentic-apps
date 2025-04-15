# Email Composer Agent

The Email Composer Agent is a demonstration AI agent developed with LangGraph, designed to assist in the composition of emails. 
It gathers necessary email details through ongoing user engagement in a chat format until the user affirms that the email is complete. Subsequently, it delivers the finalized email text.

## Prerequisites

Before running the application, ensure you have the following:

- **Azure OpenAI API Key**
- **Python 3.9 or higher**
- **Poetry**

## Running the Email Agent directly
* Install dependencies
    ```
    poetry install
    ```

* Run the agent
    ```
    export AZURE_OPENAI_MODEL=gpt-4o-mini
    export AZURE_OPENAI_API_KEY=***YOUR_OPENAI_API_KEY***
    export AZURE_OPENAI_ENDPOINT=***YOUR_OPENAI_ENDPOINT***
    export OPENAI_API_VERSION=2024-07-01-preview 
    poetry run python main.py 
    ```

## Running the Email Agent using Agent Workflow Server

* Create an environment variable file with the following data:
    ```commandline
    echo "
    AZURE_OPENAI_MODEL=gpt-4o-mini
    AZURE_OPENAI_API_KEY=***YOUR_OPENAI_API_KEY***
    AZURE_OPENAI_ENDPOINT=***YOUR_OPENAI_ENDPOINT***
    OPENAI_API_VERSION=2024-07-01-preview 
    API_HOST=0.0.0.0
    " > deploy/.mailcomposer.env
    ```
* Make sure that the workflow server manager cli (`wfsm`) is added to your path
* Start the workflow server
    ```
    cd deploy;
    wfsm deploy -m ./mailcomposer.json -e .mailcomposer.env
    ```


