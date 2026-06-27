# MCP integration fixtures

Local test harness lives in the monorepo at `scripts/verify/` (not repo root).

| Prompt / informal name | Canonical path |
|------------------------|----------------|
| `mcp_test_server.py` | [`scripts/verify/mcp_test_server.py`](../../../../scripts/verify/mcp_test_server.py) |
| `test_mcp_e2e.py` | [`scripts/verify/mcp_sdk_e2e.py`](../../../../scripts/verify/mcp_sdk_e2e.py) |
| Shared assertions | [`scripts/verify/mcp_sdk_e2e_checks.py`](../../../../scripts/verify/mcp_sdk_e2e_checks.py) |

## Install dependencies

From monorepo root:

```bash
pip install -r requirements-dev.txt
pip install -e "sdk/python[dev]"
```

Requires: `mcp>=1.12`, `PyJWT`, `httpx`, `lime-agents-sdk` (local editable).

## Start the test resource server

Terminal 1 (monorepo root):

```bash
PYTHONPATH=. python scripts/verify/mcp_test_server.py
```

Listens on `http://127.0.0.1:9000` by default:

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Liveness |
| `POST /tools/echo` | Legacy REST federation (`mcp_test_client.py`) |
| `/mcp` | Streamable HTTP MCP (FastMCP + LIME JWT via JWKS) |

JWT verification uses [`scripts/verify/lime_mcp_jwt.py`](../../../../scripts/verify/lime_mcp_jwt.py) (PyJWT, LIME JWKS envelope unwrap). JWKS cache TTL: `LIME_JWKS_CACHE_TTL_SECONDS` (default `3600`).

## Bearer lane (REST echo)

```bash
set LIME_MCP_INTEGRATION=1
set LIME_AGENT_TOKEN=at_...
set MCP_SERVER_URL=http://127.0.0.1:9000
cd sdk/python
pytest tests/integration/test_mcp_live.py -m mcp_integration -v
```

## Full streamable MCP SDK E2E

Covers all `LimeAgent` MCP facade methods (`list_tools`, `call_tool`, resources, prompts, ping, logging, capabilities).

**Operator script** (monorepo root; auto-starts local MCP RS unless `MCP_E2E_AUTOSTART_SERVER=0`):

```bash
set LIME_AGENT_TOKEN=at_...
set MCP_SERVER_URL=http://127.0.0.1:9000
PYTHONPATH=. python scripts/verify/mcp_sdk_e2e.py
```

Expected: `MCP_SDK_E2E: OK`

**Pytest** (same checks):

```bash
set LIME_MCP_INTEGRATION=1
set LIME_AGENT_TOKEN=at_...
set MCP_SERVER_URL=http://127.0.0.1:9000
cd sdk/python
pytest tests/integration/test_mcp_streamable_e2e.py -m mcp_integration -v
```

Server must be running; tests auto-skip if `/health` is unreachable.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LIME_AGENT_TOKEN` | — | Valid agent token (required for E2E) |
| `LIME_API_BASE` | `https://lime.pics/api/v1` | LIME API root for SDK |
| `MCP_SERVER_URL` | `http://127.0.0.1:9000` | Test RS base URL (SDK appends `/mcp`) |
| `MCP_E2E_AUTOSTART_SERVER` | `1` | Auto-start/recycle local `mcp_test_server.py` (`0` = manual server only) |
| `MCP_E2E_REUSE_SERVER` | `0` | Reuse existing RS on `MCP_SERVER_URL` when healthy (`1` = skip recycle) |
| `NO_PROXY` | (auto) | Script appends `127.0.0.1,localhost` so local RS bypasses HTTP_PROXY |
| `MCP_RS_HOST` / `MCP_RS_PORT` | `127.0.0.1` / `9000` | Server bind address |
| `LIME_BASE_URL` | `https://lime.pics` | LIME origin for JWKS/metadata |
| `LIME_OAUTH_AUDIENCE` | `mcp` | JWT audience |
| `LIME_JWKS_CACHE_TTL_SECONDS` | `3600` | JWKS cache TTL on RS |
| `LIME_JWT_VERIFY_LEEWAY_SECONDS` | `120` | Clock skew leeway |

## Legacy prod federation E2E

```bash
# Terminal 1
PYTHONPATH=. python scripts/verify/mcp_test_server.py

# Terminal 2
set LIME_PROD_VERIFY_AGENT_TOKEN=at_...
PYTHONPATH=. python scripts/verify/mcp_test_client.py
```

Expected: `MCP_OAUTH_E2E: OK`
