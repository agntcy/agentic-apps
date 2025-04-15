# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from pydantic import AnyUrl
from state import EmailReviewerInput, EmailReview,ConfigSchema
from agntcy_acp.manifest import (
    AgentManifest,
    AgentDeployment,
    DeploymentOptions,
    LlamaIndexConfig,
    EnvVar,
    AgentMetadata,
    AgentACPSpec,
    AgentRef,
    Capabilities,
    SourceCodeDeployment
)


manifest = AgentManifest(
    metadata=AgentMetadata(
        ref=AgentRef(name="org.agntcy.mail_reviewer", version="0.0.1", url=None),
        description="Review emails"),
    specs=AgentACPSpec(
        input=EmailReviewerInput.model_json_schema(),
        output=EmailReview.model_json_schema(),
        config=ConfigSchema.model_json_schema(),
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
                    framework_config=LlamaIndexConfig(
                        framework_type="llamaindex",
                        path="email_reviewer:email_reviewer_workflow"
                    )
                )
            )
        ],
        env_vars=[EnvVar(name="AZURE_OPENAI_API_KEY", desc="Azure key for the OpenAI service")],
        dependencies=[]
    )
)

with open(f"{Path(__file__).parent}/../deploy/email_reviewer.json", "w") as f:
    f.write(manifest.model_dump_json(
        exclude_unset=True,
        exclude_none=True,
        indent=2
    ))