from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_MONOREPO_ROOT = Path(__file__).resolve().parents[4]
if str(_MONOREPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_MONOREPO_ROOT))

from lime_agents import LimeAgent

from scripts.verify.mcp_sdk_e2e_checks import (
    McpSdkE2eFailure,
    probe_streamable_server,
    run_all_mcp_sdk_checks,
    run_parallel_two_url_check,
)


@pytest.fixture
def mcp_server_url() -> str:
    host = os.getenv("MCP_RS_HOST", "127.0.0.1")
    port = os.getenv("MCP_RS_PORT", "9000")
    return os.getenv("MCP_SERVER_URL", f"http://{host}:{port}").rstrip("/")


@pytest.mark.mcp_integration
@pytest.mark.asyncio
async def test_mcp_streamable_full_facade_e2e(mcp_server_url: str) -> None:
    token = os.getenv("LIME_AGENT_TOKEN", "").strip()
    if not token:
        pytest.skip("LIME_AGENT_TOKEN is required")

    if not await probe_streamable_server(mcp_server_url):
        pytest.skip(
            "streamable MCP server not running "
            "(PYTHONPATH=. python scripts/verify/mcp_test_server.py)",
        )

    base_url = os.getenv("LIME_API_BASE", "https://lime.pics/api/v1").rstrip("/")
    async with LimeAgent(agent_token=token, base_url=base_url) as agent:
        try:
            passed = await run_all_mcp_sdk_checks(agent, mcp_server_url)
        except McpSdkE2eFailure as exc:
            pytest.fail(str(exc))

    assert len(passed) >= 14


@pytest.mark.mcp_integration
@pytest.mark.asyncio
async def test_mcp_parallel_two_server_urls(mcp_server_url: str) -> None:
    token = os.getenv("LIME_AGENT_TOKEN", "").strip()
    if not token:
        pytest.skip("LIME_AGENT_TOKEN is required")

    if not await probe_streamable_server(mcp_server_url):
        pytest.skip("streamable MCP server not running")

    base_url = os.getenv("LIME_API_BASE", "https://lime.pics/api/v1").rstrip("/")
    async with LimeAgent(agent_token=token, base_url=base_url) as agent:
        try:
            await run_parallel_two_url_check(agent, mcp_server_url)
        except McpSdkE2eFailure as exc:
            pytest.fail(str(exc))
