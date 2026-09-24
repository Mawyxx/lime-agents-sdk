from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from mcp.types import Implementation, InitializeResult, ServerCapabilities

from lime_agents._mcp._transport import McpTransportHandle, _guard_response_url
from lime_agents._oauth import _McpTokenIssuer


def test_transport_session_before_open() -> None:
    issuer = MagicMock(spec=_McpTokenIssuer)
    handle = McpTransportHandle("https://mcp.example.com", "example.com", issuer)
    with pytest.raises(RuntimeError, match="not open"):
        _ = handle.session


@pytest.mark.asyncio
async def test_transport_reuses_open_session() -> None:
    issuer = MagicMock(spec=_McpTokenIssuer)
    issuer.generation_for = MagicMock(return_value=1)
    token = MagicMock()
    token.access_token = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJhZ2VudF8xIn0.sig"
    issuer.get_access_token = AsyncMock(return_value=token)
    issuer.invalidate_and_refresh = AsyncMock(return_value=token)
    issuer.invalidate_all = AsyncMock()

    session = AsyncMock()
    init_result = InitializeResult(
        protocolVersion="2024-11-05",
        capabilities=ServerCapabilities(tools={}),
        serverInfo=Implementation(name="test-server", version="1.0.0"),
    )
    session.initialize = AsyncMock(return_value=init_result)

    @asynccontextmanager
    async def fake_streamable_http_client(
        url: str,
        *,
        http_client: Any = None,
        terminate_on_close: bool = True,
    ):
        yield MagicMock(), MagicMock(), lambda: "sid"

    @asynccontextmanager
    async def fake_client_session(read_stream: Any, write_stream: Any):
        yield session

    with (
        patch("lime_agents._mcp._transport.streamable_http_client", fake_streamable_http_client),
        patch("lime_agents._mcp._transport.ClientSession", fake_client_session),
    ):
        handle = McpTransportHandle("https://mcp.example.com", "example.com", issuer)
        first = await handle.ensure_open()
        second = await handle.ensure_open()
        assert first is second
        assert handle.session is first
        assert handle.server_capabilities == init_result.capabilities
        await handle.close()


@pytest.mark.asyncio
async def test_transport_close_swallows_stack_errors() -> None:
    issuer = MagicMock(spec=_McpTokenIssuer)
    handle = McpTransportHandle("https://mcp.example.com", "example.com", issuer)
    handle._stack.aclose = AsyncMock(side_effect=RuntimeError("stack boom"))  # noqa: SLF001
    await handle.close()


def test_transport_server_capabilities_none_before_open() -> None:
    issuer = MagicMock(spec=_McpTokenIssuer)
    handle = McpTransportHandle("https://mcp.example.com", "example.com", issuer)
    assert handle.server_capabilities is None


@pytest.mark.asyncio
async def test_transport_rejects_reserved_host_before_network() -> None:
    issuer = MagicMock(spec=_McpTokenIssuer)
    token = MagicMock()
    token.access_token = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJhZ2VudF8xIn0.sig"
    issuer.get_access_token = AsyncMock(return_value=token)
    issuer.generation_for = MagicMock(return_value=1)

    handle = McpTransportHandle(
        "https://metadata.google.internal/mcp",
        "metadata.google.internal",
        issuer,
    )
    with pytest.raises(ValueError, match="reserved"):
        await handle.ensure_open()


@pytest.mark.asyncio
async def test_guard_response_url_rejects_reserved_final_url() -> None:
    response = httpx.Response(
        200,
        request=httpx.Request("GET", "https://127.0.0.1.nip.io/steal"),
    )
    with pytest.raises(ValueError, match="reserved"):
        await _guard_response_url(response)


@pytest.mark.asyncio
async def test_guard_response_url_allows_public_final_url() -> None:
    response = httpx.Response(
        200,
        request=httpx.Request("GET", "https://mcp.lime.pics/mcp"),
    )
    await _guard_response_url(response)


@pytest.mark.asyncio
async def test_transport_does_not_follow_redirects() -> None:
    issuer = MagicMock(spec=_McpTokenIssuer)
    token = MagicMock()
    token.access_token = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJhZ2VudF8xIn0.sig"
    issuer.get_access_token = AsyncMock(return_value=token)
    issuer.generation_for = MagicMock(return_value=1)

    session = AsyncMock()
    init_result = InitializeResult(
        protocolVersion="2024-11-05",
        capabilities=ServerCapabilities(),
        serverInfo=Implementation(name="test-server", version="1.0.0"),
    )
    session.initialize = AsyncMock(return_value=init_result)

    requested: list[str] = []
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(
            302,
            headers={"Location": "https://metadata.google.internal/steal"},
        )

    real_async_client = httpx.AsyncClient

    def client_factory(**kwargs: Any) -> httpx.AsyncClient:
        captured["follow_redirects"] = kwargs.get("follow_redirects")
        captured["event_hooks"] = kwargs.get("event_hooks")
        return real_async_client(transport=httpx.MockTransport(handler), **kwargs)

    @asynccontextmanager
    async def fake_streamable_http_client(
        url: str,
        *,
        http_client: Any = None,
        terminate_on_close: bool = True,
    ):
        captured["response"] = await http_client.get(url)
        yield MagicMock(), MagicMock(), lambda: "sid"

    @asynccontextmanager
    async def fake_client_session(read_stream: Any, write_stream: Any):
        yield session

    with (
        patch("lime_agents._mcp._transport.httpx.AsyncClient", new=client_factory),
        patch("lime_agents._mcp._transport.streamable_http_client", fake_streamable_http_client),
        patch("lime_agents._mcp._transport.ClientSession", fake_client_session),
    ):
        handle = McpTransportHandle(
            "https://mcp.example.com/mcp",
            "mcp.example.com",
            issuer,
        )
        await handle.ensure_open()

    assert captured["follow_redirects"] is False
    assert captured["event_hooks"]["response"] == [_guard_response_url]
    assert captured["response"].status_code == 302
    assert requested == ["https://mcp.example.com/mcp"]
