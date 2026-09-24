# Changelog

## 3.0.2

### Security

- MCP target hosts now reject reserved/special-use names (localhost, `*.local`,
  `*.internal`, `*.intranet`, `*.corp`, `*.home`, `*.lan`, cloud metadata,
  `kubernetes*`) and IP-encoding wildcard DNS services (`nip.io`, `sslip.io`,
  `xip.io`, `traefik.me`, `localtest.me`, `lvh.me`) — parity with Core
  `mcp_domain.py` — plus strict IP-literal obfuscation rejection (`127.1`,
  `2130706433`, `0x7f000001`, `0177.0.0.1`). Validation is syntactic and
  deterministic (no DNS resolution), documented in `lime_agents._domain`.
- MCP streamable-HTTP transport no longer follows redirects
  (`follow_redirects=False`) and re-validates every response URL against the
  same host policy through a response hook, so a redirect toward a
  reserved/special-use host fails closed instead of leaking the bearer token.

### Fixed

- `McpSessionPool.aclose()` re-raises `asyncio.CancelledError` — direct or
  wrapped in an exception group — instead of classifying it as shutdown noise;
  cancellation always propagates.

## 3.0.1

### Fixed

- PoW (audit R-14): `login()` now solves the server-verified domain-separated digest
  `SHA-256(b"lime:pow:v1\0" || challenge || 0x00 || nonce)` instead of the legacy
  `SHA-256(challenge + nonce)` concatenation. Servers running the R-14 verifier reject
  the legacy digest, so **>= 3.0.1 is required** for site-login approve.
- Typed agent-auth errors: HTTP **403** `AGENT_INACTIVE` -> `AgentInactiveError`,
  403 `AGENT_USER_SUSPENDED` -> `AgentUserSuspendedError`, **503** `AUTH_UNAVAILABLE` ->
  `AuthUnavailableError` (`AuthenticationError` / `ApiError` subclasses respectively).
- RFC 6749 `{"error": "access_denied"}` (HTTP 403) on `POST /modules/oauth/token`
  now maps to `OAuthCapabilityError`.
- MCP transport teardown errors are now logged through the SDK logger instead of
  being swallowed, and the no-op `try/finally` in `McpSessionPool.session()` is gone.

### Changed

- HTTP retries are idempotency-aware: `GET` keeps retrying 408/429/500/502/503/504,
  while `POST` retries only 408/429/503 — a POST is never blind-replayed on 500/502/504
  without an `Idempotency-Key`.
- Envelope error mapping is a single owner (`lime_agents._errors.map_envelope_error`)
  shared by the platform client and the OAuth token issuer.

### Docs / DX

- README site-login example uses the UUID wire format; documents the R-14 PoW
  requirement and the known `login()` 404-after-approve recovery limitation (ADR 0058).

## 3.0.0 — Retire agent reputation field

### Breaking

- Removed `AgentProfile.agent_reputation`. Platform profiles/passports no longer
  expose reputation (`passport_version=5`; claim ABSENT; storage dropped).

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
