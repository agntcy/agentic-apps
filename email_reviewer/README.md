# Email Reviewer

The Email Reviewer Agent is a demonstration AI agent developed with Llama-index, designed to review email to address a specific target audience.

## Requirements

- LlamaIndex: https://docs.llamaindex.ai/en/stable/getting_started/installation/
- **Azure OpenAI API Key**
- **Python 3.9 or higher**
- **Poetry**

## Running the Email Reviewer agent using LlamaDeploy


* Copy and adapt `.env`: 
    ```
    cp .env.example .env
    ```
*  Install LlamaDeploy: 
    ```
    pip install llama_deploy
    ```
*  Run LlamaDeploy:
    ```
    python -m llama_deploy.apiserver`
    ```
    or
    ```
    docker run -p 4501:4501 -v .:/opt/quickstart -w /opt/quickstart llamaindex/llama-deploy:main
    ```
* Create deployment config from template: 
    ```
    sed "s|\${PWD}|$(pwd)|g" "email_reviewer.tmpl.yaml" > "email_reviewer.yaml"
    ```

*  Deploy the workflow: 
    ```
    llamactl deploy email_reviewer.yaml
    ```

## Running the Email Agent using Agent Workflow Server

* Copy and adapt `.env`: `cp .env.example .env`
* Make sure that the workflow server manager cli (`wfsm`) is added to your path
* Start the workflow server
    ```
    cd deploy;
    wfsm deploy -m ./email_reviewer.json -e .mailcomposer.env
    ```

## Test agent

You can use `usage_example.py` to use the Llama Client SDK to call the agent with given inputs (see source code):
`python usage_example.py `


