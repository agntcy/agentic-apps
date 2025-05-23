# Email Reviewer

The Email Reviewer Agent is a demonstration AI agent developed with Llama-index, designed to review email to address a specific target audience.

The main workflow is defined in [email_reviewer.py](email_reviewer/email_reviewer.py).

## Requirements

- [Agent Workflow Server](https://docs.agntcy.org/pages/agws/workflow_server_manager.html#installation)
- **Azure OpenAI API Key or OpenAI API Key**
- **Python 3.9 or higher**
- **Poetry**

## Testing the Email Reviewer Locally

Install dependencies:

```
poetry env activate
poetry install
```

Copy the `.env.example` file to `.env` and set the environment variables.

Fill in the `AZURE*` variables if you want to use Azure OpenAI, otherwise fill in the `OPENAI*` variables. Comment out the variables you don't want to use.

```
cp .env.example .env
```

Test the agent (This will generate a review for the email defined in the `main()` function):

```
python email_reviewer/email_reviewer.py
```

## Running the Email Agent using Agent Workflow Server

* Download the Agent Workflow Server Manager by following these [instructions](https://docs.agntcy.org/pages/agws/workflow_server_manager.html#installation).
* Edit the file `deploy/email_reviewer_example.yaml`:
    ```yaml
        config:
            org.agntcy.mail_reviewer:
                port: 52393
                apiKey: 799cccc7-49e4-420a-b0a8-e4de949ae673
                id: 45fb3f84-c0d7-41fb-bae3-363ca8f8092a
                envVars:
                    AZURE_OPENAI_API_KEY: [YOUR AZURE OPEN API KEY]
                    AZURE_OPENAI_ENDPOINT: https://[YOUR ENDPOINT].openai.azure.com
    ```
* Start the workflow server through the worflow server manager.
    ```
    wfsm deploy -m ./deploy/email_reviewer.json -c ./deploy/email_reviewer_example.yaml --dryRun=false
    ```
    
* Export the following environment variables
    ```
    export AGENT_ID=45fb3f84-c0d7-41fb-bae3-363ca8f8092a
    export API_KEY=799cccc7-49e4-420a-b0a8-e4de949ae673
    export WORKFLOW_SERVER_PORT=52393
    ```

* Then, make a request in another terminal and wait for the response
    ```
    curl -s -H 'content-type: application/json' -H "x-api-key: ${API_KEY}" -d "{\"agent_id\": \"${AGENT_ID}\", \"input\": { \"email\": \"Dear Team,\n\nI am writng to inform you that the server will be down for maintenance on Saturday, 25th December 2022 from 8:00 AM to 12:00 PM. During this time, the server won't not be accessible.\n\nWe apologize for any inconvenience this may cause and appreciate your understandings.\n\nBest regards,\nJohn Doe\", \"target_audience\": \"technical\" }, \"config\": {} }" http://127.0.0.1:${WORKFLOW_SERVER_PORT}/runs/wait
    ```
