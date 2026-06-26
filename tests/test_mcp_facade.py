from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from lime_agents import LimeAgent
from lime_agents._types import McpAccessToken


def _oauth_handler(_: httpx.Request) -> httpx.Response:
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


def _agent_with_mock_http() -> LimeAgent:
    http_client = httpx.AsyncClient(transport=httpx.MockTransport(_oauth_handler))
    return LimeAgent(
        agent_token="at_test",
        base_url="http://test/api/v1",
        http_client=http_client,
    )


def _mock_mcp_session() -> AsyncMock:
    session = AsyncMock()
    session.list_tools.return_value = MagicMock(tools=[MagicMock(name="echo")])
    session.call_tool.return_value = MagicMock(is_error=False, content=[])
    session.list_resources.return_value = MagicMock(resources=[])
    session.list_resource_templates.return_value = MagicMock(resourceTemplates=[])
    session.list_prompts.return_value = MagicMock(prompts=[])
    session.read_resource.return_value = MagicMock(contents=[])
    session.get_prompt.return_value = MagicMock(messages=[])
    session.set_logging_level.return_value = MagicMock()
    session.send_ping.return_value = MagicMock()
    session.get_server_capabilities.return_value = MagicMock(model_dump=lambda **_: {"tools": {}})
    session.send_progress_notification = AsyncMock()
    return session


@asynccontextmanager
async def _mcp_transport_patches(session: AsyncMock):
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
        session.initialize = AsyncMock()
        yield session

    with (
        patch("lime_agents._mcp._transport.streamable_http_client", fake_streamable_http_client),
        patch("lime_agents._mcp._transport.ClientSession", fake_client_session),
    ):
        yield


@pytest.mark.asyncio
async def test_get_mcp_access_token() -> None:
    agent = _agent_with_mock_http()
    token = await agent.get_mcp_access_token()
    assert isinstance(token, McpAccessToken)
    await agent.aclose()


@pytest.mark.asyncio
async def test_list_tools() -> None:
    session = _mock_mcp_session()
    agent = _agent_with_mock_http()
    async with _mcp_transport_patches(session):
        tools = await agent.list_tools("https://mcp.example.com")
    assert len(tools) == 1
    await agent.aclose()


@pytest.mark.asyncio
async def test_call_tool() -> None:
    session = _mock_mcp_session()
    agent = _agent_with_mock_http()
    async with _mcp_transport_patches(session):
        result = await agent.call_tool("https://mcp.example.com", "echo", {"text": "hi"})
    assert result.is_error is False
    await agent.aclose()


@pytest.mark.asyncio
async def test_list_resources() -> None:
    session = _mock_mcp_session()
    agent = _agent_with_mock_http()
    async with _mcp_transport_patches(session):
        resources = await agent.list_resources("https://mcp.example.com")
    assert resources == []
    await agent.aclose()


@pytest.mark.asyncio
async def test_list_resource_templates() -> None:
    session = _mock_mcp_session()
    agent = _agent_with_mock_http()
    async with _mcp_transport_patches(session):
        templates = await agent.list_resource_templates("https://mcp.example.com")
    assert templates == []
    await agent.aclose()


@pytest.mark.asyncio
async def test_list_prompts() -> None:
    session = _mock_mcp_session()
    agent = _agent_with_mock_http()
    async with _mcp_transport_patches(session):
        prompts = await agent.list_prompts("https://mcp.example.com")
    assert prompts == []
    await agent.aclose()


@pytest.mark.asyncio
async def test_read_resource() -> None:
    session = _mock_mcp_session()
    agent = _agent_with_mock_http()
    async with _mcp_transport_patches(session):
        result = await agent.read_resource("https://mcp.example.com", "file:///data.txt")
    assert result.contents == []
    await agent.aclose()


@pytest.mark.asyncio
async def test_get_prompt() -> None:
    session = _mock_mcp_session()
    agent = _agent_with_mock_http()
    async with _mcp_transport_patches(session):
        result = await agent.get_prompt("https://mcp.example.com", "greet", {"name": "Alice"})
    assert result.messages == []
    await agent.aclose()


@pytest.mark.asyncio
async def test_set_logging_level() -> None:
    session = _mock_mcp_session()
    agent = _agent_with_mock_http()
    async with _mcp_transport_patches(session):
        await agent.set_logging_level("https://mcp.example.com", "info")
    session.set_logging_level.assert_awaited_once_with("info")
    await agent.aclose()


@pytest.mark.asyncio
async def test_send_ping() -> None:
    session = _mock_mcp_session()
    agent = _agent_with_mock_http()
    async with _mcp_transport_patches(session):
        await agent.send_ping("https://mcp.example.com")
    session.send_ping.assert_awaited_once()
    await agent.aclose()


@pytest.mark.asyncio
async def test_get_server_capabilities() -> None:
    session = _mock_mcp_session()
    agent = _agent_with_mock_http()
    async with _mcp_transport_patches(session):
        caps = await agent.get_server_capabilities("https://mcp.example.com")
    assert caps == {"tools": {}}
    await agent.aclose()


@pytest.mark.asyncio
async def test_get_server_capabilities_none() -> None:
    session = _mock_mcp_session()
    session.get_server_capabilities.return_value = None
    agent = _agent_with_mock_http()
    async with _mcp_transport_patches(session):
        caps = await agent.get_server_capabilities("https://mcp.example.com")
    assert caps == {}
    await agent.aclose()


@pytest.mark.asyncio
async def test_get_server_capabilities_without_model_dump() -> None:
    session = _mock_mcp_session()
    session.get_server_capabilities.return_value = object()
    agent = _agent_with_mock_http()
    async with _mcp_transport_patches(session):
        caps = await agent.get_server_capabilities("https://mcp.example.com")
    assert caps == {}
    await agent.aclose()


@pytest.mark.asyncio
async def test_get_server_capabilities_non_dict_dump() -> None:
    session = _mock_mcp_session()
    session.get_server_capabilities.return_value = MagicMock(model_dump=lambda **_: "bad")
    agent = _agent_with_mock_http()
    async with _mcp_transport_patches(session):
        caps = await agent.get_server_capabilities("https://mcp.example.com")
    assert caps == {}
    await agent.aclose()


@pytest.mark.asyncio
async def test_send_progress_notification() -> None:
    session = _mock_mcp_session()
    agent = _agent_with_mock_http()
    async with _mcp_transport_patches(session):
        await agent.send_progress_notification("https://mcp.example.com", "tok", 50.0, 100.0)
    session.send_progress_notification.assert_awaited_once_with("tok", 50.0, 100.0)
    await agent.aclose()


@pytest.mark.asyncio
async def test_mcp_session_cached() -> None:
    session = _mock_mcp_session()
    open_count = {"n": 0}

    @asynccontextmanager
    async def fake_streamable_http_client(
        url: str,
        *,
        http_client: Any = None,
        terminate_on_close: bool = True,
    ):
        yield MagicMock(), MagicMock(), lambda: "sid"

    @asynccontextmanager
    async def counting_session(read_stream: Any, write_stream: Any):
        open_count["n"] += 1
        session.initialize = AsyncMock()
        yield session

    agent = _agent_with_mock_http()
    with (
        patch("lime_agents._mcp._transport.streamable_http_client", fake_streamable_http_client),
        patch("lime_agents._mcp._transport.ClientSession", counting_session),
    ):
        await agent.list_tools("https://mcp.example.com")
        await agent.list_tools("https://mcp.example.com")
    assert open_count["n"] == 1
    await agent.aclose()


@pytest.mark.asyncio
async def test_mcp_multiple_servers() -> None:
    session = _mock_mcp_session()
    open_count = {"n": 0}

    @asynccontextmanager
    async def fake_streamable_http_client(
        url: str,
        *,
        http_client: Any = None,
        terminate_on_close: bool = True,
    ):
        yield MagicMock(), MagicMock(), lambda: "sid"

    @asynccontextmanager
    async def counting_session(read_stream: Any, write_stream: Any):
        open_count["n"] += 1
        session.initialize = AsyncMock()
        yield session

    agent = _agent_with_mock_http()
    with (
        patch("lime_agents._mcp._transport.streamable_http_client", fake_streamable_http_client),
        patch("lime_agents._mcp._transport.ClientSession", counting_session),
    ):
        await agent.list_tools("https://mcp1.example.com")
        await agent.list_tools("https://mcp2.example.com")
    assert open_count["n"] == 2
    await agent.aclose()


@pytest.mark.asyncio
async def test_mcp_aclose_closes_pool() -> None:
    session = _mock_mcp_session()
    agent = _agent_with_mock_http()
    async with _mcp_transport_patches(session):
        await agent.list_tools("https://mcp.example.com")
    await agent.aclose()
    assert agent._mcp_pool is None  # noqa: SLF001


@pytest.mark.asyncio
async def test_require_mcp_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import lime_agents._agent as agent_module

    def _raise_import() -> None:
        raise ImportError("MCP support requires: pip install lime-agents-sdk[mcp]")

    monkeypatch.setattr(agent_module, "require_mcp", _raise_import)
    agent = _agent_with_mock_http()
    with pytest.raises(ImportError, match="lime-agents-sdk\\[mcp\\]"):
        await agent.list_tools("https://mcp.example.com")
    await agent.aclose()
