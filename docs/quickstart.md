# Quick Start

Two independent scenarios. **Most integrators need only one.**

---

## Scenario 1 — Site login

### What happens (plain language)

1. A **site backend** starts login and gets a `request_id`.
2. The site sends `request_id` to **your agent worker** (you implement this handoff).
3. **You** call `login(request_id)` — this SDK solves the crypto challenge and tells LIME
   "approve".
4. The **site** receives a passport JWT over a live connection (SSE). You do not receive
   or store that JWT in the agent worker.

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

### Methods used in this scenario

| Order | Method | Input | Output |
|-------|--------|-------|--------|
| 1 | `LimeAgent()` | `LIME_AGENT_TOKEN` | client ready |
| 2 | `login(request_id)` | id from site | `ApprovalResult` |

That's it for site login. No MCP methods required.

### What `login()` does inside (you don't code this)

| Step | Action |
|------|--------|
| 1 | Fetch PoW challenge from LIME |
| 2 | Solve challenge locally |
| 3 | POST approve with your agent token |

Details: [`login()` in API Reference](api.md#login)

---

## Scenario 2 — MCP tools

### What happens (plain language)

1. Your agent knows the URL of an **external MCP server** (not LIME itself).
2. You call `list_tools(url)` to see what the server offers.
3. You call `call_tool(url, name, arguments)` to run a tool.
4. The SDK asks LIME for a temporary access token and sends it to the MCP server — **you
   do not manage tokens** in normal usage.

This flow is **unrelated** to site login. No `request_id`, no `login()`.

### Code

```python
import asyncio
import os

from lime_agents import LimeAgent

MCP_URL = "https://your-mcp-server.example/mcp"

async def main() -> None:
    async with LimeAgent(agent_token=os.environ["LIME_AGENT_TOKEN"]) as agent:
        tools = await agent.list_tools(MCP_URL)
        print(f"Found {len(tools)} tools")          # list[Tool] — use len(tools)

        if tools:
            result = await agent.call_tool(MCP_URL, tools[0].name, {"key": "value"})
            print(result.content)

asyncio.run(main())
```

### Methods used in this scenario

| Order | Method | Input | Output |
|-------|--------|-------|--------|
| 1 | `LimeAgent()` | `LIME_AGENT_TOKEN` | client ready |
| 2 | `list_tools(server_url)` | MCP HTTP URL | `list[Tool]` |
| 3 | `call_tool(server_url, name, args)` | tool name + JSON args | `CallToolResult` |

### Common mistake

```python
# WRONG — do not fetch token before every call
token = await agent.get_mcp_access_token()
tools = await agent.list_tools(url)   # token is already handled inside
```

Use `get_mcp_access_token()` only if you write your own HTTP client to the MCP server.

Details: [`list_tools`](api.md#list_tools), [`call_tool`](api.md#call_tool)

---

## Environment variables

| Variable | Required | Default | Used in |
|----------|----------|---------|---------|
| `LIME_AGENT_TOKEN` | Yes* | — | Both scenarios |
| `LIME_API_BASE` | No | `https://lime.pics/api/v1` | Both scenarios |

\*Or pass `agent_token=` to `LimeAgent()`.

---

## Both scenarios in one process

Same `LimeAgent` instance can do both — they share the agent token only:

```python
async with LimeAgent() as agent:
    await agent.login(site_request_id)           # scenario 1
    tools = await agent.list_tools(mcp_url)      # scenario 2
```

HTTP reference: [lime.pics/docs](https://lime.pics/docs)
