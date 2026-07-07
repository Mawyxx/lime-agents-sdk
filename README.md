# lime-agents-sdk — Cryptographic Passport for AI Agents (JWT + MCP OAuth)

**`lime-agents-sdk`** is the official **Python agent SDK** for [LIME](https://lime.pics) — an **AI agent identity** platform that issues **cryptographic passports** (signed JWTs) for autonomous workers. Agent runtimes authenticate with a single opaque **`X-Agent-Token`**, confirm site logins in one async call, and connect to **MCP** resource servers via **MCP OAuth** — without browsers, QR codes, or hand-rolled HTTP.

Use this package when you build **agent workers** (not site backends). Pair with [`lime-sites-sdk`](https://github.com/Mawyxx/lime-site-sdk) on the site side for login creation, SSE delivery, and passport verification.

[![PyPI version](https://img.shields.io/pypi/v/lime-agents-sdk)](https://pypi.org/project/lime-agents-sdk/)
[![Python versions](https://img.shields.io/pypi/pyversions/lime-agents-sdk)](https://pypi.org/project/lime-agents-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/Mawyxx/lime-agents-sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/Mawyxx/lime-agents-sdk/actions/workflows/ci.yml)
[![Documentation](https://readthedocs.org/projects/lime-agents-sdk/badge/?version=latest)](https://lime-agents-sdk.readthedocs.io/)
[![MCP compatible](https://img.shields.io/badge/MCP-compatible-00C853)](https://modelcontextprotocol.io/)

**📖 Python API (Read the Docs):** [lime-agents-sdk.readthedocs.io](https://lime-agents-sdk.readthedocs.io/)  
**📖 Platform HTTP docs:** [lime.pics/docs#guide-agentSdk](https://lime.pics/docs#guide-agentSdk)  
**📦 This SDK:** [github.com/Mawyxx/lime-agents-sdk](https://github.com/Mawyxx/lime-agents-sdk)  
**🌐 Platform:** [https://lime.pics](https://lime.pics)

---

## Why lime-agents-sdk?

| Problem | SDK solution |
|---------|----------------|
| Manual PoW + approve HTTP | `await agent.login(request_id)` — challenge fetch, SHA-256 PoW, approve, retries |
| Two auth lanes (LIME vs MCP) | `X-Agent-Token` for LIME APIs; short-lived **MCP JWT** for external MCP servers |
| MCP OAuth boilerplate | `list_tools` / `call_tool` auto-issue + cache MCP JWT; optional `get_mcp_access_token()` for the raw token |
| Fragile agent credentials | Env-based `LIME_AGENT_TOKEN` (Stripe-style), typed errors, `py.typed` |

### Two JWT flows (do not mix them)

LIME uses **two different JWT artifacts**. This SDK covers the **agent worker** side only.

| Flow | Who gets the JWT | Audience / use | This SDK |
|------|------------------|----------------|---------|
| **Site login passport** | **Site backend** (via SSE) | `aud=lime-site-login` — cryptographic passport for the logged-in session | Agent calls `login()` only; site verifies JWT with [`lime-sites-sdk`](https://github.com/Mawyxx/lime-site-sdk) + Core JWKS |
| **MCP access token** | **Agent worker** (cached in SDK; not sent to site) | `aud=mcp` — Bearer token for **external** MCP resource servers | MCP facade methods auto-issue + cache; optional `get_mcp_access_token()` if you need the raw JWT |

The MCP JWT is signed with LIME Core keys (JWKS at `GET /api/v1/core/.well-known/jwks.json`). Default TTL is **300 seconds (5 minutes)**. The SDK caches it in your worker and performs **lazy refresh** on the next MCP call when the token is within **~30 seconds of expiry** (`mcp_token_refresh_skew`, default `30`) — there is **no background refresh task**. You send the JWT to **remote** MCP servers as `Authorization: Bearer` — not to the site backend. **MCP JWTs are rejected on LIME HTTP APIs** — only opaque `X-Agent-Token` works there.

---

## Installation

```bash
pip install lime-agents-sdk
```

Latest from GitHub:

```bash
pip install git+https://github.com/Mawyxx/lime-agents-sdk.git
```

**Requirements:** Python 3.10+ · runtime deps: `httpx`, `mcp`

---

## Quick start

### Scenario A — Site login (headless agent authentication)

**Story:** A site backend starts a login request and hands `request_id` to your agent worker. The worker proves identity with PoW + approve. The **site** receives the signed **agent passport JWT** over SSE (handled by `lime-sites-sdk`). Your worker only runs the approve step.

```python
import asyncio
import os

from lime_agents import LimeAgent, ApiError, PowTimeoutError

# LIME_AGENT_TOKEN=at_...  (from the LIME owner portal — server-side secret only)
REQUEST_ID = "lr_abc123"  # from your site backend / job queue


async def main() -> None:
    # One LimeAgent per worker process (reuse across jobs)
    agent = LimeAgent(agent_token=os.environ["LIME_AGENT_TOKEN"])

    try:
        result = await agent.login(REQUEST_ID)
        print(result.status)  # APPROVED after successful approve (site receives passport JWT via SSE separately)
        print(result.approved_agent_id)  # agent UUID from approve response (may be None on edge cases)
    except PowTimeoutError:
        print("PoW not solved in time — increase pow_timeout or retry")
    except ApiError as exc:
        print(f"[{exc.code}] {exc.message}")
    finally:
        await agent.aclose()


asyncio.run(main())
```

**What `login()` does internally:**

1. `GET /api/v1/auth/requests/{request_id}` — read PoW challenge (no auth)
2. Solve PoW in a thread pool (`asyncio.to_thread`)
3. `POST /api/v1/modules/agent-login/requests/{request_id}/approve` with `X-Agent-Token` + `{"pow_nonce": "..."}`

**Site side (separate package):** [`lime-sites-sdk`](https://github.com/Mawyxx/lime-site-sdk) → `create_login_request()` → SSE `on_login` → `verify_passport()` against Core JWKS.

---

### Scenario B — MCP tools (MCP OAuth + streamable HTTP client)

**Story:** Your agent calls tools on an **external** MCP resource server. LIME issues a **short-lived MCP JWT** (~5 min) from your `X-Agent-Token`. The SDK attaches `Authorization: Bearer`, pools sessions per server URL, and retries on 401 after refresh.

```python
import asyncio
import os

from lime_agents import LimeAgent, CallToolResult, Tool

MCP_ENDPOINT = "https://mcp.example.com/mcp"  # full streamable HTTP path, not just the host


async def main() -> None:
    async with LimeAgent(agent_token=os.environ["LIME_AGENT_TOKEN"]) as agent:
        # MCP JWT (~300s TTL) is fetched automatically on first list_tools / call_tool
        tools: list[Tool] = await agent.list_tools(MCP_ENDPOINT)
        print([t.name for t in tools])

        result: CallToolResult = await agent.call_tool(
            MCP_ENDPOINT,
            tools[0].name,
            {"text": "hello from LIME agent"},
        )
        if result.isError:
            print("tool error:", result.content)
        else:
            print(result.content)

        # Same agent, another MCP server — sessions cached per URL
        # await agent.call_tool("https://other-mcp.example.com/mcp", "get_weather", {"city": "Berlin"})


asyncio.run(main())
```

**Credential lanes (never swap headers):**

| Lane | Header | Used for |
|------|--------|----------|
| LIME platform | `X-Agent-Token` | `login()`, `get_profile()`, `POST .../oauth/token` |
| External MCP RS | `Authorization: Bearer <mcp_jwt>` | `list_tools`, `call_tool`, resources, prompts |

OAuth issuance: `POST /api/v1/modules/oauth/token` — **header only, empty body** ([MCP OAuth ADR](https://github.com/Mawyxx/Lime/blob/main/docsN/adr/0081-oauth-module-for-mcp.md)). Resource servers verify the JWT via Core JWKS — use [`lime-mcp-server-sdk`](https://github.com/Mawyxx/lime-mcp-server-sdk) on the server side.

---

## Features

- **One-call site login** — `await agent.login(request_id)` wraps PoW fetch, solve, and approve with `X-Agent-Token`
- **MCP OAuth built-in** — issue, cache, and **lazy-refresh** 5-minute MCP JWTs on the next `list_tools` / `call_tool` when near expiry; no manual `/oauth/token` in app code
- **Typed MCP client** — `list_tools`, `call_tool`, `read_resource`, `get_prompt`, … with `mcp.types` models re-exported from `lime_agents`
- **Automatic Proof-of-Work** — SHA-256 solver with configurable `pow_timeout` and transient retry policy
- **Production-ready LIME HTTP** — httpx async client, exponential backoff on 408/429/5xx for **platform** calls (`login`, profile, OAuth issuance); MCP calls retry on 401 after token refresh
- **Strict typing** — `ApprovalResult`, `AgentProfile`, `McpAccessToken`, `py.typed`, mypy-clean public API

---

## Comparison with Official MCP SDK

The official [`mcp`](https://github.com/modelcontextprotocol/python-sdk) package (PyPI: `mcp`) is the **protocol SDK**: transports, `ClientSession`, JSON-RPC types, server tooling (`FastMCP`), and generic OAuth helpers. **`lime-agents-sdk` depends on it** and wraps the client path for **LIME agent workers** — site login, LIME OAuth token issuance, session pooling, and typed facade methods.

Choose **`mcp` alone** when you need full control over transports, non-LIME OAuth (authorization code + PKCE, dynamic client registration), MCP servers, or stdio/SSE transports. Choose **`lime-agents-sdk`** when your worker already has a LIME `X-Agent-Token` and you want MCP tool calls with minimal boilerplate.

### Side-by-side

| Feature / Aspect | Official MCP SDK (`mcp`) | LIME SDK (`lime-agents-sdk`) | Benefit of LIME |
|------------------|--------------------------|------------------------------|-----------------|
| **Scope** | Client + server protocol stack, multiple transports | LIME **agent worker** client only (login, profile, MCP tools) | One package for LIME identity + MCP; less assembly |
| **Typical MCP tool call** | Wire `streamable_http_client` → `ClientSession` → `initialize()` → `list_tools()` / `call_tool()` yourself | `await agent.list_tools(url)` / `await agent.call_tool(url, name, args)` | Fewer lines; no manual session wiring |
| **LIME machine OAuth** (`X-Agent-Token` → MCP JWT) | Not built-in; you implement token fetch + Bearer header on `httpx.AsyncClient` | `POST /modules/oauth/token` (empty body) via `_McpTokenIssuer`; auto-attached on MCP calls | No hand-rolled LIME OAuth client |
| **Generic OAuth** | `OAuthClientProvider` (auth code + PKCE), `ClientCredentialsOAuthProvider`, `TokenStorage` protocol | Not a general OAuth library; LIME token model only | — (use `mcp` auth if you need RFC flows outside LIME) |
| **Token caching** | Your `TokenStorage` implementation | In-memory cache in `_McpTokenIssuer` | Works out of the box |
| **Token refresh** | Refresh via `refresh_token` when present (`OAuthClientProvider`); expiry checked on requests | **Lazy refresh**: next MCP call when within `mcp_token_refresh_skew` (default 30s) of `expires_in`; **single-flight** lock | No refresh_token dance for LIME JWT; no thundering herd on `/oauth/token` |
| **Background refresh timer** | None in core (refresh on next HTTP request when token invalid) | None (same lazy-on-call model) | Honest behavior; no hidden tasks |
| **Session pooling** | You manage `ClientSession` lifecycle per server URL | `McpSessionPool` — one pooled session per URL, shared OAuth issuer | Reuse connections across calls; parallel different URLs |
| **Same-URL concurrency** | Your responsibility | `serialize_mcp_per_url=True` by default (one in-flight op per URL) | Safer default for streamable HTTP sessions |
| **401 from MCP RS** | Your error handling | Invalidate JWT, close pooled transports, **one retry** → `McpAuthenticationError` | Recovery without app-level token loops |
| **HTTP retries (408/429/5xx)** | Transport-level reconnection (`MAX_RECONNECTION_ATTEMPTS=2` on streamable HTTP); OAuth layer retries refresh | Exponential backoff on **LIME platform** HTTP only (`login`, profile, OAuth); MCP layer: 401 + broken-session retry only | Clear split: platform resilience vs MCP auth recovery |
| **Site login (PoW + approve)** | Not included | `await agent.login(request_id)` | LIME-specific; not in `mcp` |
| **Return types** | MCP protocol models (`list_tools` → result with `.tools`) | `list[Tool]` facade; re-exports `mcp.types` | Slightly simpler agent code |

### Minimal example — list tools + call

**Official `mcp` (streamable HTTP + Bearer you obtained yourself):**

```python
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

MCP_URL = "https://mcp.example.com/mcp"
ACCESS_TOKEN = "..."  # you fetch and refresh this


async def main() -> None:
    async with httpx.AsyncClient(
        headers={"Authorization": f"Bearer {ACCESS_TOKEN}"},
        timeout=30.0,
    ) as http:
        async with streamable_http_client(MCP_URL, http_client=http) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = (await session.list_tools()).tools
                result = await session.call_tool(tools[0].name, {"text": "hi"})
```

**`lime-agents-sdk` (LIME OAuth + pool + facade):**

```python
from lime_agents import LimeAgent

MCP_URL = "https://mcp.example.com/mcp"


async def main() -> None:
    async with LimeAgent() as agent:  # LIME_AGENT_TOKEN from env
        tools = await agent.list_tools(MCP_URL)
        result = await agent.call_tool(MCP_URL, tools[0].name, {"text": "hi"})
```

### Summary

- **`mcp`** is the right foundation for **protocol-level** work (servers, custom OAuth, arbitrary transports).
- **`lime-agents-sdk`** is a **LIME-specific client layer** on top of `mcp` that removes repetitive OAuth, session, and pooling code for agent workers.
- LIME does **not** replace `mcp` for server authors or for non-LIME OAuth; it **composes** `mcp` where LIME's machine token model applies.

Details: [MCP OAuth & pool](https://lime-agents-sdk.readthedocs.io/en/latest/mcp-oauth/) (Read the Docs).

---

## API reference (summary)

### `LimeAgent`

| Method | Description |
|--------|-------------|
| `await agent.login(request_id)` | Site login approve flow → `ApprovalResult` |
| `await agent.get_profile()` | `GET /core/agents/me/profile` → `AgentProfile` |
| `await agent.get_mcp_access_token()` | Optional: expose cached MCP OAuth JWT (~300s TTL); not required before MCP calls |
| `await agent.list_tools(server_url)` | MCP tools (typed `Tool`) |
| `await agent.call_tool(server_url, name, args)` | MCP tool invocation → `CallToolResult` |
| `await agent.list_resources(...)` / `read_resource(...)` / `list_prompts(...)` / `get_prompt(...)` | Full MCP facade |
| `async with agent.mcp_session(url)` | Low-level `mcp.ClientSession` with per-URL lock |

**Constructor highlights:** `agent_token` / `LIME_AGENT_TOKEN`, `base_url` / `LIME_API_BASE` (default `https://lime.pics/api/v1`), `timeout`, `max_retries`, `mcp_token_refresh_skew` (default `30`, lazy refresh window), `serialize_mcp_per_url` (default `True`).

**Context manager:** `async with LimeAgent() as agent:` calls `aclose()` on exit. For long-running workers, create **one** instance at startup and reuse it.

### Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LIME_AGENT_TOKEN` | Yes* | Agent secret (`at_...`) from the LIME portal |
| `LIME_API_BASE` | No | API root, e.g. `https://lime.pics/api/v1` |

\*Unless `agent_token=` is passed to the constructor.

### Errors

All inherit from `LimeError`: `AuthenticationError`, `PowTimeoutError`, `RateLimitError`, `ApiError`, `McpAuthenticationError`, `OAuthCapabilityError`.

---

## Related packages

| Package | Role |
|---------|------|
| [`lime-sites-sdk`](https://github.com/Mawyxx/lime-site-sdk) | Site backend: create login, SSE events, **verify site passport JWT** |
| [`lime-mcp-server-sdk`](https://github.com/Mawyxx/lime-mcp-server-sdk) | MCP resource server: **verify MCP Bearer JWT** via Core JWKS |

---

## Contributing

Issues and pull requests: [github.com/Mawyxx/lime-agents-sdk](https://github.com/Mawyxx/lime-agents-sdk)

```bash
git clone https://github.com/Mawyxx/lime-agents-sdk.git
cd lime-agents-sdk
pip install -e ".[dev]"
ruff check src tests
mypy src/lime_agents
pytest --cov=lime_agents --cov-fail-under=100
```

CI runs on Python 3.10–3.13 with **100% line coverage** on `src/lime_agents`.

---

## License

MIT — see [LICENSE](LICENSE).
