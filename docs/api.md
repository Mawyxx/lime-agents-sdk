# API Reference

New to this SDK? Read [Home](index.md) first — two scenarios and the method table.

HTTP routes: [LIME platform docs](https://lime.pics/docs).

## Signature cheat sheet

Readable overview before auto-generated details below.

<div class="sig-cheat" markdown="1">

=== "Scenario 1 — Site login"

    ```python
    agent = LimeAgent(agent_token: str | None = None, ...)

    await agent.login(request_id: str) -> ApprovalResult

    await agent.get_profile() -> AgentProfile
    ```

=== "Scenario 2 — MCP tools"

    ```python
    await agent.list_tools(server_url: str) -> list[Tool]

    await agent.call_tool(
        server_url: str,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> CallToolResult

    await agent.get_mcp_access_token(*, force_refresh: bool = False) -> McpAccessToken
    ```

=== "Setup / cleanup"

    ```python
    async with LimeAgent() as agent: ...   # calls aclose() on exit

    await agent.aclose() -> None
    ```

</div>

Minimum setup: `LimeAgent()` reads `LIME_AGENT_TOKEN` from the environment.

## Methods by scenario

=== "Scenario 1 — Site login"

    | Method | Returns |
    |--------|---------|
    | [`login()`](#lime_agents.LimeAgent.login) | `ApprovalResult` |
    | [`get_profile()`](#lime_agents.LimeAgent.get_profile) | `AgentProfile` (optional) |

=== "Scenario 2 — MCP tools"

    | Method | Returns |
    |--------|---------|
    | [`list_tools()`](#lime_agents.LimeAgent.list_tools) | `list[Tool]` |
    | [`call_tool()`](#lime_agents.LimeAgent.call_tool) | `CallToolResult` |
    | [`list_resources()`](#lime_agents.LimeAgent.list_resources) | `list[Resource]` |
    | [`read_resource()`](#lime_agents.LimeAgent.read_resource) | `ReadResourceResult` |
    | [`list_prompts()`](#lime_agents.LimeAgent.list_prompts) | `list[Prompt]` |
    | [`get_prompt()`](#lime_agents.LimeAgent.get_prompt) | `GetPromptResult` |
    | [`get_mcp_access_token()`](#lime_agents.LimeAgent.get_mcp_access_token) | `McpAccessToken` (rare) |

=== "Setup (both)"

    | Method | Returns |
    |--------|---------|
    | [`LimeAgent()`](#lime_agents.LimeAgent.__init__) | client |
    | [`aclose()`](#lime_agents.LimeAgent.aclose) | `None` |

## Class overview

::: lime_agents.LimeAgent
    options:
      heading_level: 2
      show_root_heading: true
      members: false

## Lifecycle

::: lime_agents.LimeAgent.__init__
    options:
      heading_level: 3
      show_root_heading: true
      show_symbol_type_heading: false

::: lime_agents.LimeAgent.aclose
    options:
      heading_level: 3
      show_root_heading: true
      show_symbol_type_heading: false

## Site login

::: lime_agents.LimeAgent.login
    options:
      heading_level: 3
      show_root_heading: true
      show_symbol_type_heading: false

## Profile

::: lime_agents.LimeAgent.get_profile
    options:
      heading_level: 3
      show_root_heading: true
      show_symbol_type_heading: false

## MCP OAuth (optional)

::: lime_agents.LimeAgent.get_mcp_access_token
    options:
      heading_level: 3
      show_root_heading: true
      show_symbol_type_heading: false

## MCP — tools and resources

All MCP methods take `server_url` (full HTTP MCP endpoint). OAuth JWT is attached
automatically with **lazy refresh** (see [MCP OAuth & pool](mcp-oauth.md)).

::: lime_agents.LimeAgent.list_tools
    options:
      heading_level: 3
      show_root_heading: true
      show_symbol_type_heading: false

::: lime_agents.LimeAgent.call_tool
    options:
      heading_level: 3
      show_root_heading: true
      show_symbol_type_heading: false

::: lime_agents.LimeAgent.list_resources
    options:
      heading_level: 3
      show_root_heading: true
      show_symbol_type_heading: false

::: lime_agents.LimeAgent.read_resource
    options:
      heading_level: 3
      show_root_heading: true
      show_symbol_type_heading: false

::: lime_agents.LimeAgent.list_prompts
    options:
      heading_level: 3
      show_root_heading: true
      show_symbol_type_heading: false

::: lime_agents.LimeAgent.get_prompt
    options:
      heading_level: 3
      show_root_heading: true
      show_symbol_type_heading: false

::: lime_agents.LimeAgent.mcp_session
    options:
      heading_level: 3
      show_root_heading: true
      show_symbol_type_heading: false

## Result types

::: lime_agents.ApprovalResult
    options:
      heading_level: 3
      show_root_heading: true

::: lime_agents.AgentProfile
    options:
      heading_level: 3
      show_root_heading: true

::: lime_agents.McpAccessToken
    options:
      heading_level: 3
      show_root_heading: true

## Errors

| Exception | When |
|-----------|------|
| `AuthenticationError` | Missing `LIME_AGENT_TOKEN` |
| `PowTimeoutError` | PoW not solved in time |
| `ApiError` | LIME API business error |
| `McpAuthenticationError` | MCP server rejected OAuth JWT |
| `OAuthCapabilityError` | OAuth token endpoint unavailable |
| `RateLimitError` | HTTP 429 from LIME |

::: lime_agents.LimeError
    options:
      heading_level: 3
      show_root_heading: true

::: lime_agents.AuthenticationError
    options:
      heading_level: 3
      show_root_heading: true

::: lime_agents.PowTimeoutError
    options:
      heading_level: 3
      show_root_heading: true

::: lime_agents.RateLimitError
    options:
      heading_level: 3
      show_root_heading: true

::: lime_agents.ApiError
    options:
      heading_level: 3
      show_root_heading: true

::: lime_agents.McpAuthenticationError
    options:
      heading_level: 3
      show_root_heading: true

::: lime_agents.OAuthCapabilityError
    options:
      heading_level: 3
      show_root_heading: true
