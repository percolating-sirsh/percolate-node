"""Pydantic AI agent factory with dynamic MCP tool integration.

This factory creates Pydantic AI agents from agent-let schemas (JSON).
Key patterns from carrier reference:
- Schema dumper to avoid sending system prompt twice (docstring IS the prompt)
- MCP tool factory for dynamic tool attachment from schema
- OpenTelemetry instrumentation (disabled by default in settings)
"""

from __future__ import annotations

from typing import Any

from json_schema_to_pydantic import PydanticModelBuilder
from loguru import logger
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models import KnownModelName, Model

from percolate.agents.context import AgentContext
from percolate.agents.registry import load_agentlet_schema
from percolate.agents.tool_wrapper import create_pydantic_tool
from percolate.otel import (
    set_agent_context_attributes,
    set_agent_resource_attributes,
    setup_instrumentation,
)
from percolate.settings import settings


def _create_model_from_schema(agent_schema: dict[str, Any]) -> type[BaseModel]:
    """Create Pydantic model dynamically from agent schema using json-schema-to-pydantic.

    Uses the json-schema-to-pydantic library for robust conversion that properly handles:
    - Nested objects and arrays
    - Complex type definitions ($ref, anyOf, allOf, etc.)
    - Required fields and defaults
    - Field descriptions and constraints
    - Recursive schema definitions

    Args:
        agent_schema: Agent schema dict (JSON Schema format)

    Returns:
        Dynamically created Pydantic BaseModel class

    Example:
        >>> schema = {
        ...     "title": "ResearchAgent",
        ...     "type": "object",
        ...     "properties": {
        ...         "findings": {"type": "array", "items": {"type": "string"}},
        ...         "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0}
        ...     }
        ... }
        >>> Model = _create_model_from_schema(schema)
        >>> instance = Model(findings=["fact 1", "fact 2"], confidence=0.9)
    """
    # Use json-schema-to-pydantic library for robust conversion
    # Handles nested objects, arrays, required fields, complex types, etc.
    builder = PydanticModelBuilder()
    model = builder.create_pydantic_model(agent_schema, root_schema=agent_schema)

    # Override model name with FQN if available (carrier pattern)
    fqn = agent_schema.get("fully_qualified_name")
    if fqn:
        class_name = fqn.rsplit(".", 1)[-1]
        model.__name__ = class_name
    # Fallback to title if no FQN (percolate pattern)
    elif "title" in agent_schema:
        model.__name__ = agent_schema["title"]

    logger.debug(f"Created dynamic Pydantic model from schema: {model.__name__}")
    return model


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

    Args:
        context: AgentContext with schema URI, model, session info
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
    # Initialize OTEL instrumentation if enabled (idempotent)
    setup_instrumentation()

    # Load agent schema from context or use override
    agent_schema = agent_schema_override
    if agent_schema is None and context and context.agent_schema_uri:
        # Load from percolate-rocks database or filesystem
        # Database location configured via percolate-rocks settings/env
        agent_schema = load_agentlet_schema(uri=context.agent_schema_uri, tenant_id=context.tenant_id)

    # Set agent resource attributes BEFORE creating agent (propagates to all spans)
    set_agent_resource_attributes(agent_schema=agent_schema)

    # Determine model: override > context.default_model > settings
    model = model_override or (context.default_model if context else settings.default_model)

    # Extract schema fields
    system_prompt = agent_schema.get("description", "") if agent_schema else ""
    metadata = agent_schema.get("json_schema_extra", {}) if agent_schema else {}
    tool_configs = metadata.get("tools", [])

    logger.info(f"Creating agent with model={model}, tools={len(tool_configs)}")

    # Build list of Tool instances from MCP tool configs
    tools = []
    if tool_configs:
        tools = await _build_mcp_tools(tool_configs)

    # Determine result_type: explicit > derive from schema
    final_result_type = result_type
    if final_result_type is None and agent_schema and "properties" in agent_schema:
        # Create dynamic Pydantic model from JSON schema
        final_result_type = _create_model_from_schema(agent_schema)

    # Create agent with optional output_type for structured output and tools
    # Enable OTEL instrumentation on agent (requires instrument=True for Pydantic AI)
    if final_result_type:
        # Wrap the result_type to strip description if needed
        wrapped_result_type = _create_schema_wrapper(
            final_result_type, strip_description=strip_model_description
        )
        agent = Agent(
            model=model,
            system_prompt=system_prompt,
            output_type=wrapped_result_type,
            tools=tools,
            instrument=True,  # Enable OTEL instrumentation
        )
    else:
        agent = Agent(
            model=model,
            system_prompt=system_prompt,
            tools=tools,
            instrument=True,  # Enable OTEL instrumentation
        )

    # Set OTEL span attributes for context tracking
    agentlet_name = context.agent_schema_uri if context else None
    set_agent_context_attributes(context=context, agentlet_name=agentlet_name, agent_schema=agent_schema)

    return agent


async def _build_mcp_tools(tool_configs: list[dict[str, str]]) -> list:
    """Build list of Pydantic AI Tool instances from MCP tool configs.

    For "percolate" or "default" server, uses local MCP tools directly.
    For other servers, would resolve URLs from environment variables (not implemented).

    Args:
        tool_configs: List of tool configurations with mcp_server and tool_name

    Returns:
        List of Pydantic AI Tool instances

    Example tool_config:
        {"mcp_server": "percolate", "tool_name": "search_memory", "usage": "..."}
        -> Creates Tool from percolate.mcplib.tools.search_memory
    """
    logger.debug(f"Building {len(tool_configs)} MCP tools")

    tools = []

    # Group tools by MCP server
    tools_by_server: dict[str, list[dict[str, str]]] = {}
    for tool_config in tool_configs:
        server_name = tool_config["mcp_server"]
        tools_by_server.setdefault(server_name, []).append(tool_config)

    # Process each server
    for server_name, tool_config_list in tools_by_server.items():
        # "percolate" or "default" -> use local tools
        if server_name in ("percolate", "default"):
            server_tools = _build_local_tools(tool_config_list)
            tools.extend(server_tools)
        else:
            # TODO: Remote server -> query MCP server for tool schemas
            # Should work like this:
            # 1. Look up server URL from env vars (e.g., MCP_SERVER_{NAME}_URL)
            # 2. Connect to MCP server (HTTP/SSE transport)
            # 3. Query tools/list endpoint to get available tools
            # 4. For each tool in tool_config_list, get schema from server
            # 5. Create Pydantic AI Tool that proxies calls to remote server
            #
            # Example:
            #   server_url = os.getenv(f"MCP_SERVER_{server_name.upper()}_URL")
            #   async with MCPClient(server_url) as client:
            #       available_tools = await client.list_tools()
            #       for tool_config in tool_config_list:
            #           tool_schema = available_tools[tool_config["tool_name"]]
            #           tool = create_remote_tool(client, tool_schema)
            #           server_tools.append(tool)
            logger.warning(f"Remote MCP server '{server_name}' not yet supported")

    return tools


def _build_local_tools(tool_configs: list[dict[str, str]]) -> list:
    """Build Tool instances from local MCP tools.

    Uses create_pydantic_tool() to wrap MCP functions with explicit schema
    and takes_ctx=False.

    Args:
        tool_configs: List of tool configurations

    Returns:
        List of Tool instances
    """
    # TODO: MCP servers should advertise their tools via the MCP protocol (tools/list).
    # This manual import approach does NOT scale and breaks for remote servers.
    #
    # Proper implementation:
    # 1. Query MCP server for available tools: GET /mcp/tools/list
    # 2. Server returns tool schemas (name, description, parameters, return type)
    # 3. Dynamically create Pydantic AI tools from schemas
    # 4. Works for both local AND remote MCP servers
    #
    # Current approach only works for local Python imports - won't work for:
    # - Remote MCP servers over HTTP/SSE
    # - MCP servers in different languages
    # - Third-party MCP servers
    #
    # See: https://spec.modelcontextprotocol.io/specification/server/tools/
    mcp_tools = {}

    # Try to import common MCP tools
    try:
        from percolate.mcplib.tools import search_knowledge_base
        mcp_tools["search_knowledge_base"] = search_knowledge_base
    except ImportError:
        logger.debug("search_knowledge_base tool not available")

    try:
        from percolate.mcplib.tools import lookup_entity
        mcp_tools["lookup_entity"] = lookup_entity
    except ImportError:
        logger.debug("lookup_entity tool not available")

    try:
        from percolate.mcplib.tools import parse_document
        mcp_tools["parse_document"] = parse_document
    except ImportError:
        logger.debug("parse_document tool not available")

    try:
        from percolate.mcplib.tools import ask_agent
        mcp_tools["ask_agent"] = ask_agent
    except ImportError:
        logger.debug("ask_agent tool not available")

    try:
        from percolate.mcplib.tools import create_agent
        mcp_tools["create_agent"] = create_agent
    except ImportError:
        logger.debug("create_agent tool not available")

    tools = []

    for tool_config in tool_configs:
        tool_name = tool_config["tool_name"]

        if tool_name in mcp_tools:
            mcp_tool_func = mcp_tools[tool_name]

            # Create Pydantic AI Tool instance with explicit schema
            tool = create_pydantic_tool(mcp_tool_func)
            tools.append(tool)
            logger.info(f"Built local tool: {tool_name}")
        else:
            logger.warning(f"Local tool '{tool_name}' not found in mcp_tools map")

    return tools
