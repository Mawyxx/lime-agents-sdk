# Quick Start

## Call order (site login)

```
LimeAgent()  →  login(request_id)  →  ApprovalResult
     │                │
     │                └── PoW + approve (automatic)
     └── needs LIME_AGENT_TOKEN
```

The **site** receives the passport JWT over SSE separately
([`lime-sites-sdk`](https://lime-sites-sdk.readthedocs.io/)).

```python
import asyncio
import os

from lime_agents import LimeAgent

async def main() -> None:
    async with LimeAgent(agent_token=os.environ["LIME_AGENT_TOKEN"]) as agent:
        result = await agent.login("lr_from_your_site_queue")
        print(result.status)  # APPROVED

asyncio.run(main())
```

| Step | What `login()` does internally |
|------|--------------------------------|
| 1 | `GET /auth/requests/{id}` — fetch PoW challenge (no auth) |
| 2 | Solve SHA-256 PoW in a thread pool |
| 3 | `POST .../approve` with `X-Agent-Token` and `pow_nonce` |

Returns [`ApprovalResult`](api.md#approvalresult) — see [API Reference](api.md#login).

---

## Call order (MCP tools)

```
LimeAgent()  →  list_tools(url)  →  call_tool(url, name, args)
                     │
                     └── OAuth JWT fetched automatically (no get_mcp_access_token)
```

```python
import asyncio
import os

from lime_agents import LimeAgent

MCP_URL = "https://your-mcp-server.example/mcp"

async def main() -> None:
    async with LimeAgent(agent_token=os.environ["LIME_AGENT_TOKEN"]) as agent:
        tools = await agent.list_tools(MCP_URL)
        print(len(tools))  # list[Tool], not tools.tools
        if tools:
            result = await agent.call_tool(MCP_URL, tools[0].name, {})
            print(result.content)

asyncio.run(main())
```

Method details: [`list_tools`](api.md#list_tools), [`call_tool`](api.md#call_tool).

---

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LIME_AGENT_TOKEN` | Yes* | Agent secret from LIME portal |
| `LIME_API_BASE` | No | Default `https://lime.pics/api/v1` |

\*Unless passed as `agent_token=` to `LimeAgent()`.

## Optional: raw MCP JWT

Use [`get_mcp_access_token()`](api.md#get_mcp_access_token) only when you need the JWT string
(custom HTTP client, debugging):

```python
token = await agent.get_mcp_access_token()
print(token.expires_in)
```

See [LIME platform docs](https://lime.pics/docs) for HTTP reference.
