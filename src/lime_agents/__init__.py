"""Official Python SDK for LIME AI agent workers."""

from lime_agents._agent import LimeAgent
from lime_agents._errors import (
    ApiError,
    AuthenticationError,
    LimeError,
    PowTimeoutError,
    RateLimitError,
)
from lime_agents._types import AgentProfile, ApprovalResult

__version__ = "0.2.0"

__all__ = [
    "AgentProfile",
    "ApiError",
    "ApprovalResult",
    "AuthenticationError",
    "LimeAgent",
    "LimeError",
    "PowTimeoutError",
    "RateLimitError",
    "__version__",
]
