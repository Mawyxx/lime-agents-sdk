"""Pytest configuration for lime-agents-sdk (workspace root: sdk/python)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_SDK_ROOT = Path(__file__).resolve().parents[1]
_SRC = _SDK_ROOT / "src"

# Prefer the in-tree package over any globally installed lime-agents-sdk wheel.
_src_str = str(_SRC)
if _src_str not in sys.path:
    sys.path.insert(0, _src_str)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: live HTTP tests against LIME API (requires LIME_INTEGRATION=1)",
    )
    config.addinivalue_line(
        "markers",
        "mcp_integration: MCP streamable HTTP E2E (requires LIME_MCP_INTEGRATION=1)",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.getenv("LIME_INTEGRATION") != "1":
        skip_integration = pytest.mark.skip(
            reason="Set LIME_INTEGRATION=1 to run live API tests",
        )
        for item in items:
            if item.get_closest_marker("integration"):
                item.add_marker(skip_integration)

    if os.getenv("LIME_MCP_INTEGRATION") != "1":
        skip_mcp = pytest.mark.skip(
            reason="Set LIME_MCP_INTEGRATION=1 to run MCP integration tests",
        )
        for item in items:
            if item.get_closest_marker("mcp_integration"):
                item.add_marker(skip_mcp)
