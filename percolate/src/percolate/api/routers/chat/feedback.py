"""Feedback endpoint for chat completions."""

from typing import Any

from fastapi import Header, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from percolate.api.routers.chat.completions import router
from percolate.memory import SessionStore


class FeedbackRequest(BaseModel):
    """User feedback on an assistant interaction."""

    session_id: str = Field(description="Session identifier")
    message_id: str | None = Field(default=None, description="Specific message being rated")
    score: float = Field(ge=0.0, le=1.0, description="Feedback score between 0 and 1 (0=thumbs_down, 1=thumbs_up)")
    label: str | None = Field(default=None, description="Feedback label (any string)")
    feedback_text: str | None = Field(default=None, description="Optional comment")
    trace_id: str | None = Field(default=None, description="OTEL trace ID")
    span_id: str | None = Field(default=None, description="OTEL span ID")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class FeedbackResponse(BaseModel):
    """Feedback submission response."""

    feedback_id: str = Field(description="Unique feedback identifier")
    session_id: str = Field(description="Session identifier")
    status: str = Field(description="success or error")


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    body: FeedbackRequest,
    x_tenant_id: str = Header(default="default", alias="X-Tenant-Id"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
):
    """
    Submit user feedback on an assistant interaction.

    This endpoint allows users to provide feedback on assistant responses,
    which can be linked back to specific messages and OTEL traces for analysis.

    ## Headers

    | Header | Required | Description |
    |--------|----------|-------------|
    | X-Tenant-Id | No | Tenant identifier (default: "default") |
    | X-User-Id | No | User identifier for attribution |

    ## Request Body

    | Field | Required | Description |
    |-------|----------|-------------|
    | session_id | Yes | Session identifier |
    | message_id | No | Specific message being rated |
    | score | Yes | Feedback score 0-1 (0=thumbs_down, 1=thumbs_up) |
    | label | No | Feedback label (any string) |
    | feedback_text | No | Optional comment text |
    | trace_id | No | OTEL trace ID for linking |
    | span_id | No | OTEL span ID for linking |
    | metadata | No | Additional metadata |

    ## Examples

    Thumbs up:
    ```json
    {
      "session_id": "sess-456",
      "score": 1.0,
      "label": "thumbs_up",
      "feedback_text": "Very helpful!"
    }
    ```

    Thumbs down:
    ```json
    {
      "session_id": "sess-456",
      "score": 0.0,
      "label": "thumbs_down",
      "feedback_text": "Not accurate"
    }
    ```

    Custom rating:
    ```json
    {
      "session_id": "sess-456",
      "score": 0.75,
      "label": "good_but_slow",
      "feedback_text": "Correct but took too long"
    }
    ```
    """
    logger.info(
        f"Feedback submission: session={body.session_id}, tenant={x_tenant_id}, "
        f"score={body.score}, label={body.label}"
    )

    # Initialize session store
    session_store = SessionStore()

    try:
        # Save feedback
        feedback_id = session_store.save_feedback(
            session_id=body.session_id,
            tenant_id=x_tenant_id,
            label=body.label,
            message_id=body.message_id,
            score=body.score,
            feedback_text=body.feedback_text,
            trace_id=body.trace_id,
            span_id=body.span_id,
            user_id=x_user_id,
            metadata=body.metadata,
        )

        if not feedback_id:
            raise HTTPException(
                status_code=500,
                detail="Failed to save feedback"
            )

        return FeedbackResponse(
            feedback_id=feedback_id,
            session_id=body.session_id,
            status="success",
        )

    except Exception as e:
        logger.error(f"Feedback submission error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save feedback: {str(e)}"
        )
