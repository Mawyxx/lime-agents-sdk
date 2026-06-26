from __future__ import annotations

import os

import httpx
import pytest

from lime_agents import LimeAgent


@pytest.fixture
def mcp_server_url() -> str:
    host = os.getenv("MCP_RS_HOST", "127.0.0.1")
    port = os.getenv("MCP_RS_PORT", "9000")
    return os.getenv("MCP_SERVER_URL", f"http://{host}:{port}").rstrip("/")


@pytest.mark.mcp_integration
@pytest.mark.asyncio
async def test_bearer_lane_against_mcp_test_server(mcp_server_url: str) -> None:
    """Validates MCP JWT Bearer against scripts/verify/mcp_test_server.py (not full MCP RPC)."""
    token = os.getenv("LIME_AGENT_TOKEN", "").strip()
    if not token:
        pytest.skip("LIME_AGENT_TOKEN is required")

    base_url = os.getenv("LIME_API_BASE", "https://lime.pics/api/v1").rstrip("/")
    async with LimeAgent(agent_token=token, base_url=base_url) as agent:
        mcp_token = await agent.get_mcp_access_token()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{mcp_server_url}/tools/echo",
            headers={"Authorization": f"Bearer {mcp_token.access_token}"},
            json={"text": "sdk-integration"},
            timeout=30.0,
        )

    if response.status_code == 404:
        pytest.skip("mcp_test_server not running or echo route unavailable")

    assert response.status_code == 200
    body = response.json()
    assert body.get("echo") == "sdk-integration"


@pytest.mark.mcp_integration
@pytest.mark.asyncio
async def test_list_tools_live_streamable_fixture(mcp_server_url: str) -> None:
    """Full MCP RPC when MCP_SERVER_URL points at a streamable HTTP MCP server."""
    token = os.getenv("LIME_AGENT_TOKEN", "").strip()
    if not token:
        pytest.skip("LIME_AGENT_TOKEN is required")

    if os.getenv("MCP_STREAMABLE_SERVER") != "1":
        pytest.skip("Set MCP_STREAMABLE_SERVER=1 when MCP_SERVER_URL is streamable MCP")

    base_url = os.getenv("LIME_API_BASE", "https://lime.pics/api/v1").rstrip("/")
    async with LimeAgent(agent_token=token, base_url=base_url) as agent:
        try:
            tools = await agent.list_tools(f"{mcp_server_url}/mcp")
        except Exception as exc:
            pytest.skip(f"streamable MCP server unavailable: {exc}")
        assert isinstance(tools, list)
