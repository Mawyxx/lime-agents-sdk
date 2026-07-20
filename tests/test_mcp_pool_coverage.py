from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.types import ServerCapabilities

from lime_agents._mcp._pool import McpSessionPool
from lime_agents._oauth import _McpTokenIssuer


def _duck_exception_group(message: str, exceptions: list[BaseException]) -> BaseException:
    group_type = type("ExceptionGroup", (Exception,), {})
    group = group_type(message)
    group.exceptions = exceptions  # type: ignore[attr-defined]
    return group


def _make_issuer() -> _McpTokenIssuer:
    issuer = MagicMock(spec=_McpTokenIssuer)
    gens: dict[str, int] = {}

    def generation_for(domain: str) -> int:
        return gens.get(domain, 1)

    async def get_access_token(domain: str, *, force_refresh: bool = False):
        gens[domain] = gens.get(domain, 1)
        if force_refresh:
            gens[domain] += 1
        token = MagicMock()
        token.access_token = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJhZ2VudF8xIn0.sig"
        return token

    async def invalidate_and_refresh(domain: str):
        gens[domain] = gens.get(domain, 1) + 1
        token = MagicMock()
        token.access_token = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJhZ2VudF8xIn0.sig"
        return token

    issuer.generation_for = generation_for
    issuer.get_access_token = AsyncMock(side_effect=get_access_token)
    issuer.invalidate_and_refresh = AsyncMock(side_effect=invalidate_and_refresh)
    issuer.invalidate_all = AsyncMock()
    return issuer


@pytest.mark.asyncio
async def test_pool_get_server_capabilities_when_closed() -> None:
    pool = McpSessionPool(_make_issuer())
    await pool.aclose()
    with pytest.raises(RuntimeError, match="closed"):
        await pool.get_server_capabilities("https://mcp.example.com")


@pytest.mark.asyncio
async def test_pool_session_context_when_closed() -> None:
    pool = McpSessionPool(_make_issuer())
    await pool.aclose()
    with pytest.raises(RuntimeError, match="closed"):
        async with pool.session("https://mcp.example.com"):
            pass


@pytest.mark.asyncio
async def test_pool_get_server_capabilities_empty_fallback() -> None:
    session = AsyncMock()
    fake_http, fake_session = _mock_transport_stack(session)

    @asynccontextmanager
    async def fake_client_session(read_stream: Any, write_stream: Any):
        session.initialize = AsyncMock(return_value=_init_result(ServerCapabilities()))
        yield session

    with (
        patch("lime_agents._mcp._transport.streamable_http_client", fake_http),
        patch("lime_agents._mcp._transport.ClientSession", fake_client_session),
    ):
        pool = McpSessionPool(_make_issuer())
        entry = await pool._get_entry("https://mcp.example.com", "mcp.example.com")  # noqa: SLF001
        async with entry.connect_lock:
            await entry.transport.ensure_open()
        entry.transport._server_capabilities = None  # noqa: SLF001
        result = await pool.get_server_capabilities("https://mcp.example.com")
        assert isinstance(result, ServerCapabilities)
        await pool.aclose()


@pytest.mark.asyncio
async def test_pool_broken_session_reconnect() -> None:
    from anyio import BrokenResourceError

    session = AsyncMock()
    session.list_tools = AsyncMock(
        side_effect=[BrokenResourceError(), MagicMock(tools=[])],
    )
    fake_http, fake_session = _mock_transport_stack(session)

    with (
        patch("lime_agents._mcp._transport.streamable_http_client", fake_http),
        patch("lime_agents._mcp._transport.ClientSession", fake_session),
    ):
        pool = McpSessionPool(_make_issuer())
        result = await pool.run("https://mcp.example.com", lambda s: s.list_tools())
        assert result.tools == []
        await pool.aclose()


@pytest.mark.asyncio
async def test_pool_aclose_swallows_shutdown_noise() -> None:
    pool = McpSessionPool(_make_issuer())
    entry = await pool._get_entry("https://mcp.example.com", "mcp.example.com")  # noqa: SLF001

    async def noisy_close() -> None:
        raise RuntimeError("cancel scope mismatch during shutdown")

    entry.transport.close = noisy_close  # type: ignore[method-assign]
    pool._entries["https://mcp.example.com"] = entry  # noqa: SLF001
    await pool.aclose()


@pytest.mark.asyncio
async def test_pool_aclose_logs_unexpected_close_error(caplog: pytest.LogCaptureFixture) -> None:
    pool = McpSessionPool(_make_issuer())
    entry = await pool._get_entry("https://mcp.example.com", "mcp.example.com")  # noqa: SLF001

    async def failing_close() -> None:
        raise RuntimeError("close failed hard")

    entry.transport.close = failing_close  # type: ignore[method-assign]
    pool._entries["https://mcp.example.com"] = entry  # noqa: SLF001

    with caplog.at_level("WARNING", logger="lime.agents.mcp"):
        await pool.aclose()
    assert any("close failed hard" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_pool_session_context_manager_yields_session() -> None:
    session = AsyncMock()
    fake_http, fake_session = _mock_transport_stack(session)

    with (
        patch("lime_agents._mcp._transport.streamable_http_client", fake_http),
        patch("lime_agents._mcp._transport.ClientSession", fake_session),
    ):
        pool = McpSessionPool(_make_issuer())
        async with pool.session("https://mcp.example.com") as mcp_session:
            assert mcp_session is session
        await pool.aclose()


def test_pool_is_shutdown_noise_exception_group() -> None:
    group = _duck_exception_group(
        "shutdown",
        [Exception("cancel scope mismatch"), Exception("session termination failed")],
    )
    assert McpSessionPool._is_shutdown_noise(group) is True
    mixed = _duck_exception_group("mixed", [RuntimeError("boom")])
    assert McpSessionPool._is_shutdown_noise(mixed) is False


def test_pool_is_broken_session_exception_group() -> None:
    group = _duck_exception_group("broken", [Exception("brokenresource in stream")])
    assert McpSessionPool._is_broken_session(group) is True


def test_pool_is_shutdown_noise_session_termination_message() -> None:
    assert McpSessionPool._is_shutdown_noise(Exception("Session termination failed")) is True


def _mock_transport_stack(
    session: AsyncMock,
    *,
    init_result: Any | None = None,
) -> Any:
    from mcp.types import Implementation, InitializeResult

    default_init = InitializeResult(
        protocolVersion="2024-11-05",
        capabilities=ServerCapabilities(),
        serverInfo=Implementation(name="test-server", version="1.0.0"),
    )

    @asynccontextmanager
    async def fake_streamable_http_client(
        url: str,
        *,
        http_client: Any = None,
        terminate_on_close: bool = True,
    ):
        read_stream = MagicMock()
        write_stream = MagicMock()
        yield read_stream, write_stream, lambda: "sid"

    @asynccontextmanager
    async def fake_client_session(read_stream: Any, write_stream: Any):
        session.initialize = AsyncMock(return_value=init_result or default_init)
        yield session

    return fake_streamable_http_client, fake_client_session


def _init_result(capabilities: Any) -> Any:
    from mcp.types import Implementation, InitializeResult, ServerCapabilities

    if not isinstance(capabilities, ServerCapabilities):
        capabilities = ServerCapabilities()
    return InitializeResult(
        protocolVersion="2024-11-05",
        capabilities=capabilities,
        serverInfo=Implementation(name="test-server", version="1.0.0"),
    )
