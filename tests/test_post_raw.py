from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from lime_agents._client import LimeClient
from lime_agents._errors import LimeError


def _token_ok() -> bytes:
    return json.dumps(
        {
            "access_token": "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJhZ2VudF8xIn0.sig",
            "token_type": "Bearer",
            "expires_in": 3600,
        },
    ).encode()


@pytest.mark.asyncio
async def test_post_raw_json_domain_success() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["token"] = request.headers.get("X-Agent-Token")
        seen["content_type"] = request.headers.get("Content-Type")
        seen["body"] = json.loads(request.content.decode())
        seen["url"] = str(request.url)
        return httpx.Response(
            200,
            content=_token_ok(),
            headers={"cache-control": "no-store"},
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = LimeClient(
        agent_token="at_test_token",
        base_url="http://test/api/v1",
        timeout=5.0,
        max_retries=0,
        http_client=http_client,
    )
    response = await client.post_raw("/modules/oauth/token", {"domain": "autonomad.ai"})
    assert response.status_code == 200
    assert seen["method"] == "POST"
    assert seen["token"] == "at_test_token"
    assert seen["content_type"] == "application/json"
    assert seen["body"] == {"domain": "autonomad.ai"}
    assert "domain=" not in seen["url"]
    await client.aclose()


@pytest.mark.asyncio
async def test_post_raw_retries_on_503() -> None:
    calls = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, content=b'{"error":"unavailable"}')
        return httpx.Response(200, content=_token_ok(), headers={"cache-control": "no-store"})

    client = LimeClient(
        agent_token="at_test",
        base_url="http://test/api/v1",
        timeout=5.0,
        max_retries=2,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    response = await client.post_raw("/modules/oauth/token", {"domain": "example.com"})
    assert response.status_code == 200
    assert calls["n"] == 2
    await client.aclose()


@pytest.mark.asyncio
async def test_post_raw_no_retry_on_400() -> None:
    calls = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(
            400,
            content=json.dumps({"error": "invalid_request"}).encode(),
        )

    client = LimeClient(
        agent_token="at_test",
        base_url="http://test/api/v1",
        timeout=5.0,
        max_retries=2,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    response = await client.post_raw("/modules/oauth/token", {"domain": "example.com"})
    assert response.status_code == 400
    assert calls["n"] == 1
    await client.aclose()


@pytest.mark.asyncio
async def test_post_raw_transport_error_retries() -> None:
    calls = {"n": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectError("refused")

    client = LimeClient(
        agent_token="at_test",
        base_url="http://test/api/v1",
        timeout=5.0,
        max_retries=1,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(LimeError, match="refused"):
        await client.post_raw("/modules/oauth/token", {"domain": "example.com"})
    assert calls["n"] == 2
    await client.aclose()
