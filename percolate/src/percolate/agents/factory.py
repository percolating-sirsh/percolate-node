"""Pydantic AI agent factory for agent-let creation."""

from typing import Any
from pydantic_ai import Agent
from pydantic_ai.models import KnownModelName, Model

from percolate.agents.context import AgentContext


async def create_agent(
    context: AgentContext,
    schema: dict[str, Any],
    model_override: KnownModelName | Model | None = None,
    result_type: type | None = None,
) -> Agent:
    """Create Pydantic AI agent from schema and context.

    Factory function that constructs a configured Pydantic AI agent from
    an agent-let schema (JSON) and execution context. Handles:
    - Model selection (override > context > schema)
    - System prompt extraction from schema
    - MCP tool attachment from schema tool references
    - Result type binding for structured outputs

    Args:
        context: Agent execution context (user, tenant, session)
        schema: Agent-let schema (JSON dict with metadata)
        model_override: Optional model to override context/schema
        result_type: Optional Pydantic model for structured output

    Returns:
        Configured Pydantic AI agent ready for execution

    Example:
        >>> schema = {"description": "Research assistant...", "tools": [...]}
        >>> ctx = AgentContext(tenant_id="tenant-123")
        >>> agent = await create_agent(ctx, schema)
        >>> result = await agent.run("What is percolate?")
    """
    # Determine model (override > context > default)
    model = model_override or context.default_model

    # Extract system prompt and metadata from schema
    system_prompt = schema.get("description", "")
    metadata = schema.get("json_schema_extra", {})
    tool_configs = metadata.get("tools", [])

    # Create base agent with model and prompt
    agent = Agent(
        model=model,
        system_prompt=system_prompt,
        result_type=result_type,
    )

    # Attach MCP tools if specified in schema
    if tool_configs:
        await _attach_mcp_tools(agent, tool_configs, context)

    return agent


async def _attach_mcp_tools(
    agent: Agent,
    tool_configs: list[dict[str, str]],
    context: AgentContext,
) -> None:
    """Attach MCP tools to agent dynamically.

    Groups tools by MCP server, connects to each server, and registers
    matching tools with the agent. Each tool becomes a callable function
    available to the agent during execution.

    Args:
        agent: Pydantic AI agent to attach tools to
        tool_configs: List of tool specifications from schema
        context: Agent context (for tenant scoping if needed)

    Example:
        >>> tool_configs = [
        ...     {"mcp_server": "percolate", "tool_name": "search_knowledge_base"}
        ... ]
        >>> await _attach_mcp_tools(agent, tool_configs, ctx)
    """
    # Group tools by server to minimize connections
    tools_by_server: dict[str, list[dict[str, str]]] = {}
    for tool_config in tool_configs:
        server_name = tool_config["mcp_server"]
        tools_by_server.setdefault(server_name, []).append(tool_config)

    # Connect to each MCP server and register tools
    # TODO: Implement MCP client connection and tool registration
    raise NotImplementedError("MCP tool attachment not yet implemented")


def _register_dynamic_tool(
    agent: Agent,
    tool_name: str,
    tool_description: str,
    tool_function: Any,
) -> None:
    """Register single dynamic tool with agent.

    Wraps MCP tool invocation in a Pydantic AI tool decorator, making it
    callable by the agent with proper type hints and documentation.

    Args:
        agent: Agent to register tool with
        tool_name: Tool identifier (e.g., 'search_knowledge_base')
        tool_description: Human-readable tool usage description
        tool_function: Async callable that invokes MCP tool

    Example:
        >>> async def search(**kwargs): ...
        >>> _register_dynamic_tool(agent, "search", "Search memory", search)
    """
    # Set function metadata for agent discovery
    tool_function.__name__ = tool_name
    tool_function.__doc__ = tool_description

    # Register with Pydantic AI
    agent.tool()(tool_function)
