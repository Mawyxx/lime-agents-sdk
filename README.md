# LIME Agents SDK

[![PyPI version](https://img.shields.io/pypi/v/lime-agents-sdk)](https://pypi.org/project/lime-agents-sdk/)
[![Python versions](https://img.shields.io/pypi/pyversions/lime-agents-sdk)](https://pypi.org/project/lime-agents-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/Mawyxx/lime-agents-sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/Mawyxx/lime-agents-sdk/actions/workflows/ci.yml)

Official Python SDK for [LIME](https://lime.pics) agent workers. Async-first client that performs site-login approval end-to-end: fetch Proof-of-Work challenge, solve SHA-256 PoW, submit approve with retries.

## Installation

```bash
pip install lime-agents-sdk
```

Install the latest commit from GitHub:

```bash
pip install git+https://github.com/Mawyxx/lime-agents-sdk.git
```

**Requirements:** Python 3.10+

## Quick start

Examples use readable names (`Lime`, `login`) on top of the shipped API (`LimeAgent`, `approve`). See [API reference](#api-reference) for exact types and parameters.

### Minimal

```python
from lime_agents import LimeAgent as _LimeAgent


class Lime(_LimeAgent):
    """aiogram-style client: token first, login() instead of approve()."""

    def __init__(self, token: str):
        super().__init__(agent_token=token)

    async def login(self, request_id: str):
        return await self.approve(request_id)


AGENT_TOKEN = "at_..."  # LIME Owner Portal → agent token (copy once)

async def login_to_site(request_id: str) -> str:
    """Agent confirms sign-in to a site. Returns status."""
    lime = Lime(AGENT_TOKEN)
    try:
        result = await lime.login(request_id)
        return result.status  # "DELIVERED"
    finally:
        await lime.aclose()
```

### Production

```python
from lime_agents import LimeAgent as _LimeAgent, PowTimeoutError, ApiError


class Lime(_LimeAgent):
    def __init__(self, token: str):
        super().__init__(agent_token=token)

    async def login(self, request_id: str):
        return await self.approve(request_id)


AGENT_TOKEN = "at_..."


class Agent:
    """Autonomous worker that signs in to sites when asked."""

    def __init__(self):
        self.lime = Lime(AGENT_TOKEN)

    async def on_login_required(self, request_id: str) -> str | None:
        """Site requires login — agent confirms."""
        try:
            result = await self.lime.login(request_id)
            return result.status
        except PowTimeoutError:
            # Proof-of-Work exceeded pow_timeout (default 10s) — retry once
            try:
                result = await self.lime.login(request_id)
                return result.status
            except PowTimeoutError:
                return None
        except ApiError as exc:
            print(f"[{exc.code}] {exc.message}")
            return None
```

## Authentication

The SDK authenticates agent HTTP calls with the `X-Agent-Token` header.

**Resolution order:**

1. Constructor argument `agent_token="at_..."`
2. Environment variable `LIME_AGENT_TOKEN`

If neither is set (or the value is empty after trimming), construction raises `AuthenticationError`:

```python
from lime_agents import LimeAgent, AuthenticationError

try:
    agent = LimeAgent()
except AuthenticationError as exc:
    print(exc.message)
```

Obtain the agent token once when registering an agent in the LIME owner portal. Store it as a server-side secret in your worker environment.

## Integration pattern: Headless agent

Typical embedding: hold one `LimeAgent` per worker process and call `approve()` when a login request arrives.

```python
from lime_agents import LimeAgent


class TradingAgent:
    def __init__(self, token: str):
        self.lime = LimeAgent(agent_token=token)

    async def on_login_required(self, request_id: str) -> str:
        result = await self.lime.approve(request_id)
        return result.status
```

The site backend creates the request (`POST /modules/agent-login/requests`), delivers `login_request_id` to your worker, and long-polls events until status becomes `DELIVERED`. Your worker only runs the approve step above.

## API reference

### `LimeAgent`

Async client for agent-runtime operations (approve login, read profile).

#### Constructor

All arguments are keyword-only.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `agent_token` | `str \| None` | `None` | Agent secret. Falls back to `LIME_AGENT_TOKEN`. |
| `base_url` | `str \| None` | `None` | API root including `/api/v1`. Falls back to `LIME_API_BASE`, then `https://lime.pics/api/v1`. |
| `timeout` | `float` | `30.0` | Per-request HTTP timeout in seconds (httpx). |
| `max_retries` | `int` | `3` | Maximum retries on transient network errors and HTTP 408/429/5xx. |
| `pow_timeout` | `float` | `10.0` | Wall-clock budget in seconds for the PoW solver loop. |
| `http_client` | `httpx.AsyncClient \| None` | `None` | Inject a custom async HTTP client (tests, corporate proxy/TLS). When omitted, the SDK creates and owns a client. |

```python
agent = LimeAgent(
    agent_token="at_live_...",
    base_url="https://lime.pics/api/v1",
    timeout=60.0,
    max_retries=5,
    pow_timeout=15.0,
)
```

**Context manager:** `async with LimeAgent() as agent:` calls `aclose()` on exit. Call `await agent.aclose()` manually when not using a context manager.

#### `async approve(request_id: str) -> ApprovalResult`

Confirms a site login request on behalf of the agent.

**Internal steps:**

1. `GET /auth/requests/{request_id}` (public, no auth) — read `pow_challenge`, `pow_difficulty`
2. Solve PoW: find `nonce` such that `int(SHA256(challenge + nonce), 16) < 2**(256 - difficulty)`
3. `POST /modules/agent-login/requests/{request_id}/approve` with `X-Agent-Token` and body `{"pow_nonce": "<nonce>"}`

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `request_id` | `str` | Login request ID from the site backend (`login_request_id` from create). |

**Returns:** `ApprovalResult` with FSM status (typically `DELIVERED` after successful approve).

```python
from lime_agents import LimeAgent, PowTimeoutError, ApiError

async with LimeAgent() as agent:
    try:
        result = await agent.approve("550e8400-e29b-41d4-a716-446655440000")
        print(result.status, result.approved_agent_id)
    except PowTimeoutError:
        print("PoW not solved in time; increase pow_timeout or retry")
    except ApiError as exc:
        print(exc.code, exc.http_status, exc.message)
```

#### `async get_profile() -> AgentProfile`

Returns the authenticated agent's Core profile.

**HTTP:** `GET /core/agents/me/profile` with `X-Agent-Token`.

```python
async with LimeAgent() as agent:
    profile = await agent.get_profile()
    print(profile.agent_id)
    print(profile.owner_kyc_level)
    print(profile.agent_reputation)
```

## Types

### `ApprovalResult`

Frozen dataclass returned by `approve()`.

| Field | Type | Description |
|-------|------|-------------|
| `request_id` | `str` | Login request ID |
| `site_id` | `str` | Site that created the request |
| `status` | `str` | FSM value, e.g. `APPROVED`, `DELIVERED` |
| `expires_at` | `datetime` | Request expiry (timezone-aware when API sends offset) |
| `approved_agent_id` | `str \| None` | Agent that approved (set after approve) |

### `AgentProfile`

Frozen dataclass returned by `get_profile()`. Matches `GET /core/agents/me/profile` response fields.

| Field | Type | Description |
|-------|------|-------------|
| `agent_id` | `str` | Agent identifier |
| `owner_id` | `str` | Owning LIME user |
| `display_name` | `str \| None` | Public display name |
| `avatar_url` | `str \| None` | Avatar URL |
| `description` | `str \| None` | Public description |
| `owner_kyc_level` | `int \| None` | Owner KYC level synced from Foundation |
| `agent_reputation` | `int \| None` | Reputation score |

## Error handling

All SDK exceptions inherit from `LimeError`. Each carries `message`, and optionally `code`, `http_status`, and `detail` (API envelope).

| Exception | When |
|-----------|------|
| `LimeError` | Base class; transport failures after retries, malformed JSON |
| `AuthenticationError` | Missing/empty token at construct; HTTP 401; `MISSING_AGENT_TOKEN`, `INVALID_AGENT_TOKEN` |
| `PowTimeoutError` | PoW solver exceeded `pow_timeout` |
| `RateLimitError` | HTTP 429 / `RATE_LIMIT_EXCEEDED` |
| `ApiError` | Other API errors (`ok: false` envelope) |

`ApiError` attributes: `code`, `message`, `http_status`, `detail`.

```python
import asyncio

from lime_agents import (
    LimeAgent,
    LimeError,
    AuthenticationError,
    PowTimeoutError,
    RateLimitError,
    ApiError,
)

async def run() -> None:
    try:
        async with LimeAgent() as agent:
            await agent.approve("lr_abc123")
    except AuthenticationError as exc:
        print("auth:", exc.message)
    except PowTimeoutError as exc:
        print("pow:", exc.message)
    except RateLimitError as exc:
        print("rate limit:", exc.http_status)
    except ApiError as exc:
        print(f"api [{exc.http_status}] {exc.code}: {exc.message}")
    except LimeError as exc:
        print("sdk:", exc.message)

asyncio.run(run())
```

**Non-retried HTTP statuses:** 400, 401, 403, 404, 409 (e.g. `INVALID_POW`, `SITE_LOGIN_CONFLICT`).

## Configuration

### Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LIME_AGENT_TOKEN` | Yes (unless `agent_token=` passed) | Agent secret (`at_...`) |
| `LIME_API_BASE` | No | API root, e.g. `https://lime.pics/api/v1` |

### Constructor tuning

| Use case | Suggestion |
|----------|------------|
| Slow network | Increase `timeout` (e.g. `60.0`) |
| Flaky upstream | Increase `max_retries` (e.g. `5`) |
| High PoW difficulty / slow CPU | Increase `pow_timeout` (e.g. `30.0`) |
| Staging / self-hosted API | Set `base_url` or `LIME_API_BASE` |

### Logging

HTTP and retry events are logged under the **`lime`** logger (not `lime_agents`):

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logging.getLogger("lime").setLevel(logging.DEBUG)
```

At `DEBUG`, the client logs request method and URL. Tokens, `pow_challenge`, and `pow_nonce` are never logged.

## Advanced usage

### Custom `httpx.AsyncClient`

Inject a client for custom TLS, proxies, or tests. **You own the client lifecycle** when injecting; the SDK does not close an injected client.

```python
import httpx
from lime_agents import LimeAgent


async def approve_with_proxy() -> None:
    client = httpx.AsyncClient(
        timeout=60.0,
        verify="/path/to/corporate-ca.pem",
        proxy="http://proxy.corp.example:8080",
    )
    agent = LimeAgent(agent_token="at_...", http_client=client)
    try:
        await agent.approve("lr_abc123")
    finally:
        await client.aclose()
```

### Retries and timeouts

Retries use exponential backoff with jitter on connection errors, timeouts, and HTTP 408, 429, 500, 502, 503, 504. Each retry attempt is bounded by `max_retries` (default 3).

```python
agent = LimeAgent(
    agent_token="at_...",
    max_retries=5,
    timeout=45.0,
    pow_timeout=20.0,
)
```

### PoW debugging

PoW runs in a thread pool (`asyncio.to_thread`) so the event loop stays responsive. To observe HTTP flow (not nonce values):

```python
import logging

logging.getLogger("lime").setLevel(logging.DEBUG)
```

If `PowTimeoutError` occurs, increase `pow_timeout` or verify `pow_difficulty` from `GET /auth/requests/{id}` (default 15 on production).

## Links

- **SDK repository:** [github.com/Mawyxx/lime-agents-sdk](https://github.com/Mawyxx/lime-agents-sdk)
- **LIME API docs:** [lime.pics/docs](https://lime.pics/docs)
- **LIME platform:** [github.com/Mawyxx/Lime](https://github.com/Mawyxx/Lime)

## License

MIT — see [LICENSE](LICENSE).
