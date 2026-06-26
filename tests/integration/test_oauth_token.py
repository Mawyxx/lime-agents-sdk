from __future__ import annotations

import base64
import json
import os

import httpx
import pytest

from lime_agents import LimeAgent


def _decode_jwt_sub(token: str) -> str:
    payload_b64 = token.split(".", 1)[1]
    padded = payload_b64 + "=" * (-len(payload_b64) % 4)
    payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub.strip():
        raise AssertionError("JWT missing sub claim")
    return sub.strip()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_mcp_access_token_live() -> None:
    token = os.getenv("LIME_AGENT_TOKEN", "").strip()
    if not token:
        pytest.skip("LIME_AGENT_TOKEN is required")

    base_url = os.getenv("LIME_API_BASE", "https://lime.pics/api/v1").rstrip("/")
    async with LimeAgent(agent_token=token, base_url=base_url) as agent:
        mcp_token = await agent.get_mcp_access_token()
        profile = await agent.get_profile()
        assert mcp_token.token_type == "Bearer"
        assert mcp_token.access_token.count(".") == 2
        assert _decode_jwt_sub(mcp_token.access_token) == profile.agent_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mcp_jwt_rejected_on_lime_profile() -> None:
    token = os.getenv("LIME_AGENT_TOKEN", "").strip()
    if not token:
        pytest.skip("LIME_AGENT_TOKEN is required")

    base_url = os.getenv("LIME_API_BASE", "https://lime.pics/api/v1").rstrip("/")
    async with LimeAgent(agent_token=token, base_url=base_url) as agent:
        mcp_token = await agent.get_mcp_access_token()

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{base_url}/core/agents/me/profile",
            headers={"Authorization": f"Bearer {mcp_token.access_token}"},
        )
    assert response.status_code == 401
