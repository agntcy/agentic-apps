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

### 1. Clone the Required Repositories

Clone the following repositories:

- [ACP SDK](https://github.com/agntcy/acp-sdk/tree/main)
- [Workflow Server](https://github.com/agntcy/workflow-srv)
- [Workflow Server Manager](https://github.com/agntcy/workflow-srv-mgr)
- [API Bridge Agent](https://github.com/agntcy/api-bridge-agnt)

It is recommended to work within each of the cloned directories after cloning them.

```sh
# Clone the ACP SDK repository
git clone https://github.com/agntcy/acp-sdk.git
cd acp-sdk

# Clone the Workflow Server repository
git clone https://github.com/agntcy/workflow-srv.git
cd workflow-srv

# Clone the Workflow Server Manager repository
git clone https://github.com/agntcy/workflow-srv-mgr.git
cd workflow-srv-mgr

# Clone the API Bridge Agent repository
git clone https://github.com/agntcy/api-bridge-agnt.git
cd api-bridge-agnt
```

### 2. Build the Workflow Server Manager

Navigate to the `workflow-srv-mgr` directory and build the Workflow Server Manager:

```sh
cd wfsm
make build
```

Add the `wfsm` executable to your system's PATH:

#### For macOS:
```sh
cd build
chmod +x wfsm
echo 'export PATH=$PATH:/path/to/the/repo/workflow-srv-mgr/wfsm/build' >> ~/.zshrc
source ~/.zshrc
```

#### For Linux:
```sh
cd build
chmod +x wfsm
echo 'export PATH=$PATH:/path/to/the/repo/workflow-srv-mgr/wfsm/build' >> ~/.bashrc
source ~/.bashrc
```

### 3. Build the Workflow Server

Navigate to the `workflow-srv` directory and build the Docker image for the Workflow Server:

```sh
git submodule update --init --recursive
make docker-build-dev
```

### 4. Run the API Bridge Agent

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
  --header "x-tyk-authorization: foo"****
```

---

## Running the Marketing Campaign Manager

The Marketing Campaign Manager application can be run in two ways:
1. Using the **ACP client**.
2. Using **LangGraph** directly.

Both methods allow users to interactively create a marketing campaign by providing input through a chat interface. The **MailComposer agent** generates email drafts, while the **EmailReviewer agent** reviews and refines the drafts.

An [IO Mapper Agent](https://github.com/agntcy/iomapper-agnt) is used in the application to automatically transform the output of the MailComposer to match the input of the EmailReviewer.

The **ACP client** or **LangGraph** applications handle communication with the Marketing Campaign application, which orchestrates interactions with the dependent agents.

All commands and scripts should be executed from the `examples/marketing-campaign` directory, where this guide is located.

### Prerequisites for Both Methods

Before running the application, ensure the following prerequisites are met:

1. **Bridge Agent**: The API Bridge Agent must be running as explained in Step 4 of the setup instructions.
2. **`wfsm` CLI**: The Workflow Server Manager CLI (`wfsm`) must be added to your system's PATH.
3. **Dependencies**: Install Python dependencies in the `examples/marketing-campaign` directory:
   ```sh
   cd examples/marketing-campaign
   poetry install
   ```

---

### Method 1: Using the ACP Client

This method demonstrates how to communicate with the Marketing Campaign application using the **ACP (Agent Connect Protocol) client**. The workflow server for the Marketing Campaign application must be started manually. Once running, it will automatically launch the workflow servers for its dependencies, **MailComposer** and **EmailReviewer**, as defined in the deployment configuration of the [marketing-campaign manifest](./deploy/marketing-campaign.json).

#### Steps:

1. **Configure the Agents**:
   Before starting the workflow server, provide the necessary configurations for the agents. Open the `./deploy/marketing_campaign_example.yaml` file located in the `deploy` folder and update the following values with your configuration:

   ```yaml
   values:
     AZURE_OPENAI_API_KEY: your_secret
     AZURE_OPENAI_ENDPOINT: "the_url.com"
     API_HOST: 0.0.0.0
     SENDGRID_HOST: http://host.docker.internal:8080
     SENDGRID_API_KEY: SG.your-api-key
   dependencies:
     - name: mailcomposer
       values:
         AZURE_OPENAI_API_KEY: your_secret
         AZURE_OPENAI_ENDPOINT: "the_url.com"
     - name: email_reviewer
       values:
         AZURE_OPENAI_API_KEY: your_secret
         AZURE_OPENAI_ENDPOINT: "the_url.com"
   ```

2. **Start the Workflow Server**:
   Run the following command to deploy the Marketing Campaign workflow server:
   ```sh
   wfsm deploy -m ./deploy/marketing-campaign.json -e ./deploy/marketing_campaign_example.yaml -b workflowserver:latest
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

3. **Export Environment Variables**:
   Use the information from the logs to set the following environment variables:
   ```sh
   export MARKETING_CAMPAIGN_HOST="http://localhost:62609"
   export MARKETING_CAMPAIGN_ID="eae32ada-aaf8-408c-bf0c-7654455ce6e3"
   export MARKETING_CAMPAIGN_API_KEY='{"x-api-key": "08817517-7000-48e9-94d8-01d22cf7d20a"}'

   # Configuration of the application
   export RECIPIENT_EMAIL_ADDRESS="recipient@example.com"
   export SENDER_EMAIL_ADDRESS="sender@example.com" # Sender email address as configured in Sendgrid
   ```

4. **Run the Application**:
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

1. **Start Workflow Servers for Dependencies**:
   Manually start the workflow servers for the **MailComposer** and **EmailReviewer** agents in separate terminals:
   ```sh
   wfsm deploy -m ../mailcomposer/deploy/mailcomposer.json -e ../mailcomposer/deploy/mailcomposer_example.yaml -b workflowserver:latest
   ```
   ```sh
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

2. **Export Additional Environment Variables**:
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

3. **Run the Application**:
   Start the Marketing Campaign Manager application using LangGraph:
   ```sh
   poetry run python src/marketing_campaign/main_langgraph.py
   ```

   Interact by invoking the langgraph application to compose and review emails. Once approved, the email will be sent to the recipient via SendGrid.

---

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

By following these steps, you can successfully run the Marketing Campaign Manager application using either the ACP client or LangGraph. Both methods allow you to compose, review, and send marketing emails interactively.
