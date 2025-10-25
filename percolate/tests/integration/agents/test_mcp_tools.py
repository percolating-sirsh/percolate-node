"""Integration tests for MCP agent tool calling.

Tests the agent-let framework with real MCP tools:
- Tool registration from schema
- Tool invocation during agent execution
- Structured output validation
"""

import pytest

from percolate.agents.context import AgentContext
from percolate.agents.factory import create_agent


@pytest.mark.asyncio
async def test_tool_registration():
    """Test that MCP tools are registered from agent schema."""
    ctx = AgentContext(
        tenant_id="test-tenant",
        agent_schema_uri="mcp-agent",
    )

    agent = await create_agent(ctx)

    # Verify tools are loaded
    toolset = agent._function_toolset
    assert toolset is not None, "Should have function toolset"
    assert len(toolset.tools) == 3, "Should have 3 tools"

    # Tools is a dict mapping name -> tool
    tool_names = set(toolset.tools.keys())
    assert "search_knowledge_base" in tool_names
    assert "parse_document" in tool_names
    assert "ask_agent" in tool_names


@pytest.mark.asyncio
@pytest.mark.skipif(
    "ANTHROPIC_API_KEY" not in __import__("os").environ,
    reason="Requires ANTHROPIC_API_KEY",
)
async def test_agent_with_search_tool():
    """Test agent calling search_knowledge_base tool."""
    ctx = AgentContext(
        tenant_id="test-tenant",
        agent_schema_uri="mcp-agent",
    )

    agent = await create_agent(ctx)

    result = await agent.run("Search for information about REM memory")

    # Print result for inspection
    print(f"\n--- Agent Output ---")
    print(f"Answer: {result.output.answer}")
    print(f"Reasoning: {result.output.reasoning}")
    print(f"Tools Used: {result.output.tools_used}")
    print(f"Confidence: {result.output.confidence}")

    # Verify structured output (result.output is the Pydantic model)
    assert result.output.answer
    assert result.output.reasoning
    assert result.output.tools_used
    assert isinstance(result.output.confidence, float)
    assert 0.0 <= result.output.confidence <= 1.0

    # Verify tool was used
    assert "search_knowledge_base" in result.output.tools_used


@pytest.mark.asyncio
@pytest.mark.skipif(
    "ANTHROPIC_API_KEY" not in __import__("os").environ,
    reason="Requires ANTHROPIC_API_KEY",
)
async def test_agent_with_parse_tool():
    """Test agent calling parse_document tool."""
    ctx = AgentContext(
        tenant_id="test-tenant",
        agent_schema_uri="mcp-agent",
    )

    agent = await create_agent(ctx)

    result = await agent.run("Parse the document at /tmp/test.pdf")

    # Print result for inspection
    print(f"\n--- Agent Output ---")
    print(f"Answer: {result.output.answer}")
    print(f"Reasoning: {result.output.reasoning}")
    print(f"Tools Used: {result.output.tools_used}")
    print(f"Confidence: {result.output.confidence}")

    # Verify structured output
    assert result.output.answer
    assert result.output.reasoning
    assert isinstance(result.output.tools_used, list)

    # Verify parse tool was used
    assert "parse_document" in result.output.tools_used


@pytest.mark.asyncio
@pytest.mark.skipif(
    "ANTHROPIC_API_KEY" not in __import__("os").environ,
    reason="Requires ANTHROPIC_API_KEY",
)
async def test_agent_with_ask_agent_tool():
    """Test agent calling ask_agent tool."""
    ctx = AgentContext(
        tenant_id="test-tenant",
        agent_schema_uri="mcp-agent",
    )

    agent = await create_agent(ctx)

    result = await agent.run("Ask the test-agent: What is 2+2?")

    # Verify structured output
    assert result.output.answer
    assert result.output.reasoning
    assert isinstance(result.output.tools_used, list)

    # Verify ask_agent tool was used
    assert "ask_agent" in result.output.tools_used
