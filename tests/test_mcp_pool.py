from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lime_agents._errors import McpAuthenticationError
from lime_agents._mcp._deps import require_mcp
from lime_agents._mcp._pool import McpSessionPool
from lime_agents._oauth import _McpTokenIssuer


class _FakeAuthError(Exception):
    status = 401


def _make_issuer() -> _McpTokenIssuer:
    issuer = MagicMock(spec=_McpTokenIssuer)
    issuer.generation = 1
    token = MagicMock()
    token.access_token = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJhZ2VudF8xIn0.sig"
    issuer.get_access_token = AsyncMock(return_value=token)
    issuer.invalidate_and_refresh = AsyncMock(
        side_effect=lambda: setattr(issuer, "generation", issuer.generation + 1) or token,
    )
    return issuer


def _mock_transport_stack(session: AsyncMock) -> Any:
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
        session.initialize = AsyncMock()
        yield session

    return fake_streamable_http_client, fake_client_session


@pytest.mark.asyncio
async def test_pool_run_executes_operation() -> None:
    session = AsyncMock()
    session.list_tools.return_value = MagicMock(tools=[MagicMock(name="echo")])
    fake_http, fake_session = _mock_transport_stack(session)

    with (
        patch("lime_agents._mcp._transport.streamable_http_client", fake_http),
        patch("lime_agents._mcp._transport.ClientSession", fake_session),
    ):
        pool = McpSessionPool(_make_issuer())
        tools = await pool.run("https://mcp.example.com", lambda s: s.list_tools())
        assert len(tools.tools) == 1
        await pool.aclose()


@pytest.mark.asyncio
async def test_pool_reuses_same_url() -> None:
    session = AsyncMock()
    session.list_tools.return_value = MagicMock(tools=[])
    fake_http, fake_session = _mock_transport_stack(session)
    open_count = {"n": 0}

    @asynccontextmanager
    async def counting_session(read_stream: Any, write_stream: Any):
        open_count["n"] += 1
        session.initialize = AsyncMock()
        yield session

    with (
        patch("lime_agents._mcp._transport.streamable_http_client", fake_http),
        patch("lime_agents._mcp._transport.ClientSession", counting_session),
    ):
        pool = McpSessionPool(_make_issuer())
        await pool.run("https://mcp.example.com", lambda s: s.list_tools())
        await pool.run("https://mcp.example.com", lambda s: s.list_tools())
        assert open_count["n"] == 1
        await pool.aclose()


@pytest.mark.asyncio
async def test_pool_different_urls_create_entries() -> None:
    session = AsyncMock()
    session.list_tools.return_value = MagicMock(tools=[])
    fake_http, _ = _mock_transport_stack(session)
    open_count = {"n": 0}

    @asynccontextmanager
    async def counting_session(read_stream: Any, write_stream: Any):
        open_count["n"] += 1
        session.initialize = AsyncMock()
        yield session

    with (
        patch("lime_agents._mcp._transport.streamable_http_client", fake_http),
        patch("lime_agents._mcp._transport.ClientSession", counting_session),
    ):
        pool = McpSessionPool(_make_issuer())
        await pool.run("https://mcp1.example.com", lambda s: s.list_tools())
        await pool.run("https://mcp2.example.com", lambda s: s.list_tools())
        assert open_count["n"] == 2
        await pool.aclose()


@pytest.mark.asyncio
async def test_pool_invalid_url() -> None:
    pool = McpSessionPool(_make_issuer())
    with pytest.raises(ValueError, match="http"):
        await pool.run("not-a-url", lambda s: s.list_tools())
    await pool.aclose()


@pytest.mark.asyncio
async def test_pool_empty_url() -> None:
    pool = McpSessionPool(_make_issuer())
    with pytest.raises(ValueError, match="non-empty"):
        await pool.run("   ", lambda s: s.list_tools())
    await pool.aclose()


@pytest.mark.asyncio
async def test_pool_retry_on_auth_failure() -> None:
    session = AsyncMock()
    session.call_tool = AsyncMock(side_effect=[_FakeAuthError("401"), MagicMock(is_error=False)])
    fake_http, fake_session = _mock_transport_stack(session)
    issuer = _make_issuer()

    with (
        patch("lime_agents._mcp._transport.streamable_http_client", fake_http),
        patch("lime_agents._mcp._transport.ClientSession", fake_session),
    ):
        pool = McpSessionPool(issuer)
        result = await pool.run(
            "https://mcp.example.com",
            lambda s: s.call_tool("echo", {"text": "hi"}),
            retry_on_auth=True,
        )
        assert result.is_error is False
        issuer.invalidate_and_refresh.assert_awaited_once()
        await pool.aclose()


@pytest.mark.asyncio
async def test_pool_auth_failure_after_retry_raises() -> None:
    session = AsyncMock()
    session.call_tool = AsyncMock(side_effect=_FakeAuthError("401"))
    fake_http, fake_session = _mock_transport_stack(session)

    with (
        patch("lime_agents._mcp._transport.streamable_http_client", fake_http),
        patch("lime_agents._mcp._transport.ClientSession", fake_session),
    ):
        pool = McpSessionPool(_make_issuer())
        with pytest.raises(McpAuthenticationError):
            await pool.run(
                "https://mcp.example.com",
                lambda s: s.call_tool("echo", {}),
                retry_on_auth=True,
            )
        await pool.aclose()


@pytest.mark.asyncio
async def test_pool_closed_raises() -> None:
    pool = McpSessionPool(_make_issuer())
    await pool.aclose()
    with pytest.raises(RuntimeError, match="closed"):
        await pool.run("https://mcp.example.com", lambda s: s.list_tools())


@pytest.mark.asyncio
async def test_pool_serializes_same_url() -> None:
    session = AsyncMock()
    active = {"n": 0}
    max_active = {"n": 0}

    async def slow_list_tools() -> MagicMock:
        active["n"] += 1
        max_active["n"] = max(max_active["n"], active["n"])
        await asyncio.sleep(0.05)
        active["n"] -= 1
        return MagicMock(tools=[])

    session.list_tools = slow_list_tools
    fake_http, fake_session = _mock_transport_stack(session)

    with (
        patch("lime_agents._mcp._transport.streamable_http_client", fake_http),
        patch("lime_agents._mcp._transport.ClientSession", fake_session),
    ):
        pool = McpSessionPool(_make_issuer())
        await asyncio.gather(
            pool.run("https://mcp.example.com", lambda s: s.list_tools()),
            pool.run("https://mcp.example.com", lambda s: s.list_tools()),
        )
        assert max_active["n"] == 1
        await pool.aclose()


@pytest.mark.asyncio
async def test_refresh_all_tokens_closes_entries() -> None:
    session = AsyncMock()
    session.list_tools.return_value = MagicMock(tools=[])
    fake_http, fake_session = _mock_transport_stack(session)
    issuer = _make_issuer()

    with (
        patch("lime_agents._mcp._transport.streamable_http_client", fake_http),
        patch("lime_agents._mcp._transport.ClientSession", fake_session),
    ):
        pool = McpSessionPool(issuer)
        await pool.run("https://mcp.example.com", lambda s: s.list_tools())
        await pool.refresh_all_tokens()
        issuer.invalidate_and_refresh.assert_awaited_once()
        await pool.aclose()


def test_require_mcp_passes_when_installed() -> None:
    require_mcp()


@pytest.mark.asyncio
async def test_pool_non_auth_exception_propagates() -> None:
    session = AsyncMock()
    session.list_tools = AsyncMock(side_effect=RuntimeError("boom"))
    fake_http, fake_session = _mock_transport_stack(session)

    with (
        patch("lime_agents._mcp._transport.streamable_http_client", fake_http),
        patch("lime_agents._mcp._transport.ClientSession", fake_session),
    ):
        pool = McpSessionPool(_make_issuer())
        with pytest.raises(RuntimeError, match="boom"):
            await pool.run("https://mcp.example.com", lambda s: s.list_tools())
        await pool.aclose()


@pytest.mark.asyncio
async def test_pool_no_retry_when_disabled() -> None:
    session = AsyncMock()
    session.call_tool = AsyncMock(side_effect=_FakeAuthError("401"))
    fake_http, fake_session = _mock_transport_stack(session)

    with (
        patch("lime_agents._mcp._transport.streamable_http_client", fake_http),
        patch("lime_agents._mcp._transport.ClientSession", fake_session),
    ):
        pool = McpSessionPool(_make_issuer())
        with pytest.raises(_FakeAuthError):
            await pool.run(
                "https://mcp.example.com",
                lambda s: s.call_tool("echo", {}),
                retry_on_auth=False,
            )
        await pool.aclose()


@pytest.mark.asyncio
async def test_pool_retry_non_auth_failure_on_second_attempt() -> None:
    session = AsyncMock()
    session.call_tool = AsyncMock(side_effect=[_FakeAuthError("401"), RuntimeError("boom")])
    fake_http, fake_session = _mock_transport_stack(session)

    with (
        patch("lime_agents._mcp._transport.streamable_http_client", fake_http),
        patch("lime_agents._mcp._transport.ClientSession", fake_session),
    ):
        pool = McpSessionPool(_make_issuer())
        with pytest.raises(RuntimeError, match="boom"):
            await pool.run(
                "https://mcp.example.com",
                lambda s: s.call_tool("echo", {}),
                retry_on_auth=True,
            )
        await pool.aclose()


@pytest.mark.asyncio
async def test_refresh_after_auth_failure_closes_other_entries() -> None:
    session = AsyncMock()
    session.call_tool = AsyncMock(side_effect=_FakeAuthError("401"))
    fake_http, fake_session = _mock_transport_stack(session)
    issuer = _make_issuer()

    with (
        patch("lime_agents._mcp._transport.streamable_http_client", fake_http),
        patch("lime_agents._mcp._transport.ClientSession", fake_session),
    ):
        pool = McpSessionPool(issuer)
        await pool.run("https://mcp1.example.com", lambda s: s.list_tools())
        with pytest.raises(McpAuthenticationError):
            await pool.run(
                "https://mcp2.example.com",
                lambda s: s.call_tool("echo", {}),
                retry_on_auth=True,
            )
        await pool.aclose()


def test_pool_is_auth_failure_helpers() -> None:
    assert McpSessionPool._is_auth_failure(_FakeAuthError()) is True
    assert McpSessionPool._is_auth_failure(Exception("HTTP 401 unauthorized")) is True
    assert McpSessionPool._is_auth_failure(Exception("invalid_token")) is True
    assert McpSessionPool._is_auth_failure(Exception("boom")) is False
