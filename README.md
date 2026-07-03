# lime-agents-sdk — Cryptographic Passport for AI Agents (JWT + MCP OAuth)

**`lime-agents-sdk`** is the official **Python agent SDK** for [LIME](https://lime.pics) — an **AI agent identity** platform that issues **cryptographic passports** (signed JWTs) for autonomous workers. Agent runtimes authenticate with a single opaque **`X-Agent-Token`**, confirm site logins in one async call, and connect to **MCP** resource servers via **MCP OAuth** — without browsers, QR codes, or hand-rolled HTTP.

Use this package when you build **agent workers** (not site backends). Pair with [`lime-sites-sdk`](https://github.com/Mawyxx/lime-site-sdk) on the site side for login creation, SSE delivery, and passport verification.

[![PyPI version](https://img.shields.io/pypi/v/lime-agents-sdk)](https://pypi.org/project/lime-agents-sdk/)
[![Python versions](https://img.shields.io/pypi/pyversions/lime-agents-sdk)](https://pypi.org/project/lime-agents-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/Mawyxx/lime-agents-sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/Mawyxx/lime-agents-sdk/actions/workflows/ci.yml)
[![MCP compatible](https://img.shields.io/badge/MCP-compatible-00C853)](https://modelcontextprotocol.io/)

**📖 Platform API docs:** [https://lime.pics/docs](https://lime.pics/docs#guide-agentSdk)  
**📦 This SDK:** [github.com/Mawyxx/lime-agents-sdk](https://github.com/Mawyxx/lime-agents-sdk)  
**🌐 Platform:** [https://lime.pics](https://lime.pics)

---

## Why lime-agents-sdk?

| Problem | SDK solution |
|---------|----------------|
| Manual PoW + approve HTTP | `await agent.login(request_id)` — challenge fetch, SHA-256 PoW, approve, retries |
| Two auth lanes (LIME vs MCP) | `X-Agent-Token` for LIME APIs; short-lived **MCP JWT** for external MCP servers |
| MCP OAuth boilerplate | `get_mcp_access_token()` + typed `list_tools` / `call_tool` facade |
| Fragile agent credentials | Env-based `LIME_AGENT_TOKEN` (Stripe-style), typed errors, `py.typed` |

### Two JWT flows (do not mix them)

LIME uses **two different JWT artifacts**. This SDK covers the **agent worker** side only.

| Flow | Who gets the JWT | Audience / use | This SDK |
|------|------------------|----------------|---------|
| **Site login passport** | **Site backend** (via SSE) | `aud=lime-site-login` — cryptographic passport for the logged-in session | Agent calls `login()` only; site verifies JWT with [`lime-sites-sdk`](https://github.com/Mawyxx/lime-site-sdk) + Core JWKS |
| **MCP access token** | **Agent worker** (in-process) | `aud=mcp` — Bearer token for **external** MCP resource servers | `get_mcp_access_token()` or MCP facade methods (auto-issue + cache) |

The MCP JWT is signed with LIME Core keys (JWKS at `GET /api/v1/core/.well-known/jwks.json`). Default TTL is **300 seconds (5 minutes)**. The SDK caches it and refreshes ~30s before expiry so repeated `list_tools` / `call_tool` calls stay fast. **MCP JWTs are rejected on LIME HTTP APIs** — only opaque `X-Agent-Token` works there.

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
        # Optional: inspect the cached OAuth token (TTL ~300s, auto-refresh)
        token = await agent.get_mcp_access_token()
        print(f"MCP JWT expires_in={token.expires_in}s")

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
- **MCP OAuth built-in** — issue, cache, and refresh **5-minute MCP JWTs**; no manual `/oauth/token` calls in app code
- **Typed MCP client** — `list_tools`, `call_tool`, `read_resource`, `get_prompt`, … with `mcp.types` models re-exported from `lime_agents`
- **Automatic Proof-of-Work** — SHA-256 solver with configurable `pow_timeout` and transient retry policy
- **Production-ready HTTP** — httpx async client, exponential backoff on 408/429/5xx, injectable client for tests
- **Strict typing** — `ApprovalResult`, `AgentProfile`, `McpAccessToken`, `py.typed`, mypy-clean public API

---

## API reference (summary)

### `LimeAgent`

| Method | Description |
|--------|-------------|
| `await agent.login(request_id)` | Site login approve flow → `ApprovalResult` |
| `await agent.get_profile()` | `GET /core/agents/me/profile` → `AgentProfile` |
| `await agent.get_mcp_access_token()` | MCP OAuth JWT (~300s TTL), cached with refresh skew |
| `await agent.list_tools(server_url)` | MCP tools (typed `Tool`) |
| `await agent.call_tool(server_url, name, args)` | MCP tool invocation → `CallToolResult` |
| `await agent.list_resources(...)` / `read_resource(...)` / `list_prompts(...)` / `get_prompt(...)` | Full MCP facade |
| `async with agent.mcp_session(url)` | Low-level `mcp.ClientSession` with per-URL lock |

**Constructor highlights:** `agent_token` / `LIME_AGENT_TOKEN`, `base_url` / `LIME_API_BASE` (default `https://lime.pics/api/v1`), `timeout`, `max_retries`, `pow_timeout`, `serialize_mcp_per_url` (default `True`).

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
