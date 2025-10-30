# Test topology for tenant affinity and scaling

Minimal Kind setup to test the complex multi-tenant routing and scaling behavior without full infrastructure.

## Overview

This test topology focuses on **validating the core multi-tenant challenges**:

1. **Tenant affinity routing** - Requests for same tenant go to same pod
2. **Scale-to-zero behavior** - Pods scale down when idle, up on demand
3. **KEDA scaling triggers** - Prometheus metrics drive scaling decisions
4. **Consistent hashing** - Tenant-to-pod mapping remains stable
5. **Multi-tier behavior** - Different resource tiers scale independently

**What we skip** (not needed for topology testing):
- OpenBao (use mock secrets)
- NATS (use simple HTTP endpoints)
- Redis (use in-memory cache in gateway)
- S3 (not needed for affinity testing)
- Full RocksDB (use mock data store)

**Resource budget**: ~2GB total (vs ~5GB for full stack)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Test Gateway                          │
│  - Tenant routing logic                                  │
│  - In-memory tenant→pod cache                           │
│  - Prometheus metrics exporter                          │
│  - Simulates tenant requests                            │
└─────────────────────────────────────────────────────────┘
                           │
                           ↓ (Istio VirtualService with consistent hashing)
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ↓                  ↓                  ↓
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ API-small-0  │  │ API-small-1  │  │ API-small-2  │
│ Tenant: A,B  │  │ Tenant: C,D  │  │ Tenant: E,F  │
│ 256Mi RAM    │  │ 256Mi RAM    │  │ 256Mi RAM    │
└──────────────┘  └──────────────┘  └──────────────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
                           ↓
                ┌─────────────────────┐
                │  Prometheus         │
                │  - Scrapes metrics  │
                │  - KEDA queries     │
                └─────────────────────┘
                           │
                           ↓
                ┌─────────────────────┐
                │  KEDA ScaledObject  │
                │  - Scale 0→N        │
                │  - Cooldown: 60s    │
                └─────────────────────┘
```

## Components

### 1. Test Gateway (mock percolate-gateway)

Simple FastAPI service that:
- Accepts requests with `X-Tenant-ID` header
- Routes to backend API pods via Istio
- Exports Prometheus metrics: `test_active_tenants{tier="small"}`
- Maintains in-memory tenant→pod mapping
- Simulates realistic tenant traffic patterns

### 2. Test API (mock percolate-api)

Minimal service that:
- Responds to health checks
- Accepts tenant requests
- Returns pod hostname (for affinity verification)
- Exports metrics: `test_tenant_requests{tenant_id="A", pod="api-small-0"}`
- Sleeps for configurable duration (simulate work)

### 3. KEDA ScaledObject

Scales API pods based on:
- Metric: `test_active_tenants{tier="small"}`
- Threshold: 2 tenants per pod
- Min replicas: 0
- Max replicas: 5
- Cooldown: 60s

### 4. Istio VirtualService + DestinationRule

- Consistent hashing on `X-Tenant-ID` header
- Routes requests to same pod for same tenant

## Setup

### Create test services

Create `k8s/test-topology/test-gateway.yaml`:

```yaml
---
apiVersion: v1
kind: Service
metadata:
  name: test-gateway
  namespace: percolate-test
spec:
  type: LoadBalancer
  ports:
  - name: http
    port: 8080
    targetPort: 8080
  selector:
    app: test-gateway
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-gateway
  namespace: percolate-test
spec:
  replicas: 1
  selector:
    matchLabels:
      app: test-gateway
  template:
    metadata:
      labels:
        app: test-gateway
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"
        prometheus.io/path: "/metrics"
    spec:
      containers:
      - name: gateway
        image: localhost:5001/test-gateway:dev
        ports:
        - name: http
          containerPort: 8080
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 200m
            memory: 256Mi
        env:
        - name: BACKEND_SERVICE
          value: "http://test-api-small.percolate-test.svc.cluster.local:8000"
```

Create `k8s/test-topology/test-api.yaml`:

```yaml
---
apiVersion: v1
kind: Service
metadata:
  name: test-api-small
  namespace: percolate-test
  labels:
    app: test-api
    tier: small
spec:
  clusterIP: None  # Headless service for StatefulSet
  ports:
  - name: http
    port: 8000
    targetPort: 8000
  selector:
    app: test-api
    tier: small
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: test-api-small
  namespace: percolate-test
spec:
  serviceName: test-api-small
  replicas: 0  # Start at zero, let KEDA scale
  selector:
    matchLabels:
      app: test-api
      tier: small
  template:
    metadata:
      labels:
        app: test-api
        tier: small
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        prometheus.io/path: "/metrics"
    spec:
      containers:
      - name: api
        image: localhost:5001/test-api:dev
        ports:
        - name: http
          containerPort: 8000
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 200m
            memory: 512Mi
        env:
        - name: POD_NAME
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        - name: TIER
          value: "small"
```

Create `k8s/test-topology/istio-routing.yaml`:

```yaml
---
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: test-api-routing
  namespace: percolate-test
spec:
  hosts:
  - test-api-small.percolate-test.svc.cluster.local
  http:
  - route:
    - destination:
        host: test-api-small.percolate-test.svc.cluster.local
        port:
          number: 8000
---
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: test-api-affinity
  namespace: percolate-test
spec:
  host: test-api-small.percolate-test.svc.cluster.local
  trafficPolicy:
    loadBalancer:
      consistentHash:
        httpHeaderName: x-tenant-id
    connectionPool:
      tcp:
        maxConnections: 100
      http:
        http1MaxPendingRequests: 50
        http2MaxRequests: 100
```

Create `k8s/test-topology/keda-scaler.yaml`:

```yaml
---
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: test-api-small-scaler
  namespace: percolate-test
spec:
  scaleTargetRef:
    name: test-api-small
  minReplicaCount: 0
  maxReplicaCount: 5
  cooldownPeriod: 60
  pollingInterval: 10
  triggers:
  - type: prometheus
    metadata:
      serverAddress: http://prometheus.percolate-test.svc.cluster.local:9090
      metricName: test_active_tenants
      threshold: "2"
      query: |
        sum(test_active_tenants{tier="small"})
```

Create `k8s/test-topology/kustomization.yaml`:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: percolate-test

resources:
- namespace.yaml
- prometheus.yaml
- test-gateway.yaml
- test-api.yaml
- istio-routing.yaml
- keda-scaler.yaml
```

Create `k8s/test-topology/namespace.yaml`:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: percolate-test
  labels:
    istio-injection: enabled
```

## Test Images

### Test Gateway (Python)

Create `k8s/test-topology/images/test-gateway/app.py`:

```python
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
```

Create `k8s/test-topology/images/test-gateway/Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN pip install fastapi uvicorn httpx prometheus-client

COPY app.py .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Test API (Python)

Create `k8s/test-topology/images/test-api/app.py`:

```python
from fastapi import FastAPI, Header
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client import Response as PrometheusResponse
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
    return PrometheusResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/health")
async def health():
    return {"status": "healthy", "pod": POD_NAME}

@app.get("/ready")
async def ready():
    return {"status": "ready", "pod": POD_NAME}
```

Create `k8s/test-topology/images/test-api/Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN pip install fastapi uvicorn prometheus-client

COPY app.py .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Deployment Script

Create `k8s/test-topology/setup.sh`:

```bash
#!/bin/bash
set -euo pipefail

echo "Setting up test topology for tenant affinity and scaling"

# Create Kind cluster if needed
if ! kind get clusters | grep -q test-topology; then
    echo "Creating Kind cluster..."
    kind create cluster --name test-topology
fi

# Build test images
echo "Building test images..."
cd k8s/test-topology/images/test-gateway
docker build -t localhost:5001/test-gateway:dev .

cd ../test-api
docker build -t localhost:5001/test-api:dev .

# Load images into Kind
echo "Loading images into Kind..."
kind load docker-image localhost:5001/test-gateway:dev --name test-topology
kind load docker-image localhost:5001/test-api:dev --name test-topology

# Install Istio (minimal)
if ! kubectl get namespace istio-system &> /dev/null; then
    echo "Installing Istio..."
    istioctl install --set profile=minimal -y
fi

# Install KEDA
if ! kubectl get namespace keda &> /dev/null; then
    echo "Installing KEDA..."
    kubectl apply -f https://github.com/kedacore/keda/releases/download/v2.13.0/keda-2.13.0.yaml
fi

# Deploy Prometheus
echo "Deploying Prometheus..."
kubectl apply -f k8s/test-topology/prometheus.yaml

# Deploy test topology
echo "Deploying test topology..."
kubectl apply -k k8s/test-topology/

echo "Waiting for gateway to be ready..."
kubectl wait --for=condition=ready pod -l app=test-gateway -n percolate-test --timeout=120s

echo ""
echo "Test topology deployed!"
echo ""
echo "Access:"
echo "  Gateway: kubectl port-forward -n percolate-test svc/test-gateway 8080:8080"
echo ""
echo "Test commands:"
echo "  # Simulate tenant A"
echo "  curl http://localhost:8080/simulate/tenant-a?duration=120"
echo ""
echo "  # Watch scaling"
echo "  watch kubectl get pods -n percolate-test"
echo ""
echo "  # Check metrics"
echo "  curl http://localhost:8080/metrics"
```

## Testing Scenarios

### Test 1: Scale from zero

```bash
# Port-forward gateway
kubectl port-forward -n percolate-test svc/test-gateway 8080:8080 &

# Verify zero replicas
kubectl get statefulset test-api-small -n percolate-test
# Should show 0/0 replicas

# Simulate tenant A (2 minutes of activity)
curl http://localhost:8080/simulate/tenant-a?duration=120

# Watch scaling in another terminal
watch kubectl get pods -n percolate-test

# Expected: Pod scales up within 30 seconds
```

### Test 2: Tenant affinity

```bash
# Simulate 4 tenants concurrently
for tenant in A B C D; do
  curl http://localhost:8080/simulate/tenant-${tenant}?duration=300 &
done

# Watch pod assignment
watch kubectl get pods -n percolate-test -o wide

# Check affinity metrics
curl http://localhost:8080/metrics | grep test_affinity_hits

# Expected:
# - 2 pods scale up (threshold is 2 tenants/pod)
# - Each tenant consistently routes to same pod
# - Affinity hit counter increases
```

### Test 3: Scale-to-zero cooldown

```bash
# Simulate tenant activity for 60s
curl http://localhost:8080/simulate/tenant-e?duration=60

# Wait and watch
watch kubectl get pods -n percolate-test

# Expected:
# - Pod scales up immediately
# - After 60s of no activity, pod stays up during cooldown (60s)
# - After cooldown, pod scales to zero
```

### Test 4: Multi-tenant scaling

```bash
# Simulate 10 tenants
for i in {1..10}; do
  curl http://localhost:8080/simulate/tenant-${i}?duration=180 &
done

# Watch scaling
watch kubectl get pods -n percolate-test

# Expected:
# - Scales to 5 pods (10 tenants / 2 per pod)
# - Each tenant routes to consistent pod
# - Prometheus shows 10 active tenants
```

### Test 5: Consistent hashing verification

```bash
# Send 100 requests for tenant-x
for i in {1..100}; do
  curl -H "X-Tenant-ID: tenant-x" http://localhost:8080/request
done

# Check which pod handled requests
curl http://localhost:8080/metrics | grep -A 10 test_tenant_requests

# Expected:
# - All 100 requests go to same pod
# - test_affinity_hits counter shows 99 hits (first request establishes, rest hit)
```

## Verification

### Check KEDA scaling

```bash
# View ScaledObject status
kubectl get scaledobjects -n percolate-test

# Describe for details
kubectl describe scaledobject test-api-small-scaler -n percolate-test

# Check HPA created by KEDA
kubectl get hpa -n percolate-test
```

### Check Istio routing

```bash
# Verify VirtualService
kubectl get virtualservice -n percolate-test

# Verify DestinationRule
kubectl get destinationrule -n percolate-test

# Check routing config
istioctl proxy-config routes test-gateway-<pod>.percolate-test
```

### Check Prometheus metrics

```bash
# Port-forward Prometheus
kubectl port-forward -n percolate-test svc/prometheus 9090:9090 &

# Query active tenants
curl "http://localhost:9090/api/v1/query?query=test_active_tenants"

# Query affinity hits
curl "http://localhost:9090/api/v1/query?query=rate(test_affinity_hits[5m])"
```

## Expected Results

| Test | Metric | Expected Value |
|------|--------|----------------|
| Scale from zero | Time to first response | <30s |
| Tenant affinity | Affinity hit rate | >95% |
| Scale-to-zero | Cooldown period | 60s |
| Multi-tenant | Pods scaled | 5 (10 tenants / 2) |
| Consistent hashing | Requests to same pod | 100% |

## Cleanup

```bash
# Delete test topology
kubectl delete namespace percolate-test

# Delete Kind cluster
kind delete cluster --name test-topology
```

## Benefits of This Approach

1. **Focused testing** - Only tests the complex parts (routing, scaling)
2. **Fast iteration** - ~2GB RAM, quick rebuild cycles
3. **Clear validation** - Simple pass/fail criteria
4. **No infrastructure overhead** - No OpenBao, NATS, Redis, S3
5. **Real behavior** - Uses actual Istio and KEDA
6. **Easy debugging** - Minimal components to troubleshoot

## Next Steps

Once topology is validated:
1. Add this logic to full `percolate-gateway`
2. Implement tenant→pod caching in Redis
3. Add NATS-based scaling triggers
4. Deploy full infrastructure
5. Test with real workloads
