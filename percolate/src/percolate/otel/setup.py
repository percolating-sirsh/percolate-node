"""OpenTelemetry setup and instrumentation with OpenInference semantics."""

from loguru import logger
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import Span, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from percolate.settings import settings

# Track if we've already set up instrumentation
_instrumentation_setup = False


class AgentAttributeSpanProcessor(SpanProcessor):
    """Custom span processor that adds agent_uuid to ALL spans as a span attribute.

    The OTEL collector filters spans by checking span attributes (context: span),
    so we need agent_uuid on every span, not just in resource attributes.
    """

    def on_start(self, span: Span, parent_context=None) -> None:
        """Called when a span starts - add agent_uuid from resource to span attributes."""
        # Get tracer provider to access resource
        tracer_provider = trace.get_tracer_provider()

        if not hasattr(tracer_provider, "_resource"):
            return

        # Get agent attributes from resource
        resource = tracer_provider._resource

        if resource and hasattr(resource, "attributes"):
            agent_uuid = resource.attributes.get("agent_uuid")
            agent_fqn = resource.attributes.get("agent_fqn")
            agent_version = resource.attributes.get("agent_version")

            # Add to span attributes (required for OTEL collector routing)
            if agent_uuid:
                span.set_attribute("agent_uuid", agent_uuid)
            if agent_fqn:
                span.set_attribute("agent_fqn", agent_fqn)
            if agent_version:
                span.set_attribute("agent_version", agent_version)

    def on_end(self, span: Span) -> None:
        """Called when a span ends - no-op."""
        pass

    def shutdown(self) -> None:
        """Called when the processor is being shut down - no-op."""
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Called to flush any buffered spans - no-op, returns True."""
        return True


def setup_instrumentation() -> None:
    """Initialize OpenTelemetry instrumentation for Pydantic AI.

    This function is idempotent and safe to call multiple times.
    Subsequent calls after successful initialization are no-ops.

    Architecture:
        - OTEL traces flow to OTEL Collector (K8s) then relay to Phoenix
        - NOT direct to Phoenix (separate feedback API handles that)
        - SimpleSpanProcessor used (no batching, lower memory)
    """
    global _instrumentation_setup

    if not settings.otel.enabled:
        logger.debug("OTEL instrumentation disabled")
        return

    # Idempotency check - only set up once
    if _instrumentation_setup:
        logger.debug("OTEL instrumentation already configured")
        return

    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        # Create resource with service name and project name (OpenInference convention)
        resource = Resource.create(
            {
                "service.name": settings.otel.service_name,
                "openinference.project.name": settings.project_name,
            }
        )

        # Initialize tracer provider
        tracer_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(tracer_provider)

        # Configure OTLP exporter (uses OTEL_EXPORTER_OTLP_ENDPOINT env var)
        # Collector relays to Phoenix - never export directly to Phoenix
        exporter = OTLPSpanExporter(insecure=True)

        # Add custom processor FIRST to copy agent_uuid from resource to span attributes
        # This is REQUIRED for OTEL collector routing (checks span attributes, not resource)
        tracer_provider.add_span_processor(AgentAttributeSpanProcessor())
        logger.debug("Added AgentAttribute span processor for collector routing")

        # Add OpenInference span processor for PydanticAI
        try:
            from openinference.instrumentation.pydantic_ai import OpenInferenceSpanProcessor

            tracer_provider.add_span_processor(OpenInferenceSpanProcessor())
            logger.debug("Added OpenInference span processor")
        except ImportError:
            logger.warning(
                "openinference-instrumentation-pydantic-ai not installed. "
                "Install with: uv add openinference-instrumentation-pydantic-ai"
            )

        # Add OTLP exporter with simple processing (no batching, lower memory)
        tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))

        # Mark as successfully set up
        _instrumentation_setup = True

        logger.success(
            f"OTEL instrumentation configured for {settings.otel.service_name} "
            f"(exports to OTEL collector)"
        )

    except Exception as e:
        logger.error(f"Failed to setup OTEL instrumentation: {e}")
        raise RuntimeError(
            "OTEL instrumentation setup failed. "
            "Check configuration or disable with OTEL__ENABLED=false"
        ) from e
