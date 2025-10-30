from fastapi import FastAPI, Header, Response
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
import httpx
import os
import time
from collections import defaultdict
import asyncio

app = FastAPI()

# Prometheus metrics
active_tenants_gauge = Gauge('test_active_tenants', 'Number of active tenants', ['tier'])
request_counter = Counter('test_requests_total', 'Total requests', ['tenant_id', 'tier'])
affinity_counter = Counter('test_affinity_hits', 'Affinity hits', ['tenant_id', 'pod'])

# In-memory tenant tracking
tenant_last_seen = defaultdict(float)
tenant_to_pod = {}

BACKEND_SERVICE = os.getenv('BACKEND_SERVICE', 'http://test-api-small:8000')
TENANT_TIMEOUT = 300  # 5 minutes

async def cleanup_inactive_tenants():
    """Background task to clean up inactive tenants"""
    while True:
        await asyncio.sleep(30)
        now = time.time()
        inactive = [t for t, last in tenant_last_seen.items() if now - last > TENANT_TIMEOUT]
        for tenant in inactive:
            del tenant_last_seen[tenant]
            tenant_to_pod.pop(tenant, None)

        # Update active tenants metric
        active_count = len(tenant_last_seen)
        active_tenants_gauge.labels(tier='small').set(active_count)

@app.on_event("startup")
async def startup():
    asyncio.create_task(cleanup_inactive_tenants())

@app.get("/request")
async def make_request(x_tenant_id: str = Header(...)):
    """Route request to backend with tenant affinity"""
    tenant_last_seen[x_tenant_id] = time.time()
    request_counter.labels(tenant_id=x_tenant_id, tier='small').inc()

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BACKEND_SERVICE}/process",
            headers={"X-Tenant-ID": x_tenant_id},
            timeout=10.0
        )
        pod_name = response.json().get('pod')

        # Track affinity
        if x_tenant_id in tenant_to_pod:
            if tenant_to_pod[x_tenant_id] == pod_name:
                affinity_counter.labels(tenant_id=x_tenant_id, pod=pod_name).inc()
        tenant_to_pod[x_tenant_id] = pod_name

        return response.json()

@app.get("/simulate/{tenant_id}")
async def simulate_tenant(tenant_id: str, duration: int = 60):
    """Simulate tenant activity for testing"""
    end_time = time.time() + duration
    count = 0

    while time.time() < end_time:
        try:
            await make_request(x_tenant_id=tenant_id)
            count += 1
            await asyncio.sleep(1)
        except Exception as e:
            print(f"Error: {e}")

    return {"tenant_id": tenant_id, "requests": count}

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/health")
async def health():
    return {"status": "healthy", "active_tenants": len(tenant_last_seen)}
