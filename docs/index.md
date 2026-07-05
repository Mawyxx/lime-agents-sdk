# lime-agents-sdk

Python library for **your AI agent process** — the program that runs on your server and
acts on behalf of a registered LIME agent.

[![PyPI](https://img.shields.io/pypi/v/lime-agents-sdk)](https://pypi.org/project/lime-agents-sdk/)
[![Documentation](https://readthedocs.org/projects/lime-agents-sdk/badge/?version=latest)](https://lime-agents-sdk.readthedocs.io/)
[![GitHub](https://img.shields.io/github/stars/Mawyxx/lime-agents-sdk?style=social)](https://github.com/Mawyxx/lime-agents-sdk)

---

## Who is this for?

You registered an **agent** in the [LIME portal](https://lime.pics) and got a secret
`agent_token`. This SDK is the Python client your agent worker uses to talk to LIME.

You do **not** need this SDK on the website backend — that side uses
[lime-sites-sdk](https://lime-sites-sdk.readthedocs.io/).

---

## Two separate jobs (pick yours)

This SDK can do **two different things**. They do not depend on each other — use one, the
other, or both.

### Scenario 1 — Approve user login on a website

**When:** A user wants to log into someone else's site through your agent.

**Who does what:**

```
Site backend (lime-sites-sdk)     Your agent worker (THIS SDK)
        │                                    │
        │  1. create_login_request()         │
        │───────────────────────────────────>│  2. login(request_id)
        │                                    │
        │  3. receives passport via SSE      │
        │     (you don't handle this)        │
```

**What you call:**

```python
async with LimeAgent() as agent:
    result = await agent.login(request_id)   # one method — SDK does the rest
    print(result.status)                     # "APPROVED"
```

**You need:** `LIME_AGENT_TOKEN` in environment.

**Full walkthrough:** [Quick Start — Site login](quickstart.md#scenario-1-site-login)

---

### Scenario 2 — Call tools on an external MCP server

**When:** Your agent must use tools hosted on another server (calculator, database, API
adapter, etc.) that trusts LIME-issued tokens.

**What you call:**

```python
async with LimeAgent() as agent:
    tools = await agent.list_tools("https://your-mcp-server.example/mcp")
    result = await agent.call_tool("https://your-mcp-server.example/mcp", tools[0].name, {})
```

**You need:** same `LIME_AGENT_TOKEN`. The SDK requests a short-lived access token from
LIME automatically — you do **not** call `get_mcp_access_token()` unless you build custom
HTTP yourself.

**Full walkthrough:** [Quick Start — MCP tools](quickstart.md#scenario-2-mcp-tools)

---

## Class structure: `LimeAgent`

Everything lives in **one class**. Methods are grouped by scenario:

```
LimeAgent
│
├─── SETUP (always first)
│    LimeAgent(agent_token=...)     create client; reads LIME_AGENT_TOKEN from env
│    async with LimeAgent(): ...    same + auto cleanup on exit
│    await agent.aclose()            close connections manually
│
├─── SCENARIO 1 — Site login
│    await agent.login(request_id)   → ApprovalResult
│         PoW + approve in one call. Site gets JWT separately (not your job).
│
├─── Optional — Agent profile
│    await agent.get_profile()       → AgentProfile
│
└─── SCENARIO 2 — MCP tools
     await agent.list_tools(url)     → list[Tool]
     await agent.call_tool(url, name, args)  → CallToolResult
     await agent.get_mcp_access_token()      → McpAccessToken  (rare; auto otherwise)
     … list_resources, read_resource, list_prompts, get_prompt (same url pattern)
```

Method signatures and errors: [API Reference](api.md).

---

## What you need before coding

| Item | Where to get it |
|------|-----------------|
| `LIME_AGENT_TOKEN` | LIME portal → your agent → copy token once |
| `request_id` (scenario 1) | Site backend creates it; passes to your worker (queue, RPC, message) |
| MCP server URL (scenario 2) | URL of the external MCP HTTP endpoint |

Optional env var `LIME_API_BASE` — default `https://lime.pics/api/v1`.

---

## Install

```bash
pip install lime-agents-sdk
```

Details: [Installation](installation.md)

---

## Other LIME SDKs

| SDK | Your role |
|-----|-----------|
| **lime-agents-sdk** (this) | Agent worker process |
| [lime-sites-sdk](https://lime-sites-sdk.readthedocs.io/) | Website backend |
| [lime-mcp-server-sdk](https://lime-mcp-server-sdk.readthedocs.io/) | MCP server operator (verify tokens) |

Platform HTTP reference: [lime.pics/docs](https://lime.pics/docs#guide-agentSdk)

---

## Next pages

1. [Quick Start](quickstart.md) — copy-paste examples for both scenarios
2. [API Reference](api.md) — every method, one section each
3. [Examples](examples.md) — error handling, multiple MCP servers
