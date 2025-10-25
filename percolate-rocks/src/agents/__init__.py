"""Agent-let framework for Percolate-Rocks.

This module provides the agent-let factory pattern using Pydantic AI:
- AgentContext: Execution context with tenant isolation
- create_agent: Factory function for building agents from schemas
- create_pydantic_tool: MCP tool wrapper for Pydantic AI
- load_agentlet_schema: Schema loading from percolate-rocks DB

Key patterns from carrier:
- Dynamic model generation from JSON Schema
- Schema wrapper to strip descriptions (docstring IS system prompt)
- MCP tool dynamic loading and wrapping
- Context propagation through execution stack
"""

from .context import AgentContext
from .factory import create_agent
from .registry import load_agentlet_schema
from .tool_wrapper import create_pydantic_tool

__all__ = [
    "AgentContext",
    "create_agent",
    "create_pydantic_tool",
    "load_agentlet_schema",
]
