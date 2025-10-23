# Spike: Multi-Tenant Platform Layer

## Goal

Design and prototype the cloud platform infrastructure for Percolate, including:
- **Kubernetes deployment** with Argo CD for GitOps
- **Tiered tenant management** (A/B/C tiers with independent scaling)
- **Gateway** with tier-aware routing and context blob caching
- **Management database** for tenants, billing, payments, archival
- **Operational services** for monitoring, archival, and maintenance

## Questions to Answer

### Architecture
- [ ] How do we structure K8s resources for multi-tier deployment?
- [ ] Should gateway be part of platform or separate service?
- [ ] Where does tenant database live (shared vs per-tier)?
- [ ] How do we handle cross-tier operations (upgrades, migrations)?

### Management Database
- [ ] What's the minimal schema for tenant management?
- [ ] Do we use PostgreSQL or something lighter?
- [ ] How do we track tenant state (hot/warm/cold)?
- [ ] Where do we store billing and payment info?

### Routing & Gateway
- [ ] How does gateway discover tier pods?
- [ ] What's the routing strategy (consistent hash vs K8s service)?
- [ ] How do we implement context blob caching?
- [ ] How do we handle authentication at gateway level?

### Operational Concerns
- [ ] How do we archive cold tenant data to S3?
- [ ] What metrics do we need for HPA decisions?
- [ ] How do we handle tenant migrations (tier changes)?
- [ ] What's the DR (disaster recovery) strategy?

## Approach

### Phase 1: K8s Manifests & Argo Setup (Days 1-2)

Create Argo Application manifests for:

```
platform/
├── argo-app.yaml                   # Root Argo Application
├── apps/
│   ├── tier-a-deployment.yaml     # Premium tier
│   ├── tier-b-deployment.yaml     # Standard tier
│   ├── tier-c-deployment.yaml     # Free tier
│   ├── gateway-deployment.yaml    # API Gateway
│   └── management-deployment.yaml # Platform services
├── base/
│   ├── namespace.yaml             # percolate namespace
│   ├── config.yaml                # ConfigMap
│   └── secrets.yaml               # Sealed Secrets
└── monitoring/
    ├── prometheus.yaml
    └── grafana-dashboards.yaml
```

**Test:**
- Deploy to local kind cluster
- Verify tier isolation
- Test HPA scaling

### Phase 2: Management Database Schema (Day 2)

Design PostgreSQL schema for platform:

```sql
-- Tenants
CREATE TABLE tenants (
    id UUID PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    tier VARCHAR(10) NOT NULL,  -- A, B, C
    status VARCHAR(20) NOT NULL,  -- active, suspended, deleted
    security_mode VARCHAR(20),  -- node_based, mobile_only
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Devices
CREATE TABLE devices (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    device_name VARCHAR(255) NOT NULL,
    platform VARCHAR(50),  -- ios, android, macos, web
    public_key_signing TEXT NOT NULL,
    public_key_encryption TEXT NOT NULL,
    last_seen_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Subscriptions & Billing
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    tier VARCHAR(10) NOT NULL,
    status VARCHAR(20) NOT NULL,  -- active, canceled, past_due
    stripe_subscription_id VARCHAR(255),
    current_period_start TIMESTAMP,
    current_period_end TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Tenant State (hot/warm/cold tracking)
CREATE TABLE tenant_states (
    tenant_id UUID PRIMARY KEY REFERENCES tenants(id),
    state VARCHAR(10) NOT NULL,  -- hot, warm, cold
    pod_id VARCHAR(255),  -- Current pod hosting tenant
    last_access_at TIMESTAMP,
    last_eviction_at TIMESTAMP,
    memory_mb INTEGER,
    data_size_mb INTEGER,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Archival Tracking
CREATE TABLE archival_jobs (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    job_type VARCHAR(50) NOT NULL,  -- archive, restore
    status VARCHAR(20) NOT NULL,  -- pending, running, completed, failed
    s3_location TEXT,
    data_size_mb INTEGER,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

**Test:**
- CRUD operations
- Query performance with 1M tenants
- Connection pooling

### Phase 3: Gateway Implementation (Days 3-4)

Build tier-aware gateway with:

```python
# platform/src/gateway/main.py

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import httpx

app = FastAPI()

class TierRouter:
    """Routes requests to appropriate tier deployment"""

    async def route_request(self, tenant_id: str) -> str:
        # Query management DB for tenant tier
        tier = await db.get_tenant_tier(tenant_id)

        # Route to tier-specific service
        tier_services = {
            "A": "http://percolate-tier-a:8000",
            "B": "http://percolate-tier-b:8000",
            "C": "http://percolate-tier-c:8000"
        }
        return tier_services[tier]

class ContextBlobCache:
    """Manages encrypted context blobs for instant cold-start"""

    async def get_context_blob(self, tenant_id: str) -> bytes:
        # Fetch from S3
        return await s3.get_object(
            Bucket="percolate-context-cache",
            Key=f"tenants/{tenant_id}/context.bin"
        )

    async def use_for_instant_response(
        self,
        tenant_id: str,
        message: str
    ):
        # Get cached context
        context_blob = await self.get_context_blob(tenant_id)

        # Start pod warming in background
        asyncio.create_task(warm_tenant_pod(tenant_id))

        # Generate response from cache
        async for chunk in generate_from_context(context_blob, message):
            yield chunk

@app.api_route("/{path:path}", methods=["GET", "POST"])
async def gateway(path: str, request: Request):
    tenant_id = extract_tenant_from_auth(request)

    # Route to tier
    target_url = await tier_router.route_request(tenant_id)

    # Proxy request
    async with httpx.AsyncClient() as client:
        response = await client.request(
            method=request.method,
            url=f"{target_url}/{path}",
            headers=dict(request.headers),
            content=await request.body()
        )
        return StreamingResponse(
            response.aiter_bytes(),
            status_code=response.status_code
        )
```

**Test:**
- Load testing with 1000 concurrent requests
- Tier routing correctness
- Context blob caching performance

### Phase 4: Management Services (Day 4-5)

Build operational services:

```python
# platform/src/management/archival.py

class ArchivalService:
    """Archives cold tenant data to S3"""

    async def find_cold_tenants(self) -> List[str]:
        """Find tenants idle > 60 days"""
        return await db.query("""
            SELECT tenant_id FROM tenant_states
            WHERE state = 'cold'
            AND last_access_at < NOW() - INTERVAL '60 days'
        """)

    async def archive_tenant(self, tenant_id: str):
        """Archive tenant data to S3"""
        # 1. Dump RocksDB to tar.gz
        # 2. Encrypt with tenant key
        # 3. Upload to S3
        # 4. Delete local data
        # 5. Update archival_jobs table

# platform/src/management/tenant_migrations.py

class TenantMigrationService:
    """Handles tenant tier upgrades/downgrades"""

    async def upgrade_tenant(
        self,
        tenant_id: str,
        from_tier: str,
        to_tier: str
    ):
        """Migrate tenant to new tier"""
        # 1. Update tenant record
        # 2. Evict from old tier pod
        # 3. Trigger load on new tier pod
        # 4. Update routing cache
        # 5. Send upgrade notification
```

**Test:**
- Archival job end-to-end
- Tenant migration flow
- Error handling and rollback

## Success Criteria

### Must Have
- ✅ Working Argo deployment to K8s cluster
- ✅ Tier-aware routing functional
- ✅ Management database schema complete
- ✅ Context blob caching working
- ✅ Archival service operational
- ✅ Tenant migration process defined

### Nice to Have
- ✅ Automated tenant provisioning
- ✅ Billing integration (Stripe webhook)
- ✅ Multi-region support
- ✅ DR failover tested
- ✅ Grafana dashboards

## Implementation Log

### Day 1: Argo Application Structure

**Goal:** Create GitOps structure for multi-tier deployment

**Argo App Hierarchy:**

```yaml
# argo-app.yaml - Root application
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: percolate-platform
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/percolation-labs/platform
    targetRevision: main
    path: apps
  destination:
    server: https://kubernetes.default.svc
    namespace: percolate
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

**Learnings:**
- [Document as you build]

### Day 2: Management Database

**Goal:** Schema design and testing

**Schema Decisions:**
- [Document choices made]

**Benchmarks:**
- [Add performance results]

**Learnings:**
- [Document findings]

### Day 3: Gateway Implementation

**Goal:** Tier routing and context caching

**Routing Strategy:**
- [Document chosen approach]

**Performance:**
- [Add latency measurements]

**Learnings:**
- [Document findings]

### Day 4-5: Management Services

**Goal:** Archival and migration services

**Implementation:**
- [Document approach]

**Learnings:**
- [Document findings]

## Architecture Diagrams

### Overall Platform Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Cloudflare                        │
│               (DNS, DDoS protection)                 │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│                   Gateway Pod                        │
│  ┌───────────────────────────────────────────────┐  │
│  │ Tier Router                                   │  │
│  │  - Query management DB for tenant tier       │  │
│  │  - Route to appropriate tier service         │  │
│  └───────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────┐  │
│  │ Context Blob Cache                            │  │
│  │  - Fetch from S3                              │  │
│  │  - Generate instant response while warming    │  │
│  └───────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
        ▼            ▼            ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Tier A Pods  │ │ Tier B Pods  │ │ Tier C Pods  │
│  (Premium)   │ │  (Standard)  │ │    (Free)    │
│   2-50       │ │   1-100      │ │   1-200      │
│ HPA: 6/pod   │ │ HPA: 12/pod  │ │ HPA: 20/pod  │
└──────────────┘ └──────────────┘ └──────────────┘
        │            │            │
        └────────────┼────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│            Management Services                       │
│  ┌───────────────────────────────────────────────┐  │
│  │ PostgreSQL (Tenant Management)                │  │
│  │  - Tenants, devices, subscriptions           │  │
│  │  - Tenant state tracking                      │  │
│  │  - Billing and payments                       │  │
│  └───────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────┐  │
│  │ Archival Service                              │  │
│  │  - Find cold tenants                          │  │
│  │  - Archive to S3                              │  │
│  │  - Restore on demand                          │  │
│  └───────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────┐  │
│  │ Migration Service                             │  │
│  │  - Tenant tier upgrades/downgrades           │  │
│  │  - Cross-tier data movement                   │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### Tenant Request Flow

```
1. Request arrives at Gateway
2. Extract tenant_id from JWT
3. Query management DB: SELECT tier FROM tenants WHERE id = ?
4. Route to tier service: tier-{a|b|c}.percolate.svc:8000
5. If tenant cold:
   a. Fetch context blob from S3
   b. Start pod warming (background)
   c. Generate response from cache
   d. Future requests use warm pod
```

## Management Database Schema (Complete)

```sql
-- Core tenant management
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    tier VARCHAR(10) NOT NULL CHECK (tier IN ('A', 'B', 'C')),
    status VARCHAR(20) NOT NULL CHECK (status IN ('active', 'suspended', 'deleted')),
    security_mode VARCHAR(20) NOT NULL DEFAULT 'node_based',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_security_mode CHECK (
        security_mode IN ('node_based', 'mobile_only')
    )
);

CREATE INDEX idx_tenants_tier ON tenants(tier);
CREATE INDEX idx_tenants_status ON tenants(status);
CREATE INDEX idx_tenants_email ON tenants(email);

-- Device registry
CREATE TABLE devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    device_name VARCHAR(255) NOT NULL,
    platform VARCHAR(50) CHECK (platform IN ('ios', 'android', 'macos', 'linux', 'web')),
    public_key_signing TEXT NOT NULL,
    public_key_encryption TEXT NOT NULL,
    last_seen_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_devices_tenant ON devices(tenant_id);
CREATE INDEX idx_devices_last_seen ON devices(last_seen_at);

-- Subscriptions
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    tier VARCHAR(10) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('active', 'canceled', 'past_due', 'trialing')),
    stripe_customer_id VARCHAR(255),
    stripe_subscription_id VARCHAR(255),
    current_period_start TIMESTAMP,
    current_period_end TIMESTAMP,
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_subscriptions_tenant ON subscriptions(tenant_id);
CREATE INDEX idx_subscriptions_status ON subscriptions(status);
CREATE INDEX idx_subscriptions_stripe ON subscriptions(stripe_subscription_id);

-- Tenant runtime state (hot/warm/cold)
CREATE TABLE tenant_states (
    tenant_id UUID PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    state VARCHAR(10) NOT NULL CHECK (state IN ('hot', 'warm', 'cold')),
    pod_id VARCHAR(255),  -- K8s pod currently hosting
    tier_deployment VARCHAR(10),  -- tier-a, tier-b, tier-c
    last_access_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_eviction_at TIMESTAMP,
    memory_mb INTEGER,
    data_size_mb INTEGER,
    rocksdb_location TEXT,  -- Path or S3 URL
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tenant_states_state ON tenant_states(state);
CREATE INDEX idx_tenant_states_last_access ON tenant_states(last_access_at);
CREATE INDEX idx_tenant_states_pod ON tenant_states(pod_id);

-- Archival jobs
CREATE TABLE archival_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    job_type VARCHAR(50) NOT NULL CHECK (job_type IN ('archive', 'restore', 'backup')),
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    s3_bucket VARCHAR(255),
    s3_key TEXT,
    data_size_mb INTEGER,
    compression VARCHAR(20) DEFAULT 'zstd',
    encryption_mode VARCHAR(20) DEFAULT 'tenant_key',
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_archival_jobs_tenant ON archival_jobs(tenant_id);
CREATE INDEX idx_archival_jobs_status ON archival_jobs(status);
CREATE INDEX idx_archival_jobs_created ON archival_jobs(created_at);

-- Billing events
CREATE TABLE billing_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    event_type VARCHAR(50) NOT NULL,  -- invoice.paid, subscription.created, etc.
    stripe_event_id VARCHAR(255) UNIQUE,
    amount_cents INTEGER,
    currency VARCHAR(3) DEFAULT 'USD',
    metadata JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_billing_events_tenant ON billing_events(tenant_id);
CREATE INDEX idx_billing_events_type ON billing_events(event_type);

-- Metrics snapshots (for HPA and monitoring)
CREATE TABLE tenant_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    metric_name VARCHAR(100) NOT NULL,  -- requests_per_minute, memory_mb, etc.
    metric_value NUMERIC NOT NULL,
    recorded_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tenant_metrics_tenant_time ON tenant_metrics(tenant_id, recorded_at DESC);
CREATE INDEX idx_tenant_metrics_name ON tenant_metrics(metric_name);

-- Audit log
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    user_id UUID,  -- For admin actions
    action VARCHAR(100) NOT NULL,  -- tenant.created, device.verified, etc.
    resource_type VARCHAR(50),
    resource_id UUID,
    metadata JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_log_tenant ON audit_log(tenant_id);
CREATE INDEX idx_audit_log_action ON audit_log(action);
CREATE INDEX idx_audit_log_created ON audit_log(created_at DESC);
```

## Kubernetes Manifests

### Tier A Deployment (Premium)

```yaml
# apps/tier-a-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: percolate-tier-a
  namespace: percolate
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
        ports:
        - containerPort: 8000
        env:
        - name: PERCOLATE_TENANT_TIER
          value: "A"
        - name: PERCOLATE_MAX_HOT_TENANTS
          value: "8"
        - name: PERCOLATE_MANAGEMENT_DB_URL
          valueFrom:
            secretKeyRef:
              name: platform-secrets
              key: management-db-url
        resources:
          requests:
            memory: "4Gi"
            cpu: "1600m"
          limits:
            memory: "5Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: percolate-tier-a
  namespace: percolate
spec:
  selector:
    app: percolate
    tier: premium
  ports:
  - port: 8000
    targetPort: 8000
  sessionAffinity: ClientIP
  sessionAffinityConfig:
    clientIP:
      timeoutSeconds: 3600
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: percolate-tier-a-hpa
  namespace: percolate
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: percolate-tier-a
  minReplicas: 2
  maxReplicas: 50
  metrics:
  - type: Pods
    pods:
      metric:
        name: hot_tenants_count
      target:
        type: AverageValue
        averageValue: "6"
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 60
```

### Gateway Deployment

```yaml
# apps/gateway-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: percolate-gateway
  namespace: percolate
spec:
  replicas: 3
  selector:
    matchLabels:
      app: percolate-gateway
  template:
    metadata:
      labels:
        app: percolate-gateway
    spec:
      containers:
      - name: gateway
        image: percolate-gateway:latest
        ports:
        - containerPort: 8080
        env:
        - name: MANAGEMENT_DB_URL
          valueFrom:
            secretKeyRef:
              name: platform-secrets
              key: management-db-url
        - name: S3_CONTEXT_CACHE_BUCKET
          value: "percolate-context-cache"
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
---
apiVersion: v1
kind: Service
metadata:
  name: percolate-gateway
  namespace: percolate
spec:
  type: LoadBalancer
  selector:
    app: percolate-gateway
  ports:
  - port: 443
    targetPort: 8080
```

## Key Learnings

### What Worked Well

- [Document successes]

### What Didn't Work

- [Document failures and why]

### Operational Surprises

- [Document unexpected findings]

## Recommendation for Production

### Architecture Decisions

- [What design should we use?]

### Critical Components

- [What must be implemented first?]

### Nice-to-Have Features

- [What can wait?]

## Open Questions

- [ ] How do we handle database migrations for management DB?
- [ ] What's the backup strategy for management database?
- [ ] How do we implement rate limiting at gateway level?
- [ ] Should we use Istio service mesh or keep simple?
- [ ] How do we handle multi-region deployment?

## Next Steps

1. **If spike successful:** Create production K8s manifests in main repo
2. **Management services:** Implement tenant management API
3. **Gateway:** Build production gateway with all features
4. **Monitoring:** Set up Prometheus, Grafana, alerts
5. **Documentation:** Create runbooks for ops team
6. **Archive spike:** Move to `.spikes/archived/platform-YYYYMMDD`

## References

- Multi-tenant allocation: `docs/07-multi-tenant-allocation.md`
- K8s HPA: https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/
- Argo CD: https://argo-cd.readthedocs.io/
- Sealed Secrets: https://github.com/bitnami-labs/sealed-secrets
