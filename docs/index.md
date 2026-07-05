# lime-agents-sdk

Official Python SDK for **LIME AI agent workers**. One-call site login (PoW + approve),
Core profile access, and typed MCP client for external resource servers with automatic
MCP OAuth JWT issuance.

[![PyPI](https://img.shields.io/pypi/v/lime-agents-sdk)](https://pypi.org/project/lime-agents-sdk/)
[![Documentation](https://readthedocs.org/projects/lime-agents-sdk/badge/?version=latest)](https://lime-agents-sdk.readthedocs.io/)
[![GitHub](https://img.shields.io/github/stars/Mawyxx/lime-agents-sdk?style=social)](https://github.com/Mawyxx/lime-agents-sdk)

## Key features

- `await agent.login(request_id)` — PoW fetch, solve, and approve with retries
- MCP OAuth client — JWT auto-issued on `list_tools` / `call_tool` (cached ~5 min)
- Dual credential lanes — `X-Agent-Token` for LIME APIs; Bearer MCP JWT for external RS only
- Typed MCP facade — re-exports `mcp.types` models
- Strict typing with `py.typed` and 100% test coverage

## Credential boundary

| Role | Credential | SDK |
|------|------------|-----|
| **Agent worker** | **`X-Agent-Token` + auto MCP JWT** | **This package** |
| Site backend | `X-Site-Token` + passport JWT via SSE | [lime-sites-sdk](https://lime-sites-sdk.readthedocs.io/) |
| MCP resource server | Verify Bearer MCP JWT | [lime-mcp-server-sdk](https://lime-mcp-server-sdk.readthedocs.io/) |

## Platform documentation

- [LIME platform docs — Agent SDK](https://lime.pics/docs#guide-agentSdk)
- [LIME platform docs — OAuth for MCP](https://lime.pics/docs#guide-oauthMcp)

## Minimal example

```python
# pip install lime-agents-sdk
import asyncio
from lime_agents import LimeAgent

async def main() -> None:
    async with LimeAgent() as agent:  # LIME_AGENT_TOKEN
        result = await agent.login("lr_from_your_site_queue")
        print(result.status)

asyncio.run(main())
```

## Next steps

- [Installation](installation.md)
- [Quick Start](quickstart.md)
- [API Reference](api.md)
- [Examples](examples.md)
