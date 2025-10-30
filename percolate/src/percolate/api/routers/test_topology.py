"""Test topology API endpoints for Kubernetes deployment testing.

These endpoints simulate database node behavior for testing tenant affinity,
scaling, and replication patterns in Kind clusters.
"""

import os
import time
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Response
from prometheus_client import Counter, Gauge, generate_latest
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1", tags=["test-topology"])

# Prometheus metrics
ACTIVE_TENANTS = Gauge(
    "percolate_active_tenants",
    "Number of active tenants (last 5 minutes)",
    ["tier"],
)

TENANT_REQUESTS = Counter(
    "percolate_tenant_requests_total",
    "Total requests per tenant",
    ["tenant_id", "pod", "tier"],
)

AFFINITY_HITS = Counter(
    "percolate_affinity_hits_total",
    "Tenant affinity cache hits",
    ["tenant_id", "pod"],
)

# In-memory state for testing
tenant_last_seen: dict[str, float] = {}
tenant_data: dict[str, dict] = {}

# Pod metadata (from environment)
POD_NAME = os.getenv("POD_NAME", "unknown")
TIER = os.getenv("TIER", "small")


class ResourceQuery(BaseModel):
    """Mock resource query."""

    query: str
    limit: int = 10


class ResourceCreate(BaseModel):
    """Mock resource creation."""

    content: str
    tenant_id: str
    metadata: Optional[dict] = None


class SyncMessage(BaseModel):
    """Database replication sync message."""

    operation: str  # insert, update, delete
    tenant_id: str
    resource_id: str
    timestamp: float
    data: dict


@router.get("/resources")
async def search_resources(
    query: str,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    limit: int = 10,
) -> dict:
    """Mock semantic search endpoint.

    Simulates database read operation with tenant affinity tracking.
    Used for testing tenant→pod routing consistency.
    """
    # Track tenant activity
    tenant_last_seen[x_tenant_id] = time.time()

    # Update metrics
    TENANT_REQUESTS.labels(tenant_id=x_tenant_id, pod=POD_NAME, tier=TIER).inc()
    AFFINITY_HITS.labels(tenant_id=x_tenant_id, pod=POD_NAME).inc()

    # Update active tenants gauge (5-minute window)
    current_time = time.time()
    active_count = sum(
        1 for last_seen in tenant_last_seen.values() if current_time - last_seen < 300
    )
    ACTIVE_TENANTS.labels(tier=TIER).set(active_count)

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


@router.get("/entities/{entity_id}")
async def get_entity(
    entity_id: str,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
) -> dict:
    """Mock entity lookup endpoint.

    Simulates entity graph traversal from RocksDB.
    """
    # Track tenant activity
    tenant_last_seen[x_tenant_id] = time.time()
    TENANT_REQUESTS.labels(tenant_id=x_tenant_id, pod=POD_NAME, tier=TIER).inc()

    # Update active tenants gauge
    current_time = time.time()
    active_count = sum(
        1 for last_seen in tenant_last_seen.values() if current_time - last_seen < 300
    )
    ACTIVE_TENANTS.labels(tier=TIER).set(active_count)

    # Mock response
    return {
        "pod": POD_NAME,
        "tenant_id": x_tenant_id,
        "entity_id": entity_id,
        "name": f"Mock Entity {entity_id}",
        "properties": {
            "type": "test",
            "created_at": current_time,
        },
        "relationships": [],
    }


@router.post("/resources")
async def create_resource(
    resource: ResourceCreate,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
) -> dict:
    """Mock resource creation endpoint.

    Simulates database write with replication publishing to NATS.
    In real implementation, this would publish to NATS sync stream.
    """
    # Track tenant activity
    tenant_last_seen[x_tenant_id] = time.time()
    TENANT_REQUESTS.labels(tenant_id=x_tenant_id, pod=POD_NAME, tier=TIER).inc()

    # Update active tenants gauge
    current_time = time.time()
    active_count = sum(
        1 for last_seen in tenant_last_seen.values() if current_time - last_seen < 300
    )
    ACTIVE_TENANTS.labels(tier=TIER).set(active_count)

    # Store in mock database
    resource_id = f"resource-{int(current_time * 1000)}"
    if x_tenant_id not in tenant_data:
        tenant_data[x_tenant_id] = {}

    tenant_data[x_tenant_id][resource_id] = {
        "content": resource.content,
        "metadata": resource.metadata,
        "created_at": current_time,
        "pod": POD_NAME,
    }

    # TODO: Publish to NATS sync stream for replication
    # await nats_client.publish(
    #     f"percolate.sync.{x_tenant_id}",
    #     SyncMessage(
    #         operation="insert",
    #         tenant_id=x_tenant_id,
    #         resource_id=resource_id,
    #         timestamp=current_time,
    #         data=tenant_data[x_tenant_id][resource_id],
    #     ).model_dump_json().encode(),
    # )

    return {
        "pod": POD_NAME,
        "tenant_id": x_tenant_id,
        "resource_id": resource_id,
        "status": "created",
        "timestamp": current_time,
    }


@router.post("/sync")
async def receive_sync(
    sync: SyncMessage,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
) -> dict:
    """Mock replication sync endpoint.

    Receives sync messages from peer database nodes via NATS.
    Applies changes to local RocksDB replica.
    """
    current_time = time.time()

    # Apply sync operation
    if sync.tenant_id not in tenant_data:
        tenant_data[sync.tenant_id] = {}

    if sync.operation == "insert" or sync.operation == "update":
        tenant_data[sync.tenant_id][sync.resource_id] = sync.data
    elif sync.operation == "delete":
        tenant_data[sync.tenant_id].pop(sync.resource_id, None)

    # Calculate replication lag
    replication_lag_ms = (current_time - sync.timestamp) * 1000

    return {
        "pod": POD_NAME,
        "tenant_id": sync.tenant_id,
        "operation": sync.operation,
        "resource_id": sync.resource_id,
        "replication_lag_ms": replication_lag_ms,
        "status": "applied",
    }


@router.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint.

    Exposes metrics for KEDA scaling:
    - percolate_active_tenants: Number of active tenants (5-minute window)
    - percolate_tenant_requests_total: Request counter per tenant
    - percolate_affinity_hits_total: Tenant affinity hits
    """
    return Response(content=generate_latest(), media_type="text/plain")


@router.get("/health")
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


@router.get("/ready")
async def ready() -> dict:
    """Readiness check endpoint."""
    return {
        "status": "ready",
        "pod": POD_NAME,
        "tier": TIER,
    }
