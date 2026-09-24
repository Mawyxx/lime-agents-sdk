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
    "target",
    [
        "localhost",
        "https://localhost/mcp",
        "localhost:8443",
        "mcp.local",
        "https://mcp.local/mcp",
        "service.internal",
        "https://service.internal/mcp",
        "metadata.google.internal",
        "metadata",
        "kubernetes",
        "kubernetes.default.svc",
        "kubernetes.default.svc.cluster.local",
    ],
)
def test_extract_rejects_reserved_hosts(target: str) -> None:
    with pytest.raises(ValueError, match="reserved"):
        extract_and_normalize_domain(target)


@pytest.mark.parametrize(
    "target",
    [
        "nip.io",
        "127.0.0.1.nip.io",
        "https://127.0.0.1.nip.io/mcp",
        "10.0.0.1.sslip.io",
        "172.16.0.1.xip.io",
        "app.localtest.me",
        "api.lvh.me",
        "kd8t8y.traefik.me",
    ],
)
def test_extract_rejects_ip_encoding_dns_services(target: str) -> None:
    with pytest.raises(ValueError, match="reserved"):
        extract_and_normalize_domain(target)


@pytest.mark.parametrize(
    "target",
    [
        "2130706433",
        "0x7f000001",
        "0X7F000001",
        "017700000001",
        "127.1",
        "0x7f.0.0.1",
        "0177.0.0.1",
        "1.2.3.4.5",
        "https://127.1/mcp",
        "https://0x7f000001/mcp",
    ],
)
def test_extract_rejects_ip_literal_obfuscations(target: str) -> None:
    with pytest.raises(ValueError, match="IP address"):
        extract_and_normalize_domain(target)


@pytest.mark.parametrize(
    "target",
    [
        "mcp.lime.pics",
        "123.example.com",
        "api.internal-tools.com",
        "notlocal.dev",
        "mylocal.example.org",
    ],
)
def test_extract_accepts_public_lookalikes(target: str) -> None:
    assert extract_and_normalize_domain(target) == target


def test_resolve_rejects_reserved_host_url() -> None:
    with pytest.raises(ValueError, match="reserved"):
        resolve_mcp_http_url("https://127.0.0.1.nip.io/mcp")


def test_extract_rejects_non_string() -> None:
    with pytest.raises(ValueError, match="non-empty string"):
        extract_and_normalize_domain(123)  # type: ignore[arg-type]


def test_extract_rejects_port_only() -> None:
    with pytest.raises(ValueError, match="valid DNS hostname"):
        extract_and_normalize_domain(":443")


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


def test_resolve_rejects_non_string() -> None:
    with pytest.raises(ValueError, match="non-empty string"):
        resolve_mcp_http_url(None)  # type: ignore[arg-type]


def test_resolve_rejects_whitespace_only() -> None:
    with pytest.raises(ValueError, match="non-empty string"):
        resolve_mcp_http_url("   ")
