from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from lime_agents._client import LimeClient
from lime_agents._errors import ApiError, AuthenticationError, LimeError, RateLimitError


def _envelope_ok(data: dict[str, Any]) -> bytes:
    return json.dumps({"ok": True, "data": data}).encode()


def _envelope_err(
    code: str,
    message: str,
    *,
    detail: dict[str, Any] | None = None,
) -> bytes:
    error: dict[str, Any] = {"code": code, "message": message}
    if detail is not None:
        error["detail"] = detail
    return json.dumps({"ok": False, "error": error}).encode()


@pytest.fixture
def client_factory():
    def _make(handler: httpx.MockTransport) -> LimeClient:
        http_client = httpx.AsyncClient(transport=handler, base_url="http://test")
        return LimeClient(
            agent_token="at_test_token",
            base_url="http://test/api/v1",
            timeout=5.0,
            max_retries=2,
            http_client=http_client,
        )

    return _make


@pytest.mark.asyncio
async def test_get_public_success(client_factory) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "X-Agent-Token" not in request.headers
        return httpx.Response(200, content=_envelope_ok({"field": "value"}))

    client = client_factory(httpx.MockTransport(handler))
    data = await client.get_public("/auth/requests/lr_1")
    assert data == {"field": "value"}
    await client.aclose()


@pytest.mark.asyncio
async def test_post_sends_agent_token(client_factory) -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["token"] = request.headers.get("X-Agent-Token")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, content=_envelope_ok({"status": "DELIVERED"}))

    client = client_factory(httpx.MockTransport(handler))
    await client.post("/modules/agent-login/requests/lr_1/approve", {"pow_nonce": "42"})
    assert seen["token"] == "at_test_token"
    assert seen["body"] == {"pow_nonce": "42"}
    await client.aclose()


@pytest.mark.asyncio
async def test_api_error_mapping(client_factory) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            content=_envelope_err("INVALID_POW", "bad nonce"),
        )

    client = client_factory(httpx.MockTransport(handler))
    with pytest.raises(ApiError) as exc:
        await client.post("/approve", {"pow_nonce": "x"})
    assert exc.value.code == "INVALID_POW"
    assert exc.value.http_status == 400
    await client.aclose()


@pytest.mark.asyncio
async def test_rate_limit_error(client_factory) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            content=_envelope_err("RATE_LIMIT_EXCEEDED", "slow down"),
        )

    client = client_factory(httpx.MockTransport(handler))
    with pytest.raises(RateLimitError):
        await client.get("/core/agents/me/profile")
    await client.aclose()


@pytest.mark.asyncio
async def test_authentication_error(client_factory) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            content=_envelope_err("INVALID_AGENT_TOKEN", "bad token"),
        )

    client = client_factory(httpx.MockTransport(handler))
    with pytest.raises(AuthenticationError):
        await client.get("/core/agents/me/profile")
    await client.aclose()


@pytest.mark.asyncio
async def test_retry_on_503_then_success(client_factory) -> None:
    calls = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, content=_envelope_err("UNAVAILABLE", "try again"))
        return httpx.Response(200, content=_envelope_ok({"ok_field": 1}))

    client = client_factory(httpx.MockTransport(handler))
    data = await client.get("/core/agents/me/profile")
    assert data == {"ok_field": 1}
    assert calls["n"] == 2
    await client.aclose()


@pytest.mark.asyncio
async def test_no_retry_on_400(client_factory) -> None:
    calls = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(400, content=_envelope_err("INVALID_POW", "bad"))

    client = client_factory(httpx.MockTransport(handler))
    with pytest.raises(ApiError):
        await client.post("/approve", {"pow_nonce": "1"})
    assert calls["n"] == 1
    await client.aclose()


@pytest.mark.asyncio
async def test_invalid_json_raises(client_factory) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json")

    client = client_factory(httpx.MockTransport(handler))
    with pytest.raises(LimeError, match="Invalid JSON"):
        await client.get_public("/auth/requests/x")
    await client.aclose()


@pytest.mark.asyncio
async def test_unexpected_payload_shape(client_factory) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b'"string"')

    client = client_factory(httpx.MockTransport(handler))
    with pytest.raises(LimeError, match="Unexpected response shape"):
        await client.get_public("/auth/requests/x")
    await client.aclose()


@pytest.mark.asyncio
async def test_success_missing_data(client_factory) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=json.dumps({"ok": True, "data": "bad"}).encode())

    client = client_factory(httpx.MockTransport(handler))
    with pytest.raises(LimeError, match="missing data"):
        await client.get_public("/auth/requests/x")
    await client.aclose()


@pytest.mark.asyncio
async def test_error_missing_error_object(client_factory) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=json.dumps({"ok": False}).encode())

    client = client_factory(httpx.MockTransport(handler))
    with pytest.raises(LimeError, match="missing error object"):
        await client.get_public("/auth/requests/x")
    await client.aclose()


@pytest.mark.asyncio
async def test_transport_error_retries_then_raises(client_factory) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = client_factory(httpx.MockTransport(handler))
    with pytest.raises(LimeError, match="connection refused"):
        await client.get_public("/auth/requests/x")
    await client.aclose()


@pytest.mark.asyncio
async def test_owned_client_closed_on_aclose() -> None:
    client = LimeClient(
        agent_token="at_test",
        base_url="http://test/api/v1",
        timeout=5.0,
        max_retries=0,
    )
    await client.aclose()
