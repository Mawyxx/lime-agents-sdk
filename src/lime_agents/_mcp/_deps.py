from __future__ import annotations


def require_mcp() -> None:
    try:
        import mcp  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "MCP support requires: pip install lime-agents-sdk[mcp]",
        ) from exc
