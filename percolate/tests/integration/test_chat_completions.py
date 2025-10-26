"""Integration tests for /v1/chat/completions endpoint with session persistence.

These tests verify that:
1. Chat completions API works with OpenAI-compatible format
2. Sessions are properly saved to percolate-rocks database
3. Conversation history is persisted across multiple requests
4. Token usage is tracked correctly

Requirements:
- API keys in ~/.bash_profile or .env:
  - PERCOLATE_ANTHROPIC_API_KEY (for Claude models)
  - PERCOLATE_OPENAI_API_KEY (for OpenAI models)
- Test agent: percolate-test-agent (should exist in src/percolate/schema/agentlets/)
- percolate-rocks database with sessions schema registered
"""

import os
from uuid import uuid4

import httpx
import pytest
from rem_db import Database

# Base URL for API tests
BASE_URL = "http://127.0.0.1:8000"
TIMEOUT = 60.0


@pytest.fixture
def tenant_id():
    """Generate unique tenant ID for test isolation."""
    return f"test-tenant-{uuid4().hex[:8]}"


@pytest.fixture
def session_id():
    """Generate unique session ID for conversation tracking."""
    return f"session-{uuid4().hex[:12]}"


@pytest.fixture
def http_client():
    """HTTP client for API requests."""
    return httpx.AsyncClient(timeout=TIMEOUT, base_url=BASE_URL)


@pytest.fixture
def rem_database(tmp_path, tenant_id):
    """
    REM database instance for verifying session persistence.

    This uses a temporary database path to avoid conflicts with running server.
    In production, sessions would be saved to the main database.
    """
    db_path = str(tmp_path / "rem-test.db")
    db = Database(path=db_path, tenant_id=tenant_id)

    # Register sessions schema (same as used by SessionStore)
    sessions_schema = {
        "title": "Session",
        "type": "object",
        "properties": {
            "session_id": {"type": "string"},
            "tenant_id": {"type": "string"},
            "agent_uri": {"type": ["string", "null"]},
            "messages": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "role": {"type": "string"},
                        "content": {"type": ["string", "object"]},
                        "model": {"type": ["string", "null"]},
                        "timestamp": {"type": "string", "format": "date-time"},
                        "usage": {"type": ["object", "null"]},
                    },
                },
            },
            "metadata": {"type": "object"},
            "created_at": {"type": "string", "format": "date-time"},
            "updated_at": {"type": "string", "format": "date-time"},
        },
        "required": ["session_id", "tenant_id", "messages"],
    }

    db.register_schema("sessions", sessions_schema)
    yield db


@pytest.mark.asyncio
@pytest.mark.skipif(
    "PERCOLATE_ANTHROPIC_API_KEY" not in os.environ
    and "ANTHROPIC_API_KEY" not in os.environ,
    reason="Requires ANTHROPIC_API_KEY or PERCOLATE_ANTHROPIC_API_KEY in environment",
)
@pytest.mark.skip(
    reason="Requires running server: uv run percolate serve --port 8000"
)
async def test_chat_completion_basic(http_client, tenant_id):
    """
    Test basic chat completion without session persistence.

    This verifies the OpenAI-compatible API format works correctly.
    """
    # Create chat completion request
    request_body = {
        "model": "percolate-test-agent",
        "messages": [{"role": "user", "content": "What is 2 + 2?"}],
    }

    response = await http_client.post(
        "/v1/chat/completions",
        json=request_body,
        headers={
            "Content-Type": "application/json",
            "X-Tenant-Id": tenant_id,
        },
    )

    # Verify response
    assert response.status_code == 200, f"Failed: {response.text}"

    data = response.json()

    # Verify OpenAI-compatible structure
    assert data["object"] == "chat.completion"
    assert "id" in data
    assert data["id"].startswith("chatcmpl-")
    assert "created" in data
    assert isinstance(data["created"], int)

    # Verify model
    assert "model" in data

    # Verify choices
    assert "choices" in data
    assert len(data["choices"]) > 0

    choice = data["choices"][0]
    assert choice["index"] == 0
    assert choice["finish_reason"] == "stop"

    # Verify message
    message = choice["message"]
    assert message["role"] == "assistant"
    assert "content" in message
    assert len(message["content"]) > 0

    # Verify usage
    assert "usage" in data
    usage = data["usage"]
    assert usage["prompt_tokens"] > 0
    assert usage["completion_tokens"] > 0
    assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]


@pytest.mark.asyncio
@pytest.mark.skipif(
    "PERCOLATE_ANTHROPIC_API_KEY" not in os.environ
    and "ANTHROPIC_API_KEY" not in os.environ,
    reason="Requires ANTHROPIC_API_KEY or PERCOLATE_ANTHROPIC_API_KEY in environment",
)
@pytest.mark.skip(
    reason="Requires running server: uv run percolate serve --port 8000"
)
async def test_chat_completion_with_session_persistence(
    http_client, tenant_id, session_id, rem_database
):
    """
    Test chat completion with session persistence to percolate-rocks.

    This is the main integration test verifying:
    1. Sessions are created in database
    2. Messages are appended to conversation
    3. Token usage is tracked per message
    4. Session can be retrieved and inspected

    NOTE: This test uses a separate test database. In production, SessionStore
    would use the main percolate-rocks database at ~/.p8/db/.
    """
    # First message in conversation
    first_request = {
        "model": "percolate-test-agent",
        "messages": [{"role": "user", "content": "What is percolate?"}],
    }

    first_response = await http_client.post(
        "/v1/chat/completions",
        json=first_request,
        headers={
            "Content-Type": "application/json",
            "X-Tenant-Id": tenant_id,
            "X-Session-Id": session_id,
        },
    )

    assert first_response.status_code == 200
    first_data = first_response.json()

    # Verify session_id is returned
    assert first_data.get("session_id") == session_id

    # Second message in same conversation
    second_request = {
        "model": "percolate-test-agent",
        "messages": [
            {"role": "user", "content": "What is percolate?"},
            {
                "role": "assistant",
                "content": first_data["choices"][0]["message"]["content"],
            },
            {"role": "user", "content": "Tell me more about its privacy features"},
        ],
    }

    second_response = await http_client.post(
        "/v1/chat/completions",
        json=second_request,
        headers={
            "Content-Type": "application/json",
            "X-Tenant-Id": tenant_id,
            "X-Session-Id": session_id,
        },
    )

    assert second_response.status_code == 200
    second_data = second_response.json()

    # --- Verify Session Persistence in Database ---

    # NOTE: This verification step requires percolate-rocks v0.2.1+ with working
    # get() and query() methods. For now, this is a TODO placeholder.

    # TODO: Verify session exists in database
    # session = rem_database.get(session_id)
    # assert session is not None
    # assert session["session_id"] == session_id
    # assert session["tenant_id"] == tenant_id

    # TODO: Verify messages are stored
    # assert len(session["messages"]) >= 2  # At least user + assistant
    # assert session["messages"][0]["role"] == "user"
    # assert session["messages"][0]["content"] == "What is percolate?"
    # assert session["messages"][1]["role"] == "assistant"

    # TODO: Verify token usage is tracked
    # for message in session["messages"]:
    #     if message["role"] == "assistant":
    #         assert message["usage"] is not None
    #         assert message["usage"]["input_tokens"] > 0
    #         assert message["usage"]["output_tokens"] > 0

    # For now, just verify the API responses are correct
    assert first_data["usage"]["total_tokens"] > 0
    assert second_data["usage"]["total_tokens"] > 0


@pytest.mark.asyncio
@pytest.mark.skipif(
    "PERCOLATE_ANTHROPIC_API_KEY" not in os.environ
    and "ANTHROPIC_API_KEY" not in os.environ,
    reason="Requires ANTHROPIC_API_KEY or PERCOLATE_ANTHROPIC_API_KEY in environment",
)
@pytest.mark.skip(
    reason="Requires running server: uv run percolate serve --port 8000"
)
async def test_chat_completion_structured_output(http_client, tenant_id):
    """
    Test that structured output from agent-lets is properly formatted.

    Agent-lets return structured data (Pydantic models). The chat completion
    endpoint should convert this to readable text for the user.
    """
    request_body = {
        "model": "percolate-test-agent",
        "messages": [{"role": "user", "content": "Explain agent-lets in one sentence"}],
    }

    response = await http_client.post(
        "/v1/chat/completions",
        json=request_body,
        headers={
            "Content-Type": "application/json",
            "X-Tenant-Id": tenant_id,
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Verify structured output is converted to text
    message_content = data["choices"][0]["message"]["content"]
    assert isinstance(message_content, str)
    assert len(message_content) > 0

    # Should contain the answer field from agent output
    # (test-agent returns {answer, confidence, tags, reasoning, joke})
    assert len(message_content) > 10  # Reasonable answer length


@pytest.mark.asyncio
@pytest.mark.skipif(
    "PERCOLATE_ANTHROPIC_API_KEY" not in os.environ
    and "ANTHROPIC_API_KEY" not in os.environ,
    reason="Requires ANTHROPIC_API_KEY or PERCOLATE_ANTHROPIC_API_KEY in environment",
)
@pytest.mark.skip(
    reason="Requires running server: uv run percolate serve --port 8000"
)
async def test_chat_completion_error_handling(http_client, tenant_id):
    """Test error handling for invalid requests."""

    # Test 1: Empty messages
    response = await http_client.post(
        "/v1/chat/completions",
        json={"model": "percolate-test-agent", "messages": []},
        headers={"Content-Type": "application/json", "X-Tenant-Id": tenant_id},
    )
    assert response.status_code == 400
    assert "at least one message" in response.json()["detail"].lower()

    # Test 2: No user messages
    response = await http_client.post(
        "/v1/chat/completions",
        json={
            "model": "percolate-test-agent",
            "messages": [{"role": "system", "content": "You are helpful"}],
        },
        headers={"Content-Type": "application/json", "X-Tenant-Id": tenant_id},
    )
    assert response.status_code == 400
    assert "user message" in response.json()["detail"].lower()

    # Test 3: Invalid agent URI
    response = await http_client.post(
        "/v1/chat/completions",
        json={
            "model": "nonexistent-agent",
            "messages": [{"role": "user", "content": "test"}],
        },
        headers={"Content-Type": "application/json", "X-Tenant-Id": tenant_id},
    )
    assert response.status_code == 500
    assert "error" in response.json()["detail"].lower()

    # Test 4: Streaming not supported
    response = await http_client.post(
        "/v1/chat/completions",
        json={
            "model": "percolate-test-agent",
            "messages": [{"role": "user", "content": "test"}],
            "stream": True,
        },
        headers={"Content-Type": "application/json", "X-Tenant-Id": tenant_id},
    )
    assert response.status_code == 400
    assert "streaming not yet supported" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_chat_completion_openai_client_compatibility(tenant_id, session_id):
    """
    Test using actual OpenAI Python client (demonstrates compatibility).

    This test shows that Percolate can be used as a drop-in replacement
    for OpenAI's API in existing codebases.

    NOTE: Requires server to be running.
    """
    pytest.skip("Requires running server and is demonstration only")

    from openai import OpenAI

    # Create client pointing to Percolate
    client = OpenAI(
        base_url="http://localhost:8000/v1",
        api_key="not-needed",  # Percolate uses X-Tenant-Id header
    )

    # Use OpenAI client normally
    response = client.chat.completions.create(
        model="percolate-test-agent",
        messages=[{"role": "user", "content": "What is 2+2?"}],
    )

    # Verify response
    assert response.id.startswith("chatcmpl-")
    assert response.object == "chat.completion"
    assert len(response.choices) > 0
    assert response.choices[0].message.role == "assistant"
    assert len(response.choices[0].message.content) > 0
    assert response.usage.total_tokens > 0


# --- Unit Tests (No Server Required) ---


def test_chat_message_model():
    """Test ChatMessage Pydantic model."""
    from percolate.api.routers.chat.models import ChatMessage

    # Valid message
    msg = ChatMessage(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"
    assert msg.name is None

    # With name
    msg_with_name = ChatMessage(role="user", content="Hi", name="Alice")
    assert msg_with_name.name == "Alice"


def test_chat_completion_request_model():
    """Test ChatCompletionRequest Pydantic model."""
    from percolate.api.routers.chat.models import ChatCompletionRequest, ChatMessage

    # Minimal valid request
    req = ChatCompletionRequest(
        model="test-model",
        messages=[ChatMessage(role="user", content="test")],
    )
    assert req.model == "test-model"
    assert len(req.messages) == 1
    assert req.stream is False
    assert req.agent_uri is None

    # With overrides
    req_override = ChatCompletionRequest(
        model="gpt-4",
        messages=[ChatMessage(role="user", content="test")],
        agent_uri="my-agent",
        temperature=0.7,
    )
    assert req_override.agent_uri == "my-agent"
    assert req_override.temperature == 0.7


def test_chat_completion_response_model():
    """Test ChatCompletionResponse Pydantic model."""
    from percolate.api.routers.chat.models import (
        ChatCompletionResponse,
        ChatCompletionChoice,
        ChatCompletionUsage,
        ChatMessage,
    )

    usage = ChatCompletionUsage(
        prompt_tokens=10, completion_tokens=20, total_tokens=30
    )

    message = ChatMessage(role="assistant", content="Response")

    choice = ChatCompletionChoice(
        index=0, message=message, finish_reason="stop"
    )

    response = ChatCompletionResponse(
        id="chatcmpl-123",
        created=1234567890,
        model="test-model",
        choices=[choice],
        usage=usage,
        session_id="session-abc",
    )

    assert response.id == "chatcmpl-123"
    assert response.object == "chat.completion"
    assert len(response.choices) == 1
    assert response.usage.total_tokens == 30
    assert response.session_id == "session-abc"


@pytest.mark.asyncio
@pytest.mark.skipif(
    "PERCOLATE_ANTHROPIC_API_KEY" not in os.environ
    and "ANTHROPIC_API_KEY" not in os.environ,
    reason="Requires ANTHROPIC_API_KEY or PERCOLATE_ANTHROPIC_API_KEY in environment",
)
@pytest.mark.skip(
    reason="Requires running server: uv run percolate serve --port 8000"
)
async def test_feedback_with_trace_id_linking(http_client, tenant_id, session_id):
    """
    Test end-to-end flow: chat completion with trace_id → feedback with trace_id.

    This verifies:
    1. Assistant messages are saved with trace_id/span_id from OTEL
    2. Feedback can be submitted with session_id
    3. Feedback is linked back to the message via trace_id

    This is critical for observability - feedback links to traces in Phoenix/Arize.
    """
    # Send chat completion request with session tracking
    chat_request = {
        "model": "percolate-test-agent",
        "messages": [{"role": "user", "content": "What is percolate?"}],
    }

    chat_response = await http_client.post(
        "/v1/chat/completions",
        json=chat_request,
        headers={
            "Content-Type": "application/json",
            "X-Tenant-Id": tenant_id,
            "X-Session-Id": session_id,
            "X-User-Id": "test-user-123",
        },
    )

    assert chat_response.status_code == 200
    chat_data = chat_response.json()

    # Verify session_id is returned
    assert chat_data.get("session_id") == session_id
    assert chat_data["choices"][0]["message"]["role"] == "assistant"
    assert len(chat_data["choices"][0]["message"]["content"]) > 0

    # Submit positive feedback on the response
    feedback_request = {
        "session_id": session_id,
        "score": 1.0,
        "label": "thumbs_up",
        "feedback_text": "Very helpful explanation!",
    }

    feedback_response = await http_client.post(
        "/v1/chat/feedback",
        json=feedback_request,
        headers={
            "Content-Type": "application/json",
            "X-Tenant-Id": tenant_id,
            "X-User-Id": "test-user-123",
        },
    )

    assert feedback_response.status_code == 200
    feedback_data = feedback_response.json()

    # Verify feedback response
    assert feedback_data["status"] == "success"
    assert "feedback_id" in feedback_data
    assert feedback_data["session_id"] == session_id

    # TODO: Verify database state when percolate-rocks query support is added
    # from percolate.memory import SessionStore
    # store = SessionStore()
    # messages = store.get_messages(session_id, tenant_id)
    # assert len(messages) > 0
    # assistant_message = [m for m in messages if m.role == "assistant"][0]
    # assert assistant_message.trace_id is not None
    # assert assistant_message.span_id is not None


@pytest.mark.asyncio
@pytest.mark.skip(
    reason="Requires running server: uv run percolate serve --port 8000"
)
async def test_feedback_validation(http_client, tenant_id, session_id):
    """Test feedback validation for invalid inputs."""

    # Test 1: Score out of range (> 1)
    response = await http_client.post(
        "/v1/chat/feedback",
        json={
            "session_id": session_id,
            "score": 1.5,
        },
        headers={
            "Content-Type": "application/json",
            "X-Tenant-Id": tenant_id,
        },
    )
    assert response.status_code == 422  # Pydantic validation error

    # Test 2: Score out of range (< 0)
    response = await http_client.post(
        "/v1/chat/feedback",
        json={
            "session_id": session_id,
            "score": -0.5,
        },
        headers={
            "Content-Type": "application/json",
            "X-Tenant-Id": tenant_id,
        },
    )
    assert response.status_code == 422  # Pydantic validation error

    # Test 3: Valid feedback with all fields
    response = await http_client.post(
        "/v1/chat/feedback",
        json={
            "session_id": session_id,
            "score": 0.75,
            "label": "good_but_slow",
            "feedback_text": "Needs improvement on X",
            "metadata": {"source": "web_ui", "page": "chat"},
        },
        headers={
            "Content-Type": "application/json",
            "X-Tenant-Id": tenant_id,
            "X-User-Id": "user-456",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "feedback_id" in data
