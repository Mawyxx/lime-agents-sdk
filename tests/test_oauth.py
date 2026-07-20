from __future__ import annotations

import asyncio
import json
import time

import httpx
import pytest

from lime_agents._client import LimeClient
from lime_agents._errors import (
    ApiError,
    AuthenticationError,
    LimeError,
    OAuthCapabilityError,
    RateLimitError,
)
from lime_agents._oauth import _McpTokenIssuer
from lime_agents._types import McpAccessToken


def _token_response() -> httpx.Response:
    return httpx.Response(
        200,
        content=json.dumps(
            {
                "access_token": "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJhZ2VudF8xIn0.sig",
                "token_type": "Bearer",
                "expires_in": 3600,
            },
        ).encode(),
        headers={"cache-control": "no-store"},
    )


def _client_with_response(response: httpx.Response) -> LimeClient:
    handler = lambda _: response  # noqa: E731
    return LimeClient(
        agent_token="at_test",
        base_url="http://test/api/v1",
        timeout=5.0,
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


@pytest.mark.asyncio
async def test_oauth_success() -> None:
    client = _client_with_response(_token_response())
    issuer = _McpTokenIssuer(client, refresh_skew=30.0)
    token = await issuer.get_access_token("example.com")
    assert token.token_type == "Bearer"
    assert token.access_token.count(".") == 2
    assert token.expires_in == 3600
    await client.aclose()


@pytest.mark.asyncio
async def test_oauth_cache_hit() -> None:
    calls = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return _token_response()

    client = LimeClient(
        agent_token="at_test",
        base_url="http://test/api/v1",
        timeout=5.0,
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    issuer = _McpTokenIssuer(client, refresh_skew=30.0)
    first = await issuer.get_access_token("example.com")
    second = await issuer.get_access_token("example.com")
    assert first.access_token == second.access_token
    assert calls["n"] == 1
    await client.aclose()


@pytest.mark.asyncio
async def test_oauth_force_refresh() -> None:
    calls = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return _token_response()

    client = LimeClient(
        agent_token="at_test",
        base_url="http://test/api/v1",
        timeout=5.0,
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    issuer = _McpTokenIssuer(client, refresh_skew=30.0)
    await issuer.get_access_token("example.com")
    await issuer.get_access_token("example.com", force_refresh=True)
    assert calls["n"] == 2
    await client.aclose()


@pytest.mark.asyncio
async def test_oauth_refresh_when_expired() -> None:
    calls = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return _token_response()

    client = LimeClient(
        agent_token="at_test",
        base_url="http://test/api/v1",
        timeout=5.0,
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    issuer = _McpTokenIssuer(client, refresh_skew=30.0)
    issuer._cached["example.com"] = McpAccessToken(  # noqa: SLF001
        access_token="eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJhZ2VudF8xIn0.sig",
        token_type="Bearer",
        expires_in=60,
        issued_at=time.monotonic() - 40,
    )
    await issuer.get_access_token("example.com")
    assert calls["n"] == 1
    await client.aclose()


@pytest.mark.asyncio
async def test_oauth_invalid_client() -> None:
    response = httpx.Response(
        401,
        content=json.dumps(
            {"error": "invalid_client", "error_description": "bad token"},
        ).encode(),
    )
    client = _client_with_response(response)
    issuer = _McpTokenIssuer(client)
    with pytest.raises(AuthenticationError) as exc:
        await issuer.get_access_token("example.com")
    assert exc.value.code == "invalid_client"
    await client.aclose()


@pytest.mark.asyncio
async def test_oauth_invalid_request() -> None:
    response = httpx.Response(
        400,
        content=json.dumps(
            {"error": "invalid_request", "error_description": "body not allowed"},
        ).encode(),
    )
    client = _client_with_response(response)
    issuer = _McpTokenIssuer(client)
    with pytest.raises(ApiError) as exc:
        await issuer.get_access_token("example.com")
    assert exc.value.code == "invalid_request"
    await client.aclose()


@pytest.mark.asyncio
async def test_oauth_capability_denied() -> None:
    response = httpx.Response(
        403,
        content=json.dumps(
            {
                "ok": False,
                "error": {
                    "code": "OAUTH_CAPABILITY_DENIED",
                    "message": "missing oauth:issue",
                },
            },
        ).encode(),
    )
    client = _client_with_response(response)
    issuer = _McpTokenIssuer(client)
    with pytest.raises(OAuthCapabilityError) as exc:
        await issuer.get_access_token("example.com")
    assert exc.value.code == "OAUTH_CAPABILITY_DENIED"
    await client.aclose()


@pytest.mark.asyncio
async def test_oauth_rate_limit_envelope() -> None:
    response = httpx.Response(
        429,
        content=json.dumps(
            {
                "ok": False,
                "error": {"code": "RATE_LIMIT_EXCEEDED", "message": "slow down"},
            },
        ).encode(),
    )
    client = _client_with_response(response)
    issuer = _McpTokenIssuer(client)
    with pytest.raises(RateLimitError):
        await issuer.get_access_token("example.com")
    await client.aclose()


@pytest.mark.asyncio
async def test_oauth_invalid_token_shape() -> None:
    response = httpx.Response(
        200,
        content=json.dumps({"access_token": "x", "token_type": "Bearer"}).encode(),
        headers={"cache-control": "no-store"},
    )
    client = _client_with_response(response)
    issuer = _McpTokenIssuer(client)
    with pytest.raises(ApiError, match="access_token, token_type, expires_in"):
        await issuer.get_access_token("example.com")
    await client.aclose()


@pytest.mark.asyncio
async def test_oauth_wrong_token_type() -> None:
    response = httpx.Response(
        200,
        content=json.dumps(
            {
                "access_token": "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJhIn0.s",
                "token_type": "Basic",
                "expires_in": 1,
            },
        ).encode(),
        headers={"cache-control": "no-store"},
    )
    client = _client_with_response(response)
    issuer = _McpTokenIssuer(client)
    with pytest.raises(ApiError, match="Bearer"):
        await issuer.get_access_token("example.com")
    await client.aclose()


@pytest.mark.asyncio
async def test_oauth_missing_cache_control() -> None:
    response = httpx.Response(
        200,
        content=json.dumps(
            {
                "access_token": "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJhZ2VudF8xIn0.sig",
                "token_type": "Bearer",
                "expires_in": 3600,
            },
        ).encode(),
    )
    client = _client_with_response(response)
    issuer = _McpTokenIssuer(client)
    with pytest.raises(ApiError, match="Cache-Control"):
        await issuer.get_access_token("example.com")
    await client.aclose()


@pytest.mark.asyncio
async def test_oauth_non_jwt_access_token() -> None:
    response = httpx.Response(
        200,
        content=json.dumps(
            {"access_token": "opaque", "token_type": "Bearer", "expires_in": 3600},
        ).encode(),
        headers={"cache-control": "no-store"},
    )
    client = _client_with_response(response)
    issuer = _McpTokenIssuer(client)
    with pytest.raises(ApiError, match="JWT"):
        await issuer.get_access_token("example.com")
    await client.aclose()


@pytest.mark.asyncio
async def test_oauth_invalid_json() -> None:
    response = httpx.Response(200, content=b"not-json")
    client = _client_with_response(response)
    issuer = _McpTokenIssuer(client)
    with pytest.raises(LimeError, match="Invalid JSON"):
        await issuer.get_access_token("example.com")
    await client.aclose()


@pytest.mark.asyncio
async def test_oauth_unexpected_success_envelope() -> None:
    response = httpx.Response(
        403,
        content=json.dumps({"ok": True, "data": {}}).encode(),
    )
    client = _client_with_response(response)
    issuer = _McpTokenIssuer(client)
    with pytest.raises(LimeError, match="Unexpected success"):
        await issuer.get_access_token("example.com")
    await client.aclose()


@pytest.mark.asyncio
async def test_oauth_envelope_missing_error() -> None:
    response = httpx.Response(503, content=json.dumps({"ok": False}).encode())
    client = _client_with_response(response)
    issuer = _McpTokenIssuer(client)
    with pytest.raises(LimeError, match="missing error object"):
        await issuer.get_access_token("example.com")
    await client.aclose()


@pytest.mark.asyncio
async def test_oauth_rfc6749_rate_limit() -> None:
    response = httpx.Response(
        429,
        content=json.dumps({"error": "slow_down", "error_description": "wait"}).encode(),
    )
    client = _client_with_response(response)
    issuer = _McpTokenIssuer(client)
    with pytest.raises(RateLimitError):
        await issuer.get_access_token("example.com")
    await client.aclose()


@pytest.mark.asyncio
async def test_oauth_envelope_401() -> None:
    response = httpx.Response(
        401,
        content=json.dumps(
            {
                "ok": False,
                "error": {"code": "INVALID_AGENT_TOKEN", "message": "bad"},
            },
        ).encode(),
    )
    client = _client_with_response(response)
    issuer = _McpTokenIssuer(client)
    with pytest.raises(AuthenticationError):
        await issuer.get_access_token("example.com")
    await client.aclose()


@pytest.mark.asyncio
async def test_oauth_envelope_generic_api_error() -> None:
    response = httpx.Response(
        503,
        content=json.dumps(
            {
                "ok": False,
                "error": {"code": "OAUTH_TOKEN_ISSUANCE_FAILED", "message": "down"},
            },
        ).encode(),
    )
    client = _client_with_response(response)
    issuer = _McpTokenIssuer(client)
    with pytest.raises(ApiError) as exc:
        await issuer.get_access_token("example.com")
    assert exc.value.code == "OAUTH_TOKEN_ISSUANCE_FAILED"
    await client.aclose()


@pytest.mark.asyncio
async def test_oauth_non_dict_body() -> None:
    response = httpx.Response(200, content=b'"string"')
    client = _client_with_response(response)
    issuer = _McpTokenIssuer(client)
    with pytest.raises(LimeError, match="Unexpected token response"):
        await issuer.get_access_token("example.com")
    await client.aclose()


@pytest.mark.asyncio
async def test_oauth_error_invalid_json_on_failure() -> None:
    response = httpx.Response(401, content=b"not-json")
    client = _client_with_response(response)
    issuer = _McpTokenIssuer(client)
    with pytest.raises(LimeError, match="Invalid JSON"):
        await issuer.get_access_token("example.com")
    await client.aclose()


@pytest.mark.asyncio
async def test_oauth_error_non_dict_on_failure() -> None:
    response = httpx.Response(401, content=b'"string"')
    client = _client_with_response(response)
    issuer = _McpTokenIssuer(client)
    with pytest.raises(LimeError, match="Unexpected response shape"):
        await issuer.get_access_token("example.com")
    await client.aclose()


@pytest.mark.asyncio
async def test_oauth_rfc6749_generic_api_error() -> None:
    response = httpx.Response(
        503,
        content=json.dumps({"error": "server_error", "error_description": "down"}).encode(),
    )
    client = _client_with_response(response)
    issuer = _McpTokenIssuer(client)
    with pytest.raises(ApiError) as exc:
        await issuer.get_access_token("example.com")
    assert exc.value.code == "server_error"
    await client.aclose()


@pytest.mark.asyncio
async def test_oauth_concurrent_refresh_single_flight() -> None:
    calls = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return _token_response()

    client = LimeClient(
        agent_token="at_test",
        base_url="http://test/api/v1",
        timeout=5.0,
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    issuer = _McpTokenIssuer(client, refresh_skew=30.0)
    await asyncio.gather(*[issuer.get_access_token("example.com") for _ in range(20)])
    assert calls["n"] == 1
    await client.aclose()


@pytest.mark.asyncio
async def test_oauth_double_check_cache_after_lock() -> None:
    calls = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return _token_response()

    client = LimeClient(
        agent_token="at_test",
        base_url="http://test/api/v1",
        timeout=5.0,
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    issuer = _McpTokenIssuer(client, refresh_skew=30.0)
    issuer._cached.pop("example.com", None)  # noqa: SLF001

    async def slow_issue(domain: str) -> McpAccessToken:
        assert domain == "example.com"
        calls["n"] += 1
        await asyncio.sleep(0.05)
        return McpAccessToken(
            access_token="eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJhZ2VudF8xIn0.sig",
            token_type="Bearer",
            expires_in=3600,
            issued_at=time.monotonic(),
        )

    issuer._issue_token = slow_issue  # type: ignore[method-assign]

    async def waiter() -> McpAccessToken:
        await asyncio.sleep(0.01)
        return await issuer.get_access_token("example.com")

    await asyncio.gather(issuer.get_access_token("example.com"), waiter())
    assert calls["n"] == 1
    await client.aclose()


@pytest.mark.asyncio
async def test_invalidate_and_refresh_increments_generation() -> None:
    client = _client_with_response(_token_response())
    issuer = _McpTokenIssuer(client)
    await issuer.get_access_token("example.com")
    before = issuer.generation_for("example.com")
    await issuer.invalidate_and_refresh("example.com")
    assert issuer.generation_for("example.com") == before + 1
    await client.aclose()


@pytest.mark.asyncio
async def test_oauth_token_json_domain_wire() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["content_type"] = request.headers.get("Content-Type")
        seen["body"] = json.loads(request.content.decode())
        return _token_response()

    client = LimeClient(
        agent_token="at_test",
        base_url="http://test/api/v1",
        timeout=5.0,
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    issuer = _McpTokenIssuer(client)
    await issuer.get_access_token("autonomad.ai")
    assert seen["content_type"] == "application/json"
    assert seen["body"] == {"domain": "autonomad.ai"}
    assert "domain=" not in str(seen["url"])
    await client.aclose()


@pytest.mark.asyncio
async def test_oauth_per_domain_cache() -> None:
    bodies: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content.decode()))
        return _token_response()

    client = LimeClient(
        agent_token="at_test",
        base_url="http://test/api/v1",
        timeout=5.0,
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    issuer = _McpTokenIssuer(client, refresh_skew=30.0)
    await issuer.get_access_token("a.example")
    await issuer.get_access_token("a.example")
    await issuer.get_access_token("b.example")
    assert bodies == [{"domain": "a.example"}, {"domain": "b.example"}]
    await client.aclose()


@pytest.mark.asyncio
async def test_oauth_invalidate_only_one_domain() -> None:
    calls = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return _token_response()

    client = LimeClient(
        agent_token="at_test",
        base_url="http://test/api/v1",
        timeout=5.0,
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    issuer = _McpTokenIssuer(client, refresh_skew=30.0)
    await issuer.get_access_token("a.example")
    await issuer.get_access_token("b.example")
    assert calls["n"] == 2
    issuer.invalidate("a.example")
    await issuer.get_access_token("a.example")
    await issuer.get_access_token("b.example")
    assert calls["n"] == 3
    await client.aclose()


@pytest.mark.asyncio
async def test_oauth_concurrent_same_domain_single_flight() -> None:
    calls = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return _token_response()

    client = LimeClient(
        agent_token="at_test",
        base_url="http://test/api/v1",
        timeout=5.0,
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    issuer = _McpTokenIssuer(client, refresh_skew=30.0)
    await asyncio.gather(*[issuer.get_access_token("same.example") for _ in range(20)])
    assert calls["n"] == 1
    await client.aclose()
