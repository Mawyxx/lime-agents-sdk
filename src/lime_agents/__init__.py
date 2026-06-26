"""Official Python SDK for LIME AI agent workers."""

from lime_agents._agent import LimeAgent
from lime_agents._errors import (
    ApiError,
    AuthenticationError,
    LimeError,
    McpAuthenticationError,
    OAuthCapabilityError,
    PowTimeoutError,
    RateLimitError,
)
from lime_agents._types import AgentProfile, ApprovalResult, McpAccessToken

__version__ = "0.3.0"

__all__ = [
    "AgentProfile",
    "ApiError",
    "ApprovalResult",
    "AuthenticationError",
    "LimeAgent",
    "LimeError",
    "McpAccessToken",
    "McpAuthenticationError",
    "OAuthCapabilityError",
    "PowTimeoutError",
    "RateLimitError",
    "__version__",
]
