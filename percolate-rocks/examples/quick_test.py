#!/usr/bin/env python3
"""Quick test script for agent-let framework.

This script demonstrates the complete agent-let workflow without requiring
a full API server. Run directly with:

    python examples/quick_test.py

Note: Requires ANTHROPIC_API_KEY environment variable for actual execution.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from agents import AgentContext, create_agent, load_agentlet_schema


async def test_schema_loading():
    """Test 1: Load agent schemas from filesystem."""
    print("=" * 60)
    print("TEST 1: Loading agent schemas")
    print("=" * 60)

    # Load test-agent schema
    print("\n1. Loading test-agent schema...")
    schema = load_agentlet_schema("test-agent", tenant_id="default")
    print(f"   ✓ Loaded: {schema['title']}")
    print(f"   ✓ Description: {schema['description'][:80]}...")
    print(f"   ✓ Properties: {list(schema['properties'].keys())}")

    # Load researcher schema
    print("\n2. Loading researcher schema...")
    schema = load_agentlet_schema("researcher", tenant_id="default")
    print(f"   ✓ Loaded: {schema['title']}")
    print(f"   ✓ Tools: {[t['tool_name'] for t in schema['json_schema_extra']['tools']]}")

    print("\n✅ Schema loading test passed!\n")


async def test_context_creation():
    """Test 2: Create AgentContext from headers."""
    print("=" * 60)
    print("TEST 2: Context creation")
    print("=" * 60)

    # Simulate HTTP headers
    headers = {
        "X-Tenant-ID": "tenant-123",
        "X-User-ID": "user-456",
        "X-Session-ID": "session-abc",
        "X-Model-Name": "claude-sonnet-4.5",
        "X-Agent-Schema": "test-agent",
    }

    print("\n1. Parsing headers...")
    for key, value in headers.items():
        print(f"   {key}: {value}")

    print("\n2. Creating context...")
    ctx = AgentContext.from_headers(headers, tenant_id="tenant-123")
    print(f"   ✓ Tenant ID: {ctx.tenant_id}")
    print(f"   ✓ User ID: {ctx.user_id}")
    print(f"   ✓ Session ID: {ctx.session_id}")
    print(f"   ✓ Model: {ctx.default_model}")
    print(f"   ✓ Agent URI: {ctx.agent_schema_uri}")

    print("\n✅ Context creation test passed!\n")


async def test_agent_creation():
    """Test 3: Create agent from schema."""
    print("=" * 60)
    print("TEST 3: Agent creation")
    print("=" * 60)

    # Create context
    print("\n1. Creating context...")
    ctx = AgentContext(
        tenant_id="tenant-123",
        agent_schema_uri="test-agent",
        default_model="claude-sonnet-4.5"
    )
    print(f"   ✓ Context created for tenant: {ctx.tenant_id}")

    # Create agent
    print("\n2. Creating agent from schema...")
    agent = await create_agent(ctx)
    print(f"   ✓ Agent created")
    print(f"   ✓ System prompt: {agent.system_prompt[:80]}...")
    print(f"   ✓ Model: {agent.model}")

    print("\n✅ Agent creation test passed!\n")


async def test_agent_execution():
    """Test 4: Execute agent (requires API key)."""
    print("=" * 60)
    print("TEST 4: Agent execution (requires API key)")
    print("=" * 60)

    import os
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("\n⚠️  Skipping: ANTHROPIC_API_KEY not set")
        print("   Set environment variable to test actual execution\n")
        return

    # Create context and agent
    print("\n1. Creating agent...")
    ctx = AgentContext(
        tenant_id="tenant-123",
        agent_schema_uri="test-agent",
        default_model="claude-sonnet-4.5"
    )
    agent = await create_agent(ctx)
    print("   ✓ Agent created")

    # Execute with simple prompt
    print("\n2. Executing agent with prompt: 'What is 2 + 2?'")
    result = await agent.run("What is 2 + 2?")

    print("\n3. Structured output:")
    print(f"   Answer: {result.data.answer}")
    print(f"   Reasoning: {result.data.reasoning}")
    print(f"   Confidence: {result.data.confidence}")
    print(f"   Tags: {result.data.tags}")

    print("\n4. Usage metrics:")
    if hasattr(result, 'usage'):
        print(f"   Input tokens: {result.usage().get('input_tokens', 'N/A')}")
        print(f"   Output tokens: {result.usage().get('output_tokens', 'N/A')}")

    print("\n✅ Agent execution test passed!\n")


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("AGENT-LET FRAMEWORK QUICK TEST")
    print("=" * 60 + "\n")

    try:
        # Run tests
        await test_schema_loading()
        await test_context_creation()
        await test_agent_creation()
        await test_agent_execution()

        print("=" * 60)
        print("ALL TESTS PASSED ✅")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
