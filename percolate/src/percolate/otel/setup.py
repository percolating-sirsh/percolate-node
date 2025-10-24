"""OpenTelemetry setup and instrumentation."""

from loguru import logger
from percolate.agents.context import AgentContext
from percolate.settings import settings

# Track if we've already set up instrumentation
_instrumentation_setup = False


def setup_instrumentation() -> None:
    """Initialize OpenTelemetry instrumentation.

    Idempotent - safe to call multiple times. Sets up:
    - OTLP exporter to Phoenix/Jaeger
    - Pydantic AI instrumentation
    - FastAPI instrumentation

    Only runs if settings.otel_enabled is True.
    """
    global _instrumentation_setup

    if not settings.otel_enabled:
        logger.debug("OTEL disabled in settings")
        return

    if _instrumentation_setup:
        logger.debug("OTEL already initialized")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from openinference.instrumentation.pydantic_ai import PydanticAIInstrumentor

        # Set up tracer provider
        tracer_provider = TracerProvider()
        trace.set_tracer_provider(tracer_provider)

        # Add OTLP exporter
        otlp_exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint)
        tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

        # Instrument Pydantic AI
        PydanticAIInstrumentor().instrument()

        _instrumentation_setup = True
        logger.info(f"OTEL instrumentation enabled: {settings.otel_endpoint}")

    except ImportError as e:
        logger.warning(f"OTEL dependencies not installed: {e}")
    except Exception as e:
        logger.error(f"Failed to setup OTEL instrumentation: {e}")


def set_agent_attributes(context: AgentContext | None, agentlet_name: str | None) -> None:
    """Set agent context attributes on the current span.

    Args:
        context: Agent execution context
        agentlet_name: Agent-let schema URI
    """
    if not settings.otel_enabled:
        return

    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span.is_recording():
            if context:
                if context.tenant_id:
                    span.set_attribute("percolate.tenant_id", context.tenant_id)
                if context.user_id:
                    span.set_attribute("percolate.user_id", context.user_id)
                if context.session_id:
                    span.set_attribute("percolate.session_id", context.session_id)
            if agentlet_name:
                span.set_attribute("percolate.agentlet", agentlet_name)

    except Exception as e:
        logger.debug(f"Failed to set OTEL attributes: {e}")
