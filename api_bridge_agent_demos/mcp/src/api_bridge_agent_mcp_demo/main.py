# Copyright AGNTCY Contributors (https://github.com/agntcy)
# SPDX-License-Identifier: Apache-2.0

import click
import httpx

from llama_index.core.workflow import Context, Event, StartEvent, StopEvent, Workflow, step
from pydantic import BaseModel, Field


class ACPOutput(BaseModel):
    demo_result: str = Field(..., description="The email content to be reviewed and corrected")


class APIBridge:
    def __init__(self, base_url: str):
        self.base_url: str = base_url

    async def nlq(self, service: str, query: str) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            headers = {"content-type": "application/nlq"}
            response = await client.post(f"{self.base_url}/{service}/", headers=headers, content=query)
            if response.status_code == 200:
                return response.text
            else:
                raise Exception(f"API Bridge call failed with status code {response.status_code}")

    async def api(self, query: str) -> str:
        return await self.nlq("aba", query)

    async def mcp(self, query: str) -> str:
        return await self.nlq("mcp", query)


class InputEvent(StartEvent):
    repository: str
    api_bridge_url: str


class GetRepoInfoEvent(Event):
    repository: str


class RepoInfoEvent(Event):
    description: str


class PreparedDescriptionEvent(Event):
    description: str


class ExampleWorkflow(Workflow):
    @step
    async def setup(self, ctx: Context, ev: InputEvent) -> GetRepoInfoEvent:
        self.api_bridge = APIBridge(base_url=ev.api_bridge_url)

        await ctx.set("repository", ev.repository)

        return GetRepoInfoEvent(repository=ev.repository)

    @step
    async def get_repo_info(self, ev: GetRepoInfoEvent) -> RepoInfoEvent:
        description = await self.api_bridge.nlq(
            "github",
            f"show me the README.md file of the github repository named '{ev.repository}'",
        )
        return RepoInfoEvent(description=description)

    @step
    async def prepare_description(self, ev: RepoInfoEvent) -> PreparedDescriptionEvent:
        # FIXME Add an LLM call to do a nice presentation
        description = ev.description.upper()
        return PreparedDescriptionEvent(description=description)

    @step
    async def send_description(self, ev: PreparedDescriptionEvent) -> StopEvent:
        result = await self.api_bridge.mcp(f"Search for subjets related to this description:\n===\n{ev.description}\n---\n")
        acp_output = ACPOutput(demo_result=result)
        return StopEvent(result=acp_output)


mcp_example_workflow = ExampleWorkflow(timeout=60.0)


async def amain(repository, api_bridge_url):
    result = await mcp_example_workflow.run(repository=repository, api_bridge_url=api_bridge_url)
    print(result)


@click.command()
@click.option("--repository", prompt="Github repository to analyze", required=True)
@click.option("--api-bridge-url", prompt="API Bridge Agent base URL", required=False, default="http://localhost:8080")
def main(repository, api_bridge_url):
    import asyncio

    asyncio.run(amain(repository, api_bridge_url))


if __name__ == "__main__":
    main()
