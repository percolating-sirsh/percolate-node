"""Integration tests for agent-let framework.

Tests the complete agent-let execution pipeline:
1. Loading schemas from filesystem
2. Creating agents with context
3. Executing agents with structured output
4. Context header parsing

Run with: pytest tests/integration/test_agent_framework.py -v
"""

import asyncio
import sys
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

from agents import AgentContext, create_agent, load_agentlet_schema


class TestAgentLoading:
    """Test agent schema loading from filesystem and database."""

    def test_load_system_agent_test_agent(self):
        """Load system test-agent schema from filesystem."""
        schema = load_agentlet_schema("test-agent", tenant_id="default")

        assert schema["title"] == "TestAgent"
        assert schema["short_name"] == "test_agent"
        assert "description" in schema
        assert "properties" in schema
        assert "answer" in schema["properties"]
        assert "confidence" in schema["properties"]

    def test_load_system_agent_researcher(self):
        """Load system researcher schema from filesystem."""
        schema = load_agentlet_schema("researcher", tenant_id="default")

        assert schema["title"] == "ResearchAgent"
        assert schema["short_name"] == "researcher"
        assert len(schema["json_schema_extra"]["tools"]) == 2  # search_memory, lookup_entity

    def test_load_nonexistent_agent_raises_error(self):
        """Loading non-existent agent should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_agentlet_schema("nonexistent-agent", tenant_id="default")

    def test_load_user_agent_not_implemented(self):
        """User agent loading should raise error (not yet implemented)."""
        with pytest.raises(FileNotFoundError, match="TODO: Implement percolate-rocks"):
            load_agentlet_schema("user/tenant-123/my-agent", tenant_id="tenant-123")


class TestAgentContext:
    """Test AgentContext model and header parsing."""

    def test_context_from_headers(self):
        """Extract context from HTTP headers."""
        headers = {
            "X-User-ID": "user-123",
            "X-Session-ID": "session-abc",
            "X-Device-ID": "device-xyz",
            "X-Model-Name": "claude-opus-4",
            "X-Agent-Schema": "researcher",
            "X-DB-Path": "/custom/db/path",
        }

        ctx = AgentContext.from_headers(headers, tenant_id="tenant-456")

        assert ctx.user_id == "user-123"
        assert ctx.session_id == "session-abc"
        assert ctx.device_id == "device-xyz"
        assert ctx.tenant_id == "tenant-456"
        assert ctx.default_model == "claude-opus-4"
        assert ctx.agent_schema_uri == "researcher"
        assert ctx.db_path == "/custom/db/path"

    def test_context_defaults(self):
        """Context should have sensible defaults."""
        ctx = AgentContext(tenant_id="tenant-123")

        assert ctx.tenant_id == "tenant-123"
        assert ctx.user_id is None
        assert ctx.session_id is None
        assert ctx.default_model == "claude-sonnet-4.5"
        assert ctx.agent_schema_uri is None
        assert ctx.db_path is None


@pytest.mark.asyncio
class TestAgentFactory:
    """Test agent creation from schemas."""

    async def test_create_agent_from_schema_override(self):
        """Create agent from explicit schema dict."""
        schema = {
            "description": "You are a helpful assistant.",
            "properties": {
                "answer": {"type": "string", "description": "The answer"}
            },
            "required": ["answer"],
            "json_schema_extra": {"tools": []}
        }

        ctx = AgentContext(tenant_id="default")
        agent = await create_agent(ctx, agent_schema_override=schema)

        assert agent is not None
        assert agent.system_prompt == "You are a helpful assistant."

    async def test_create_agent_from_context_uri(self):
        """Create agent from context.agent_schema_uri."""
        ctx = AgentContext(
            tenant_id="default",
            agent_schema_uri="test-agent"
        )

        agent = await create_agent(ctx)

        assert agent is not None
        assert "test agent" in agent.system_prompt.lower()

    async def test_create_agent_with_model_override(self):
        """Override default model in agent creation."""
        schema = {
            "description": "Test agent",
            "properties": {},
            "json_schema_extra": {"tools": []}
        }

        ctx = AgentContext(tenant_id="default", default_model="claude-sonnet-4.5")
        agent = await create_agent(ctx, agent_schema_override=schema, model_override="claude-opus-4")

        # Note: Pydantic AI agent doesn't expose model directly, so we can't assert on it
        # This test just ensures no errors are raised
        assert agent is not None


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires API key for LLM execution")
class TestAgentExecution:
    """Test actual agent execution (requires API key).

    These tests are skipped by default. To run:
    1. Set ANTHROPIC_API_KEY environment variable
    2. Run: pytest tests/integration/test_agent_framework.py::TestAgentExecution -v
    """

    async def test_execute_test_agent(self):
        """Execute test-agent with a simple question."""
        ctx = AgentContext(
            tenant_id="default",
            agent_schema_uri="test-agent"
        )

        agent = await create_agent(ctx)
        result = await agent.run("What is 2 + 2?")

        # Check structured output
        assert hasattr(result, 'data')
        assert hasattr(result.data, 'answer')
        assert hasattr(result.data, 'confidence')
        assert hasattr(result.data, 'reasoning')
        assert hasattr(result.data, 'tags')

        # Validate types
        assert isinstance(result.data.answer, str)
        assert isinstance(result.data.confidence, float)
        assert 0.0 <= result.data.confidence <= 1.0
        assert isinstance(result.data.tags, list)

    async def test_execute_researcher_agent(self):
        """Execute researcher agent (will fail on tool calls until MCP tools implemented)."""
        ctx = AgentContext(
            tenant_id="default",
            agent_schema_uri="researcher"
        )

        agent = await create_agent(ctx)

        # This will likely fail when it tries to call search_memory tool
        # since MCP tools are not yet implemented
        with pytest.raises(Exception):
            result = await agent.run("Research the history of databases")


# Run tests directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
