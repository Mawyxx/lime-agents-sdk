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


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.getenv("LIME_INTEGRATION") == "1":
        return
    skip = pytest.mark.skip(reason="Set LIME_INTEGRATION=1 to run live API tests")
    for item in items:
        if "integration" in item.nodeid.replace("\\", "/"):
            item.add_marker(skip)
