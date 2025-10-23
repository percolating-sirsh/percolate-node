# Cloud Deployment Architecture

## Overview

Percolate's cloud deployment uses a **shared reading service** model for optimal resource utilization and cost efficiency.

## Architecture

### Deployment Topology

```
┌────────────────────────────────────────────────────────────┐
│                    Gateway / Load Balancer                  │
│              (tenant.percolationlabs.ai)                    │
└────────────┬────────────────────────────┬──────────────────┘
             │                            │
             │ Route by tenant            │ Route to reading
             ▼                            ▼
┌────────────────────────┐   ┌────────────────────────────┐
│  Tenant-Specific       │   │   Shared Reading Service   │
│  Percolate Nodes       │   │   (percolate-reading)      │
│  (REM + API)           │   │                            │
├────────────────────────┤   ├────────────────────────────┤
│ Pod: tenant-alice      │   │ Pod: reading-1 (GPU)       │
│ - RocksDB (encrypted)  │   │ - Whisper models           │
│ - Agent runtime        │   │ - Heavy embeddings         │
│ - API server           │──>│ - OCR services             │
│                        │   │ - Document parsers         │
├────────────────────────┤   ├────────────────────────────┤
│ Pod: tenant-bob        │   │ Pod: reading-2 (GPU)       │
│ - RocksDB (encrypted)  │   │ - Stateless                │
│ - Agent runtime        │   │ - Load balanced            │
│ - API server           │──>│ - Auto-scaling             │
├────────────────────────┤   └────────────────────────────┘
│ Pod: tenant-carol      │
│ - RocksDB (encrypted)  │
│ - Agent runtime        │──┐
│ - API server           │  │
└────────────────────────┘  │
         ...                │
         (N tenants)         │
                            ▼
                ┌────────────────────────┐
                │ Pod: reading-3 (GPU)   │
                │ - Horizontal scale     │
                └────────────────────────┘
```

## Node Types

### Percolate Node (Tenant-Specific)

**Characteristics:**
- **One pod per tenant** (complete isolation)
- Lightweight resource requirements
- Persistent storage (RocksDB on PV)
- Scales with tenant count

**Resources:**
- CPU: 2 cores
- RAM: 4GB
- Disk: 20GB (persistent volume)
- No GPU required

**Deployment:**
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: percolate-tenant-{tenant_id}
spec:
  replicas: 1  # Single pod per tenant
  template:
    spec:
      containers:
      - name: percolate
        image: percolate:latest
        env:
        - name: TENANT_ID
          value: "{tenant_id}"
        - name: PERCOLATE_READING_URL
          value: "http://percolate-reading-service:8001"
        volumeMounts:
        - name: data
          mountPath: /var/lib/percolate
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 20Gi
```

### Percolate-Reading Node (Shared Service)

**Characteristics:**
- **Shared across all tenants** (stateless)
- Heavy resource requirements (GPU)
- Horizontal scaling based on load
- No persistent storage

**Resources (per pod):**
- CPU: 8 cores
- RAM: 16GB
- GPU: 1x NVIDIA T4 or better
- Disk: 20GB (ephemeral, for model cache)

**Deployment:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: percolate-reading
spec:
  replicas: 3  # Scale based on demand
  template:
    spec:
      nodeSelector:
        accelerator: nvidia-tesla-t4
      containers:
      - name: percolate-reading
        image: percolate-reading:latest
        resources:
          limits:
            nvidia.com/gpu: 1
        env:
        - name: PERCOLATE_READING_DEVICE
          value: "cuda"
```

## Cost Optimization

### Per-Tenant Costs

**Percolate Node (REM):**
- CPU: 2 cores × $0.05/hr = $0.10/hr
- RAM: 4GB × $0.01/GB/hr = $0.04/hr
- Disk: 20GB × $0.0001/GB/hr = $0.002/hr
- **Total: ~$3.50/tenant/month**

**Shared Reading Service:**
- GPU instance (T4): $0.35/hr
- Serves 100+ tenants simultaneously
- **Cost per tenant: ~$0.04/tenant/month**

**Total: ~$3.54/tenant/month** (excluding bandwidth)

### Comparison: Dedicated vs Shared

| Model | GPU per Tenant | Cost per Tenant |
|-------|----------------|-----------------|
| **Dedicated** | 1 GPU each | $250/month |
| **Shared (Percolate)** | 1/100th GPU | $3.54/month |
| **Savings** | - | **98.6%** |

## Scaling Strategy

### Horizontal Scaling

**Percolate Nodes:**
- Scale: 1 pod per tenant
- Trigger: New tenant signup
- Method: Create new StatefulSet

**Reading Nodes:**
- Scale: Based on request queue depth
- Trigger: Queue length > 100 requests
- Method: Horizontal Pod Autoscaler (HPA)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: percolate-reading-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: percolate-reading
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Pods
    pods:
      metric:
        name: request_queue_depth
      target:
        type: AverageValue
        averageValue: "100"
```

### Vertical Scaling

**Reading Node GPU Tiers:**

| Tier | GPU | Max Tenants | Use Case |
|------|-----|-------------|----------|
| **Small** | T4 | 50 | Development |
| **Medium** | L4 | 100 | Production |
| **Large** | A10G | 200 | High volume |

## Load Balancing

### Reading Service Load Balancer

**Strategy:** Least-connections with sticky sessions (tenant-based)

```yaml
apiVersion: v1
kind: Service
metadata:
  name: percolate-reading-service
spec:
  type: LoadBalancer
  sessionAffinity: ClientIP  # Sticky sessions
  selector:
    app: percolate-reading
  ports:
  - port: 8001
    targetPort: 8001
```

**Benefits:**
- Model caching per pod improves performance
- Tenant requests hit same pod when possible
- Reduces model loading overhead

## Multi-Region Deployment

### Regional Architecture

```
┌─────────────────────────────────────────────────┐
│           Global Gateway (Cloudflare)           │
│         (percolationlabs.ai)                    │
└────────┬────────────────────────┬───────────────┘
         │                        │
         │ Route by region        │
         ▼                        ▼
┌──────────────────┐    ┌──────────────────┐
│   US-East-1      │    │   EU-West-1      │
├──────────────────┤    ├──────────────────┤
│ Percolate Nodes  │    │ Percolate Nodes  │
│ - tenant-alice   │    │ - tenant-david   │
│ - tenant-bob     │    │ - tenant-eve     │
│                  │    │                  │
│ Reading Service  │    │ Reading Service  │
│ - 3 GPU pods     │    │ - 3 GPU pods     │
└──────────────────┘    └──────────────────┘
```

**Data Residency:**
- Tenant data stays in specified region
- Reading service per region
- Cross-region sync for redundancy only

## Security

### Tenant Isolation

**Percolate Nodes:**
- Separate pods per tenant (no shared resources)
- Encrypted RocksDB (per-tenant keys)
- Network policies (no inter-tenant communication)

**Reading Service:**
- Stateless (no data retention)
- Tenant ID validated on all requests
- Processing isolated per request
- Results returned immediately (not stored)

### Network Policies

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: tenant-isolation
spec:
  podSelector:
    matchLabels:
      app: percolate
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: gateway
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: percolate-reading
  - to:
    - podSelector:
        matchLabels:
          app: postgres
```

## Monitoring

### Metrics to Track

**Percolate Nodes (per tenant):**
- Memory usage (RocksDB size)
- Request latency (p50, p95, p99)
- Agent execution time
- Storage usage

**Reading Service (shared):**
- GPU utilization
- Request queue depth
- Processing time per operation
- Model loading time
- Throughput (requests/sec)

### Prometheus Metrics

```yaml
# Percolate node
percolate_memory_size_bytes{tenant_id="alice"}
percolate_request_duration_seconds{tenant_id="alice"}
percolate_agent_execution_seconds{tenant_id="alice"}

# Reading service
percolate_reading_gpu_utilization_percent
percolate_reading_queue_depth
percolate_reading_processing_duration_seconds{operation="parse_pdf"}
percolate_reading_throughput_requests_per_second
```

## Disaster Recovery

### Backup Strategy

**Percolate Nodes:**
- RocksDB snapshots every 6 hours
- S3 backup for cold storage
- Point-in-time recovery

**Reading Service:**
- No backups needed (stateless)
- Model cache rebuilt on pod restart

### High Availability

**Percolate Nodes:**
- 2 replicas per tenant (active-standby)
- Automatic failover on pod failure
- Data replicated between replicas

**Reading Service:**
- Minimum 3 replicas per region
- Auto-scaling up to 10 replicas
- Zero-downtime deployments

## Cost Projections

### 1,000 Tenants

| Component | Count | Cost/Month |
|-----------|-------|------------|
| Percolate nodes | 1,000 | $3,500 |
| Reading service | 10 GPU pods | $2,500 |
| Storage (S3) | 20TB | $460 |
| Bandwidth | 100TB | $9,000 |
| **Total** | | **$15,460** |

**Per tenant:** $15.46/month

### 10,000 Tenants

| Component | Count | Cost/Month |
|-----------|-------|------------|
| Percolate nodes | 10,000 | $35,000 |
| Reading service | 50 GPU pods | $12,500 |
| Storage (S3) | 200TB | $4,600 |
| Bandwidth | 1PB | $90,000 |
| **Total** | | **$142,100** |

**Per tenant:** $14.21/month

**Economies of scale:** 8% reduction per tenant

## References

- Kubernetes: https://kubernetes.io
- HPA: https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/
- GPU on K8s: https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/
- Network Policies: https://kubernetes.io/docs/concepts/services-networking/network-policies/
