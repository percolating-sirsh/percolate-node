"""Unit tests for MCP tool implementations.

These tests verify MCP tool logic without requiring a running server.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from percolate.mcplib.tools.agent import ask_agent
from percolate.agents.context import AgentContext


@pytest.mark.asyncio
async def test_ask_agent_tool_basic():
    """Test ask_agent tool with basic arguments."""
    # Mock the agent factory and execution
    mock_agent = Mock()
    mock_result = Mock()
    mock_result.output = {
        "answer": "Test response",
        "confidence": 0.95,
        "tags": ["test"],
    }
    mock_result.usage = Mock(return_value=Mock(input_tokens=100, output_tokens=50))
    mock_result.all_messages = Mock(return_value=[Mock(model_name="test-model")])
    mock_agent.run = AsyncMock(return_value=mock_result)

    # Mock schema loading
    mock_schema = {"title": "TestAgent", "properties": {}}

    with patch("percolate.mcplib.tools.agent.create_pydantic_agent", return_value=mock_agent), \
         patch("percolate.mcplib.tools.agent.load_agentlet_schema", return_value=mock_schema):
        result = await ask_agent(
            ctx=None,
            agent_uri="test-agent",
            tenant_id="test-tenant",
            prompt="Test prompt",
        )

        # Verify result structure
        assert result["status"] == "success"
        assert "response" in result
        assert result["response"]["answer"] == "Test response"
        assert result["response"]["confidence"] == 0.95


@pytest.mark.asyncio
async def test_ask_agent_context_creation():
    """Test that ask_agent creates proper AgentContext."""
    mock_agent = Mock()
    mock_result = Mock()
    mock_result.output = {"answer": "Test", "confidence": 1.0, "tags": []}
    mock_result.usage = Mock(return_value=Mock(input_tokens=100, output_tokens=50))
    mock_result.all_messages = Mock(return_value=[Mock(model_name="test-model")])
    mock_agent.run = AsyncMock(return_value=mock_result)

    mock_schema = {"title": "TestAgent", "properties": {}}

    with patch("percolate.mcplib.tools.agent.create_pydantic_agent", return_value=mock_agent) as mock_create, \
         patch("percolate.mcplib.tools.agent.load_agentlet_schema", return_value=mock_schema):
        await ask_agent(
            ctx=None,
            agent_uri="test-agent",
            tenant_id="test-tenant",
            prompt="Test prompt",
            session_id="session-456",
        )

        # Verify create_pydantic_agent was called with correct context
        call_args = mock_create.call_args
        context = call_args.kwargs["context"]

        assert isinstance(context, AgentContext)
        assert context.tenant_id == "test-tenant"
        assert context.session_id == "session-456"


@pytest.mark.asyncio
async def test_ask_agent_model_override():
    """Test that model parameter overrides default."""
    mock_agent = Mock()
    mock_result = Mock()
    mock_result.output = {"answer": "Test", "confidence": 1.0, "tags": []}
    mock_result.usage = Mock(return_value=Mock(input_tokens=100, output_tokens=50))
    mock_result.all_messages = Mock(return_value=[Mock(model_name="claude-opus-4")])
    mock_agent.run = AsyncMock(return_value=mock_result)

    mock_schema = {"title": "TestAgent", "properties": {}}

    with patch("percolate.mcplib.tools.agent.create_pydantic_agent", return_value=mock_agent) as mock_create, \
         patch("percolate.mcplib.tools.agent.load_agentlet_schema", return_value=mock_schema):
        await ask_agent(
            ctx=None,
            agent_uri="test-agent",
            tenant_id="test-tenant",
            prompt="Test prompt",
            model="claude-opus-4",
        )

        # Verify context has custom model
        call_args = mock_create.call_args
        context = call_args.kwargs["context"]

        assert context.default_model == "claude-opus-4"


@pytest.mark.asyncio
async def test_ask_agent_error_handling():
    """Test ask_agent error handling."""
    mock_agent = Mock()
    mock_agent.run = AsyncMock(side_effect=ValueError("Invalid agent"))

    mock_schema = {"title": "TestAgent", "properties": {}}

    with patch("percolate.mcplib.tools.agent.create_pydantic_agent", return_value=mock_agent), \
         patch("percolate.mcplib.tools.agent.load_agentlet_schema", return_value=mock_schema):
        result = await ask_agent(
            ctx=None,
            agent_uri="invalid-agent",
            tenant_id="test-tenant",
            prompt="Test prompt",
        )

        # Verify error response structure
        assert result["status"] == "error"
        assert "error" in result
        assert "Invalid agent" in result["error"]
