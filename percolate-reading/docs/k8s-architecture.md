# Kubernetes Architecture for Percolate-Reading

## Overview

Percolate-reading deploys in two modes using a **single Docker image**:

1. **Gateway Mode**: Receives uploads, stages to S3, queues jobs to NATS
2. **Worker Mode**: Listens to NATS queue, processes files, writes results to S3

**Key Technology Decisions:**
- **NATS JetStream**: Durable message queue for job distribution
- **KEDA**: Auto-scale workers based on NATS queue depth (scales to zero)
- **S3/Minio**: Shared storage for file staging and artifacts
- **Same Codebase**: Single Docker image, mode controlled by env var

## Architecture Diagram

```
┌────────────────────────────────────────────────────────┐
│                 Load Balancer (Ingress)                │
└────────────────────┬───────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────┐
│          percolate-reading Gateway Pods                │
│  Replicas: 3 (fixed)                                   │
│  Resources: 512Mi memory, 500m CPU (lightweight)       │
│                                                         │
│  Responsibilities:                                      │
│  1. Receive file uploads (multipart/form-data)         │
│  2. Stage file to S3/Minio (tenant-scoped bucket)      │
│  3. Create job metadata                                │
│  4. Queue job message to NATS JetStream                │
│  5. Return 202 Accepted with job_id                    │
│  6. Export tenant context to S3 (for instant LLM)      │
└────────────────────┬───────────────────────────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │   NATS JetStream      │
         │   - Stream: JOBS      │
         │   - Subject: jobs.*   │
         │   - Retention: 7d     │
         │   - Max msgs: 100k    │
         └──────────┬────────────┘
                    │
                    │ (KEDA ScaledObject watches)
                    ▼
┌────────────────────────────────────────────────────────┐
│        percolate-reading Worker Pods (KEDA)            │
│  Min Replicas: 0 (scales to zero when idle)            │
│  Max Replicas: 50                                      │
│  Resources: 2-16Gi memory, 1-4 CPU (configurable)      │
│                                                         │
│  Scaling Trigger:                                      │
│  - NATS queue depth > 5 → scale up                     │
│  - NATS queue depth = 0 → scale to zero                │
│                                                         │
│  Responsibilities:                                      │
│  1. Subscribe to NATS subject: jobs.parse              │
│  2. Receive job message (tenant_id, job_id, s3_uri)    │
│  3. Download file from S3                              │
│  4. Process with provider (PDF/Excel/Audio/Image)      │
│  5. Write artifacts to S3 (structured.md, tables/)     │
│  6. Update job status in RocksDB (optional)            │
│  7. Send webhook callback (if configured)              │
│  8. Acknowledge NATS message                           │
└────────────────────┬───────────────────────────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │    S3/Minio Storage   │
         │                       │
         │  Buckets:             │
         │  - percolate-files    │
         │    (staged uploads)   │
         │  - percolate-artifacts│
         │    (parse results)    │
         │  - percolate-context  │
         │    (tenant context)   │
         └───────────────────────┘
```

## Deployment Modes

### Gateway Mode
```yaml
env:
  - name: PERCOLATE_READING_GATEWAY_MODE
    value: "true"
  - name: PERCOLATE_READING_S3_ENABLED
    value: "true"
  - name: PERCOLATE_READING_NATS_ENABLED
    value: "true"
  - name: PERCOLATE_READING_NATS_URL
    value: "nats://nats:4222"
```

**Behavior:**
- Starts FastAPI server on port 8001
- POST /v1/parse → stages to S3 → queues NATS message
- Returns 202 Accepted immediately (no processing)
- Exports tenant context to S3 for instant LLM serving

### Worker Mode
```yaml
env:
  - name: PERCOLATE_READING_GATEWAY_MODE
    value: "false"
  - name: PERCOLATE_READING_WORKER_MODE
    value: "true"
  - name: PERCOLATE_READING_S3_ENABLED
    value: "true"
  - name: PERCOLATE_READING_NATS_ENABLED
    value: "true"
  - name: PERCOLATE_READING_NATS_URL
    value: "nats://nats:4222"
  - name: PERCOLATE_READING_NATS_QUEUE_GROUP
    value: "parse-workers"
```

**Behavior:**
- Subscribes to NATS subject: `jobs.parse`
- Pulls job messages from queue
- Downloads file from S3
- Processes with appropriate provider
- Writes results to S3
- Sends webhook callback (optional)
- Acknowledges NATS message

## NATS JetStream Configuration

### Stream Definition
```json
{
  "name": "JOBS",
  "subjects": ["jobs.*"],
  "retention": "workqueue",
  "max_msgs": 100000,
  "max_age": 604800000000000,  // 7 days in nanoseconds
  "max_msg_size": 10485760,     // 10MB
  "storage": "file",
  "num_replicas": 3,
  "discard": "old"
}
```

### Consumer Definition
```json
{
  "durable_name": "parse-workers",
  "deliver_policy": "all",
  "ack_policy": "explicit",
  "ack_wait": 300000000000,     // 5 minutes
  "max_deliver": 3,
  "filter_subject": "jobs.parse",
  "max_ack_pending": 100
}
```

### Job Message Format
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "acme-corp",
  "file_name": "report.pdf",
  "file_type": "application/pdf",
  "s3_uri": "s3://percolate-files/acme-corp/550e8400.../report.pdf",
  "storage_strategy": "tenant",
  "callback_url": "https://api.acme.com/webhooks/parse",
  "priority": 5,
  "resources": {
    "cpu": "2",
    "memory": "4Gi",
    "gpu": "0"
  },
  "created_at": "2025-10-25T10:30:00Z"
}
```

## KEDA Configuration

### ScaledObject for Workers
```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: percolate-reading-workers
  namespace: percolate
spec:
  scaleTargetRef:
    name: percolate-reading-workers
  minReplicaCount: 0                    # Scale to zero when idle
  maxReplicaCount: 50
  pollingInterval: 10                   # Check every 10 seconds
  cooldownPeriod: 60                    # Wait 60s before scaling down

  triggers:
  - type: nats-jetstream
    metadata:
      natsServerMonitoringEndpoint: "nats.percolate.svc:8222"
      stream: "JOBS"
      consumer: "parse-workers"
      lagThreshold: "5"                 # Scale up if >5 pending messages
      activationLagThreshold: "1"       # Activate if >=1 message
```

**Scaling Behavior:**
- **Queue depth 0**: Scale to 0 replicas (save costs)
- **Queue depth 1-5**: Scale to 1 replica
- **Queue depth 6-10**: Scale to 2 replicas
- **Queue depth 11+**: Scale proportionally (1 pod per 5 messages)
- **Max 50 pods**: Hard limit to prevent runaway scaling

## Kubernetes Manifests

### Gateway Deployment
```yaml
# k8s/gateway/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: percolate-reading-gateway
  namespace: percolate
  labels:
    app: percolate-reading
    component: gateway
spec:
  replicas: 3
  selector:
    matchLabels:
      app: percolate-reading
      component: gateway
  template:
    metadata:
      labels:
        app: percolate-reading
        component: gateway
    spec:
      containers:
      - name: gateway
        image: percolate-reading:latest
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 8001
          name: http
        env:
        - name: PERCOLATE_READING_GATEWAY_MODE
          value: "true"
        - name: PERCOLATE_READING_S3_ENABLED
          value: "true"
        - name: PERCOLATE_READING_S3_ENDPOINT
          value: "http://minio.percolate.svc:9000"
        - name: PERCOLATE_READING_S3_BUCKET
          value: "percolate-files"
        - name: PERCOLATE_READING_S3_ACCESS_KEY
          valueFrom:
            secretKeyRef:
              name: s3-credentials
              key: access-key
        - name: PERCOLATE_READING_S3_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: s3-credentials
              key: secret-key
        - name: PERCOLATE_READING_NATS_ENABLED
          value: "true"
        - name: PERCOLATE_READING_NATS_URL
          value: "nats://nats.percolate.svc:4222"
        - name: PERCOLATE_READING_NATS_QUEUE_SUBJECT
          value: "jobs.parse"
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8001
          initialDelaySeconds: 10
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8001
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: percolate-reading-gateway
  namespace: percolate
spec:
  type: ClusterIP
  selector:
    app: percolate-reading
    component: gateway
  ports:
  - port: 8001
    targetPort: 8001
    name: http
```

### Worker Deployment (Scaled by KEDA)
```yaml
# k8s/workers/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: percolate-reading-workers
  namespace: percolate
  labels:
    app: percolate-reading
    component: worker
spec:
  replicas: 1  # Managed by KEDA, will be overridden
  selector:
    matchLabels:
      app: percolate-reading
      component: worker
  template:
    metadata:
      labels:
        app: percolate-reading
        component: worker
    spec:
      containers:
      - name: worker
        image: percolate-reading:latest
        imagePullPolicy: IfNotPresent
        env:
        - name: PERCOLATE_READING_GATEWAY_MODE
          value: "false"
        - name: PERCOLATE_READING_WORKER_MODE
          value: "true"
        - name: PERCOLATE_READING_S3_ENABLED
          value: "true"
        - name: PERCOLATE_READING_S3_ENDPOINT
          value: "http://minio.percolate.svc:9000"
        - name: PERCOLATE_READING_S3_BUCKET
          value: "percolate-files"
        - name: PERCOLATE_READING_S3_ACCESS_KEY
          valueFrom:
            secretKeyRef:
              name: s3-credentials
              key: access-key
        - name: PERCOLATE_READING_S3_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: s3-credentials
              key: secret-key
        - name: PERCOLATE_READING_NATS_ENABLED
          value: "true"
        - name: PERCOLATE_READING_NATS_URL
          value: "nats://nats.percolate.svc:4222"
        - name: PERCOLATE_READING_NATS_QUEUE_GROUP
          value: "parse-workers"
        - name: PERCOLATE_READING_DEVICE
          value: "cpu"  # or "cuda" for GPU workers
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        # No liveness/readiness probes for workers (NATS handles health)
---
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: percolate-reading-workers
  namespace: percolate
spec:
  scaleTargetRef:
    name: percolate-reading-workers
  minReplicaCount: 0
  maxReplicaCount: 50
  pollingInterval: 10
  cooldownPeriod: 60
  triggers:
  - type: nats-jetstream
    metadata:
      natsServerMonitoringEndpoint: "nats.percolate.svc:8222"
      stream: "JOBS"
      consumer: "parse-workers"
      lagThreshold: "5"
      activationLagThreshold: "1"
```

### NATS JetStream Deployment
```yaml
# k8s/nats/statefulset.yaml
apiVersion: v1
kind: Service
metadata:
  name: nats
  namespace: percolate
spec:
  selector:
    app: nats
  clusterIP: None
  ports:
  - name: client
    port: 4222
  - name: monitoring
    port: 8222
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: nats
  namespace: percolate
spec:
  serviceName: nats
  replicas: 3
  selector:
    matchLabels:
      app: nats
  template:
    metadata:
      labels:
        app: nats
    spec:
      containers:
      - name: nats
        image: nats:latest
        args:
        - "--jetstream"
        - "--store_dir=/data"
        - "--cluster_name=percolate"
        ports:
        - containerPort: 4222
          name: client
        - containerPort: 8222
          name: monitoring
        volumeMounts:
        - name: data
          mountPath: /data
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 10Gi
```

## Resource Profiles

### Small File Profile (Default)
```yaml
resources:
  requests:
    memory: "2Gi"
    cpu: "1000m"
  limits:
    memory: "4Gi"
    cpu: "2000m"
```

Use for: PDF (<50MB), Excel, small images

### Large File Profile
```yaml
resources:
  requests:
    memory: "8Gi"
    cpu: "2000m"
  limits:
    memory: "16Gi"
    cpu: "4000m"
```

Use for: Large PDFs (>100MB), video transcription

### GPU Profile
```yaml
resources:
  requests:
    memory: "16Gi"
    cpu: "4000m"
    nvidia.com/gpu: "1"
  limits:
    memory: "32Gi"
    cpu: "8000m"
    nvidia.com/gpu: "1"
```

Use for: Batch embeddings, Whisper transcription, image OCR

## Deployment Strategy

### Phase 1: Local Testing (Docker Compose)
```bash
cd percolate-reading
docker-compose up -d

# Test gateway
curl -F "file=@test.pdf" http://localhost:8001/v1/parse

# Check NATS queue
nats stream info JOBS
nats consumer info JOBS parse-workers
```

### Phase 2: Kubernetes Deployment
```bash
# Create namespace
kubectl create namespace percolate

# Deploy NATS JetStream
kubectl apply -f k8s/nats/

# Deploy S3/Minio
kubectl apply -f k8s/minio/

# Deploy gateway
kubectl apply -f k8s/gateway/

# Deploy workers with KEDA
kubectl apply -f k8s/workers/

# Verify
kubectl get pods -n percolate
kubectl logs -n percolate -l component=gateway
kubectl logs -n percolate -l component=worker
```

### Phase 3: Argo CD GitOps
```bash
# Apply Argo Application
kubectl apply -f k8s/argo-app.yaml

# Sync
argocd app sync percolate-reading

# Monitor
argocd app get percolate-reading
```

## Monitoring & Observability

### Key Metrics

**Gateway:**
- `http_requests_total{endpoint="/v1/parse"}`
- `s3_upload_duration_seconds`
- `nats_publish_duration_seconds`

**Workers:**
- `nats_messages_processed_total`
- `parse_duration_seconds{provider="pdf|excel|audio"}`
- `parse_errors_total{provider}`
- `s3_artifact_write_duration_seconds`

**NATS:**
- `nats_jetstream_stream_messages{stream="JOBS"}`
- `nats_jetstream_consumer_pending{consumer="parse-workers"}`

**KEDA:**
- `keda_scaler_active{scaledObject="percolate-reading-workers"}`
- `keda_scaler_metrics_value{scaler="nats-jetstream"}`

### Prometheus Queries

```promql
# Current queue depth
nats_jetstream_stream_messages{stream="JOBS"}

# Worker scaling
sum(kube_deployment_status_replicas{deployment="percolate-reading-workers"})

# Parse throughput (jobs/min)
rate(nats_messages_processed_total[1m]) * 60

# Error rate
rate(parse_errors_total[5m]) / rate(nats_messages_processed_total[5m])
```

## Cost Optimization

### Scale-to-Zero Strategy
- Workers scale to 0 when queue empty
- Gateway runs 24/7 (lightweight, fixed 3 replicas)
- Save ~80% compute costs during idle periods

### Tiered Worker Pools
Create separate worker pools for different file sizes:
```yaml
# Small files (default)
maxReplicaCount: 50
resources: 2Gi memory, 1 CPU

# Large files (on-demand)
maxReplicaCount: 10
resources: 16Gi memory, 4 CPU

# GPU workers (expensive)
maxReplicaCount: 5
resources: 32Gi memory, 8 CPU, 1 GPU
```

Route jobs based on file size in NATS subject:
- `jobs.parse.small` → small worker pool
- `jobs.parse.large` → large worker pool
- `jobs.parse.gpu` → GPU worker pool

## Security Considerations

### Network Policies
```yaml
# Only gateway accepts external traffic
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: gateway-ingress
spec:
  podSelector:
    matchLabels:
      component: gateway
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
```

### Secrets Management
- S3 credentials: Sealed Secrets or External Secrets Operator
- API tokens: K8s Secrets (encrypted at rest)
- Tenant keys: Mounted per-worker (tenant-scoped)

### Tenant Isolation
- Workers process one tenant at a time (no multi-tenancy in worker)
- S3 bucket scoped by tenant_id
- NATS messages include tenant_id for routing

## References

- **Platform Spike**: `.spikes/platform/readme.md`
- **KEDA NATS Scaler**: https://keda.sh/docs/scalers/nats-jetstream/
- **NATS JetStream**: https://docs.nats.io/nats-concepts/jetstream
- **Argo CD**: https://argo-cd.readthedocs.io/
