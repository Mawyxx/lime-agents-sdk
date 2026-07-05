from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass(frozen=True, slots=True)
class ApprovalResult:
    """Outcome of ``LimeAgent.login()`` approve step."""

    request_id: str
    site_id: str
    status: str
    expires_at: datetime
    approved_agent_id: str | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> ApprovalResult:
        """Parse approve response envelope ``data`` object."""
        return cls(
            request_id=str(data["request_id"]),
            site_id=str(data["site_id"]),
            status=str(data["status"]),
            expires_at=_parse_datetime(str(data["expires_at"])),
            approved_agent_id=(
                str(data["approved_agent_id"]) if data.get("approved_agent_id") else None
            ),
        )


@dataclass(frozen=True, slots=True)
class McpAccessToken:
    """Short-lived MCP OAuth JWT and metadata from ``get_mcp_access_token()``."""

    access_token: str
    token_type: Literal["Bearer"]
    expires_in: int
    issued_at: float


@dataclass(frozen=True, slots=True)
class AgentProfile:
    """Authenticated agent profile from Core API."""

    agent_id: str
    owner_id: str
    display_name: str | None
    avatar_url: str | None
    description: str | None
    owner_kyc_level: int | None
    agent_reputation: int | None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> AgentProfile:
        """Parse profile JSON; accepts wire ``user_id`` / ``user_kyc_level`` aliases."""
        owner_id = data.get("owner_id") or data.get("user_id")
        if owner_id is None:
            raise KeyError("owner_id")
        owner_kyc_level = data.get("owner_kyc_level")
        if owner_kyc_level is None:
            owner_kyc_level = data.get("user_kyc_level")
        return cls(
            agent_id=str(data["agent_id"]),
            owner_id=str(owner_id),
            display_name=data.get("display_name"),
            avatar_url=data.get("avatar_url"),
            description=data.get("description"),
            owner_kyc_level=owner_kyc_level,
            agent_reputation=data.get("agent_reputation"),
        )
