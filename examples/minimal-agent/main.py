"""Minimal Agent → MCP: list tools on an external resource server."""

from __future__ import annotations

import asyncio
import os

from lime_agents import LimeAgent


async def main() -> None:
    url = os.environ.get("MCP_SERVER_URL", "https://mcp.example.com/mcp")
    async with LimeAgent() as agent:  # LIME_AGENT_TOKEN from env
        tools = await agent.list_tools(url)
        print([t.name for t in tools])


if __name__ == "__main__":
    asyncio.run(main())
