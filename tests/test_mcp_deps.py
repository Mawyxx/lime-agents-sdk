from __future__ import annotations

import importlib
from unittest.mock import patch

import pytest


def test_require_mcp_import_error_message() -> None:
    import builtins

    import lime_agents._mcp._deps as deps

    real_import = builtins.__import__

    def fake_import(
        name: str,
        globals: object = None,
        locals: object = None,
        fromlist: object = (),
        level: int = 0,
    ) -> object:
        if name == "mcp":
            raise ImportError("no mcp")
        return real_import(name, globals, locals, fromlist, level)

    with patch.object(builtins, "__import__", side_effect=fake_import):
        reloaded = importlib.reload(deps)
        with pytest.raises(ImportError, match="lime-agents-sdk\\[mcp\\]"):
            reloaded.require_mcp()
    importlib.reload(deps)
