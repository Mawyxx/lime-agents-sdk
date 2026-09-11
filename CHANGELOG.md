# Changelog

## 2.0.0 — Retire owner KYC field

### Breaking

- Removed `AgentProfile.owner_kyc_level` and wire alias parsing for `user_kyc_level`.
  Platform profiles/passports no longer expose KYC (`passport_version=4`).

### Added

- HTTP client retries once on HTTP 429 (same policy as 503).

## Docs / DX (folded from former Unreleased)

- README leads with Agent → MCP task + short code sample; site login is secondary.
- PyPI description emphasizes zero OAuth boilerplate.
- Examples: minimal-agent, mcp-client, site-login.
- Quick Start / RTD index: MCP-first mental model.

## 1.0.0 — Zero-Touch MCP Auth

Breaking SemVer major. No backward compatibility with 0.5.x empty-body tokens.

### Breaking

- All MCP facade methods require `target: str` (URL or hostname). Renamed from `server_url`.
- `get_mcp_access_token(target, *, force_refresh=False)` requires `target`.
- Token wire is `POST /modules/oauth/token` with JSON `{"domain": "<normalized>"}` (ADR 0081 Amendment v11).
- JWT cache is **per normalized domain**.
- Ports in `target` are stripped for the token/cache domain key but kept on the MCP HTTP URL.

### Added

- `extract_and_normalize_domain(target)` and `resolve_mcp_http_url(target)` public helpers.
- Domain-scoped 401 invalidate + single retry.

### Migration

```python
# 0.5.x
await agent.get_mcp_access_token()

# 1.0.0 / 2.0.0
await agent.get_mcp_access_token("https://host/mcp")
```
