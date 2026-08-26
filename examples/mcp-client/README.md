# MCP client (canonical)

List tools and call the first one. JWT issuance / cache / refresh is automatic.

```bash
pip install lime-agents-sdk
export LIME_AGENT_TOKEN=at_...
export MCP_SERVER_URL=https://your-mcp.example/mcp
python main.py
```

Pair the MCP server with [lime-mcp-server-sdk](https://github.com/Mawyxx/lime-mcp-server-sdk).
