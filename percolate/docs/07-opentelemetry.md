# OpenTelemetry tracing with OpenInference semantics

This document describes Percolate's OpenTelemetry (OTEL) instrumentation for tracking agent execution with proper OpenInference semantic conventions for LLM observability.

## Overview

Percolate integrates OTEL tracing for Pydantic AI agents with the following architecture:

```
Agent Execution → OTEL SDK → OTEL Collector (K8s) → Phoenix (observability)
                       ↓
                  OpenInference
                  Span Processor
```

**Key principles:**
- OTEL is **disabled by default** (enable via `OTEL__ENABLED=true`)
- Traces flow through OTEL Collector, never directly to Phoenix
- OpenInference semantic conventions for LLM-specific attributes
- Custom span processor ensures agent metadata on every span
- Idempotent setup (safe to call multiple times)

## Configuration

### Environment variables

OTEL configuration uses nested settings with `OTEL__` prefix:

```bash
# Enable OTEL instrumentation (disabled by default)
OTEL__ENABLED=true

# Service name for traces (identifies this service)
OTEL__SERVICE_NAME=percolate-api

# Phoenix endpoint for feedback annotations (NOT for traces)
OTEL__PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006

# Phoenix Cloud API key (optional)
OTEL__PHOENIX_API_KEY=your-api-key

# OTEL Collector endpoint (standard OTEL env var)
# Production: http://otel-collector.default.svc.cluster.local:4317
# Local testing: kubectl port-forward svc/otel-collector 4317:4317
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# Project name (OpenInference convention for Phoenix projects)
PERCOLATE_PROJECT_NAME=percolate
```

### Settings structure

OTEL settings are accessed via `settings.otel`:

```python
from percolate.settings import settings

print(settings.otel.enabled)           # False (default)
print(settings.otel.service_name)      # "percolate-api"
print(settings.project_name)           # "percolate"
```

## Architecture

### Components

1. **setup_instrumentation()** (`otel/setup.py`)
   - Initializes OTEL tracer provider with OpenInference resource
   - Adds custom span processor for agent attribute propagation
   - Adds OpenInference span processor for Pydantic AI
   - Configures OTLP exporter to send to collector

2. **AgentAttributeSpanProcessor** (`otel/setup.py`)
   - Custom span processor that copies agent_uuid from resource to span attributes
   - Required for OTEL collector routing (collector filters on span attributes)
   - Runs on every span start event

3. **set_agent_resource_attributes()** (`otel/attributes.py`)
   - Sets resource attributes that apply to ALL spans in the trace
   - Extracts agent metadata (FQN, version) from agent schema
   - Generates deterministic agent_uuid from FQN
   - Called BEFORE agent creation

4. **set_agent_context_attributes()** (`otel/attributes.py`)
   - Sets span attributes for current execution context
   - Includes tenant_id, user_id, session_id, model
   - Called AFTER agent creation

5. **get_current_trace_context()** (`otel/context.py`)
   - Retrieves current trace_id and span_id
   - Used for linking feedback to traces

### Flow

The agent factory integrates OTEL at creation time:

```python
async def create_agent(context, agent_schema_override=None, ...):
    # 1. Initialize OTEL (idempotent, no-op if disabled)
    setup_instrumentation()

    # 2. Load agent schema
    agent_schema = load_agentlet_schema(...)

    # 3. Set resource attributes BEFORE creating agent
    set_agent_resource_attributes(agent_schema=agent_schema)

    # 4. Create agent with instrument=True
    agent = Agent(
        model=model,
        system_prompt=system_prompt,
        tools=tools,
        instrument=True  # Enable OTEL instrumentation
    )

    # 5. Set span attributes AFTER creating agent
    set_agent_context_attributes(
        context=context,
        agentlet_name=agentlet_name,
        agent_schema=agent_schema
    )

    return agent
```

## Attributes

### Resource attributes (apply to all spans)

Set via `set_agent_resource_attributes()`:

| Attribute | Example | Description |
|-----------|---------|-------------|
| `service.name` | `percolate-api` | Service identifier |
| `openinference.project.name` | `percolate` | Phoenix project name |
| `agent_uuid` | `a1b2c3d4...` | Hash of agent FQN |
| `agent_fqn` | `percolate.qa-agent` | Fully qualified agent name |
| `agent_version` | `0.1.0` | Agent schema version |

### Span attributes (apply to current span)

Set via `set_agent_context_attributes()`:

| Attribute | Example | Description |
|-----------|---------|-------------|
| `percolate.tenant_id` | `tenant-123` | Tenant scope |
| `percolate.user_id` | `user-456` | User identifier |
| `percolate.session_id` | `session-789` | Session/chat ID |
| `percolate.model` | `claude-sonnet-4-5` | LLM model name |
| `percolate.agentlet` | `percolate.qa-agent` | Agent-let name |
| `percolate.agent_schema_uri` | `percolate.qa-agent` | Full schema URI |
| `agent_uuid` | `a1b2c3d4...` | Agent UUID (copied from resource) |
| `agent_fqn` | `percolate.qa-agent` | Agent FQN (copied from resource) |
| `agent_version` | `0.1.0` | Agent version (copied from resource) |

**Note:** `agent_uuid`, `agent_fqn`, and `agent_version` appear in both resource and span attributes because the OTEL collector filters on span attributes, not resource attributes.

## Local development

### Without OTEL (default)

OTEL is disabled by default, so no setup is required:

```bash
# OTEL disabled - no traces sent
uv run percolate serve
```

### With OTEL (local testing)

To test OTEL locally, you need to run an OTEL Collector and Phoenix:

```bash
# 1. Port-forward OTEL Collector from K8s cluster
kubectl port-forward svc/otel-collector 4317:4317

# 2. Port-forward Phoenix for viewing traces
kubectl port-forward svc/phoenix 6006:6006

# 3. Enable OTEL and set endpoint
export OTEL__ENABLED=true
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# 4. Start API
uv run percolate serve

# 5. Open Phoenix UI
open http://localhost:6006
```

## Kubernetes deployment

In production (K8s cluster), configure OTEL to send to the cluster's OTEL Collector:

```yaml
# k8s/percolate-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: percolate-api
spec:
  template:
    spec:
      containers:
      - name: percolate-api
        env:
        # Enable OTEL
        - name: OTEL__ENABLED
          value: "true"

        # Service name
        - name: OTEL__SERVICE_NAME
          value: "percolate-api"

        # OTEL Collector endpoint (in-cluster service)
        - name: OTEL_EXPORTER_OTLP_ENDPOINT
          value: "http://otel-collector.default.svc.cluster.local:4317"

        # Phoenix endpoint for feedback (in-cluster service)
        - name: OTEL__PHOENIX_COLLECTOR_ENDPOINT
          value: "http://phoenix.default.svc.cluster.local:6006"

        # Project name
        - name: PERCOLATE_PROJECT_NAME
          value: "percolate"
```

## Troubleshooting

### OTEL not initializing

**Symptom:** No traces appear in Phoenix

**Check:**
1. Is `OTEL__ENABLED=true` set?
2. Is `OTEL_EXPORTER_OTLP_ENDPOINT` reachable?
3. Check logs for "OTEL instrumentation configured" message

```bash
# Verify settings
python3 -c "from percolate.settings import settings; print(settings.otel.enabled)"

# Check endpoint connectivity
curl -v http://localhost:4317
```

### Missing agent attributes

**Symptom:** Traces appear but lack agent metadata

**Check:**
1. Is agent schema loaded correctly?
2. Does schema have `json_schema_extra.fqn` and `json_schema_extra.version`?
3. Is `set_agent_resource_attributes()` called before agent creation?

```python
# Verify agent schema structure
agent_schema = load_agentlet_schema(...)
metadata = agent_schema.get("json_schema_extra", {})
print(f"FQN: {metadata.get('fqn')}")
print(f"Version: {metadata.get('version')}")
```

### Circular import errors

**Symptom:** `ImportError: cannot import name 'set_agent_context_attributes' from partially initialized module`

**Solution:** Ensure `percolate.otel.attributes` uses `TYPE_CHECKING` for `AgentContext`:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from percolate.agents.context import AgentContext

def set_agent_context_attributes(context: "AgentContext | None", ...):
    ...
```

## References

- [OpenInference Semantic Conventions](https://github.com/Arize-ai/openinference)
- [OpenTelemetry Python SDK](https://opentelemetry-python.readthedocs.io/)
- [Pydantic AI Instrumentation](https://ai.pydantic.dev/observability/)
- [Arize Phoenix](https://docs.arize.com/phoenix)
