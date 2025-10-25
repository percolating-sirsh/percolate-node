"""Integration test for MCP agent with tool calling.

This test demonstrates:
1. Loading an agent schema with MCP tool references
2. Tool registration and wrapping
3. Agent execution with tool calling
4. Structured output validation
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from agents import AgentContext, create_agent


async def test_mcp_agent_with_calculator():
    """Test agent calling calculator tool."""
    print("\n=== Test 1: Agent with Calculator Tool ===\n")

    # Create context
    ctx = AgentContext(
        tenant_id="test-tenant",
        agent_schema_uri="mcp-agent",
    )

    # Create agent from schema
    print("Creating agent from schema...")
    agent = await create_agent(ctx)
    print(f"✓ Agent created: {agent}")
    print(f"✓ Tools loaded: {len(agent._function_tools)} tools")

    # Test with calculation query
    prompt = "What is 15 multiplied by 23?"
    print(f"\nPrompt: {prompt}")
    print("Running agent...")

    result = await agent.run(prompt)

    print("\n=== Result ===")
    print(f"Answer: {result.data.answer}")
    print(f"Reasoning: {result.data.reasoning}")
    print(f"Tools Used: {result.data.tools_used}")
    print(f"Confidence: {result.data.confidence}")

    # Verify tool was called
    assert result.data.tools_used, "Agent should have called tools"
    assert "calculator" in result.data.tools_used, "Calculator tool should be used"
    assert "345" in result.data.answer, "Answer should contain 345"

    print("\n✓ Test passed!")


async def test_mcp_agent_with_weather():
    """Test agent calling weather tool."""
    print("\n=== Test 2: Agent with Weather Tool ===\n")

    ctx = AgentContext(
        tenant_id="test-tenant",
        agent_schema_uri="mcp-agent",
    )

    agent = await create_agent(ctx)

    prompt = "What's the weather in London?"
    print(f"Prompt: {prompt}")
    print("Running agent...")

    result = await agent.run(prompt)

    print("\n=== Result ===")
    print(f"Answer: {result.data.answer}")
    print(f"Reasoning: {result.data.reasoning}")
    print(f"Tools Used: {result.data.tools_used}")
    print(f"Confidence: {result.data.confidence}")

    # Verify tool was called
    assert result.data.tools_used, "Agent should have called tools"
    assert "get_weather" in result.data.tools_used, "Weather tool should be used"

    print("\n✓ Test passed!")


async def test_mcp_agent_with_multiple_tools():
    """Test agent using multiple tools."""
    print("\n=== Test 3: Agent with Multiple Tools ===\n")

    ctx = AgentContext(
        tenant_id="test-tenant",
        agent_schema_uri="mcp-agent",
    )

    agent = await create_agent(ctx)

    prompt = "Calculate 100 divided by 4, then tell me the weather in that city with that temperature."
    print(f"Prompt: {prompt}")
    print("Running agent...")

    result = await agent.run(prompt)

    print("\n=== Result ===")
    print(f"Answer: {result.data.answer}")
    print(f"Reasoning: {result.data.reasoning}")
    print(f"Tools Used: {result.data.tools_used}")
    print(f"Confidence: {result.data.confidence}")

    # Verify tools were called
    assert result.data.tools_used, "Agent should have called tools"
    assert "calculator" in result.data.tools_used, "Calculator tool should be used"

    print("\n✓ Test passed!")


async def test_tool_registration():
    """Test that tools are properly registered from schema."""
    print("\n=== Test 4: Tool Registration ===\n")

    ctx = AgentContext(
        tenant_id="test-tenant",
        agent_schema_uri="mcp-agent",
    )

    agent = await create_agent(ctx)

    # Check tools are registered
    print(f"Number of tools: {len(agent._function_tools)}")
    tool_names = [tool.name for tool in agent._function_tools]
    print(f"Tool names: {tool_names}")

    assert len(agent._function_tools) == 2, "Should have 2 tools"
    assert "calculator" in tool_names, "Should have calculator tool"
    assert "get_weather" in tool_names, "Should have get_weather tool"

    print("\n✓ Tool registration verified!")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("MCP Agent Integration Tests")
    print("=" * 60)

    try:
        # Test tool registration
        await test_tool_registration()

        # Test individual tools
        await test_mcp_agent_with_calculator()
        await test_mcp_agent_with_weather()

        # Test multiple tool usage
        await test_mcp_agent_with_multiple_tools()

        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
