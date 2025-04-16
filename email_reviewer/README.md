# Email Reviewer

The Email Reviewer Agent is a demonstration AI agent developed with Llama-index, designed to review email to address a specific target audience.

The main workflow is defined in [email_reviewer.py](email_reviewer/email_reviewer.py).

The [generate_manifest.py](email_reviewer/generate_manifest.py) file is used to generate the manifest for the agent workflow server from ACP.

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

* Copy and adapt `.env` into `deploy/email_reviewer_example.yaml` and set the environment variables
* Make sure that the workflow server manager cli (`wfsm`) is added to your path
* Start the workflow server
    ```
    cd deploy;
    wfsm deploy -m ./email_reviewer.json -e ../.env
    ```
* Once you start the server, note down the port number, agent ID, and API key, and store them as environment variables
    ```
    export AGENT_ID=<agent_id>
    export API_KEY=<api_key>
    export WORKFLOW_SERVER_PORT=<port_number>
    ```
* Then, make a request in another terminal and wait for the response
    ```
    curl -s -H 'content-type: application/json' -H "x-api-key: ${API_KEY}" -d "{\"agent_id\": \"${AGENT_ID}\", \"input\": { \"email\": \"Dear Team,\n\nI am writng to inform you that the server will be down for maintenance on Saturday, 25th December 2022 from 8:00 AM to 12:00 PM. During this time, the server won't not be accessible.\n\nWe apologize for any inconvenience this may cause and appreciate your understandings.\n\nBest regards,\nJohn Doe\", \"target_audience\": \"technical\" }, \"config\": {} }" http://127.0.0.1:${WORKFLOW_SERVER_PORT}/runs/wait
    ```
