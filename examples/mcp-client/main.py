"""Canonical Agent → MCP: list_tools + call_tool."""

from __future__ import annotations

import asyncio
import os

from lime_agents import CallToolResult, LimeAgent, Tool


async def main() -> None:
    url = os.environ.get("MCP_SERVER_URL", "https://mcp.example.com/mcp")
    async with LimeAgent(agent_token=os.environ["LIME_AGENT_TOKEN"]) as agent:
        tools: list[Tool] = await agent.list_tools(url)
        print([t.name for t in tools])
        if not tools:
            return

        result: CallToolResult = await agent.call_tool(
            url,
            tools[0].name,
            {"text": "hello from LIME agent"},
        )
        if result.isError:
            print("tool error:", result.content)
        else:
            print(result.content)


if __name__ == "__main__":
    asyncio.run(main())
