from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass(frozen=True, slots=True)
class ApprovalResult:
    request_id: str
    site_id: str
    status: str
    expires_at: datetime
    approved_agent_id: str | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> ApprovalResult:
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
    access_token: str
    token_type: Literal["Bearer"]
    expires_in: int
    issued_at: float


@dataclass(frozen=True, slots=True)
class AgentProfile:
    agent_id: str
    owner_id: str
    display_name: str | None
    avatar_url: str | None
    description: str | None
    owner_kyc_level: int | None
    agent_reputation: int | None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> AgentProfile:
        return cls(
            agent_id=str(data["agent_id"]),
            owner_id=str(data["owner_id"]),
            display_name=data.get("display_name"),
            avatar_url=data.get("avatar_url"),
            description=data.get("description"),
            owner_kyc_level=data.get("owner_kyc_level"),
            agent_reputation=data.get("agent_reputation"),
        )
