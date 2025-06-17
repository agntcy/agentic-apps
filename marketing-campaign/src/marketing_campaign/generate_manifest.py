# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0
from datetime import datetime, timezone
from pathlib import Path

from agntcy_acp.manifest import (
    AgentACPSpec,
    AgentDependency,
    AgentDeployment,
    AgentManifest,
    AgentRef,
    Capabilities,
    DeploymentManifest,
    DeploymentOptions,
    EnvVar,
    LangGraphConfig,
    Locator,
    Manifest,
    Skill,
    SourceCodeDeployment,
    OASF_EXTENSION_NAME_MANIFEST,
)
from pydantic import AnyUrl

from marketing_campaign.state import ConfigModel, OverallState

# Deps are relative to the main manifest file.
mailcomposer_dependency_manifest = "mailcomposer.json"
email_reviewer_dependency_manifest = "email_reviewer.json"

manifest = AgentManifest(
    name="org.agntcy.marketing-campaign",
    authors=["AGNTCY Internet of Agents Collective"],
    annotations={"type": "langgraph"},
    version="0.3.1",
    locators=[
        Locator(
            url="https://github.com/agntcy/agentic-apps/tree/main/marketing-campaign",
            type="source-code",
        ),
    ],
    description="Offer a chat interface to compose an email for a marketing campaign. Final output is the email that could be used for the campaign",
    created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    schema_version="0.1.3",
    skills=[
        Skill(
            category_name="Natural Language Processing",
            category_uid=1,
            class_name="Dialogue Generation",
            class_uid=10204,
        ),
        Skill(
            category_name="Natural Language Processing",
            category_uid=1,
            class_name="Text Completion",
            class_uid=10201,
        ),
        Skill(
            category_name="Natural Language Processing",
            category_uid=1,
            class_name="Text Paraphrasing",
            class_uid=10203,
        ),
        Skill(
            category_name="Natural Language Processing",
            category_uid=1,
            class_name="Knowledge Synthesis",
            class_uid=10303,
        ),
        Skill(
            category_name="Natural Language Processing",
            category_uid=1,
            class_name="Text Style Transfer",
            class_uid=10206,
        ),
        Skill(
            category_name="Natural Language Processing",
            category_uid=1,
            class_name="Tone and Style Adjustment",
            class_uid=10602,
        ),
    ],
    extensions=[
        Manifest(
            name=OASF_EXTENSION_NAME_MANIFEST,
            version="v0.2.2",
            data=DeploymentManifest(
                acp=AgentACPSpec(
                    input=OverallState.model_json_schema(),
                    output=OverallState.model_json_schema(),
                    config=ConfigModel.model_json_schema(),
                    capabilities=Capabilities(
                        threads=False, callbacks=False, interrupts=False, streaming=None
                    ),
                    custom_streaming_update=None,
                    thread_state=None,
                    interrupts=None,
                ),
                deployment=AgentDeployment(
                    deployment_options=[
                        DeploymentOptions(
                            root=SourceCodeDeployment(
                                type="source_code",
                                name="source_code_local",
                                url=AnyUrl("file://../"),
                                framework_config=LangGraphConfig(
                                    framework_type="langgraph",
                                    graph="marketing_campaign.app:graph",
                                ),
                            )
                        )
                    ],
                    env_vars=[
                        EnvVar(
                            name="AZURE_OPENAI_API_KEY",
                            desc="Azure key for the OpenAI service",
                        ),
                        EnvVar(
                            name="AZURE_OPENAI_ENDPOINT",
                            desc="Azure endpoint for the OpenAI service",
                        ),
                        EnvVar(name="SENDGRID_API_KEY", desc="Sendgrid API key"),
                    ],
                    agent_deps=[
                        AgentDependency(
                            name="mailcomposer",
                            ref=AgentRef(
                                name="org.agntcy.mailcomposer",
                                version="0.0.1",
                                url=AnyUrl(f"file://{mailcomposer_dependency_manifest}"),
                            ),
                            deployment_option=None,
                            env_var_values=None,
                        ),
                        AgentDependency(
                            name="email_reviewer",
                            ref=AgentRef(
                                name="org.agntcy.email_reviewer",
                                version="0.0.1",
                                url=AnyUrl(f"file://{email_reviewer_dependency_manifest}"),
                            ),
                            deployment_option=None,
                            env_var_values=None,
                        ),
                    ],
                ),
            ),
        ),
    ],
)

with open(
    f"{Path(__file__).parent.parent.parent}/manifests/marketing-campaign.json", "w"
) as f:
    json_content = manifest.model_dump_json(
        exclude_unset=True, exclude_none=True, indent=2
    )
    f.write(json_content)
    f.write("\n")
