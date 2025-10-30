from fastapi import FastAPI, Header, Response
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
import os
import time

app = FastAPI()

POD_NAME = os.getenv('POD_NAME', 'unknown')
TIER = os.getenv('TIER', 'small')

# Prometheus metrics
request_counter = Counter('test_tenant_requests', 'Requests per tenant', ['tenant_id', 'pod', 'tier'])

@app.get("/process")
async def process(x_tenant_id: str = Header(...)):
    """Process tenant request"""
    request_counter.labels(tenant_id=x_tenant_id, pod=POD_NAME, tier=TIER).inc()

    # Simulate some work
    time.sleep(0.1)

    return {
        "pod": POD_NAME,
        "tenant_id": x_tenant_id,
        "tier": TIER,
        "timestamp": time.time()
    }

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/health")
async def health():
    return {"status": "healthy", "pod": POD_NAME}

@app.get("/ready")
async def ready():
    return {"status": "ready", "pod": POD_NAME}
