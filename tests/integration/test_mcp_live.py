from __future__ import annotations

import os

import httpx
import pytest

from lime_agents import LimeAgent


@pytest.fixture
def mcp_server_url() -> str:
    host = os.getenv("MCP_RS_HOST", "localhost")
    port = os.getenv("MCP_RS_PORT", "9000")
    return os.getenv("MCP_SERVER_URL", f"http://{host}:{port}").rstrip("/")


@pytest.mark.mcp_integration
@pytest.mark.asyncio
async def test_bearer_lane_against_mcp_test_server(mcp_server_url: str) -> None:
    """Validates MCP JWT Bearer against scripts/verify/mcp_test_server.py REST echo."""
    token = os.getenv("LIME_AGENT_TOKEN", "").strip()
    if not token:
        pytest.skip("LIME_AGENT_TOKEN is required")

    base_url = os.getenv("LIME_API_BASE", "https://lime.pics/api/v1").rstrip("/")
    async with LimeAgent(agent_token=token, base_url=base_url) as agent:
        mcp_token = await agent.get_mcp_access_token(mcp_server_url)

    async with httpx.AsyncClient(trust_env=False) as client:
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
    assert "sdk-integration" in str(body.get("result", ""))
    assert body.get("sub")
