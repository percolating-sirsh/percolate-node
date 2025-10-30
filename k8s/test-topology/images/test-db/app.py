"""Test database node for topology validation.

Uses both OpenTelemetry (for OTLP export) and Prometheus client (for /metrics endpoint).
"""

import os
import time
from typing import Optional

from fastapi import FastAPI, Header, Response
from prometheus_client import Counter, Gauge, generate_latest
from pydantic import BaseModel

# OpenTelemetry imports
from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Pod metadata
POD_NAME = os.getenv("POD_NAME", "unknown")
TIER = os.getenv("TIER", "small")
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")

# Setup OpenTelemetry
resource = Resource.create(
    {
        "service.name": "test-db",
        "service.instance.id": POD_NAME,
        "deployment.environment": "test",
        "tier": TIER,
    }
)

# OTLP exporter for OpenTelemetry Collector
otlp_exporter = OTLPMetricExporter(endpoint=OTEL_ENDPOINT, insecure=True)
reader = PeriodicExportingMetricReader(otlp_exporter, export_interval_millis=15000)
meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
metrics.set_meter_provider(meter_provider)

# Get meter for creating metrics
meter = metrics.get_meter(__name__)

# OpenTelemetry metrics (exported via OTLP)
otel_active_tenants = meter.create_up_down_counter(
    "percolate.active_tenants",
    description="Number of active tenants (last 5 minutes)",
    unit="tenants",
)

otel_tenant_requests = meter.create_counter(
    "percolate.tenant_requests",
    description="Total requests per tenant",
    unit="requests",
)

otel_affinity_hits = meter.create_counter(
    "percolate.affinity_hits",
    description="Tenant affinity cache hits",
    unit="hits",
)

# Prometheus metrics (for /metrics endpoint - used by KEDA)
prom_active_tenants_gauge = Gauge(
    "percolate_active_tenants",
    "Number of active tenants (last 5 minutes)",
    ["tier"],
)

prom_tenant_requests_counter = Counter(
    "percolate_tenant_requests_total",
    "Total requests per tenant",
    ["tenant_id", "pod", "tier"],
)

prom_affinity_hits_counter = Counter(
    "percolate_affinity_hits_total",
    "Tenant affinity cache hits",
    ["tenant_id", "pod"],
)

# Initialize FastAPI
app = FastAPI()

# Instrument FastAPI with OpenTelemetry (auto-tracing)
FastAPIInstrumentor.instrument_app(app)

# In-memory state
tenant_last_seen: dict[str, float] = {}
tenant_data: dict[str, dict] = {}


class ResourceCreate(BaseModel):
    """Resource creation request."""

    content: str
    metadata: Optional[dict] = None


class SyncMessage(BaseModel):
    """Replication sync message."""

    operation: str
    tenant_id: str
    resource_id: str
    timestamp: float
    data: dict


@app.get("/api/v1/resources")
async def search_resources(
    query: str,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    limit: int = 10,
) -> dict:
    """Mock semantic search endpoint."""
    # Track tenant activity
    tenant_last_seen[x_tenant_id] = time.time()

    # Update active tenants gauge (5-minute window)
    current_time = time.time()
    active_count = sum(
        1 for last_seen in tenant_last_seen.values() if current_time - last_seen < 300
    )

    # Update Prometheus metrics (for KEDA)
    prom_tenant_requests_counter.labels(
        tenant_id=x_tenant_id, pod=POD_NAME, tier=TIER
    ).inc()
    prom_affinity_hits_counter.labels(tenant_id=x_tenant_id, pod=POD_NAME).inc()
    prom_active_tenants_gauge.labels(tier=TIER).set(active_count)

    # Update OpenTelemetry metrics (for OTLP export)
    otel_tenant_requests.add(
        1, {"tenant_id": x_tenant_id, "pod": POD_NAME, "tier": TIER}
    )
    otel_affinity_hits.add(1, {"tenant_id": x_tenant_id, "pod": POD_NAME})
    # Note: OTEL doesn't have set() for gauges, so we track via counter deltas

    # Mock response
    return {
        "pod": POD_NAME,
        "tenant_id": x_tenant_id,
        "query": query,
        "results": [
            {
                "id": f"resource-{i}",
                "content": f"Mock result {i} for query: {query}",
                "score": 0.9 - (i * 0.1),
            }
            for i in range(min(limit, 3))
        ],
        "total": 3,
        "timestamp": current_time,
    }


@app.get("/api/v1/entities/{entity_id}")
async def get_entity(
    entity_id: str,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
) -> dict:
    """Mock entity lookup endpoint."""
    tenant_last_seen[x_tenant_id] = time.time()

    current_time = time.time()
    active_count = sum(
        1 for last_seen in tenant_last_seen.values() if current_time - last_seen < 300
    )

    # Prometheus metrics
    prom_tenant_requests_counter.labels(
        tenant_id=x_tenant_id, pod=POD_NAME, tier=TIER
    ).inc()
    prom_active_tenants_gauge.labels(tier=TIER).set(active_count)

    # OpenTelemetry metrics
    otel_tenant_requests.add(
        1, {"tenant_id": x_tenant_id, "pod": POD_NAME, "tier": TIER}
    )

    return {
        "pod": POD_NAME,
        "tenant_id": x_tenant_id,
        "entity_id": entity_id,
        "name": f"Mock Entity {entity_id}",
        "properties": {"type": "test", "created_at": current_time},
        "relationships": [],
    }


@app.post("/api/v1/resources")
async def create_resource(
    resource: ResourceCreate,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
) -> dict:
    """Mock resource creation endpoint."""
    tenant_last_seen[x_tenant_id] = time.time()

    current_time = time.time()
    active_count = sum(
        1 for last_seen in tenant_last_seen.values() if current_time - last_seen < 300
    )

    # Prometheus metrics
    prom_tenant_requests_counter.labels(
        tenant_id=x_tenant_id, pod=POD_NAME, tier=TIER
    ).inc()
    prom_active_tenants_gauge.labels(tier=TIER).set(active_count)

    # OpenTelemetry metrics
    otel_tenant_requests.add(
        1, {"tenant_id": x_tenant_id, "pod": POD_NAME, "tier": TIER}
    )

    resource_id = f"resource-{int(current_time * 1000)}"
    if x_tenant_id not in tenant_data:
        tenant_data[x_tenant_id] = {}

    tenant_data[x_tenant_id][resource_id] = {
        "content": resource.content,
        "metadata": resource.metadata,
        "created_at": current_time,
        "pod": POD_NAME,
    }

    return {
        "pod": POD_NAME,
        "tenant_id": x_tenant_id,
        "resource_id": resource_id,
        "status": "created",
        "timestamp": current_time,
    }


@app.post("/api/v1/sync")
async def receive_sync(
    sync: SyncMessage,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
) -> dict:
    """Mock replication sync endpoint."""
    current_time = time.time()

    if sync.tenant_id not in tenant_data:
        tenant_data[sync.tenant_id] = {}

    if sync.operation in ["insert", "update"]:
        tenant_data[sync.tenant_id][sync.resource_id] = sync.data
    elif sync.operation == "delete":
        tenant_data[sync.tenant_id].pop(sync.resource_id, None)

    replication_lag_ms = (current_time - sync.timestamp) * 1000

    return {
        "pod": POD_NAME,
        "tenant_id": sync.tenant_id,
        "operation": sync.operation,
        "resource_id": sync.resource_id,
        "replication_lag_ms": replication_lag_ms,
        "status": "applied",
    }


@app.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type="text/plain")


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "pod": POD_NAME,
        "tier": TIER,
        "active_tenants": len(
            [
                t
                for t, last_seen in tenant_last_seen.items()
                if time.time() - last_seen < 300
            ]
        ),
    }


@app.get("/ready")
async def ready() -> dict:
    """Readiness check endpoint."""
    return {"status": "ready", "pod": POD_NAME, "tier": TIER}
