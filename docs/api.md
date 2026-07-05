# API Reference

Human-readable index below. Each method has its **own section** with signature, parameters,
return value, and errors.

HTTP route tables live in [LIME platform docs](https://lime.pics/docs) — not duplicated here.

---

## `LimeAgent` — method index

| Method | What it does | Returns |
|--------|--------------|---------|
| [`LimeAgent()`](#limeagent) | Create client; reads `LIME_AGENT_TOKEN` | `LimeAgent` |
| [`login()`](#login) | PoW + approve one site-login request | `ApprovalResult` |
| [`get_profile()`](#get_profile) | Fetch agent Core profile | `AgentProfile` |
| [`get_mcp_access_token()`](#get_mcp_access_token) | Raw MCP JWT (optional; MCP methods auto-issue) | `McpAccessToken` |
| [`list_tools()`](#list_tools) | List tools on external MCP server | `list[Tool]` |
| [`call_tool()`](#call_tool) | Run one MCP tool | `CallToolResult` |
| [`list_resources()`](#list_resources) | List MCP resources | `list[Resource]` |
| [`read_resource()`](#read_resource) | Read one MCP resource URI | `ReadResourceResult` |
| [`list_prompts()`](#list_prompts) | List MCP prompts | `list[Prompt]` |
| [`get_prompt()`](#get_prompt) | Fetch one MCP prompt | `GetPromptResult` |
| [`mcp_session()`](#mcp_session) | Low-level MCP session context manager | `ClientSession` |
| [`aclose()`](#aclose) | Close HTTP + MCP connections | `None` |

!!! tip "Typical flows"
    **Site login worker:** `LimeAgent()` → `login(request_id)` → done (site gets JWT via SSE).

    **MCP worker:** `LimeAgent()` → `list_tools(url)` → `call_tool(url, name, args)`.
    No manual OAuth step.

---

## Class overview

::: lime_agents.LimeAgent
    options:
      heading_level: 2
      show_root_heading: true
      members: false
      show_docstring_attributes: false

---

## Lifecycle

### `LimeAgent()`

::: lime_agents.LimeAgent.__init__
    options:
      heading_level: 4
      show_root_heading: true
      show_symbol_type_heading: false

### `aclose()`

::: lime_agents.LimeAgent.aclose
    options:
      heading_level: 4
      show_root_heading: true
      show_symbol_type_heading: false

---

## Site login

### `login()`

::: lime_agents.LimeAgent.login
    options:
      heading_level: 4
      show_root_heading: true
      show_symbol_type_heading: false

---

## Profile

### `get_profile()`

::: lime_agents.LimeAgent.get_profile
    options:
      heading_level: 4
      show_root_heading: true
      show_symbol_type_heading: false

---

## MCP OAuth (optional)

### `get_mcp_access_token()`

::: lime_agents.LimeAgent.get_mcp_access_token
    options:
      heading_level: 4
      show_root_heading: true
      show_symbol_type_heading: false

---

## MCP — tools & resources

All MCP methods take **`server_url`**: full streamable HTTP endpoint (e.g. `https://host/mcp`).
OAuth JWT is attached automatically.

### `list_tools()`

::: lime_agents.LimeAgent.list_tools
    options:
      heading_level: 4
      show_root_heading: true
      show_symbol_type_heading: false

### `call_tool()`

::: lime_agents.LimeAgent.call_tool
    options:
      heading_level: 4
      show_root_heading: true
      show_symbol_type_heading: false

### `list_resources()`

::: lime_agents.LimeAgent.list_resources
    options:
      heading_level: 4
      show_root_heading: true
      show_symbol_type_heading: false

### `read_resource()`

::: lime_agents.LimeAgent.read_resource
    options:
      heading_level: 4
      show_root_heading: true
      show_symbol_type_heading: false

### `list_prompts()`

::: lime_agents.LimeAgent.list_prompts
    options:
      heading_level: 4
      show_root_heading: true
      show_symbol_type_heading: false

### `get_prompt()`

::: lime_agents.LimeAgent.get_prompt
    options:
      heading_level: 4
      show_root_heading: true
      show_symbol_type_heading: false

### `mcp_session()`

::: lime_agents.LimeAgent.mcp_session
    options:
      heading_level: 4
      show_root_heading: true
      show_symbol_type_heading: false

---

## Result types

### `ApprovalResult`

::: lime_agents.ApprovalResult
    options:
      heading_level: 3
      show_root_heading: true

### `AgentProfile`

::: lime_agents.AgentProfile
    options:
      heading_level: 3
      show_root_heading: true

### `McpAccessToken`

::: lime_agents.McpAccessToken
    options:
      heading_level: 3
      show_root_heading: true

---

## Errors

| Exception | When |
|-----------|------|
| `AuthenticationError` | Missing `LIME_AGENT_TOKEN` |
| `PowTimeoutError` | PoW not solved in time |
| `ApiError` | LIME API returned business error |
| `McpAuthenticationError` | MCP server rejected OAuth JWT |
| `OAuthCapabilityError` | OAuth token endpoint unavailable |
| `RateLimitError` | HTTP 429 from LIME |

### `LimeError`

::: lime_agents.LimeError
    options:
      heading_level: 4
      show_root_heading: true

### `AuthenticationError`

::: lime_agents.AuthenticationError
    options:
      heading_level: 4
      show_root_heading: true

### `PowTimeoutError`

::: lime_agents.PowTimeoutError
    options:
      heading_level: 4
      show_root_heading: true

### `RateLimitError`

::: lime_agents.RateLimitError
    options:
      heading_level: 4
      show_root_heading: true

### `ApiError`

::: lime_agents.ApiError
    options:
      heading_level: 4
      show_root_heading: true

### `McpAuthenticationError`

::: lime_agents.McpAuthenticationError
    options:
      heading_level: 4
      show_root_heading: true

### `OAuthCapabilityError`

::: lime_agents.OAuthCapabilityError
    options:
      heading_level: 4
      show_root_heading: true
