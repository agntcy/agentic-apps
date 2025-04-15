# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from pydantic import AnyUrl
from marketing_campaign.state import OverallState, ConfigModel
from agntcy_acp.manifest import (
    AgentManifest,
    AgentDeployment,
    DeploymentOptions,
    LangGraphConfig,
    EnvVar,
    AgentMetadata,
    AgentACPSpec,
    AgentRef,
    Capabilities,
    SourceCodeDeployment,
    AgentDependency
)


manifest = AgentManifest(
    metadata=AgentMetadata(
        ref=AgentRef(name="org.agntcy.marketing-campaign", version="0.0.1", url=None),
        description="Offer a chat interface to compose an email for a marketing campaign. Final output is the email that could be used for the campaign"),
    specs=AgentACPSpec(
        input=OverallState.model_json_schema(),
        output=OverallState.model_json_schema(),
        config=ConfigModel.model_json_schema(),
        capabilities=Capabilities(
            threads=False,
            callbacks=False,
            interrupts=False,
            streaming=None
        ),
        custom_streaming_update=None,
        thread_state=None,
        interrupts=None
    ),
    deployment=AgentDeployment(
        deployment_options=[
            DeploymentOptions(
                root = SourceCodeDeployment(
                    type="source_code",
                    name="source_code_local",
                    url=AnyUrl("file://../"),
                    framework_config=LangGraphConfig(
                        framework_type="langgraph",
                        graph="marketing_campaign.app:graph"
                    )
                )
            )
        ],
        env_vars=[EnvVar(name="AZURE_OPENAI_API_KEY", desc="Azure key for the OpenAI service"),
                  EnvVar(name="AZURE_OPENAI_ENDPOINT", desc="Azure endpoint for the OpenAI service"),
                  EnvVar(name="SENDGRID_API_KEY", desc="Sendgrid API key")],
        dependencies=[
            AgentDependency(
                name="mailcomposer",
                ref=AgentRef(name="org.agntcy.mailcomposer", version="0.0.1", url=AnyUrl("file://mailcomposer.json")),
                deployment_option = None,
                env_var_values = None
            ),
           AgentDependency(
                name="email_reviewer",
                ref=AgentRef(name="org.agntcy.email_reviewer", version="0.0.1", url=AnyUrl("file://email_reviewer.json")),
                deployment_option = None,
                env_var_values = None
            )
        ]
    )
)

with open(f"{Path(__file__).parent}/../../deploy/marketing-campaign.json", "w") as f:
    f.write(manifest.model_dump_json(
        exclude_unset=True,
        exclude_none=True,
        indent=2
    ))
