"""OpenAI-compatible API models for chat completions."""

from typing import Literal
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """OpenAI chat message format."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    name: str | None = None
    tool_call_id: str | None = None


class ChatCompletionRequest(BaseModel):
    """OpenAI chat completion request format.

    Compatible with OpenAI's /v1/chat/completions endpoint.
    Additional agent context is provided via headers (X-Tenant-Id, X-Session-Id, etc).
    """

    model: str = Field(
        default="claude-sonnet-4-5-20250929",
        description="Model to use or agent URI",
    )
    messages: list[ChatMessage] = Field(description="Chat conversation history")
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1)
    stream: bool = Field(default=False, description="Enable SSE streaming")
    n: int | None = Field(default=1, ge=1, le=1, description="Number of completions")
    stop: str | list[str] | None = None
    presence_penalty: float | None = Field(default=None, ge=-2, le=2)
    frequency_penalty: float | None = Field(default=None, ge=-2, le=2)
    user: str | None = Field(default=None, description="Unique user identifier")

    # Percolate extensions
    agent_uri: str | None = Field(
        default=None,
        description="Override agent URI (defaults to model field)"
    )


class ChatCompletionUsage(BaseModel):
    """Token usage statistics."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionMessageDelta(BaseModel):
    """Streaming delta for chat completion."""

    role: Literal["system", "user", "assistant"] | None = None
    content: str | None = None


class ChatCompletionChoice(BaseModel):
    """Chat completion choice (non-streaming)."""

    index: int
    message: ChatMessage
    finish_reason: Literal["stop", "length", "content_filter", "tool_calls"] | None


class ChatCompletionStreamChoice(BaseModel):
    """Chat completion choice (streaming)."""

    index: int
    delta: ChatCompletionMessageDelta
    finish_reason: Literal["stop", "length", "content_filter"] | None = None


class ChatCompletionResponse(BaseModel):
    """OpenAI chat completion response (non-streaming)."""

    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: ChatCompletionUsage

    # Percolate extensions
    session_id: str | None = Field(default=None, description="Session ID if tracking enabled")


class ChatCompletionStreamResponse(BaseModel):
    """OpenAI chat completion chunk (streaming)."""

    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    choices: list[ChatCompletionStreamChoice]
