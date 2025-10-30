"""OpenTelemetry attribute management for agent tracing.

This module provides utilities for setting resource and span attributes
following OpenInference semantic conventions for LLM observability.
"""

import hashlib
from typing import TYPE_CHECKING, Any

from loguru import logger
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource

from percolate.settings import settings

if TYPE_CHECKING:
    from percolate.agents.context import AgentContext


def _generate_agent_uuid(fqn: str) -> str:
    """Generate a deterministic UUID for an agent from its FQN.

    Args:
        fqn: Fully qualified name of the agent

    Returns:
        Hex string hash (first 32 chars of SHA256)
    """
    return hashlib.sha256(fqn.encode()).hexdigest()[:32]


def set_agent_resource_attributes(agent_schema: dict[str, Any] | None = None) -> None:
    """Set agent resource attributes on the global tracer provider.

    Resource attributes apply to ALL spans in the trace. Call this BEFORE
    creating the agent to ensure attributes propagate correctly.

    Args:
        agent_schema: Agent-let JSON schema with metadata

    Example:
        >>> schema = {"json_schema_extra": {"fqn": "percolate.qa-agent", "version": "0.1.0"}}
        >>> set_agent_resource_attributes(agent_schema=schema)
    """
    if not settings.otel.enabled:
        return

    try:
        tracer_provider = trace.get_tracer_provider()

        # Extract agent metadata
        metadata = agent_schema.get("json_schema_extra", {}) if agent_schema else {}
        fqn = metadata.get("fqn", "unknown")
        version = metadata.get("version", "0.0.0")
        agent_uuid = _generate_agent_uuid(fqn)

        # Create resource with OpenInference conventions
        resource = Resource.create(
            {
                "service.name": settings.otel.service_name,
                "openinference.project.name": settings.project_name,
                "agent_uuid": agent_uuid,
                "agent_fqn": fqn,
                "agent_version": version,
            }
        )

        # Merge with existing resource
        if hasattr(tracer_provider, "_resource"):
            tracer_provider._resource = tracer_provider._resource.merge(resource)
            logger.debug(
                f"Set agent resource attributes: fqn={fqn}, version={version}, uuid={agent_uuid}"
            )

    except Exception as e:
        logger.debug(f"Failed to set agent resource attributes: {e}")


def set_agent_context_attributes(
    context: "AgentContext | None",
    agentlet_name: str | None,
    agent_schema: dict[str, Any] | None = None,
) -> None:
    """Set agent context attributes on the current span.

    Span attributes apply only to the current span and its children.
    Call this after creating the agent to track execution context.

    Args:
        context: Agent execution context
        agentlet_name: Agent-let schema URI
        agent_schema: Agent-let JSON schema (optional)

    Example:
        >>> ctx = AgentContext(tenant_id="tenant-123", user_id="user-456")
        >>> set_agent_context_attributes(ctx, "percolate.qa-agent", schema)
    """
    if not settings.otel.enabled:
        return

    try:
        current_span = trace.get_current_span()
        if not current_span.is_recording():
            return

        # Set context attributes
        if context:
            if context.tenant_id:
                current_span.set_attribute("percolate.tenant_id", context.tenant_id)
            if context.user_id:
                current_span.set_attribute("percolate.user_id", context.user_id)
            if context.session_id:
                current_span.set_attribute("percolate.session_id", context.session_id)
            if context.default_model:
                current_span.set_attribute("percolate.model", context.default_model)

        # Set agentlet attributes
        if agentlet_name:
            current_span.set_attribute("percolate.agentlet", agentlet_name)

        if context and context.agent_schema_uri:
            current_span.set_attribute("percolate.agent_schema_uri", context.agent_schema_uri)

        # Set agent schema attributes (FQN, version, UUID)
        if agent_schema:
            metadata = agent_schema.get("json_schema_extra", {})
            fqn = metadata.get("fqn")
            version = metadata.get("version")

            if fqn:
                agent_uuid = _generate_agent_uuid(fqn)
                current_span.set_attribute("agent_uuid", agent_uuid)
                current_span.set_attribute("agent_fqn", fqn)
            if version:
                current_span.set_attribute("agent_version", version)

        logger.debug("Set agent context attributes on current span")

    except Exception as e:
        logger.debug(f"Failed to set agent context attributes: {e}")
