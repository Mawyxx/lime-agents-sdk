from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.types import Implementation, InitializeResult, ServerCapabilities

from lime_agents._mcp._transport import McpTransportHandle
from lime_agents._oauth import _McpTokenIssuer


def test_transport_session_before_open() -> None:
    issuer = MagicMock(spec=_McpTokenIssuer)
    handle = McpTransportHandle("https://mcp.example.com", issuer)
    with pytest.raises(RuntimeError, match="not open"):
        _ = handle.session


@pytest.mark.asyncio
async def test_transport_reuses_open_session() -> None:
    issuer = MagicMock(spec=_McpTokenIssuer)
    issuer.generation = 1
    token = MagicMock()
    token.access_token = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJhZ2VudF8xIn0.sig"
    issuer.get_access_token = AsyncMock(return_value=token)

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
        handle = McpTransportHandle("https://mcp.example.com", issuer)
        first = await handle.ensure_open()
        second = await handle.ensure_open()
        assert first is second
        assert handle.session is first
        assert handle.server_capabilities == init_result.capabilities
        await handle.close()


@pytest.mark.asyncio
async def test_transport_close_swallows_stack_errors() -> None:
    issuer = MagicMock(spec=_McpTokenIssuer)
    handle = McpTransportHandle("https://mcp.example.com", issuer)
    handle._stack.aclose = AsyncMock(side_effect=RuntimeError("stack boom"))  # noqa: SLF001
    await handle.close()


def test_transport_server_capabilities_none_before_open() -> None:
    issuer = MagicMock(spec=_McpTokenIssuer)
    handle = McpTransportHandle("https://mcp.example.com", issuer)
    assert handle.server_capabilities is None
