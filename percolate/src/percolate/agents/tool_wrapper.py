"""Utility to create Pydantic AI-compatible wrappers for MCP tools.

Provides functionality to dynamically create Tool instances from MCP tool functions.
Uses Tool.from_schema() with explicit JSON schema and takes_ctx=False to bridge
FastMCP tools (which expect a Context parameter) to Pydantic AI tools.

Key insight: The docstring of the MCP tool IS the system prompt - avoid duplication
by stripping model-level descriptions when they match the system prompt.
"""

import inspect
import json
from typing import Any, Callable, get_type_hints

from pydantic_ai.tools import Tool


def create_pydantic_tool(mcp_tool_func: Callable) -> Tool:
    """Create a Pydantic AI Tool instance from an MCP tool function.

    Uses Tool.from_schema() to explicitly define the schema without ctx parameter.
    This bridges FastMCP tools (with ctx) to Pydantic AI tools (without ctx).

    Note: MCP tools expect a Context parameter which we pass as None. The tool's
    docstring becomes the description in the LLM prompt.

    Args:
        mcp_tool_func: The original MCP tool function (with ctx parameter)

    Returns:
        A Pydantic AI Tool instance that calls the MCP tool with ctx=None

    Example:
        from percolate.mcplib.tools.search import search_memory

        # Create tool
        tool = create_pydantic_tool(search_memory)

        # Register with agent
        agent = Agent(model, tools=[tool])
    """
    # Get the original signature and type hints
    sig = inspect.signature(mcp_tool_func)
    type_hints = get_type_hints(mcp_tool_func)

    # Get function metadata
    func_name = mcp_tool_func.__name__
    doc = mcp_tool_func.__doc__ or ""

    # Build JSON schema for parameters (excluding 'ctx')
    properties = {}
    required = []
    has_ctx = False

    for name, param in sig.parameters.items():
        if name == "ctx":
            has_ctx = True
            continue

        # Get type annotation
        param_type = type_hints.get(name, Any)

        # Build JSON schema property
        prop_schema: dict[str, Any] = {"type": _python_type_to_json_type(param_type)}

        # Use parameter name as description
        prop_schema["description"] = f"{name} parameter"

        properties[name] = prop_schema

        # Mark as required if no default value
        if param.default == inspect.Parameter.empty:
            required.append(name)

    # Build full JSON schema
    json_schema = {
        "type": "object",
        "properties": properties,
        "required": required,
    }

    # Create wrapper function that calls MCP tool
    # Only pass ctx=None if the original function has a ctx parameter
    async def wrapper(**kwargs: Any) -> Any:
        """Wrapper that calls MCP tool."""
        if has_ctx:
            return await mcp_tool_func(ctx=None, **kwargs)
        else:
            return await mcp_tool_func(**kwargs)

    # Create Tool using from_schema
    return Tool.from_schema(
        function=wrapper,
        name=func_name,
        description=doc.strip(),
        json_schema=json_schema,
        takes_ctx=False,  # Explicitly declare this tool does not take context
    )


def _python_type_to_json_type(python_type: Any) -> str:
    """Convert Python type hint to JSON schema type.

    Simplified converter for basic types. For production, consider using
    Pydantic's TypeAdapter for more robust type conversion.

    Args:
        python_type: Python type hint

    Returns:
        JSON schema type string
    """
    # Handle basic types
    if python_type == str or python_type == "str":
        return "string"
    elif python_type == int or python_type == "int":
        return "integer"
    elif python_type == float or python_type == "float":
        return "number"
    elif python_type == bool or python_type == "bool":
        return "boolean"

    # For complex types, default to string
    # TODO: Handle Union, Optional, List, Dict properly
    return "string"
