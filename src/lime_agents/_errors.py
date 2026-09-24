from __future__ import annotations

from typing import Any

_AUTH_CODES = frozenset(
    {
        "MISSING_AGENT_TOKEN",
        "INVALID_AGENT_TOKEN",
    },
)


class LimeError(Exception):
    """Base class for SDK errors."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        http_status: int | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.code = code
        self.http_status = http_status
        self.detail = detail
        super().__init__(message)


class AuthenticationError(LimeError):
    """Missing, invalid, inactive, or suspended agent token."""


class AgentInactiveError(AuthenticationError):
    """HTTP 403 ``AGENT_INACTIVE`` — agent disabled by its owner."""


class AgentUserSuspendedError(AuthenticationError):
    """HTTP 403 ``AGENT_USER_SUSPENDED`` — owning user account is suspended."""


class PowTimeoutError(LimeError):
    """PoW was not solved within the allotted time."""


class RateLimitError(LimeError):
    """HTTP 429 — rate limit exceeded."""


class ApiError(LimeError):
    """General API error with code and message."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        http_status: int,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            http_status=http_status,
            detail=detail,
        )


class OAuthCapabilityError(ApiError):
    """Agent lacks the ``oauth:mcp`` grant (RFC 6749 ``access_denied``, HTTP 403)."""


class AuthUnavailableError(ApiError):
    """HTTP 503 ``AUTH_UNAVAILABLE`` — agent-auth store unavailable (fail-closed)."""


class McpAuthenticationError(LimeError):
    """MCP resource server rejected the access token."""


def map_envelope_error(
    status: int,
    code: str,
    message: str,
    detail: dict[str, Any] | None = None,
) -> LimeError:
    """Single owner for LIME ``{ok:false,error:{code}}`` → typed SDK error."""
    if status == 429 or code == "RATE_LIMIT_EXCEEDED":
        return RateLimitError(message, code=code, http_status=status, detail=detail)
    if code == "AGENT_INACTIVE":
        return AgentInactiveError(message, code=code, http_status=status, detail=detail)
    if code == "AGENT_USER_SUSPENDED":
        return AgentUserSuspendedError(message, code=code, http_status=status, detail=detail)
    if code == "AUTH_UNAVAILABLE":
        return AuthUnavailableError(code, message, http_status=status, detail=detail)
    if status == 401 or code in _AUTH_CODES:
        return AuthenticationError(message, code=code, http_status=status, detail=detail)
    return ApiError(code, message, http_status=status, detail=detail)
