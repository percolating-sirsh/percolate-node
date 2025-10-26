"""OpenAI-compatible streaming relay for Pydantic AI agents."""

import json
import time
import uuid
from typing import AsyncGenerator

from loguru import logger
from pydantic_ai.agent import Agent

from percolate.api.routers.chat.models import (
    ChatCompletionMessageDelta,
    ChatCompletionStreamChoice,
    ChatCompletionStreamResponse,
)


async def stream_openai_response(
    agent: Agent,
    prompt: str,
    model: str,
    request_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Stream Pydantic AI agent responses in OpenAI SSE format.

    Converts Pydantic AI's run_stream() to OpenAI-compatible SSE chunks:
    - data: {"id": "...", "choices": [{"delta": {"content": "..."}}]}
    - data: [DONE]

    Args:
        agent: Pydantic AI agent instance
        prompt: User prompt to run
        model: Model name for response metadata
        request_id: Optional request ID (generates UUID if not provided)

    Yields:
        SSE-formatted strings: "data: {json}\\n\\n"
    """
    if request_id is None:
        request_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"

    created_at = int(time.time())
    is_first_chunk = True

    try:
        async with agent.run_stream(prompt) as response:
            async for text_chunk in response.stream_text():
                # First chunk includes role
                delta = ChatCompletionMessageDelta(
                    role="assistant" if is_first_chunk else None,
                    content=text_chunk,
                )
                is_first_chunk = False

                chunk = ChatCompletionStreamResponse(
                    id=request_id,
                    created=created_at,
                    model=model,
                    choices=[
                        ChatCompletionStreamChoice(
                            index=0,
                            delta=delta,
                            finish_reason=None,
                        )
                    ],
                )

                # Format as SSE: "data: {json}\n\n"
                yield f"data: {chunk.model_dump_json()}\n\n"

        # Final chunk with finish_reason
        final_chunk = ChatCompletionStreamResponse(
            id=request_id,
            created=created_at,
            model=model,
            choices=[
                ChatCompletionStreamChoice(
                    index=0,
                    delta=ChatCompletionMessageDelta(),
                    finish_reason="stop",
                )
            ],
        )
        yield f"data: {final_chunk.model_dump_json()}\n\n"

        # OpenAI termination marker
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"Streaming error: {e}")
        # Send error as final chunk
        error_data = {
            "error": {
                "message": str(e),
                "type": "internal_error",
                "code": "stream_error",
            }
        }
        yield f"data: {json.dumps(error_data)}\n\n"
        yield "data: [DONE]\n\n"
