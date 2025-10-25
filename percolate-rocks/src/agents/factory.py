"""Pydantic AI agent factory with dynamic MCP tool integration.

This factory creates Pydantic AI agents from agent-let schemas (JSON).
Key patterns from carrier reference:
- Schema dumper to avoid sending system prompt twice (docstring IS the prompt)
- MCP tool factory for dynamic tool attachment from schema
- percolate-rocks database integration for agent persistence
- Tenant isolation for user agent-lets
"""

from typing import Any

from pydantic import BaseModel, Field, create_model
from pydantic_ai import Agent
from pydantic_ai.models import KnownModelName, Model

from .context import AgentContext
from .registry import load_agentlet_schema
from .tool_wrapper import create_pydantic_tool


def _create_model_from_schema(json_schema: dict[str, Any]) -> type[BaseModel]:
    """Create a dynamic Pydantic model from JSON Schema.

    Converts agent-let JSON schema to a Pydantic model for structured output.
    Handles basic types (string, number, boolean, array) and required fields.

    Args:
        json_schema: JSON Schema dict with properties and required fields

    Returns:
        Dynamically created Pydantic model class
    """
    properties = json_schema.get("properties", {})
    required = json_schema.get("required", [])
    model_name = json_schema.get("title", "DynamicAgent")

    # Map JSON schema types to Python types
    type_map = {
        "string": str,
        "number": float,
        "integer": int,
        "boolean": bool,
        "array": list,
        "object": dict,
    }

    # Build field definitions for create_model
    field_definitions = {}
    for field_name, field_spec in properties.items():
        field_type = type_map.get(field_spec.get("type", "string"), str)
        field_description = field_spec.get("description", "")

        # Handle array types with items
        if field_spec.get("type") == "array" and "items" in field_spec:
            item_type = type_map.get(field_spec["items"].get("type", "string"), str)
            field_type = list[item_type]  # type: ignore

        # Determine if required
        if field_name in required:
            field_definitions[field_name] = (field_type, Field(description=field_description))
        else:
            field_definitions[field_name] = (field_type | None, Field(default=None, description=field_description))

    # Create dynamic model
    return create_model(model_name, **field_definitions)


def _create_schema_wrapper(result_type: type[BaseModel], strip_description: bool = True) -> type[BaseModel]:
    """Create a wrapper model that customizes schema generation.

    IMPORTANT: This prevents redundant descriptions in the LLM schema while keeping
    docstrings in our Python code for documentation. The model's docstring IS used
    as the system prompt, so we strip it from the schema sent to the LLM to avoid
    duplication (LLM sees system prompt + schema, not system prompt + schema with
    same description repeated).

    Args:
        result_type: Original Pydantic model with docstring
        strip_description: If True, removes model-level description from schema

    Returns:
        Wrapper model that generates schema without description field
    """
    if not strip_description:
        return result_type

    # Create a model that overrides schema generation
    class SchemaWrapper(result_type):  # type: ignore
        @classmethod
        def model_json_schema(cls, **kwargs):
            schema = super().model_json_schema(**kwargs)
            # Remove model-level description to avoid duplication with system prompt
            schema.pop("description", None)
            return schema

    # Preserve the original model name for debugging
    SchemaWrapper.__name__ = result_type.__name__
    return SchemaWrapper


async def create_agent(
    context: AgentContext | None = None,
    agent_schema_override: dict[str, Any] | None = None,
    model_override: KnownModelName | Model | None = None,
    result_type: type[BaseModel] | None = None,
    strip_model_description: bool = True,
) -> Agent:
    """Create a Pydantic AI agent from context or explicit schema.

    All configuration comes from context (agent schema, model, etc.)
    unless explicitly overridden. MCP tools are dynamically loaded from
    schema metadata and wrapped for Pydantic AI compatibility.

    Agent-let schemas are loaded from percolate-rocks database or filesystem.
    User agent-lets are tenant-scoped for isolation.

    Args:
        context: AgentContext with schema URI, model, tenant_id, db_path
        agent_schema_override: Optional explicit schema (bypasses context.agent_schema_uri)
        model_override: Optional explicit model (bypasses context.default_model)
        result_type: Optional Pydantic model for structured output
        strip_model_description: If True, removes model docstring from LLM schema
                                to avoid duplication with system prompt (default: True)

    Returns:
        Configured Pydantic AI Agent with MCP tools

    Example:
        >>> schema = {"description": "Research assistant...", "tools": [...]}
        >>> ctx = AgentContext(tenant_id="tenant-123")
        >>> agent = await create_agent(ctx, agent_schema_override=schema)
        >>> result = await agent.run("What is percolate?")
    """
    # Load agent schema from context or use override
    agent_schema = agent_schema_override
    if agent_schema is None and context and context.agent_schema_uri:
        # Load from percolate-rocks database or filesystem
        agent_schema = load_agentlet_schema(
            uri=context.agent_schema_uri,
            tenant_id=context.tenant_id,
            db_path=context.db_path
        )

    # Determine model: override > context.default_model > default
    model = model_override or (context.default_model if context else "claude-sonnet-4.5")

    # Extract schema fields
    system_prompt = agent_schema.get("description", "") if agent_schema else ""
    metadata = agent_schema.get("json_schema_extra", {}) if agent_schema else {}
    tool_configs = metadata.get("tools", [])

    # Build list of Tool instances from MCP tool configs
    tools = []
    if tool_configs:
        tools = await _build_mcp_tools(tool_configs, context)

    # Determine result_type: explicit > derive from schema
    final_result_type = result_type
    if final_result_type is None and agent_schema and "properties" in agent_schema:
        # Create dynamic Pydantic model from JSON schema
        final_result_type = _create_model_from_schema(agent_schema)

    # Create agent with optional output_type for structured output and tools
    if final_result_type:
        # Wrap the result_type to strip description if needed
        wrapped_result_type = _create_schema_wrapper(final_result_type, strip_description=strip_model_description)
        agent = Agent(model=model, system_prompt=system_prompt, result_type=wrapped_result_type, tools=tools)
    else:
        agent = Agent(model=model, system_prompt=system_prompt, tools=tools)

    return agent


async def _build_mcp_tools(tool_configs: list[dict[str, str]], context: AgentContext | None) -> list:
    """Build list of Pydantic AI Tool instances from MCP tool configs.

    For "percolate" or "default" server, uses local MCP tools directly.
    For other servers, would resolve URLs from environment variables (not implemented).

    Args:
        tool_configs: List of tool configurations with mcp_server and tool_name
        context: Agent context for percolate-rocks database access

    Returns:
        List of Pydantic AI Tool instances

    Example tool_config:
        {"mcp_server": "percolate", "tool_name": "search_memory", "usage": "..."}
        -> Creates Tool from local search_memory function
    """
    tools = []

    # Group tools by MCP server
    tools_by_server: dict[str, list[dict[str, str]]] = {}
    for tool_config in tool_configs:
        server_name = tool_config["mcp_server"]
        tools_by_server.setdefault(server_name, []).append(tool_config)

    # Process each server
    for server_name, tool_config_list in tools_by_server.items():
        # "percolate", "default", or "demo" -> use local tools
        if server_name in ("percolate", "default", "demo"):
            server_tools = _build_local_tools(tool_config_list, context)
            tools.extend(server_tools)
        else:
            # Remote server -> not yet implemented
            print(f"WARNING: Remote MCP server '{server_name}' not yet supported")

    return tools


def _build_local_tools(tool_configs: list[dict[str, str]], context: AgentContext | None) -> list:
    """Build Tool instances from local MCP tools.

    Uses create_pydantic_tool() to wrap MCP functions with explicit schema
    and takes_ctx=False.

    Args:
        tool_configs: List of tool configurations
        context: Agent context for database access

    Returns:
        List of Tool instances
    """
    # Import MCP tools (add more as needed)
    # Pattern from carrier project: conditional imports to avoid hard dependencies
    mcp_tools = {}

    # Try to import demo MCP tools
    try:
        from mcp_tools import calculator
        mcp_tools["calculator"] = calculator
    except ImportError:
        print("DEBUG: calculator tool not available")

    try:
        from mcp_tools import get_weather
        mcp_tools["get_weather"] = get_weather
    except ImportError:
        print("DEBUG: get_weather tool not available")

    tools = []

    for tool_config in tool_configs:
        tool_name = tool_config["tool_name"]

        if tool_name in mcp_tools:
            mcp_tool_func = mcp_tools[tool_name]

            # Create Pydantic AI Tool instance with explicit schema
            tool = create_pydantic_tool(mcp_tool_func)
            tools.append(tool)
            print(f"INFO: Built local tool: {tool_name}")
        else:
            print(f"WARNING: Local tool '{tool_name}' not found in mcp_tools map")

    return tools
