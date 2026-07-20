from __future__ import annotations

import pytest

from lime_agents._domain import extract_and_normalize_domain, resolve_mcp_http_url


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("autonomad.ai", "autonomad.ai"),
        ("https://autonomad.ai/mcp", "autonomad.ai"),
        ("http://Autonomad.AI/path", "autonomad.ai"),
        ("https://autonomad.ai:8443/mcp", "autonomad.ai"),
        ("autonomad.ai:8443", "autonomad.ai"),
        ("  https://example.com/foo/bar  ", "example.com"),
    ],
)
def test_extract_and_normalize_domain_accepts(target: str, expected: str) -> None:
    assert extract_and_normalize_domain(target) == expected


@pytest.mark.parametrize(
    "target",
    [
        "",
        "   ",
        "user@host.com",
        "https://user@host.com/mcp",
        "127.0.0.1",
        "https://127.0.0.1/mcp",
        "[::1]",
        "not_a_host!",
        "http://",
        "://bad",
    ],
)
def test_extract_and_normalize_domain_rejects(target: str) -> None:
    with pytest.raises(ValueError):
        extract_and_normalize_domain(target)


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("autonomad.ai", "https://autonomad.ai/mcp"),
        ("autonomad.ai:8443", "https://autonomad.ai:8443/mcp"),
        ("https://autonomad.ai/mcp", "https://autonomad.ai/mcp"),
        ("https://autonomad.ai:8443/mcp/", "https://autonomad.ai:8443/mcp"),
        ("http://example.com/custom", "http://example.com/custom"),
    ],
)
def test_resolve_mcp_http_url(target: str, expected: str) -> None:
    assert resolve_mcp_http_url(target) == expected


def test_resolve_rejects_invalid_target() -> None:
    with pytest.raises(ValueError):
        resolve_mcp_http_url("127.0.0.1")
