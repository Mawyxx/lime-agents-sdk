# Examples

## Scenario 1 — Site login worker

```python
import asyncio
import os

from lime_agents import ApiError, LimeAgent, PowTimeoutError

async def approve_login(request_id: str) -> None:
    async with LimeAgent(agent_token=os.environ["LIME_AGENT_TOKEN"]) as agent:
        try:
            result = await agent.login(request_id)
            print(result.status, result.approved_agent_id)
        except PowTimeoutError:
            print("PoW timeout — retry or increase pow_timeout")
        except ApiError as exc:
            print(exc.code, exc.message)

asyncio.run(approve_login("lr_abc123"))
```

Pair with [lime-sites-sdk](https://lime-sites-sdk.readthedocs.io/) on the site side.

## Scenario 2 — Multiple MCP servers {: #scenario-2-multiple-mcp-servers }

One `LimeAgent` pools sessions per server URL. Calls to **different** URLs can run in
parallel; the same OAuth JWT is shared (lazy refresh on the next MCP call).

```python
import asyncio
from lime_agents import LimeAgent

async def main() -> None:
    async with LimeAgent() as agent:
        tools_a, tools_b = await asyncio.gather(
            agent.list_tools("https://mcp-a.example/mcp"),
            agent.list_tools("https://mcp-b.example/mcp"),
        )
        print(len(tools_a), len(tools_b))

asyncio.run(main())
```

See [MCP OAuth & pool](mcp-oauth.md) for token lifecycle and retry behavior.

## Error handling

```python
from lime_agents import (
    ApiError,
    LimeAgent,
    McpAuthenticationError,
    PowTimeoutError,
)

async with LimeAgent() as agent:
    try:
        await agent.login(request_id)
    except PowTimeoutError:
        ...
    except ApiError as exc:
        if exc.code == "REQUEST_EXPIRED":
            ...

    try:
        await agent.call_tool(mcp_url, "echo", {"text": "hi"})
    except McpAuthenticationError:
        ...
```

## Anti-patterns

| Mistake | Correct approach |
|---------|------------------|
| `get_mcp_access_token(target)` before every MCP call | JWT auto-issued and lazy-refreshed on `list_tools` / `call_tool` |
| `len(tools.tools)` | `list_tools()` returns `list[Tool]` — use `len(tools)` |
| Bearer MCP JWT on LIME APIs | Use `X-Agent-Token` for LIME; Bearer only on external MCP RS |
| Expect `owner_id` in raw API JSON | Wire field is `user_id`; SDK maps to `AgentProfile.owner_id` |
