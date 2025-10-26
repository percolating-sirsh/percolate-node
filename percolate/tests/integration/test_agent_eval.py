"""Integration test for agent evaluation."""

import pytest
from percolate.mcplib.tools.agent import ask_agent


@pytest.mark.asyncio
async def test_ask_test_agent_structured_output():
    """Test that the test-agent returns all required structured fields."""
    result = await ask_agent(
        ctx=None,
        agent_uri="percolate-test-agent",
        tenant_id="test-tenant",
        prompt="What is 2 + 2?",
    )

    assert result["status"] == "success"
    assert "response" in result
    assert "usage" in result
    assert "model" in result

    # Check structured output has ALL required fields
    response = result["response"]
    assert isinstance(response, dict)

    # Verify all required fields are present
    assert "answer" in response, "Missing 'answer' field"
    assert "reasoning" in response, "Missing 'reasoning' field"
    assert "joke" in response, "Missing 'joke' field"
    assert "confidence" in response, "Missing 'confidence' field"
    assert "tags" in response, "Missing 'tags' field"

    # Verify field types and constraints
    assert isinstance(response["answer"], str)
    assert len(response["answer"]) > 0

    assert isinstance(response["reasoning"], str)
    assert len(response["reasoning"]) > 0

    assert isinstance(response["joke"], str)
    assert len(response["joke"]) > 0

    assert isinstance(response["confidence"], (int, float))
    assert 0.0 <= response["confidence"] <= 1.0

    assert isinstance(response["tags"], list)
    assert len(response["tags"]) >= 2
    assert all(isinstance(tag, str) for tag in response["tags"])

    # Verify usage metrics
    usage = result["usage"]
    assert usage["input_tokens"] > 0
    assert usage["output_tokens"] > 0


@pytest.mark.asyncio
async def test_ask_agent_with_pydantic_model():
    """Test agent evaluation using Pydantic model schema."""
    from percolate.schema.agentlets.test_agent import TestAgent
    from percolate.agents.factory import create_agent
    from percolate.agents.context import AgentContext

    # Get schema from Pydantic model
    schema = TestAgent.model_json_schema()

    # Create context
    context = AgentContext(
        tenant_id="test-tenant",
        agent_schema_uri="test-agent",
    )

    # Create agent with result_type
    agent = await create_agent(
        context=context,
        agent_schema_override=schema,
        result_type=TestAgent,
    )

    # Run agent
    result = await agent.run("Explain what Percolate is in one sentence.")

    # Verify result (Pydantic AI 1.x uses .output not .data)
    assert result.output is not None
    assert isinstance(result.output, TestAgent)
    assert result.output.answer
    assert 0.0 <= result.output.confidence <= 1.0

    # Verify usage (Pydantic AI 1.x uses .usage() method)
    usage = result.usage()
    assert usage.input_tokens > 0
    assert usage.output_tokens > 0
