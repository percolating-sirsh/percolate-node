"""Quick test to see if agent actually uses tools properly."""
import asyncio

from percolate.agents.context import AgentContext
from percolate.agents.factory import create_agent


async def main():
    ctx = AgentContext(
        tenant_id="test-tenant",
        agent_schema_uri="mcp-agent",
    )

    agent = await create_agent(ctx)

    print("\n" + "=" * 60)
    print("Testing: Search for information about REM memory")
    print("=" * 60)

    result = await agent.run("Search for information about REM memory")

    print("\n--- Agent Response ---")
    print(f"Answer: {result.output.answer}")
    print(f"\nReasoning: {result.output.reasoning}")
    print(f"\nTools Used: {result.output.tools_used}")
    print(f"Confidence: {result.output.confidence}")

    print("\n--- All Messages (checking for tool calls) ---")
    for i, msg in enumerate(result.all_messages()):
        print(f"\nMessage {i}: {msg.role}")
        if hasattr(msg, "content"):
            content_str = str(msg.content)
            print(f"  Content: {content_str[:200] if len(content_str) > 200 else content_str}")


if __name__ == "__main__":
    asyncio.run(main())
