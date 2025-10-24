"""Unit tests for MCP tool implementations.

These tests verify MCP tool logic without requiring a running server.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from percolate.mcp.tools.agent import ask_agent
from percolate.agents.context import AgentContext


@pytest.mark.asyncio
async def test_ask_agent_tool_basic():
    """Test ask_agent tool with basic arguments."""
    # Mock the agent factory and execution
    mock_agent = Mock()
    mock_agent.run = AsyncMock(
        return_value=Mock(
            data={
                "answer": "Test response",
                "confidence": 0.95,
                "tags": ["test"],
            }
        )
    )

    with patch("percolate.mcp.tools.agent.create_agent", return_value=mock_agent):
        result = await ask_agent(
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
    mock_agent.run = AsyncMock(
        return_value=Mock(data={"answer": "Test", "confidence": 1.0, "tags": []})
    )

    with patch("percolate.mcp.tools.agent.create_agent", return_value=mock_agent):
        await ask_agent(
            agent_uri="test-agent",
            tenant_id="test-tenant",
            prompt="Test prompt",
            user_id="user-123",
            session_id="session-456",
        )

        # Verify create_agent was called with correct context
        call_args = mock_agent.run.call_args
        context = call_args[1]  # Second positional argument

        assert isinstance(context, AgentContext)
        assert context.tenant_id == "test-tenant"
        assert context.user_id == "user-123"
        assert context.session_id == "session-456"


@pytest.mark.asyncio
async def test_ask_agent_model_override():
    """Test that model parameter overrides default."""
    mock_agent = Mock()
    mock_agent.run = AsyncMock(
        return_value=Mock(data={"answer": "Test", "confidence": 1.0, "tags": []})
    )

    with patch("percolate.mcp.tools.agent.create_agent", return_value=mock_agent):
        await ask_agent(
            agent_uri="test-agent",
            tenant_id="test-tenant",
            prompt="Test prompt",
            model="claude-opus-4",
        )

        # Verify context has custom model
        call_args = mock_agent.run.call_args
        context = call_args[1]

        assert context.default_model == "claude-opus-4"


@pytest.mark.asyncio
async def test_ask_agent_error_handling():
    """Test ask_agent error handling."""
    mock_agent = Mock()
    mock_agent.run = AsyncMock(side_effect=ValueError("Invalid agent"))

    with patch("percolate.mcp.tools.agent.create_agent", return_value=mock_agent):
        result = await ask_agent(
            agent_uri="invalid-agent",
            tenant_id="test-tenant",
            prompt="Test prompt",
        )

        # Verify error response structure
        assert result["status"] == "error"
        assert "error" in result
        assert "Invalid agent" in result["error"]
