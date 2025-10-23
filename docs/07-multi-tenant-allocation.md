# Multi-Tenant Resource Allocation

## Overview

Percolate nodes run in Kubernetes as horizontally-scaled pods, each capable of serving multiple tenants. The system manages tenant lifecycle with **data temperature awareness** - hot (active), warm (idle), cold (archived) - to optimize resource allocation.

**Design Philosophy:**
- Start simple: Accept cold-start latency for data warming
- Lazy loading: Load tenant data on-demand
- Graceful eviction: Unload idle tenants to free resources
- Works elegantly: Same code runs locally and in scaled K8s pods
- Resource-aware: Scale based on active tenant count, not total tenants

## Tenant Tiers

Percolate supports **tiered tenants** with different resource allocations based on pricing. Each tier runs in separate K8s deployments and scales independently.

### Tier A: Premium ($49/month)

**Resource Allocation:**
- Dedicated CPU: 200m guaranteed
- Memory: 500MB per tenant
- Keep-warm: Always loaded (no cold starts)
- Max tenants per pod: 8
- SLA: 99.9% uptime, <100ms p95 latency

**Pod Spec:**
```yaml
resources:
  requests:
    memory: "4Gi"
    cpu: "1600m"
  limits:
    memory: "5Gi"
    cpu: "2000m"
```

**Scaling:**
- Min pods: 2 (HA)
- Max pods: 50
- Target: 6 tenants per pod

### Tier B: Standard ($19/month)

**Resource Allocation:**
- Shared CPU: 50m average
- Memory: 200MB per tenant
- Warm standby: 5min idle tolerance
- Max tenants per pod: 15
- SLA: 99% uptime, <500ms p95 latency

**Pod Spec:**
```yaml
resources:
  requests:
    memory: "3Gi"
    cpu: "750m"
  limits:
    memory: "4Gi"
    cpu: "1500m"
```

**Scaling:**
- Min pods: 1
- Max pods: 100
- Target: 12 tenants per pod

### Tier C: Free

**Resource Allocation:**
- Shared CPU: 20m average
- Memory: 100MB per tenant
- Cold starts: >1min idle eviction
- Max tenants per pod: 25
- SLA: Best effort, <2s p95 latency

**Pod Spec:**
```yaml
resources:
  requests:
    memory: "2Gi"
    cpu: "500m"
  limits:
    memory: "3Gi"
    cpu: "1000m"
```

**Scaling:**
- Min pods: 1
- Max pods: 200
- Target: 20 tenants per pod

### Multi-Tier Architecture

```
Gateway (Tenant Router)
    │
    ├─→ Tier A Deployment (Premium)
    │   ├─→ Pod A-1 (6 tenants)
    │   ├─→ Pod A-2 (5 tenants)
    │   └─→ Pod A-3 (7 tenants)
    │
    ├─→ Tier B Deployment (Standard)
    │   ├─→ Pod B-1 (12 tenants)
    │   ├─→ Pod B-2 (14 tenants)
    │   ├─→ Pod B-3 (11 tenants)
    │   └─→ ... (scales to 100 pods)
    │
    └─→ Tier C Deployment (Free)
        ├─→ Pod C-1 (20 tenants)
        ├─→ Pod C-2 (23 tenants)
        ├─→ Pod C-3 (19 tenants)
        └─→ ... (scales to 200 pods)
```

**Benefits:**
- **Resource isolation**: Premium tenants unaffected by free tier load
- **Independent scaling**: Each tier scales based on its own metrics
- **Cost optimization**: Pack free tenants densely, give premium tenants space
- **SLA enforcement**: Different QoS per tier
- **Fair billing**: Pay for what you get

## Tenant Lifecycle States

### Hot (Active)
**Definition:** Tenant with active requests within tier-specific timeout

**Tier-Specific Timeouts:**
- Tier A (Premium): Always hot (keep-warm enabled)
- Tier B (Standard): Last 5 minutes
- Tier C (Free): Last 1 minute

**Characteristics:**
- RocksDB fully loaded in memory
- HNSW index loaded
- Agent sessions active
- Background workers running

**Resource Footprint by Tier:**
- Tier A: 500MB memory, 200m CPU
- Tier B: 200MB memory, 50m CPU
- Tier C: 100MB memory, 20m CPU

### Warm (Idle)
**Definition:** Tenant idle beyond hot threshold but within warm window

**Tier-Specific Windows:**
- Tier A (Premium): N/A (never warm, always hot)
- Tier B (Standard): 5-60 minutes idle
- Tier C (Free): 1-10 minutes idle

**Characteristics:**
- RocksDB closed, data on disk
- HNSW index unloaded
- Agent sessions suspended
- Background workers paused

**Resource Footprint:**
- Memory: ~5MB metadata (all tiers)
- CPU: Minimal health checks
- Disk I/O: None

### Cold (Archived)
**Definition:** Tenant inactive beyond warm window

**Tier-Specific Windows:**
- Tier A (Premium): N/A (never cold)
- Tier B (Standard): >60 minutes idle
- Tier C (Free): >10 minutes idle

**Characteristics:**
- All in-memory state evicted
- RocksDB files remain on disk (local) or S3 (cloud)
- No active workers
- Requires full cold-start on next access

**Resource Footprint:**
- Memory: 0 (only registry entry)
- CPU: 0
- Disk: Persistent storage only

## Pod Resource Model

### Pod Capacity

Each pod manages a dynamic set of tenants:

```
Pod Capacity:
- Max hot tenants: 20 (memory bound)
- Max warm tenants: 100 (metadata only)
- Max cold tenants: unlimited (registry only)
```

**Example:**
- Pod with 4GB RAM can serve:
  - 20 hot tenants × 200MB = 4GB (memory saturated)
  - OR 10 hot + 50 warm = 2GB + 250MB = comfortable
  - Cold tenants have no memory impact

### Resource Allocation

```yaml
# Pod resource spec
resources:
  requests:
    memory: "2Gi"
    cpu: "1000m"
  limits:
    memory: "4Gi"
    cpu: "2000m"

# Hot tenant allocation
hot_tenant_memory: 150MB  # average
hot_tenant_cpu: 50m       # average, spikes to 200m

# Warm tenant allocation
warm_tenant_memory: 5MB   # metadata only
warm_tenant_cpu: 1m       # health checks
```

## Tenant Loading Strategy

### Lazy Loading on Request

When a request arrives for a tenant:

```python
async def handle_request(tenant_id: str, request: Request):
    tenant = await tenant_manager.get_or_load(tenant_id)

    # Tenant states:
    # - Hot: Returns immediately (already loaded)
    # - Warm: Loads RocksDB + HNSW (~500ms)
    # - Cold: Loads from disk/S3 (~2-5s)

    return await tenant.process_request(request)
```

**Cold Start Latency:**
- Warm → Hot: 500ms (load RocksDB from local disk)
- Cold → Hot: 2-5s (download from S3 if needed, then load)

**User Experience:**
- First request after idle: "Warming up your workspace..."
- Subsequent requests: Instant

### Eviction Policy

**Trigger:** Pod memory usage > 80%

**Strategy:** Evict least-recently-used warm tenants

```python
class TenantManager:
    async def evict_if_needed(self):
        if self.memory_usage_percent() > 80:
            # Sort tenants by last access time
            tenants = sorted(
                self.hot_tenants.values(),
                key=lambda t: t.last_access_time
            )

            # Evict oldest until memory < 70%
            for tenant in tenants:
                if self.memory_usage_percent() < 70:
                    break

                await self.evict_tenant(tenant.id)

    async def evict_tenant(self, tenant_id: str):
        tenant = self.hot_tenants[tenant_id]

        # 1. Flush pending writes
        await tenant.memory.flush()

        # 2. Close RocksDB
        await tenant.memory.close()

        # 3. Unload HNSW index
        tenant.hnsw = None

        # 4. Move to warm state
        self.warm_tenants[tenant_id] = TenantMetadata(
            tenant_id=tenant_id,
            last_access=tenant.last_access_time,
            config=tenant.config
        )
        del self.hot_tenants[tenant_id]

        logger.info(f"Evicted tenant {tenant_id} (hot → warm)")
```

## Data Temperature Tiers

### Tier 1: Local SSD (Hot Data)

**Storage:** Local NVMe/SSD on pod node

**Contents:**
- Active tenant RocksDB files
- Recently accessed embeddings
- Session state

**Characteristics:**
- Fast: <1ms read latency
- Limited: 100GB per node
- Ephemeral: Lost on pod restart (acceptable, reload from S3)

**Use Case:**
- Hot tenants (last 5 min)
- Warm tenants on standby (last hour)

### Tier 2: Persistent Volume (Warm Data)

**Storage:** K8s PersistentVolume (EBS, Persistent Disk)

**Contents:**
- Recently active tenant databases
- Short-term cache

**Characteristics:**
- Medium speed: 5-10ms read latency
- Moderate size: 500GB per volume
- Persistent: Survives pod restarts

**Use Case:**
- Warm tenants (last hour)
- Failover cache

### Tier 3: Object Storage (Cold Data)

**Storage:** S3/GCS/Azure Blob

**Contents:**
- All tenant databases (source of truth)
- Historical backups
- Archived tenants

**Characteristics:**
- Slow: 50-200ms first byte
- Unlimited: Scales to petabytes
- Durable: 99.999999999% durability

**Use Case:**
- Cold tenants (>1 hour idle)
- Backup and disaster recovery
- Long-term archival

## Kubernetes Scaling Strategy

### Per-Tier Deployments

Each tier has its own deployment and HPA configuration:

**Tier A Deployment (Premium):**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: percolate-tier-a
  labels:
    app: percolate
    tier: premium
spec:
  replicas: 2  # Managed by HPA
  selector:
    matchLabels:
      app: percolate
      tier: premium
  template:
    metadata:
      labels:
        app: percolate
        tier: premium
    spec:
      containers:
      - name: percolate
        image: percolate:latest
        env:
        - name: TENANT_TIER
          value: "A"
        - name: MAX_HOT_TENANTS
          value: "8"
        resources:
          requests:
            memory: "4Gi"
            cpu: "1600m"
          limits:
            memory: "5Gi"
            cpu: "2000m"
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: percolate-tier-a-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: percolate-tier-a
  minReplicas: 2  # HA for premium
  maxReplicas: 50
  metrics:
  - type: Pods
    pods:
      metric:
        name: hot_tenants_count
      target:
        type: AverageValue
        averageValue: "6"  # Target 6 premium tenants per pod
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 60  # More headroom for premium
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30  # Faster scale-up for premium
      policies:
      - type: Percent
        value: 100  # Double on spike
        periodSeconds: 30
    scaleDown:
      stabilizationWindowSeconds: 600  # Conservative scale-down
      policies:
      - type: Pods
        value: 1
        periodSeconds: 300
```

**Tier B Deployment (Standard):**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: percolate-tier-b
  labels:
    app: percolate
    tier: standard
spec:
  selector:
    matchLabels:
      app: percolate
      tier: standard
  template:
    metadata:
      labels:
        app: percolate
        tier: standard
    spec:
      containers:
      - name: percolate
        image: percolate:latest
        env:
        - name: TENANT_TIER
          value: "B"
        - name: MAX_HOT_TENANTS
          value: "15"
        resources:
          requests:
            memory: "3Gi"
            cpu: "750m"
          limits:
            memory: "4Gi"
            cpu: "1500m"
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: percolate-tier-b-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: percolate-tier-b
  minReplicas: 1
  maxReplicas: 100
  metrics:
  - type: Pods
    pods:
      metric:
        name: hot_tenants_count
      target:
        type: AverageValue
        averageValue: "12"
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 70
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Pods
        value: 2
        periodSeconds: 120
```

**Tier C Deployment (Free):**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: percolate-tier-c
  labels:
    app: percolate
    tier: free
spec:
  selector:
    matchLabels:
      app: percolate
      tier: free
  template:
    metadata:
      labels:
        app: percolate
        tier: free
    spec:
      containers:
      - name: percolate
        image: percolate:latest
        env:
        - name: TENANT_TIER
          value: "C"
        - name: MAX_HOT_TENANTS
          value: "25"
        resources:
          requests:
            memory: "2Gi"
            cpu: "500m"
          limits:
            memory: "3Gi"
            cpu: "1000m"
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: percolate-tier-c-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: percolate-tier-c
  minReplicas: 1
  maxReplicas: 200
  metrics:
  - type: Pods
    pods:
      metric:
        name: hot_tenants_count
      target:
        type: AverageValue
        averageValue: "20"
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 75  # Pack free tenants tighter
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 120  # Slower scale-up for free
      policies:
      - type: Percent
        value: 25
        periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 180  # Faster scale-down for free
      policies:
      - type: Pods
        value: 3
        periodSeconds: 90
```

**Scaling Behavior by Tier:**

| Tier | Min Pods | Max Pods | Target/Pod | Scale Up Speed | Scale Down Speed |
|------|----------|----------|------------|----------------|------------------|
| A    | 2        | 50       | 6 tenants  | Fast (30s)     | Conservative (10min) |
| B    | 1        | 100      | 12 tenants | Medium (60s)   | Moderate (5min) |
| C    | 1        | 200      | 20 tenants | Slow (120s)    | Aggressive (3min) |

### Custom Metrics

Export custom metrics for HPA:

```python
from prometheus_client import Gauge

hot_tenants_gauge = Gauge(
    'percolate_hot_tenants_count',
    'Number of hot (active) tenants in this pod'
)

warm_tenants_gauge = Gauge(
    'percolate_warm_tenants_count',
    'Number of warm (idle) tenants in this pod'
)

memory_allocated_gauge = Gauge(
    'percolate_tenant_memory_mb',
    'Total memory allocated to tenants',
    ['tenant_id']
)

class TenantManager:
    def update_metrics(self):
        hot_tenants_gauge.set(len(self.hot_tenants))
        warm_tenants_gauge.set(len(self.warm_tenants))

        for tenant_id, tenant in self.hot_tenants.items():
            memory_allocated_gauge.labels(tenant_id=tenant_id).set(
                tenant.memory_usage_mb()
            )
```

## Tenant Routing

### Tier-Aware Gateway

The gateway routes requests based on tenant tier, then to specific pods within that tier.

```python
from enum import Enum
import hashlib
from typing import Dict, List

class TenantTier(Enum):
    A = "premium"
    B = "standard"
    C = "free"

class TenantRegistry:
    """Maps tenant_id → tier (from database)"""

    async def get_tier(self, tenant_id: str) -> TenantTier:
        # Query tenant metadata from shared database
        tenant = await db.query(
            "SELECT tier FROM tenants WHERE id = ?",
            tenant_id
        )
        return TenantTier[tenant.tier]

class TierRouter:
    """Routes requests to appropriate tier deployment"""

    def __init__(self):
        self.registry = TenantRegistry()

        # K8s service endpoints per tier
        self.tier_services = {
            TenantTier.A: "percolate-tier-a.default.svc.cluster.local:8000",
            TenantTier.B: "percolate-tier-b.default.svc.cluster.local:8000",
            TenantTier.C: "percolate-tier-c.default.svc.cluster.local:8000",
        }

    async def route(self, tenant_id: str) -> str:
        """Route to tier-specific service (K8s handles pod selection)"""
        tier = await self.registry.get_tier(tenant_id)
        return self.tier_services[tier]

# Gateway API
from fastapi import FastAPI, Request
import httpx

app = FastAPI()
router = TierRouter()

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def gateway(path: str, request: Request):
    # Extract tenant_id from auth token
    tenant_id = extract_tenant_from_token(request.headers["Authorization"])

    # Route to appropriate tier
    tier_service = await router.route(tenant_id)

    # Proxy request to tier service
    async with httpx.AsyncClient() as client:
        response = await client.request(
            method=request.method,
            url=f"http://{tier_service}/{path}",
            headers=dict(request.headers),
            content=await request.body(),
        )
        return response.json()
```

### Pod Selection Within Tier

**Strategy: K8s Service Load Balancing + Consistent Hashing**

Use K8s Service for load balancing, with sticky sessions for tenant affinity:

```yaml
# Service for Tier A
apiVersion: v1
kind: Service
metadata:
  name: percolate-tier-a
spec:
  selector:
    app: percolate
    tier: premium
  ports:
  - port: 8000
    targetPort: 8000
  sessionAffinity: ClientIP  # Sticky sessions
  sessionAffinityConfig:
    clientIP:
      timeoutSeconds: 3600  # 1 hour
```

**Tenant Affinity with Custom Header:**

For better tenant affinity (same tenant → same pod), use custom hashing:

```python
class PodRouter:
    """Routes to specific pod within tier using consistent hashing"""

    def __init__(self, tier: TenantTier):
        self.tier = tier
        self.pods: List[str] = []  # Discovered from K8s API

    async def discover_pods(self):
        """Query K8s API for pod IPs in this tier"""
        from kubernetes import client, config
        config.load_incluster_config()
        v1 = client.CoreV1Api()

        pods = v1.list_namespaced_pod(
            namespace="default",
            label_selector=f"app=percolate,tier={self.tier.value}"
        )
        self.pods = [pod.status.pod_ip for pod in pods.items]

    def get_pod_for_tenant(self, tenant_id: str) -> str:
        """Consistent hash to specific pod"""
        if not self.pods:
            raise ValueError("No pods available")

        hash_value = int(hashlib.md5(tenant_id.encode()).hexdigest(), 16)
        pod_index = hash_value % len(self.pods)
        return self.pods[pod_index]

# Enhanced gateway with pod-level routing
class EnhancedGateway:
    def __init__(self):
        self.registry = TenantRegistry()
        self.tier_routers = {
            tier: PodRouter(tier) for tier in TenantTier
        }

        # Refresh pod lists every 30s
        asyncio.create_task(self.refresh_pods())

    async def refresh_pods(self):
        while True:
            for router in self.tier_routers.values():
                await router.discover_pods()
            await asyncio.sleep(30)

    async def route(self, tenant_id: str) -> str:
        tier = await self.registry.get_tier(tenant_id)
        pod_ip = self.tier_routers[tier].get_pod_for_tenant(tenant_id)
        return f"http://{pod_ip}:8000"
```

### Routing Benefits by Strategy

| Strategy | Tenant Affinity | Load Balance | Complexity | Use Case |
|----------|-----------------|--------------|------------|----------|
| K8s Service | Low | Good | Simple | Development, tier-level routing |
| K8s + SessionAffinity | Medium | Good | Simple | Production, IP-based stickiness |
| Custom Consistent Hash | High | Fair | Medium | Production, tenant-level affinity |
| Least-Loaded | Low | Excellent | High | Large scale, dynamic load |

**Recommendation:**
- **Phase 1**: K8s Service (simple)
- **Phase 2**: K8s Service + SessionAffinity (better affinity)
- **Phase 3**: Custom consistent hashing (optimal affinity)

## Local Development Mode

The same code runs locally with simplified assumptions:

```python
# percolate/src/percolate/settings.py

class Settings(BaseSettings):
    # Deployment mode
    deployment_mode: str = "local"  # local | pod | gateway

    # Resource limits (adjusted per mode)
    max_hot_tenants: int = 20 if deployment_mode == "pod" else 1
    max_memory_mb: int = 4096 if deployment_mode == "pod" else 1024

    # Data storage
    data_dir: Path = Path("./data")  # local: ./data, pod: /mnt/data
    use_s3_backup: bool = deployment_mode == "pod"
```

**Local Mode:**
- Single tenant (user's own workspace)
- No eviction (always hot)
- Local disk only
- No K8s dependencies

**Pod Mode:**
- Multi-tenant
- Eviction enabled
- Local SSD + S3 backup
- K8s-aware (health checks, metrics)

## Background Workers

### Worker Types

**1. Embedding Workers**
- Triggered by: Document upload
- Duration: 10s - 5min
- Resource: CPU + GPU (via percolate-reading)
- Lifecycle: Tenant-scoped

**2. Sync Workers**
- Triggered by: Schedule (every 5min)
- Duration: 10-60s
- Resource: Network I/O
- Lifecycle: Per active node

**3. Archival Workers**
- Triggered by: Cold tenant detection
- Duration: 30-300s
- Resource: Disk I/O + S3 bandwidth
- Lifecycle: Cluster-wide (leader-elected)

### Worker Scheduling

Use **Celery** for distributed task queue:

```python
from celery import Celery

celery = Celery('percolate', broker='redis://redis:6379/0')

@celery.task(bind=True)
def process_document(self, tenant_id: str, document_id: str):
    # Load tenant (cold start acceptable)
    tenant = tenant_manager.get_or_load(tenant_id)

    # Process document
    await tenant.process_document(document_id)

    # If tenant is now idle, it will be evicted by LRU policy

@celery.task
def sync_tenant_data(tenant_id: str):
    """Periodic sync to S3"""
    tenant = tenant_manager.get_or_load(tenant_id)
    await tenant.sync_to_s3()
```

**Worker Pod Spec:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: percolate-worker
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: worker
        image: percolate:latest
        command: ["celery", "-A", "percolate.tasks", "worker"]
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
```

## Data Warming Strategies

### Strategy 1: Context Blob Caching (Recommended)

**Approach:** Gateway stores encrypted context blob in S3, uses it for instant response while pod warms up

**Context Blob Contents:**
- Recent conversation history (last 10 messages)
- Key entities (frequently accessed)
- User preferences and settings
- Lightweight vector index (top 100 resources)
- Size: 1-5MB compressed

```python
class ContextBlob:
    """Tenant context cached in S3 for instant cold-start response"""

    tenant_id: str
    created_at: datetime
    recent_conversations: List[Message]  # Last 10 messages
    key_entities: List[Entity]  # Top 20 entities by access count
    preferences: Dict[str, Any]
    lightweight_index: List[Tuple[str, Vector]]  # Top 100 resources

class Gateway:
    async def handle_request_with_warming(
        self,
        tenant_id: str,
        message: str
    ):
        # 1. Fetch context blob from S3 (~100ms)
        context = await self.s3.get_context_blob(tenant_id)

        # 2. Start pod warming in background
        warming_task = asyncio.create_task(
            self.warm_tenant_pod(tenant_id)
        )

        # 3. Generate initial response using cached context
        if context:
            # Decrypt context (user's public key encrypted)
            decrypted = decrypt_with_tenant_key(context.blob)

            # Stream response using lightweight context
            async for chunk in self.generate_from_context(
                decrypted,
                message
            ):
                yield chunk

        # 4. Wait for pod to finish warming
        pod_url = await warming_task

        # 5. Future requests go to warm pod
        self.tenant_locations[tenant_id] = pod_url

    async def warm_tenant_pod(self, tenant_id: str) -> str:
        """Load tenant in pod while using cached context"""
        tier = await self.registry.get_tier(tenant_id)
        pod_url = await self.route_to_tier(tier, tenant_id)

        # Trigger load (non-blocking)
        await httpx.post(f"{pod_url}/internal/warm/{tenant_id}")

        return pod_url
```

**Context Blob Updates:**

Update context blob periodically or on eviction:

```python
class TenantManager:
    async def evict_tenant(self, tenant_id: str):
        tenant = self.hot_tenants[tenant_id]

        # 1. Generate context blob
        context = ContextBlob(
            tenant_id=tenant_id,
            created_at=datetime.now(),
            recent_conversations=tenant.get_recent_conversations(limit=10),
            key_entities=tenant.get_key_entities(limit=20),
            preferences=tenant.config.preferences,
            lightweight_index=tenant.get_top_resources(limit=100),
        )

        # 2. Encrypt with tenant's public key
        encrypted = encrypt_with_tenant_key(tenant_id, context)

        # 3. Upload to S3
        await s3.put_object(
            Bucket="percolate-context-cache",
            Key=f"tenants/{tenant_id}/context.bin",
            Body=encrypted,
        )

        # 4. Evict from memory
        await tenant.memory.close()
        del self.hot_tenants[tenant_id]
```

**User Experience:**
- First message after idle: ~500ms (context blob response)
- Background warming: 2-5s (transparent to user)
- Quality: Slightly degraded (cached context) for first response
- Subsequent messages: Full quality, instant

**Benefits:**
- No visible cold start delay
- Maintains conversation continuity
- Privacy-preserving (encrypted blobs)

**Trade-offs:**
- First response uses cached context (may miss recent updates)
- Additional S3 storage cost (~$0.023/GB/mo)
- Gateway complexity increases

### Strategy 2: Accept Cold Starts (Phase 1 - Simple)

**Approach:** Show user a loading message

```python
async def handle_chat_request(tenant_id: str, message: str):
    start = time.time()
    tenant = await tenant_manager.get_or_load(tenant_id)
    load_time = time.time() - start

    if load_time > 1.0:
        # Show warming message to user
        yield {
            "type": "status",
            "message": f"Warming up your workspace ({load_time:.1f}s)..."
        }

    async for chunk in tenant.chat(message):
        yield chunk
```

**User Experience:**
- First message after idle: 2-5s delay with status message
- Subsequent messages: Instant

**Implementation:** Simple, no prediction needed

### Strategy 3: Predictive Warming (Phase 3)

**Approach:** Pre-warm tenants based on patterns

```python
class TenantWarmer:
    async def predict_and_warm(self):
        """Run every 5 minutes to pre-warm likely-to-be-active tenants"""

        # Example: Warm tenants active at this time on previous days
        hour = datetime.now().hour
        tenants_to_warm = await self.db.query(
            "SELECT tenant_id FROM tenant_activity "
            "WHERE hour_of_day = ? AND day_of_week = ? "
            "GROUP BY tenant_id "
            "HAVING count(*) > 3",
            hour, datetime.now().weekday()
        )

        for tenant_id in tenants_to_warm:
            if tenant_id not in tenant_manager.hot_tenants:
                await tenant_manager.warm_tenant(tenant_id)
```

**Implementation:** Requires activity tracking

### Strategy 4: Keep-Warm Premium (Phase 4)

**Approach:** Pay to keep high-value tenants always warm

```python
class TenantConfig:
    keep_warm: bool = False  # Premium feature

class TenantManager:
    async def evict_if_needed(self):
        # Skip eviction for keep-warm tenants
        evictable = [
            t for t in self.hot_tenants.values()
            if not t.config.keep_warm
        ]
        # ... evict from evictable list
```

**Pricing:** Keep-warm add-on = +$10/month (guaranteed <100ms response)

### Warming Strategy Comparison

| Strategy | Cold Start Latency | First Response Quality | Complexity | Cost | Recommended For |
|----------|-------------------|------------------------|------------|------|-----------------|
| Context Blob | ~500ms | Good (cached) | Medium | +$0.01/tenant/mo | All paid tiers |
| Accept Cold Starts | 2-5s | Perfect | Low | $0 | Free tier, MVP |
| Predictive Warming | <1s | Perfect | High | +10% compute | High-traffic tiers |
| Keep-Warm | <100ms | Perfect | Low | +$10/tenant/mo | Premium add-on |

**Recommendation:**
- **Phase 1 (MVP)**: Accept cold starts with loading message
- **Phase 2 (Production)**: Context blob caching for all tiers
- **Phase 3 (Scale)**: Add predictive warming for Tier B+
- **Phase 4 (Premium)**: Offer keep-warm as paid add-on

## Monitoring & Observability

### Key Metrics

```python
# Tenant lifecycle
tenant_state_transitions = Counter(
    'percolate_tenant_state_transitions',
    'Tenant state transitions',
    ['from_state', 'to_state']
)

# Load performance
tenant_load_duration = Histogram(
    'percolate_tenant_load_seconds',
    'Time to load tenant from warm/cold state',
    ['from_state']
)

# Resource usage
tenant_memory_usage = Gauge(
    'percolate_tenant_memory_bytes',
    'Memory used by tenant',
    ['tenant_id', 'state']
)

# Eviction tracking
tenant_evictions = Counter(
    'percolate_tenant_evictions_total',
    'Number of tenant evictions',
    ['reason']
)
```

### Dashboard

**Pod View:**
- Hot tenants: 12 / 20 (60%)
- Warm tenants: 45
- Memory: 2.8GB / 4GB (70%)
- CPU: 1.2 cores / 2 cores (60%)

**Tenant View:**
- State: Hot (active 2min ago)
- Memory: 180MB
- Load time: 0ms (already loaded)
- Last eviction: 3 hours ago

**Cluster View:**
- Total pods: 8
- Total hot tenants: 96
- Avg tenants/pod: 12
- Scale recommendation: OK (target 15/pod)

## Implementation Phases

### Phase 1: Basic Multi-Tenancy (MVP)
- Single pod serves multiple tenants
- Lazy loading on request
- Simple LRU eviction
- Local disk storage
- Accept cold starts (show loading message)

**Complexity:** Low
**Timeline:** 2 weeks

### Phase 2: K8s Scaling
- HPA based on hot tenant count
- Consistent hash routing
- S3 backup for cold tenants
- Prometheus metrics
- Health checks

**Complexity:** Medium
**Timeline:** 3 weeks

### Phase 3: Optimization
- Predictive warming
- Least-loaded routing
- Keep-warm premium tier
- Advanced eviction policies
- Data temperature analytics

**Complexity:** High
**Timeline:** 4 weeks

## Configuration Example

```python
# percolate/src/percolate/settings.py

from enum import Enum
from pydantic import BaseSettings

class TenantTier(str, Enum):
    A = "premium"
    B = "standard"
    C = "free"

class TierConfig(BaseSettings):
    """Configuration for a specific tenant tier"""
    tier: TenantTier
    max_hot_tenants: int
    hot_tenant_memory_mb: int
    hot_tenant_cpu_millicores: int
    hot_timeout_seconds: int
    warm_timeout_seconds: int
    keep_warm: bool = False

# Tier-specific configurations
TIER_CONFIGS = {
    TenantTier.A: TierConfig(
        tier=TenantTier.A,
        max_hot_tenants=8,
        hot_tenant_memory_mb=500,
        hot_tenant_cpu_millicores=200,
        hot_timeout_seconds=0,  # Never timeout
        warm_timeout_seconds=0,  # Never warm
        keep_warm=True,
    ),
    TenantTier.B: TierConfig(
        tier=TenantTier.B,
        max_hot_tenants=15,
        hot_tenant_memory_mb=200,
        hot_tenant_cpu_millicores=50,
        hot_timeout_seconds=300,  # 5 min
        warm_timeout_seconds=3600,  # 1 hour
    ),
    TenantTier.C: TierConfig(
        tier=TenantTier.C,
        max_hot_tenants=25,
        hot_tenant_memory_mb=100,
        hot_tenant_cpu_millicores=20,
        hot_timeout_seconds=60,  # 1 min
        warm_timeout_seconds=600,  # 10 min
    ),
}

class MultiTenantSettings(BaseSettings):
    """Multi-tenant resource allocation settings"""

    # Deployment mode
    deployment_mode: str = "local"  # local | pod | gateway
    tenant_tier: TenantTier = TenantTier.C

    # Get tier config
    @property
    def tier_config(self) -> TierConfig:
        return TIER_CONFIGS[self.tenant_tier]

    # Pod capacity (from tier config)
    @property
    def max_hot_tenants(self) -> int:
        return self.tier_config.max_hot_tenants

    # Memory limits
    pod_memory_limit_mb: int = 4096
    warm_tenant_avg_memory_mb: int = 5

    # Eviction policy
    eviction_memory_threshold: float = 0.80
    eviction_target: float = 0.70

    # Storage tiers
    local_storage_path: Path = Path("/mnt/data/tenants")
    s3_bucket: Optional[str] = None
    s3_prefix: str = "tenants/"

    # Workers
    enable_background_workers: bool = True
    celery_broker_url: str = "redis://redis:6379/0"

    # Monitoring
    enable_metrics: bool = True
    metrics_port: int = 9090

    class Config:
        env_prefix = "PERCOLATE_"
```

**Environment Variables per Tier:**

```bash
# Tier A pod
PERCOLATE_DEPLOYMENT_MODE=pod
PERCOLATE_TENANT_TIER=A
PERCOLATE_POD_MEMORY_LIMIT_MB=5120

# Tier B pod
PERCOLATE_DEPLOYMENT_MODE=pod
PERCOLATE_TENANT_TIER=B
PERCOLATE_POD_MEMORY_LIMIT_MB=4096

# Tier C pod
PERCOLATE_DEPLOYMENT_MODE=pod
PERCOLATE_TENANT_TIER=C
PERCOLATE_POD_MEMORY_LIMIT_MB=3072
```

## Cost Analysis: Tiered Architecture

### Infrastructure Costs (AWS us-east-1)

**Compute Costs per Pod:**

| Tier | Instance Type | vCPU | Memory | Cost/hour | Cost/month |
|------|---------------|------|---------|-----------|------------|
| A    | c6i.xlarge    | 4    | 8GB     | $0.17     | ~$124      |
| B    | c6i.large     | 2    | 4GB     | $0.085    | ~$62       |
| C    | t3.medium     | 2    | 4GB     | $0.042    | ~$31       |

**Scaling Example (1000 tenants):**

Assume distribution:
- Tier A: 50 premium tenants ($49/mo each)
- Tier B: 300 standard tenants ($19/mo each)
- Tier C: 650 free tenants ($0/mo each)

**Pod Requirements:**
- Tier A: 50 / 6 = 9 pods × $124 = $1,116/mo
- Tier B: 300 / 12 = 25 pods × $62 = $1,550/mo
- Tier C: 650 / 20 = 33 pods × $31 = $1,023/mo

**Total Infrastructure:** $3,689/month

**Revenue:**
- Tier A: 50 × $49 = $2,450
- Tier B: 300 × $19 = $5,700
- Tier C: 650 × $0 = $0

**Total Revenue:** $8,150/month

**Gross Margin:** ($8,150 - $3,689) / $8,150 = **55%**

### Cost per Tenant by Tier

| Tier | Tenants/Pod | Pod Cost/mo | Cost/Tenant/mo | Price/mo | Margin |
|------|-------------|-------------|----------------|----------|--------|
| A    | 6           | $124        | $20.67         | $49      | 58%    |
| B    | 12          | $62         | $5.17          | $19      | 73%    |
| C    | 20          | $31         | $1.55          | $0       | -100%  |

**Key Insights:**
- Premium tier is profitable but expensive per tenant
- Standard tier has best margins (73%)
- Free tier subsidized by paid tiers (acceptable for growth)

### Optimization Strategies

**1. Over-provisioning Free Tier**

Pack free tenants tighter with aggressive eviction:
- Increase to 30 tenants/pod (from 20)
- Free tier cost: 650 / 30 = 22 pods × $31 = $682/mo (vs $1,023)
- Savings: $341/month (33% reduction)

**2. Spot Instances for Free Tier**

Use spot instances (70% discount) for free tier:
- Spot cost: $31 × 0.30 = $9.30/pod
- Free tier cost: 33 pods × $9.30 = $307/mo (vs $1,023)
- Savings: $716/month (70% reduction)
- Trade-off: Occasional restarts (acceptable for free tier)

**3. Reserved Instances for Premium**

1-year reserved instances (40% discount) for predictable premium load:
- Reserved cost: $124 × 0.60 = $74.40/pod
- Tier A cost: 9 pods × $74.40 = $670/mo (vs $1,116)
- Savings: $446/month (40% reduction)

**Optimized Total Cost:**
- Tier A: $670 (reserved)
- Tier B: $1,550 (on-demand)
- Tier C: $307 (spot)
- **Total: $2,527/month** (vs $3,689)

**Optimized Gross Margin:** ($8,150 - $2,527) / $8,150 = **69%**

### Break-Even Analysis

**Fixed Costs:**
- Gateway: 2 × t3.small = $30/mo
- Database: RDS db.t3.medium = $60/mo
- S3 storage: 100GB × $0.023 = $2.30/mo
- Data transfer: ~$100/mo
- **Total Fixed:** ~$200/mo

**Variable Costs:**
- Compute: $2,527/mo (1000 tenants)
- Per-tenant: $2.53

**Break-Even:**
- Need to cover $200 fixed + variable costs
- With 50 premium + 300 standard: Revenue = $8,150
- Variable cost: $2,527
- Fixed cost: $200
- **Profit:** $8,150 - $2,527 - $200 = **$5,423/month**

**Break-even tenant count:**
- Assume 10% premium, 30% standard, 60% free
- Revenue per 100 tenants: 10 × $49 + 30 × $19 = $1,060
- Cost per 100 tenants: ~$250
- Profit per 100 tenants: $810
- **Break-even:** ~25 tenants (3 premium, 8 standard, 14 free)

### Scaling Economics

As tenant count grows, cost per tenant decreases due to pod sharing:

| Total Tenants | Premium | Standard | Free  | Pods (A/B/C) | Total Cost | Revenue  | Margin |
|---------------|---------|----------|-------|--------------|------------|----------|--------|
| 100           | 10      | 30       | 60    | 2/3/3        | $560       | $1,060   | 47%    |
| 500           | 50      | 150      | 300   | 9/13/15      | $1,663     | $5,300   | 69%    |
| 1,000         | 100     | 300      | 600   | 17/25/30     | $2,774     | $10,600  | 74%    |
| 5,000         | 500     | 1,500    | 3,000 | 84/125/150   | $13,869    | $53,000  | 74%    |
| 10,000        | 1,000   | 3,000    | 6,000 | 167/250/300  | $27,738    | $106,000 | 74%    |

**Key Insight:** Margins stabilize at ~74% after 1,000 tenants due to efficient pod packing.

## References

- **RocksDB Tuning**: https://github.com/facebook/rocksdb/wiki/Setup-Options-and-Basic-Tuning
- **K8s HPA**: https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/
- **Consistent Hashing**: https://en.wikipedia.org/wiki/Consistent_hashing
- **Celery**: https://docs.celeryq.dev/
- **Prometheus**: https://prometheus.io/docs/practices/instrumentation/
- **AWS EC2 Pricing**: https://aws.amazon.com/ec2/pricing/on-demand/
- **K8s Resource Management**: https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/
