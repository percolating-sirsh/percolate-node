"""Agent execution context for configuration and state propagation."""

from pydantic import BaseModel, Field


class AgentContext(BaseModel):
    """Execution context for agent-let runtime.

    Carries user identity, model selection, session tracking, and agent
    schema references through the execution stack. Extractable from HTTP
    headers for API integration.

    Attributes:
        user_id: Optional user identifier for tenant scoping
        tenant_id: Tenant identifier for data isolation
        session_id: Optional session/chat identifier for history
        device_id: Optional device identifier for auth tracking
        default_model: LLM model to use for agent execution
        agent_schema_uri: URI to agent-let schema (e.g., 'researcher')
    """

    user_id: str | None = Field(
        default=None,
        description="User identifier for tenant scoping"
    )
    tenant_id: str = Field(
        description="Tenant identifier for data isolation"
    )
    session_id: str | None = Field(
        default=None,
        description="Session/chat identifier for message history"
    )
    device_id: str | None = Field(
        default=None,
        description="Device identifier for auth tracking"
    )
    default_model: str = Field(
        default="anthropic:claude-3-5-sonnet-20241022",
        description="Default LLM model for agent execution"
    )
    agent_schema_uri: str | None = Field(
        default=None,
        description="Agent-let schema URI (e.g., 'researcher', 'classifier')"
    )

    @classmethod
    def from_headers(cls, headers: dict[str, str], tenant_id: str) -> "AgentContext":
        """Extract agent context from HTTP headers.

        Maps standard X-* headers to context fields:
        - X-User-Id → user_id
        - X-Session-Id → session_id
        - X-Device-Id → device_id
        - X-Model-Name → default_model
        - X-Agent-Schema → agent_schema_uri

        Args:
            headers: HTTP request headers (case-insensitive)
            tenant_id: Tenant identifier from auth token

        Returns:
            AgentContext with extracted values

        Example:
            >>> headers = {"X-User-Id": "user-123", "X-Model-Name": "claude-opus-4"}
            >>> ctx = AgentContext.from_headers(headers, tenant_id="tenant-abc")
            >>> ctx.user_id
            'user-123'
        """
        normalized = {k.lower(): v for k, v in headers.items()}
        return cls(
            user_id=normalized.get("x-user-id"),
            tenant_id=tenant_id,
            session_id=normalized.get("x-session-id"),
            device_id=normalized.get("x-device-id"),
            default_model=normalized.get("x-model-name", "claude-sonnet-4.5"),
            agent_schema_uri=normalized.get("x-agent-schema"),
        )
