# MCP integration fixtures

## Bearer lane (JWT validation)

Use the monorepo harness:

```bash
PYTHONPATH=. python scripts/verify/mcp_test_server.py
```

Then run SDK integration tests:

```bash
set LIME_MCP_INTEGRATION=1
set LIME_AGENT_TOKEN=at_...
set MCP_SERVER_URL=http://127.0.0.1:9000
pytest tests/integration/test_mcp_live.py -m mcp_integration
```

## Full streamable MCP RPC

Point `MCP_SERVER_URL` at any streamable HTTP MCP server that trusts LIME JWKS, then:

```bash
set MCP_STREAMABLE_SERVER=1
set LIME_MCP_INTEGRATION=1
pytest tests/integration/test_mcp_live.py::test_list_tools_live_streamable_fixture -m mcp_integration
```
