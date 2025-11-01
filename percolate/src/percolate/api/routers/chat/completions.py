"""OpenAI-compatible chat completions router."""

import time
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger

from percolate.agents.context import AgentContext
from percolate.agents.factory import create_agent
from percolate.agents.registry import load_agentlet_schema
from percolate.api.routers.chat.dependencies import get_session_store
from percolate.api.routers.chat.models import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatCompletionUsage,
    ChatMessage,
)
from percolate.api.routers.chat.streaming import stream_openai_response
from percolate.memory import SessionStore
from percolate.otel import get_current_trace_context

router = APIRouter(prefix="/v1/chat", tags=["chat"])


@router.post("/completions", response_model=None)
async def chat_completions(
    body: ChatCompletionRequest,
    x_tenant_id: str = Header(default="default", alias="X-Tenant-Id"),
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_project_name: str | None = Header(default=None, alias="X-Project-Name"),
    session_store: SessionStore | None = Depends(get_session_store),
):
    """
    OpenAI-compatible chat completions with agent-let support.

    This endpoint is compatible with OpenAI's chat completions API but backed
    by Percolate agent-lets. Conversations are automatically saved to sessions
    in percolate-rocks when X-Session-Id header is provided.

    ## OpenAI Compatibility

    This endpoint can be used as a drop-in replacement for OpenAI's API:

    ```python
    from openai import OpenAI

    client = OpenAI(
        base_url="http://localhost:8000/v1",
        api_key="not-needed"  # Percolate uses tenant auth
    )

    response = client.chat.completions.create(
        model="percolate-test-agent",
        messages=[
            {"role": "user", "content": "What is 2+2?"}
        ],
        stream=True  # Supports streaming
    )
    ```

    ## Headers

    | Header | Required | Description |
    |--------|----------|-------------|
    | X-Tenant-Id | No | Tenant identifier (default: "default") |
    | X-Session-Id | No | Session ID for conversation tracking |
    | X-User-Id | No | User identifier for attribution |
    | X-Project-Name | No | Project name for session grouping |

    ## Request Body

    | Field | Required | Description |
    |-------|----------|-------------|
    | model | Yes | Model/agent URI (e.g., "percolate-test-agent") |
    | messages | Yes | Array of conversation messages |
    | stream | No | Enable SSE streaming (default: false) |
    | temperature | No | Sampling temperature (0-2) |
    | max_tokens | No | Maximum tokens to generate |
    | agent_uri | No | Override agent URI (defaults to model field) |
    """
    # Validate request
    if not body.messages:
        raise HTTPException(
            status_code=400,
            detail="At least one message is required"
        )

    # Extract user messages for prompt
    user_messages = [m for m in body.messages if m.role == "user"]
    if not user_messages:
        raise HTTPException(
            status_code=400,
            detail="At least one user message is required"
        )

    # Determine agent URI (use agent_uri if provided, otherwise model)
    agent_uri = body.agent_uri or body.model

    # Build prompt from messages (combine system and user messages)
    prompt = "\n".join(msg.content or "" for msg in body.messages if msg.role in ("system", "user"))

    # Generate request ID
    request_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"

    logger.info(
        f"Chat completion request: agent={agent_uri}, tenant={x_tenant_id}, "
        f"session={x_session_id}, stream={body.stream}"
    )

    try:
        # Create agent context first (needed for metadata)
        context = AgentContext(
            tenant_id=x_tenant_id,
            session_id=x_session_id,
            user_id=x_user_id,
            agent_schema_uri=agent_uri,
            default_model=body.model if body.agent_uri else None,
            project_name=x_project_name,
            metadata={"source": "api"},
        )

        # Save user message to session (if tracking enabled)
        if session_store and x_session_id:
            session_store.save_message(
                session_id=x_session_id,
                tenant_id=x_tenant_id,
                role="user",
                content=prompt,
                agent_uri=agent_uri,
                metadata=context.get_session_metadata(),
            )

        # Load agent schema
        agent_schema = load_agentlet_schema(
            uri=agent_uri,
            tenant_id=x_tenant_id
        )

        # Create agent
        agent = await create_agent(
            context=context,
            agent_schema_override=agent_schema,
            model_override=body.model if not body.agent_uri else None,
        )

        # Streaming response
        if body.stream:
            return StreamingResponse(
                stream_openai_response(agent, prompt, context.default_model or body.model, request_id),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
            )

        # Non-streaming response
        result = await agent.run(prompt)

        # Capture OTEL trace context for feedback linking
        trace_context = get_current_trace_context()

        # Extract response content
        response_content = result.output

        # If response is structured output (dict/BaseModel), convert to string
        if isinstance(response_content, dict):
            # Format structured output as readable text
            formatted_parts = []
            for key, value in response_content.items():
                if key in ("answer", "content", "response"):
                    # Main content field - use as primary response
                    formatted_parts.insert(0, str(value))
                elif key not in ("confidence", "tags", "reasoning"):
                    # Other fields - append as metadata
                    formatted_parts.append(f"{key}: {value}")

            response_text = "\n\n".join(formatted_parts) if formatted_parts else str(response_content)
        else:
            response_text = str(response_content)

        # Get usage stats
        usage_data = result.usage()
        usage = ChatCompletionUsage(
            prompt_tokens=usage_data.input_tokens,
            completion_tokens=usage_data.output_tokens,
            total_tokens=usage_data.input_tokens + usage_data.output_tokens,
        )

        # Get model from result
        all_messages = result.all_messages()
        model_name = all_messages[0].model_name if all_messages else body.model

        # Save assistant response to session (if tracking enabled)
        if session_store and x_session_id:
            session_store.save_message(
                session_id=x_session_id,
                tenant_id=x_tenant_id,
                role="assistant",
                content=response_text,
                agent_uri=agent_uri,
                model=model_name,
                usage={
                    "input_tokens": usage_data.input_tokens,
                    "output_tokens": usage_data.output_tokens,
                },
                trace_id=trace_context.get("trace_id"),
                span_id=trace_context.get("span_id"),
                metadata=context.get_session_metadata(),
            )

        return ChatCompletionResponse(
            id=request_id,
            created=int(time.time()),
            model=model_name,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(role="assistant", content=response_text),
                    finish_reason="stop",
                )
            ],
            usage=usage,
            session_id=x_session_id,
        )

    except Exception as e:
        logger.error(f"Chat completion error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Agent execution failed: {str(e)}"
        )
