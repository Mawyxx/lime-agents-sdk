# Changelog

## 1.0.0 — Zero-Touch MCP Auth

Breaking SemVer major. No backward compatibility with 0.5.x empty-body tokens.

### Breaking

- All MCP facade methods require `target: str` (URL or hostname). Renamed from `server_url`.
- `get_mcp_access_token(target, *, force_refresh=False)` requires `target`.
- Token wire is `POST /modules/oauth/token` with JSON `{"domain": "<normalized>"}` (ADR 0081 Amendment v11). Empty-body OAuth is removed.
- JWT cache is **per normalized domain** (not one global JWT for all servers).
- Ports in `target` are stripped for the token/cache domain key but kept on the MCP HTTP URL.

### Added

- `extract_and_normalize_domain(target)` and `resolve_mcp_http_url(target)` public helpers.
- Domain-scoped 401 invalidate + single retry (other domains' caches stay warm).

### Migration

```python
# 0.5.x
await agent.call_tool("https://host/mcp", "echo", {"text": "hi"})
await agent.get_mcp_access_token()

# 1.0.0
await agent.call_tool(target="https://host/mcp", name="echo", arguments={"text": "hi"})
# positional still works:
await agent.call_tool("https://host/mcp", "echo", {"text": "hi"})
await agent.get_mcp_access_token("https://host/mcp")
# or bare host:
await agent.call_tool("host.example", "echo", {"text": "hi"})
```
