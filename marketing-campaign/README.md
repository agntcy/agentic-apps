# Marketing Campaign Manager

The **Marketing Campaign Manager** is a demonstration AI application developed with LangGraph. It assists in composing and sending emails for marketing campaigns by interacting with multiple AI agents. This guide will walk you through the steps to set up and run the example application locally.

## Features

* It gathers necessary campaign details from the user through a chat.
* Compose an email leveraging the [Email Composer Agent](../mailcomposer/) as a remote ACP agent.
* It leverages the [IO Mapper Agent](https://github.com/agntcy/iomapper-agnt) to adapt Email Composer Agent output to Email Reviewer Agent.
* Reviews the email leveraging the [Email Reviewer Agent](../email_reviewer/) as a remote ACP agent.
* Send the email to the configured recipient through Twilio sendgrid leveraging the [API Bridge Agent](https://github.com/agntcy/api-bridge-agnt)

---

## Prerequisites

Before running the application, ensure you have the following:

### Tools and Dependencies
- [Python 3.9 or higher](https://www.python.org/downloads/)
- [Poetry](https://python-poetry.org/docs/#installation)
- [Golang](https://go.dev/doc/install)
- [Make](https://cmake.org/)
- [Git](https://git-scm.com/)
- [Git LFS](https://git-lfs.com/)
- [Docker with Buildx](https://docs.docker.com/get-started/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/)
- [Azure OpenAI API Key](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/quickstart)

---

## Setup Instructions

### 1. Run the API Bridge Agent and Connect it to SendGrid

Clone the [API Bridge Agent repo](https://github.com/agntcy/api-bridge-agnt) and follow these [instructions](https://docs.agntcy.org/pages/syntactic_sdk/api_bridge_agent.html#an-example-with-sendgrid-api) to connect it to Twilio SendGrid.

In a nutshell, navigate to the repo and run the following commands:

```sh
export OPENAI_API_KEY=***YOUR_OPENAI_API_KEY***

# Optionally, if you want to use Azure OpenAI, you also need to specify the endpoint with the OPENAI_ENDPOINT environment variable:
export OPENAI_ENDPOINT="https://YOUR-PROJECT.openai.azure.com"

make start_redis
make start_tyk
```

Configure the API Bridge Agent:

```sh
curl http://localhost:8080/tyk/apis/oas \
  --header "x-tyk-authorization: foo" \
  --header 'Content-Type: text/plain' \
  -d@configs/api.sendgrid.com.oas.json

curl http://localhost:8080/tyk/reload/group \
  --header "x-tyk-authorization: foo"
```

### 2. Download the Agent Workflow Server Manager

Follow these [instructions](https://docs.agntcy.org/pages/agws/workflow_server_manager.html#installation) to install the Agent Workflow Server Manager.

At the end of the installation you should be able to run the `wsfm` command.

### 3. Install Python dependencies
   From the `marketing-campaign` folder:

   ```sh
   poetry install
   ```

## Running the Marketing Campaign Manager

The Marketing Campaign Manager application can be run in two ways:
1. Using the **ACP client**.
2. Using **LangGraph** directly.

Both methods allow users to interactively create a marketing campaign by providing input through a chat interface. The **MailComposer agent** generates email drafts, while the **EmailReviewer agent** reviews and refines the drafts.

An [IO Mapper Agent](https://github.com/agntcy/iomapper-agnt) is used in the application to automatically transform the output of the MailComposer to match the input of the EmailReviewer.

The **ACP client** or **LangGraph** applications handle communication with the Marketing Campaign application, which orchestrates interactions with the dependent agents.

All commands and scripts should be executed from the `examples/marketing-campaign` directory, where this guide is located.


### Method 1: Using the ACP Client

This method demonstrates how to communicate with the Marketing Campaign application using the **ACP (Agent Connect Protocol) client**. The workflow server for the Marketing Campaign application must be started manually. Once running, it will automatically launch the workflow servers for its dependencies, **MailComposer** and **EmailReviewer**, as defined in the deployment configuration of the [marketing-campaign manifest](./deploy/marketing-campaign.json).

#### Steps:

1. ##### Configure the Agents

Before starting the workflow server, provide the necessary configurations for the agents. Open the `./deploy/marketing_campaign_example_env` file located in the `deploy` folder and update the following values with your configuration:

   ```dotenv
# Environment variables for the Marketing Campaign application
AZURE_OPENAI_API_KEY: your_secret
AZURE_OPENAI_ENDPOINT: "the_url.com"
API_HOST: 0.0.0.0
SENDGRID_HOST: http://host.docker.internal:8080
SENDGRID_API_KEY: SG.your-api-key

MAILCOMPOSER_AZURE_OPENAI_API_KEY: your_secret
MAILCOMPOSER_AZURE_OPENAI_ENDPOINT: "the_url.com"

EMAIL_REVIEWER_AZURE_OPENAI_API_KEY: your_secret
EMAIL_REVIEWER_AZURE_OPENAI_ENDPOINT: "the_url.com"
```

2. ##### Start the Workflow Server:

Run the following command to deploy the Marketing Campaign workflow server:
```sh
wfsm deploy -m ./deploy/marketing-campaign.json -e ./deploy/marketing_campaign_example.yaml
```

   If everything is set up correctly, the application will start, and the logs will display:
- **Agent ID**
- **API Key**
- **Host**

Example log output:
  ```plaintext
  2025-03-28T12:31:04+01:00 INF ---------------------------------------------------------------------
  2025-03-28T12:31:04+01:00 INF ACP agent deployment name: org.agntcy.marketing-campaign
  2025-03-28T12:31:04+01:00 INF ACP agent running in container: org.agntcy.marketing-campaign, listening for ACP request on: http://127.0.0.1:62609
  2025-03-28T12:31:04+01:00 INF Agent ID: eae32ada-aaf8-408c-bf0c-7654455ce6e3
  2025-03-28T12:31:04+01:00 INF API Key: 08817517-7000-48e9-94d8-01d22cf7d20a
  2025-03-28T12:31:04+01:00 INF ---------------------------------------------------------------------
  ```

3. ##### Export Environment Variables:

Use the information from the logs to set the following environment variables:

```sh
export MARKETING_CAMPAIGN_HOST="http://localhost:62609"
export MARKETING_CAMPAIGN_ID="eae32ada-aaf8-408c-bf0c-7654455ce6e3"
export MARKETING_CAMPAIGN_API_KEY='{"x-api-key": "08817517-7000-48e9-94d8-01d22cf7d20a"}'

# Configuration of the application
export RECIPIENT_EMAIL_ADDRESS="recipient@example.com"
export SENDER_EMAIL_ADDRESS="sender@example.com" # Sender email address as configured in Sendgrid
```

4. ##### Run the Application:

Start the Marketing Campaign Manager application using the ACP client:
```sh
poetry run python src/marketing_campaign/main_acp_client.py
```

Interact with the application via ACP Client to compose and review emails. Once approved, the email will be sent to the recipient via SendGrid.

---

### Method 2: Using LangGraph

This method provides an alternative way to interact with the Marketing Campaign application by directly invoking the **LangGraph graph** of the Marketing Campaign. Unlike the ACP client-based approach, this method bypasses the multi-agent software orchestration and requires manual handling of the agent dependencies.

This script is primarily intended for development and debugging purposes, allowing developers to test and refine the LangGraph logic.

#### Steps:

1. ##### Start Workflow Servers for Dependencies

Manually start the workflow servers for the **MailComposer** and **EmailReviewer** agents in separate terminals:
```sh
# Start the MailComposer agent
wfsm deploy -m ../mailcomposer/deploy/mailcomposer.json -e ../mailcomposer/deploy/mailcomposer_example_env -b workflowserver:latest
```
```sh
# Start the EmailReviewer agent
wfsm deploy -m ../email_reviewer/deploy/email_reviewer.json -e ../email_reviewer/deploy/email_reviewer_example.yaml -b workflowserver:latest
```

The logs will display the **Agent ID**, **API Key**, and **Host** for each agent. Use this information to set the following environment variables:

```sh
export MAILCOMPOSER_HOST="http://localhost:<port>"
export MAILCOMPOSER_ID="<mailcomposer-agent-id>"
export MAILCOMPOSER_API_KEY='{"x-api-key": "<mailcomposer-api-key>"}'

export EMAIL_REVIEWER_HOST="http://localhost:<port>"
export EMAIL_REVIEWER_ID="<email-reviewer-agent-id>"
export EMAIL_REVIEWER_API_KEY='{"x-api-key": "<email-reviewer-api-key>"}'
```

2. ##### Export Additional Environment Variables**:
Set the following environment variables:

```sh
export API_HOST=0.0.0.0
export SENDGRID_API_KEY=SG.your_secret
export AZURE_OPENAI_API_KEY=your_secret
export AZURE_OPENAI_ENDPOINT="the_url.com"

# Configuration of the application
export RECIPIENT_EMAIL_ADDRESS="recipient@example.com"
export SENDER_EMAIL_ADDRESS="sender@example.com" # Sender email address as configured in Sendgrid
```

3. ##### Run the Application:
Start the Marketing Campaign Manager application using LangGraph:
```sh
poetry run python src/marketing_campaign/main_langgraph.py
```

Interact by invoking the langgraph application to compose and review emails. Once approved, the email will be sent to the recipient via SendGrid.

----

### Additional Configuration

In both scripts [main_acp_client.py](./src/marketing_campaign/main_acp_client.py) and [main_langgraph.py](./src/marketing_campaign/main_langgraph.py), you can customize the target audience for the campaign by modifying the `target_audience` parameter `target_audience=TargetAudience.academic`. Available options are:
- `general`
- `technical`
- `business`
- `academic`

Example:
```python
target_audience = TargetAudience.business
```


---

### Method 3: Using UI

This method provides an alternative way to interact with the Marketing Campaign application by using a ui build with [Gradio](https://www.gradio.app/).

#### Steps:

1. ##### Adapt the `src/marketing_campaign/gradio_ui.py` file.

Set the email details

```python
os.environ["RECIPIENT_EMAIL_ADDRESS"] = ""
os.environ["SENDER_EMAIL_ADDRESS"] = ""
```

2. ##### Configure the Agents:
Before starting the workflow server, provide the necessary configurations for the agents. Open the `./deploy/marketing_campaign_example_env` file located in the `deploy` folder and update the following values with your configuration:

```dotenv
AZURE_OPENAI_API_KEY: your-api-key
AZURE_OPENAI_ENDPOINT: 'https://your-project-agents.openai.azure.com'
API_HOST: 0.0.0.0

ORG_AGNTCY_MARKETING_CAMPAIGN_SENDGRID_HOST=http://host.docker.internal:8080
ORG_AGNTCY_MARKETING_CAMPAIGN_SENDGRID_API_KEY=SG.your-api-key

MAILCOMPOSER_OPENAI_API_KEY=your-api-key
MAILCOMPOSER_AZURE_OPENAI_ENDPOINT='https://your-project-agents.openai.azure.com'

EMAIL_REVIEWER_AZURE_OPENAI_API_KEY=your-api-key
EMAIL_REVIEWER_AZURE_OPENAI_ENDPOINT='https://your-project-agents.openai.azure.com'

```

3. ##### Run the API Bridge Agent

Navigate to the `api-bridge-agnt` directory and run the following commands:

```sh
export OPENAI_API_KEY=***YOUR_OPENAI_API_KEY***

# Optionally, if you want to use Azure OpenAI, you also need to specify the endpoint with the OPENAI_ENDPOINT environment variable:
export OPENAI_ENDPOINT="https://YOUR-PROJECT.openai.azure.com"

make start_redis
make start_tyk
```

Configure the API Bridge Agent:

```sh
curl http://localhost:8080/tyk/apis/oas \
  --header "x-tyk-authorization: foo" \
  --header 'Content-Type: text/plain' \
  -d@configs/api.sendgrid.com.oas.json

curl http://localhost:8080/tyk/reload/group \
  --header "x-tyk-authorization: foo"
```

4.  ##### Run Application:
    From within examples/marketing-campaign folder run:

```sh
poetry run ui
```
---

By following these steps, you can successfully run the Marketing Campaign Manager application using either the ACP client or LangGraph. Both methods allow you to compose, review, and send marketing emails interactively.
