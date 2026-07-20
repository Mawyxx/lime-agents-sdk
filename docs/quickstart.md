# Quick Start

Two independent scenarios. **Most integrators need only one.**

## Scenario 1 — Site login {: #scenario-1 }

### What happens

1. A **site backend** starts login and gets a `request_id`.
2. The site sends `request_id` to **your agent worker** (you implement this handoff).
3. **You** call `login(request_id)` — SDK solves the challenge and approves.
4. The **site** receives a passport JWT over SSE. You do not handle that JWT.

### Code

```python
import asyncio
import os

from lime_agents import LimeAgent

async def main() -> None:
    request_id = "paste_id_from_your_site_queue"

    async with LimeAgent(agent_token=os.environ["LIME_AGENT_TOKEN"]) as agent:
        result = await agent.login(request_id)
        print(result.status)              # APPROVED
        print(result.approved_agent_id)   # your agent UUID

asyncio.run(main())
```

### Methods in this scenario

| Order | Method | Input | Output |
|-------|--------|-------|--------|
| 1 | `LimeAgent()` | `LIME_AGENT_TOKEN` | client ready |
| 2 | `login(request_id)` | id from site | `ApprovalResult` |

### Inside `login()` (automatic)

| Step | Action |
|------|--------|
| 1 | Fetch PoW challenge from LIME |
| 2 | Solve challenge locally |
| 3 | POST approve with your agent token |

→ [`login()` in API Reference](api.md#lime_agents.LimeAgent.login)

## Scenario 2 — MCP tools {: #scenario-2 }

### What happens

1. Your agent knows the URL of an **external MCP server**.
2. You call `list_tools(target)` then `call_tool(target, name, args)`.
3. SDK gets a temporary token from LIME automatically (**lazy refresh** on each MCP
   call when the cache is within `mcp_token_refresh_skew` seconds of expiry).

This flow is **unrelated** to site login. Details: [MCP OAuth & pool](mcp-oauth.md).

### Code

```python
import asyncio
import os

from lime_agents import LimeAgent

TARGET = "https://your-mcp-server.example/mcp"  # or bare host: your-mcp-server.example

async def main() -> None:
    async with LimeAgent(agent_token=os.environ["LIME_AGENT_TOKEN"]) as agent:
        tools = await agent.list_tools(TARGET)
        print(f"Found {len(tools)} tools")

        if tools:
            result = await agent.call_tool(TARGET, tools[0].name, {"key": "value"})
            print(result.content)

asyncio.run(main())
```

### Methods in this scenario

| Order | Method | Input | Output |
|-------|--------|-------|--------|
| 1 | `LimeAgent()` | `LIME_AGENT_TOKEN` | client ready |
| 2 | `list_tools(target)` | MCP URL or hostname | `list[Tool]` |
| 3 | `call_tool(target, name, args)` | tool name + JSON | `CallToolResult` |

!!! warning "Common mistake"
    Do **not** call `get_mcp_access_token(target)` before every MCP call — tokens are handled
    inside `list_tools` / `call_tool`.

→ [`list_tools`](api.md#lime_agents.LimeAgent.list_tools),
[`call_tool`](api.md#lime_agents.LimeAgent.call_tool)

## Environment variables

| Variable | Required | Default | Used in |
|----------|----------|---------|---------|
| `LIME_AGENT_TOKEN` | Yes* | — | Both scenarios |
| `LIME_API_BASE` | No | `https://lime.pics/api/v1` | Both scenarios |

\*Or pass `agent_token=` to `LimeAgent()`.

## Both scenarios in one process

```python
async with LimeAgent() as agent:
    await agent.login(site_request_id)       # scenario 1
    tools = await agent.list_tools(mcp_url)  # scenario 2
```

HTTP reference: [lime.pics/docs](https://lime.pics/docs)
