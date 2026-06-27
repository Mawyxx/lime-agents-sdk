"""Official Python SDK for LIME AI agent workers."""

from mcp.types import (
    CallToolResult,
    GetPromptResult,
    Prompt,
    ReadResourceResult,
    Resource,
    ResourceTemplate,
    ServerCapabilities,
    Tool,
)

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

__version__ = "0.5.0"

__all__ = [
    "AgentProfile",
    "ApiError",
    "ApprovalResult",
    "AuthenticationError",
    "CallToolResult",
    "GetPromptResult",
    "LimeAgent",
    "LimeError",
    "McpAccessToken",
    "McpAuthenticationError",
    "OAuthCapabilityError",
    "PowTimeoutError",
    "Prompt",
    "RateLimitError",
    "ReadResourceResult",
    "Resource",
    "ResourceTemplate",
    "ServerCapabilities",
    "Tool",
    "__version__",
]
