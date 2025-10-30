# Observability Architecture: OpenTelemetry + Prometheus + Grafana

## Overview

The test topology uses a **hybrid observability stack** that combines OpenTelemetry (for application instrumentation) with Prometheus (for metrics storage) and Grafana (for visualization).

## Architecture

```mermaid
graph TB
    subgraph "Database Pods"
        DB1[test-db-small-0<br/>OpenTelemetry SDK]
        DB2[test-db-small-1<br/>OpenTelemetry SDK]
    end

    subgraph "Metrics Pipeline"
        OTEL[OpenTelemetry Collector<br/>Batch + Export]
        PROM[Prometheus<br/>Time-series DB]
    end

    subgraph "Consumers"
        KEDA[KEDA<br/>Autoscaler]
        GRAF[Grafana<br/>Dashboards]
    end

    subgraph "Cloud (Optional)"
        DD[Datadog]
        HC[Honeycomb]
    end

    DB1 -->|OTLP gRPC<br/>port 4317| OTEL
    DB2 -->|OTLP gRPC<br/>port 4317| OTEL
    DB1 -->|/metrics<br/>port 8000| PROM
    DB2 -->|/metrics<br/>port 8000| PROM

    OTEL -->|Remote Write<br/>:9090/api/v1/write| PROM
    OTEL -.->|OTLP Export<br/>(optional)| DD
    OTEL -.->|OTLP Export<br/>(optional)| HC

    PROM -->|PromQL Query| KEDA
    PROM -->|PromQL Query| GRAF

    style DB1 fill:#27ae60
    style DB2 fill:#27ae60
    style OTEL fill:#e74c3c
    style PROM fill:#3498db
    style KEDA fill:#f39c12
    style GRAF fill:#9b59b6
```

## Why Both OpenTelemetry AND Prometheus?

### Dual Metrics Collection

Each database pod exports metrics in **two ways**:

1. **OpenTelemetry SDK → OTLP → Collector**
   - Application instrumentation (consistent with production Percolate)
   - Metrics, traces, logs in unified format
   - Flexible export to multiple backends
   - Cloud-native observability

2. **Prometheus Client → /metrics endpoint**
   - Direct Prometheus scraping
   - KEDA native integration
   - Simple local testing
   - No collector dependency for KEDA

### Why Not Choose One?

**If we used ONLY OpenTelemetry:**
```
Database Pod (OTEL only)
    ↓ (OTLP)
OTEL Collector
    ↓ (Prometheus Exporter)
Prometheus
    ↓ (Query)
KEDA
```
- **Problem**: KEDA depends on OTEL Collector being up
- **Problem**: More complex failure modes
- **Problem**: Extra hop for every metric

**If we used ONLY Prometheus:**
```
Database Pod (Prom only)
    ↓ (/metrics)
Prometheus
    ↓ (Query)
KEDA
```
- **Problem**: Not consistent with Percolate's OTEL usage
- **Problem**: No cloud export (Datadog, Honeycomb, etc.)
- **Problem**: Separate metrics pipeline from traces/logs

**With BOTH:**
```
Database Pod (OTEL + Prom)
    ├─→ (OTLP) → OTEL Collector → Cloud backends
    └─→ (/metrics) → Prometheus → KEDA + Grafana
```
- **Benefit**: KEDA has direct, reliable access to metrics
- **Benefit**: Cloud backends get rich OTLP data
- **Benefit**: Consistent with production (OTEL SDK in code)
- **Benefit**: Grafana can query Prometheus (fast, local)

## Metrics Flow

### Prometheus-based Metrics (KEDA Scaling)

**Purpose**: KEDA scaling decisions

```python
# In database pod (app.py)
from prometheus_client import Gauge

prom_active_tenants_gauge = Gauge(
    "percolate_active_tenants",
    "Number of active tenants (last 5 minutes)",
    ["tier"],
)

prom_active_tenants_gauge.labels(tier=TIER).set(active_count)
```

**Flow:**
1. Database pod exposes `/metrics` endpoint (port 8000)
2. Prometheus scrapes every 15 seconds
3. KEDA queries Prometheus: `sum(percolate_active_tenants{tier="small"})`
4. If value > threshold, KEDA scales StatefulSet

**KEDA Configuration:**
```yaml
triggers:
- type: prometheus
  metadata:
    serverAddress: http://prometheus:9090
    metricName: percolate_active_tenants
    threshold: "2"  # 2 tenants per pod
    query: sum(percolate_active_tenants{tier="small"})
```

### OpenTelemetry Metrics (Cloud Export)

**Purpose**: Unified observability in production

```python
# In database pod (app.py)
from opentelemetry import metrics

meter = metrics.get_meter(__name__)
otel_tenant_requests = meter.create_counter(
    "percolate.tenant_requests",
    description="Total requests per tenant",
    unit="requests",
)

otel_tenant_requests.add(
    1, {"tenant_id": x_tenant_id, "pod": POD_NAME, "tier": TIER}
)
```

**Flow:**
1. Database pod pushes OTLP metrics to Collector (gRPC port 4317)
2. OTEL Collector batches metrics
3. OTEL Collector exports to:
   - Prometheus (remote write)
   - Datadog (optional, via OTLP exporter)
   - Honeycomb (optional, via OTLP exporter)

**Benefits:**
- Metrics, traces, logs correlated by trace ID
- Rich attribute support (not just labels)
- Exemplars (link metrics to traces)
- Cloud backend native support

## Grafana Integration

Grafana queries **Prometheus** as its datasource:

```yaml
datasources:
- name: Prometheus
  type: prometheus
  url: http://prometheus:9090
  isDefault: true
```

**Why not query OTEL Collector directly?**
- Prometheus has better query performance (time-series optimized)
- PromQL is more mature than OTEL query languages
- Grafana has native Prometheus support
- OTEL Collector is a pipeline, not a database

### Dashboard Queries

**Active Tenants by Tier:**
```promql
percolate_active_tenants{tier="small"}
```

**Request Rate by Tenant:**
```promql
rate(percolate_tenant_requests_total[1m])
```

**Tenant Affinity Hit Rate:**
```promql
sum by (pod) (percolate_affinity_hits_total)
  / sum by (pod) (percolate_tenant_requests_total)
```

**Pod Scaling Events:**
```promql
count(kube_pod_status_phase{namespace="percolate-test",phase="Running"})
```

## Component Roles Summary

| Component | Role | What It Does |
|-----------|------|--------------|
| **Database Pod** | Metrics source | Exports metrics via OTEL SDK + Prometheus client |
| **OTEL Collector** | Metrics pipeline | Receives OTLP, batches, exports to Prometheus + cloud |
| **Prometheus** | Metrics storage | Stores time-series data, answers PromQL queries |
| **kube-state-metrics** | K8s metrics | Exposes cluster state metrics (pods, deployments, nodes, etc.) |
| **KEDA** | Autoscaler | Queries Prometheus, scales pods based on metrics |
| **Grafana** | Visualization | Queries Prometheus, displays dashboards |
| **Cloud Backends** | Long-term storage | Receives OTLP for metrics/traces/logs correlation |

### kube-state-metrics Requirement

**IMPORTANT**: kube-state-metrics must be deployed for Grafana dashboards to function correctly.

**Why it's needed:**
- Provides `kube_pod_info`, `kube_deployment_status_replicas`, and other Kubernetes state metrics
- Required for pod-level dashboards showing pod counts, node distribution, and AZ topology
- Essential for multi-AZ topology dashboards

**Deployment:**
```bash
# Deploy kube-state-metrics to kube-system namespace
kubectl apply -f k8s/test-topology/manifests/kube-state-metrics.yaml

# Verify it's running
kubectl get pods -n kube-system -l app=kube-state-metrics

# Add to Prometheus scrape config
# See prometheus.yaml for kube-state-metrics job configuration
```

**Metrics provided:**
- `kube_pod_info{namespace, pod, node}` - Pod metadata and location
- `kube_deployment_status_replicas{deployment}` - Deployment replica counts
- `kube_statefulset_replicas{statefulset}` - StatefulSet replica counts
- `kube_node_labels{node, label_*}` - Node labels (including topology zones)

## Production vs Test Differences

### Test Topology (Kind)

- Prometheus scrapes `/metrics` directly from pods
- OTEL Collector exports to Prometheus (remote write)
- Grafana in cluster for local testing
- No cloud backends (optional)

### Production (AWS/GCP)

- Prometheus Operator with ServiceMonitors
- OTEL Collector as DaemonSet (one per node)
- Grafana Cloud or managed instance
- Cloud backends enabled (Datadog, Honeycomb, etc.)
- Metrics retention: 15 days in Prometheus, 90+ days in cloud

## Metrics Inventory

### KEDA Scaling Metrics (Prometheus)

| Metric | Type | Labels | Purpose |
|--------|------|--------|---------|
| `percolate_active_tenants` | Gauge | tier | Drives database pod scaling |
| `percolate_tenant_requests_total` | Counter | tenant_id, pod, tier | Request tracking |
| `percolate_affinity_hits_total` | Counter | tenant_id, pod | Affinity verification |

### OTLP Metrics (OpenTelemetry)

| Metric | Type | Attributes | Purpose |
|--------|------|------------|---------|
| `percolate.active_tenants` | UpDownCounter | tier, pod | Active tenant tracking |
| `percolate.tenant_requests` | Counter | tenant_id, pod, tier | Request counting |
| `percolate.affinity_hits` | Counter | tenant_id, pod | Affinity hits |
| `http.server.duration` | Histogram | method, route, status | FastAPI auto-instrumentation |
| `http.server.request.size` | Histogram | method, route | Request sizes |
| `http.server.response.size` | Histogram | method, route | Response sizes |

## Configuration

### Database Pod Environment Variables

```yaml
env:
- name: OTEL_EXPORTER_OTLP_ENDPOINT
  value: "http://otel-collector:4317"
- name: OTEL_SERVICE_NAME
  value: "test-db"
- name: OTEL_RESOURCE_ATTRIBUTES
  value: "deployment.environment=test,tier=small"
```

### Prometheus Scrape Configuration

```yaml
scrape_configs:
- job_name: 'kubernetes-pods'
  kubernetes_sd_configs:
  - role: pod
    namespaces:
      names:
      - percolate-test
  relabel_configs:
  # Only scrape pods with annotation
  - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
    action: keep
    regex: true
```

### OTEL Collector Pipeline

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317

processors:
  batch:
    timeout: 10s
  resource:
    attributes:
    - key: cluster.name
      value: test-topology
      action: upsert

exporters:
  prometheusremotewrite:
    endpoint: http://prometheus:9090/api/v1/write
  logging:
    verbosity: detailed

service:
  pipelines:
    metrics:
      receivers: [otlp]
      processors: [batch, resource]
      exporters: [prometheusremotewrite, logging]
```

## Testing the Stack

### 1. Verify Prometheus scraping

```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.app=="test-db")'

# Query active tenants
curl "http://localhost:9090/api/v1/query?query=percolate_active_tenants" | jq
```

### 2. Verify OTEL Collector receiving metrics

```bash
# Check OTEL Collector logs
kubectl logs -n percolate-test deployment/otel-collector

# Should see:
# Metric #0
# Descriptor:
#      -> Name: percolate.tenant_requests
#      -> DataType: Sum
```

### 3. Verify KEDA scaling

```bash
# Check KEDA HPA
kubectl get hpa -n percolate-test

# Check KEDA logs
kubectl logs -n keda deployment/keda-operator | grep percolate
```

### 4. Verify Grafana dashboards

```bash
# Access Grafana
kubectl port-forward -n percolate-test svc/grafana 3000:3000

# Open http://localhost:3000
# Username: admin
# Password: admin
```

## Troubleshooting

### Metrics not appearing in Prometheus

**Check pod annotations:**
```bash
kubectl get pod -n percolate-test test-db-small-0 -o yaml | grep prometheus.io
```

Should show:
```yaml
prometheus.io/scrape: "true"
prometheus.io/port: "8000"
prometheus.io/path: "/metrics"
```

**Check /metrics endpoint:**
```bash
kubectl exec -n percolate-test test-db-small-0 -- curl localhost:8000/metrics
```

### OTLP export failing

**Check OTEL Collector logs:**
```bash
kubectl logs -n percolate-test deployment/otel-collector
```

**Check connectivity:**
```bash
kubectl exec -n percolate-test test-db-small-0 -- nc -zv otel-collector 4317
```

### KEDA not scaling

**Check KEDA scaler status:**
```bash
kubectl describe scaledobject -n percolate-test
```

**Check Prometheus query:**
```bash
curl "http://localhost:9090/api/v1/query?query=sum(percolate_active_tenants{tier=\"small\"})"
```

## Next Steps

1. Deploy Grafana with dashboards
2. Create dashboards for:
   - Active tenants by tier
   - Request rate by tenant
   - Tenant affinity heatmap
   - Pod scaling timeline
3. Enable cloud export (Datadog/Honeycomb)
4. Add distributed tracing (span links)
5. Correlate metrics with traces via exemplars
