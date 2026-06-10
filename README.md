# lime-agents-sdk

Python SDK for LIME 2.0 agent authentication. Zero-config, Proof-of-Work auto-solve, async-first.

## Install

```bash
pip install lime-agents-sdk
```

From GitHub (latest `main`):

```bash
pip install git+https://github.com/Mawyxx/lime-agents-sdk.git
```

Requires Python 3.10+.

## Quick start

```python
import asyncio
from lime_agents import LimeAgent

async def main() -> None:
    agent = LimeAgent()  # reads LIME_AGENT_TOKEN
    result = await agent.approve("lr_abc123")
    print(result.status)
    profile = await agent.get_profile()
    print(profile.agent_id)

asyncio.run(main())
```

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LIME_AGENT_TOKEN` | Yes | Agent secret from the owner portal |
| `LIME_API_BASE` | No | API root (default `https://lime.pics/api/v1`) |

## API

### `LimeAgent.approve(request_id)`

Fetches the PoW challenge, solves it, and approves the login request in one call.

### `LimeAgent.get_profile()`

Returns the authenticated agent's Core profile (`agent_id`, `owner_id`, `display_name`, etc.).

## Errors

| Exception | When |
|-----------|------|
| `AuthenticationError` | Missing or invalid agent token |
| `PowTimeoutError` | PoW not solved within `pow_timeout` (default 10s) |
| `RateLimitError` | HTTP 429 |
| `ApiError` | Other API errors with `code` and `message` |

All errors inherit from `LimeError`.

## Development

```bash
pip install -e ".[dev]"
pytest --cov=lime_agents --cov-fail-under=100
ruff check src tests
mypy src/lime_agents
```

## Links

- [GitHub repository](https://github.com/Mawyxx/lime-agents-sdk)
- [LIME public API docs](https://lime.pics/docs) — HTTP reference
- Architecture: ADR 0059 in [LIME 2.0](https://github.com/Mawyxx/LIME) monorepo `docsN/adr/`
