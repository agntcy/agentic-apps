# Email Composer Agent

The Email Composer Agent is a demonstration AI agent developed with LangGraph, designed to assist in the composition of emails. 
It gathers necessary email details through ongoing user engagement in a chat format until the user affirms that the email is complete. Subsequently, it delivers the finalized email text.

## Prerequisites

Before running the application, ensure you have the following:

- **Azure OpenAI API Key**
- **Python 3.9 or higher**
- **Poetry**

## Running the Mail Composer Agent directly
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

## Running the Mail Composer using Agent Workflow Server

* Download the Agent Workflow Server Manager by following these [instructions](https://docs.agntcy.org/pages/agws/workflow_server_manager.html#installation).
* Edit the file `deploy/mailcomposer_example.yaml`:
    ```yaml
        config:
            org.agntcy.mailcomposer:
                port: 52384
                apiKey: a9ee3d6a-6950-4252-b2f0-ad70ce57d603
                id: 76363e34-d684-4cab-b2b7-2721c772e42f
                envVars:
                    AZURE_OPENAI_API_KEY: [YOUR AZURE OPEN API KEY]
                    AZURE_OPENAI_ENDPOINT: https://[YOUR ENDPOINT].openai.azure.com
    ```
* Start the workflow server through the worflow server manager.
    ```
    wfsm deploy -m ./deploy/mailcomposer.json -c ./deploy/mailcomposer_example.yaml --dryRun=false
    ```


