# lime-agents-sdk

Give your AI agent a **verifiable LIME identity** and call **MCP tools** without managing OAuth tokens yourself.

```python
import asyncio

from lime_agents import LimeAgent

MCP_URL = "https://mcp.example.com/mcp"  # your MCP resource server


async def main() -> None:
    async with LimeAgent() as agent:  # reads LIME_AGENT_TOKEN
        tools = await agent.list_tools(MCP_URL)
        print([t.name for t in tools])

        if tools:
            result = await agent.call_tool(MCP_URL, tools[0].name, {"text": "hi"})
            print(result.content)


asyncio.run(main())
```

**What the SDK handles for you:** agent identity · MCP JWT issuance · cache · lazy refresh · session pooling · 401 recovery · site-login PoW/approve.

From OAuth plumbing to one function call — typical MCP list+call is **~15 lines → ~3 lines** vs hand-rolled official `mcp` client code (see [comparison](#comparison-with-official-mcp-sdk)).

[![PyPI version](https://img.shields.io/pypi/v/lime-agents-sdk)](https://pypi.org/project/lime-agents-sdk/)
[![Python versions](https://img.shields.io/pypi/pyversions/lime-agents-sdk)](https://pypi.org/project/lime-agents-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/Mawyxx/lime-agents-sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/Mawyxx/lime-agents-sdk/actions/workflows/ci.yml)
[![Documentation](https://readthedocs.org/projects/lime-agents-sdk/badge/?version=latest)](https://lime-agents-sdk.readthedocs.io/)
[![MCP compatible](https://img.shields.io/badge/MCP-compatible-00C853)](https://modelcontextprotocol.io/)

**Docs:** [Read the Docs](https://lime-agents-sdk.readthedocs.io/) · [lime.pics/docs](https://lime.pics/docs#guide-agentSdk) · [Platform](https://lime.pics)

---

## Installation

```bash
pip install lime-agents-sdk
export LIME_AGENT_TOKEN=at_...   # from https://lime.pics — agent portal
```

**Requirements:** Python 3.10+ · `httpx` · `mcp`  
**Config:** one secret — `LIME_AGENT_TOKEN` (or `agent_token=`). Zero **OAuth** boilerplate; not zero credentials.

---

## Quick start (canonical) — Agent → MCP

**This is the primary path.** Your worker already has a LIME agent token; an external MCP server trusts LIME-issued Bearer JWTs (`aud=mcp`).

```python
import asyncio
import os

from lime_agents import LimeAgent, CallToolResult, Tool

MCP_URL = os.environ.get("MCP_SERVER_URL", "https://mcp.example.com/mcp")


async def main() -> None:
    async with LimeAgent(agent_token=os.environ["LIME_AGENT_TOKEN"]) as agent:
        tools: list[Tool] = await agent.list_tools(MCP_URL)
        print([t.name for t in tools])

        if not tools:
            return

        result: CallToolResult = await agent.call_tool(
            MCP_URL,
            tools[0].name,
            {"text": "hello from LIME agent"},
        )
        if result.isError:
            print("tool error:", result.content)
        else:
            print(result.content)


asyncio.run(main())
```

Copy-paste examples: [`examples/mcp-client/`](examples/mcp-client/).

**On the MCP server:** verify Bearer with [`lime-mcp-server-sdk`](https://github.com/Mawyxx/lime-mcp-server-sdk) + Core JWKS — not with `lime-agents-sdk`.

> **Try it live:** point `MCP_SERVER_URL` at any MCP RS that accepts LIME passports. A hosted LIME playground MCP is on the roadmap — until then use your own RS or the platform guides at [lime.pics/docs](https://lime.pics/docs).

---

## Mental model — what do I need?

```text
LimeAgent
├── Core          LimeAgent() / aclose()
├── Profile       get_profile()
├── MCP (primary) list_tools · call_tool · resources · prompts
├── Advanced      get_mcp_access_token(target) · mcp_session()
└── Site login    login(request_id)   ← separate job, optional
```

| Credential | Header | Used for |
|------------|--------|----------|
| Opaque **Agent Token** | `X-Agent-Token` | Talk to LIME (`login`, profile, issue MCP JWT) |
| Short **MCP passport JWT** | `Authorization: Bearer` | Talk to **external** MCP resource servers |

Never send `X-Agent-Token` to an MCP server. Never send the MCP JWT to LIME HTTP APIs.

---

## Second scenario — Site login (headless)

Use this when a **site backend** creates a login request and your worker only needs to approve it. The **site** receives the passport over SSE ([`lime-sites-sdk`](https://github.com/Mawyxx/lime-site-sdk)) — your worker does not.

> **R-14 release note:** `lime-agents-sdk >= 3.0.1` solves the domain-separated digest
> `SHA-256(b"lime:pow:v1\0" || challenge || 0x00 || nonce)` required by R-14 servers.
> Earlier releases use the legacy formula and cannot approve logins.

```python
import asyncio
import os

from lime_agents import LimeAgent, ApiError, PowTimeoutError

# UUID from the site waiting screen / your queue (wire format)
REQUEST_ID = "550e8400-e29b-41d4-a716-446655440000"


async def main() -> None:
    agent = LimeAgent(agent_token=os.environ["LIME_AGENT_TOKEN"])  # one per worker process
    try:
        result = await agent.login(REQUEST_ID)
        print(result.status, result.approved_agent_id)
    except PowTimeoutError:
        print("PoW timeout — increase pow_timeout or retry")
    except ApiError as exc:
        print(f"[{exc.code}] {exc.message}")
    finally:
        await agent.aclose()


asyncio.run(main())
```

Example: [`examples/site-login/`](examples/site-login/).

> **Known limitation — `login()` recovery (ADR 0058):** the public challenge read
> (`GET /api/v1/auth/requests/{id}`) returns **404** once the request is approved or
> consumed. If an approve POST is processed but its response is lost (timeout), a
> retry of `login(request_id)` cannot recover the outcome — do not loop, and treat
> the site's SSE delivery as the source of truth. The agent lane has no status-poll
> fallback: `GET /api/v1/modules/agent-login/requests/{id}` requires **`X-Site-Token`**
> (site backend only).

---

## API surface (summary)

| Group | Methods |
|-------|---------|
| **Setup** | `LimeAgent(...)`, `aclose()` |
| **MCP** | `list_tools`, `call_tool`, `list_resources`, `read_resource`, `list_prompts`, `get_prompt`, … |
| **Auth / profile** | `login`, `get_profile` |
| **Advanced** | `get_mcp_access_token(target)`, `mcp_session(target)` |

Full reference: [Read the Docs — API](https://lime-agents-sdk.readthedocs.io/en/latest/api/).

**Errors:** `LimeError` → `AuthenticationError`, `PowTimeoutError`, `RateLimitError`, `ApiError`, `McpAuthenticationError`, `OAuthCapabilityError`.

**Env:** `LIME_AGENT_TOKEN` (required unless constructor), `LIME_API_BASE` (optional, default `https://lime.pics/api/v1`).

---

## Comparison with Official MCP SDK

`lime-agents-sdk` **depends on** [`mcp`](https://github.com/modelcontextprotocol/python-sdk) and composes it for the LIME machine-token model. It does **not** replace `mcp` for server authors or generic OAuth.

### Side-by-side

| Feature | Official `mcp` | `lime-agents-sdk` |
|---------|----------------|-------------------|
| Typical MCP tool call | `streamable_http_client` → `ClientSession` → `initialize` → call (~15 lines) | `list_tools` / `call_tool` (~3 lines) |
| LIME MCP JWT | You fetch + attach Bearer | Auto-issue, cache, lazy refresh, inject |
| Token storage / refresh | You implement | In-memory + single-flight lazy refresh |
| Session pooling | You manage | Per-URL pool; safe same-URL default |
| 401 from MCP RS | Your handling | Invalidate + one retry |
| Site login (PoW) | Not included | `await agent.login(request_id)` |

### Diff you can see

**Without LIME (official client + your token plumbing):**

```python
async with httpx.AsyncClient(headers={"Authorization": f"Bearer {ACCESS_TOKEN}"}) as http:
    async with streamable_http_client(MCP_URL, http_client=http) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            if tools:
                await session.call_tool(tools[0].name, {"text": "hi"})
```

**With LIME:**

```python
async with LimeAgent() as agent:
    tools = await agent.list_tools(MCP_URL)
    if tools:
        await agent.call_tool(MCP_URL, tools[0].name, {"text": "hi"})
```

**Use `mcp` alone** for MCP servers, non-LIME OAuth (PKCE, DCR), or full transport control.  
**Use `lime-agents-sdk`** when you already have a LIME `X-Agent-Token` and want MCP calls without OAuth plumbing.

---

## Two JWT flows (do not mix)

Important once you go past Quick start — details live here, not above the install.

| Flow | Who holds the JWT | Audience | This SDK |
|------|-------------------|----------|----------|
| **Site login passport** | **Site backend** (SSE) | `aud=lime-site-login` | Agent only calls `login()`; site verifies with `lime-sites-sdk` + JWKS |
| **MCP access token** | **Agent worker** (SDK cache) | `aud=mcp` | Auto on `list_tools` / `call_tool`; optional `get_mcp_access_token(target)` |

MCP JWTs: Core-signed, default TTL **~300s**, lazy refresh within `mcp_token_refresh_skew` (30s). **Rejected on LIME HTTP APIs** — only opaque `X-Agent-Token` works there.

More: [MCP OAuth & pool](https://lime-agents-sdk.readthedocs.io/en/latest/mcp-oauth/).

---

## Features

- **MCP OAuth built-in** — issue, cache, lazy-refresh 5-minute JWTs; no manual `/oauth/token` in app code
- **Typed MCP facade** — `list_tools`, `call_tool`, resources, prompts (`mcp.types` re-exported)
- **One-call site login** — PoW fetch, solve, approve
- **Production HTTP** — retries on LIME platform 408/429/5xx; MCP 401 self-heal
- **Strict typing** — `py.typed`, mypy-clean public API

---

## Related packages

| Package | Role |
|---------|------|
| [`lime-sites-sdk`](https://github.com/Mawyxx/lime-site-sdk) | Site backend: create login, SSE, verify site passport |
| [`lime-mcp-server-sdk`](https://github.com/Mawyxx/lime-mcp-server-sdk) | MCP RS: verify Bearer JWT via Core JWKS |

---

## Examples

| Path | Purpose |
|------|---------|
| [`examples/mcp-client/`](examples/mcp-client/) | Canonical Agent → MCP |
| [`examples/site-login/`](examples/site-login/) | Headless approve |
| [`examples/minimal-agent/`](examples/minimal-agent/) | Smallest MCP snippet |

---

## Contributing

```bash
git clone https://github.com/Mawyxx/lime-agents-sdk.git
cd lime-agents-sdk
pip install -e ".[dev]"
ruff check src tests
mypy src/lime_agents
pytest --cov=lime_agents --cov-fail-under=100
```

CI: Python 3.10–3.13, **100% line coverage** on `src/lime_agents`.

---

## License

MIT — see [LICENSE](LICENSE).

## Versioning

See [CHANGELOG.md](CHANGELOG.md). **1.0.0** introduces Zero-Touch `target` (breaking).
