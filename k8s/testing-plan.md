# Percolate cluster testing plan

## Overview

Testing strategy for multi-tenant Kubernetes deployment covering tenant isolation, scaling behavior, routing affinity, and security boundaries. Tests validate that the architecture meets requirements for simplicity, isolation, security, and scaling.

## Testing principles

1. **Test in production-like environment**: Use staging cluster with same topology
2. **Automate everything**: No manual testing for regression scenarios
3. **Simulate real load patterns**: Mix of chat sessions, batch jobs, idle tenants
4. **Measure SLOs**: Response time, scale-up time, isolation guarantees
5. **Chaos engineering**: Test failure scenarios (node loss, AZ outage)

## Test categories

### 1. Tenant isolation tests

**Goal**: Verify tenants cannot access each other's data or resources.

**Test scenarios**:
- **T1.1 Data isolation**: Tenant A cannot read Tenant B's RocksDB data within same pod
- **T1.2 Application-layer isolation**: Same pod serving multiple tenants maintains strict data separation
- **T1.3 Resource isolation**: Tenant A cannot exhaust cluster resources affecting Tenant B
- **T1.4 Key isolation**: Tenant A cannot access Tenant B's cryptographic keys in OpenBao
- **T1.5 Routing isolation**: Correct tenant context always used for each request

**Testing approach**:
```bash
# Test T1.1: Data isolation
# 1. Create two tenants with sample data
python3 tests/cluster/test_isolation.py create-tenants --count 2

# 2. Attempt cross-tenant data access (should fail)
python3 tests/cluster/test_isolation.py test-data-access \
  --tenant-a tenant-001 \
  --tenant-b tenant-002 \
  --expect-failure

# Test T1.2: Application-layer isolation
# 1. Send concurrent requests for different tenants to same pod
python3 tests/cluster/test_application_isolation.py \
  --pod-target percolate-api-0 \
  --tenants tenant-001,tenant-002 \
  --concurrent-requests 100 \
  --verify-no-data-leakage

# Test T1.3: Resource isolation
# 1. Generate load on Tenant A (burst to max resources)
k6 run tests/load/resource-exhaustion.js --env TENANT=tenant-001

# 2. Verify Tenant B performance unaffected
python3 tests/cluster/test_noisy_neighbor.py \
  --noisy-tenant tenant-001 \
  --victim-tenant tenant-002 \
  --max-latency-degradation 10%

# Test T1.4: Key isolation
python3 tests/cluster/test_key_isolation.py \
  --tenant tenant-001 \
  --attempt-cross-tenant-key-access \
  --expect-failure

# Test T1.5: Routing isolation
# Verify correct tenant context maintained for each request
python3 tests/cluster/test_routing_isolation.py \
  --send-requests 1000 \
  --tenants tenant-001,tenant-002,tenant-003 \
  --verify-correct-tenant-context \
  --concurrent true
```

**Expected results**:
- All cross-tenant access attempts fail with 403/404
- Same pod serving multiple tenants maintains strict data separation
- Resource quotas enforced (Tenant B maintains <10% latency increase)
- Key access attempts logged and rejected in OpenBao
- 100% routing accuracy (correct tenant context for every request)

### 2. Scaling and autoscaling tests

**Goal**: Verify KEDA scales StatefulSets from 0→N and back based on load.

**Test scenarios**:
- **T2.1 Scale from zero**: Cold start tenant, measure time to first response
- **T2.2 Scale up**: Increase load, verify pods scale 1→N
- **T2.3 Scale down**: Remove load, verify pods scale N→1
- **T2.4 Scale to zero**: Idle timeout, verify pods scale 1→0
- **T2.5 Multi-tenant scaling**: 10 tenants scale independently
- **T2.6 Scale flapping prevention**: Verify cooldown prevents rapid scale cycles

**Testing approach**:
```bash
# Test T2.1: Scale from zero
python3 tests/cluster/test_scale_from_zero.py \
  --tenant tenant-cold \
  --expect-scaled-to-zero \
  --send-request \
  --measure-ttfr \
  --max-ttfr 30s

# Test T2.2: Scale up
k6 run tests/load/scale-up.js \
  --vus 1 \
  --duration 1m \
  --env TENANT=tenant-003 \
  --env RAMP_UP=true

python3 tests/cluster/verify_scaling.py \
  --tenant tenant-003 \
  --expect-min-replicas 3 \
  --within 90s

# Test T2.3: Scale down
# (After T2.2, stop load and wait for HPA to scale down)
python3 tests/cluster/verify_scaling.py \
  --tenant tenant-003 \
  --expect-max-replicas 1 \
  --within 300s

# Test T2.4: Scale to zero
# (Wait for cooldown period after scale down)
python3 tests/cluster/verify_scaling.py \
  --tenant tenant-003 \
  --expect-replicas 0 \
  --within 600s

# Test T2.5: Multi-tenant scaling
python3 tests/cluster/test_multi_tenant_scaling.py \
  --tenants 10 \
  --concurrent-load true \
  --verify-independent-scaling

# Test T2.6: Scale flapping prevention
python3 tests/cluster/test_scale_flapping.py \
  --tenant tenant-004 \
  --oscillating-load true \
  --duration 20m \
  --max-scale-events 4
```

**Expected results**:
- TTFR (Time To First Response) from cold start: <30s
- Scale up 1→3 replicas: <90s under sustained load
- Scale down 3→1: <5min after load stops
- Scale to zero: <10min after idle (cooldown)
- Independent scaling: Each tenant scales without affecting others
- Flapping prevention: <4 scale events in 20min of oscillating load

### 3. Routing and tenant affinity tests

**Goal**: Verify Istio routes requests to correct tenant pods with sticky sessions.

**Test scenarios**:
- **T3.1 Tenant affinity**: Requests for same tenant route to same pod
- **T3.2 Consistent hashing**: Hash-based routing distributes tenants evenly
- **T3.3 Multi-AZ routing**: Prefer local AZ, failover to remote
- **T3.4 Health-aware routing**: Don't route to terminating pods
- **T3.5 Gateway routing**: Gateway correctly injects tenant headers

**Testing approach**:
```bash
# Test T3.1: Tenant affinity
python3 tests/cluster/test_tenant_affinity.py \
  --tenant tenant-005 \
  --requests 100 \
  --verify-same-pod \
  --session-duration 5m

# Test T3.2: Consistent hashing
python3 tests/cluster/test_consistent_hashing.py \
  --tenants 50 \
  --requests-per-tenant 20 \
  --verify-distribution \
  --max-skew 20%

# Test T3.3: Multi-AZ routing
python3 tests/cluster/test_az_routing.py \
  --source-az us-east-1a \
  --requests 1000 \
  --verify-local-preference 80% \
  --simulate-az-failure us-east-1a \
  --verify-failover

# Test T3.4: Health-aware routing
python3 tests/cluster/test_health_aware_routing.py \
  --tenant tenant-006 \
  --trigger-pod-termination \
  --send-concurrent-requests 50 \
  --verify-zero-errors

# Test T3.5: Gateway routing
python3 tests/cluster/test_gateway_routing.py \
  --tenants 10 \
  --requests-per-tenant 100 \
  --verify-header-injection \
  --verify-tier-routing
```

**Expected results**:
- Affinity: 100% of requests for tenant route to same pod (until scale event)
- Consistent hashing: Tenant distribution skew <20% across pods
- AZ routing: 80% local, 100% failover success on AZ outage
- Health-aware: Zero 5xx errors during pod termination
- Gateway: 100% correct tenant header injection and tier routing

### 4. Security and secrets tests

**Goal**: Verify cryptographic keys secured and access controlled.

**Test scenarios**:
- **T4.1 KMS integration**: Secrets encrypted with KMS provider
- **T4.2 Key rotation**: Rotate tenant keys without downtime
- **T4.3 Audit logging**: All key access logged
- **T4.4 Pod security**: Pods run with minimal privileges
- **T4.5 Network policies**: Only authorized traffic allowed

**Testing approach**:
```bash
# Test T4.1: KMS integration
python3 tests/cluster/test_kms.py \
  --create-secret tenant-007-key \
  --verify-encrypted-in-etcd \
  --verify-kms-unwrap

# Test T4.2: Key rotation
python3 tests/cluster/test_key_rotation.py \
  --tenant tenant-008 \
  --rotate-keys \
  --send-requests-during-rotation 100 \
  --verify-zero-errors

# Test T4.3: Audit logging
python3 tests/cluster/test_audit_logs.py \
  --access-tenant-secret tenant-009 \
  --verify-log-entry \
  --log-contains "secret accessed"

# Test T4.4: Pod security
python3 tests/cluster/test_pod_security.py \
  --namespace percolate \
  --verify-read-only-root-filesystem \
  --verify-no-privileged-containers \
  --verify-security-context

# Test T4.5: Network policies
python3 tests/cluster/test_network_policies.py \
  --tenant tenant-011 \
  --test-unauthorized-access \
  --expect-blocked
```

**Expected results**:
- Secrets encrypted in etcd via KMS
- Key rotation completes without request failures
- 100% of key accesses logged with tenant ID and timestamp
- All pods run with `readOnlyRootFilesystem: true`, `runAsNonRoot: true`
- Network policies block all unauthorized traffic

### 5. Performance and load tests

**Goal**: Validate system handles expected load with acceptable latency.

**Test scenarios**:
- **T5.1 Baseline latency**: Measure p50, p95, p99 under normal load
- **T5.2 Spike handling**: Handle 10x traffic spike
- **T5.3 Sustained load**: Maintain SLOs over 24 hours
- **T5.4 Cold start latency**: First request after scale-to-zero
- **T5.5 Concurrent tenants**: 100 tenants active simultaneously

**Testing approach**:
```bash
# Test T5.1: Baseline latency
k6 run tests/load/baseline.js \
  --vus 50 \
  --duration 10m \
  --env TENANTS=10 \
  --summary-export results/baseline.json

python3 tests/cluster/analyze_results.py \
  --input results/baseline.json \
  --verify-p95 "<500ms" \
  --verify-p99 "<1000ms"

# Test T5.2: Spike handling
k6 run tests/load/spike.js \
  --stage "0s:10,30s:100,60s:10" \
  --env TENANTS=10 \
  --summary-export results/spike.json

# Test T5.3: Sustained load
k6 run tests/load/sustained.js \
  --vus 100 \
  --duration 24h \
  --env TENANTS=50 \
  --summary-export results/sustained.json

# Test T5.4: Cold start latency
python3 tests/cluster/test_cold_start.py \
  --tenants 20 \
  --iterations 100 \
  --measure-ttfr \
  --export results/cold-start.json

# Test T5.5: Concurrent tenants
k6 run tests/load/concurrent-tenants.js \
  --vus 100 \
  --duration 30m \
  --env TENANTS=100 \
  --summary-export results/concurrent.json
```

**Expected results**:
- Baseline: p95 <500ms, p99 <1s, error rate <0.1%
- Spike: No errors during 10x spike, auto-scale handles load
- Sustained: SLOs maintained over 24h, no memory leaks
- Cold start: p95 TTFR <30s
- Concurrent: 100 tenants, p95 <750ms, error rate <0.5%

### 6. Chaos and resilience tests

**Goal**: Verify system recovers gracefully from failures.

**Test scenarios**:
- **T6.1 Pod failure**: Kill random pod, verify recovery
- **T6.2 Node failure**: Drain node, verify pod migration
- **T6.3 AZ failure**: Simulate entire AZ outage
- **T6.4 NATS failure**: NATS cluster loses quorum, verify recovery
- **T6.5 Gateway failure**: Gateway pods crash, verify failover
- **T6.6 Network partition**: Simulate network split between AZs

**Testing approach**:
```bash
# Test T6.1: Pod failure
python3 tests/chaos/test_pod_failure.py \
  --tenant tenant-012 \
  --send-load-background \
  --kill-random-pod \
  --verify-recovery \
  --max-downtime 10s

# Test T6.2: Node failure
python3 tests/chaos/test_node_failure.py \
  --drain-node ip-10-0-1-123 \
  --verify-pod-migration \
  --verify-tenant-continuity \
  --max-downtime 60s

# Test T6.3: AZ failure
python3 tests/chaos/test_az_failure.py \
  --fail-az us-east-1a \
  --duration 10m \
  --verify-failover \
  --verify-data-consistency

# Test T6.4: NATS failure
python3 tests/chaos/test_nats_failure.py \
  --stop-nats-pods 2 \
  --verify-queue-continuity \
  --verify-message-delivery

# Test T6.5: Gateway failure
python3 tests/chaos/test_gateway_failure.py \
  --send-load-background \
  --kill-all-gateway-pods \
  --verify-new-pods-ready \
  --max-downtime 15s

# Test T6.6: Network partition
python3 tests/chaos/test_network_partition.py \
  --partition us-east-1a,us-east-1b \
  --duration 5m \
  --verify-split-brain-prevention \
  --verify-rejoin
```

**Expected results**:
- Pod failure: <10s downtime, automatic recovery
- Node failure: <60s to migrate pods, no data loss
- AZ failure: Automatic failover to healthy AZs, no data loss
- NATS failure: Messages queued, delivered after recovery
- Gateway failure: <15s to new pods ready, buffered requests served
- Network partition: No split-brain, clean rejoin after heal

## Test infrastructure

### Local development testing

```bash
# Spin up local kind cluster with multi-node setup
./scripts/test-cluster-create.sh --nodes 6 --zones 3

# Deploy percolate with test configuration
helm install percolate ./charts/percolate \
  --namespace percolate-system \
  --values ./charts/percolate/values-test.yaml

# Run smoke tests
pytest tests/integration/test_smoke.py -v

# Teardown
./scripts/test-cluster-destroy.sh
```

### Staging cluster testing

```bash
# Deploy to staging cluster (production-like)
./scripts/deploy-staging.sh --environment staging

# Run full test suite
./scripts/run-tests.sh --suite all --parallel 4

# Generate test report
python3 tests/generate_report.py \
  --results results/ \
  --output reports/test-report.html
```

### CI/CD integration

```yaml
# .github/workflows/cluster-tests.yml
name: Cluster Tests

on:
  pull_request:
    paths:
      - 'manifests/**'
      - 'charts/**'
      - 'tests/cluster/**'

jobs:
  isolation-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Create test cluster
        run: ./scripts/test-cluster-create.sh
      - name: Run isolation tests
        run: pytest tests/cluster/test_isolation.py -v
      - name: Cleanup
        if: always()
        run: ./scripts/test-cluster-destroy.sh

  scaling-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Create test cluster
        run: ./scripts/test-cluster-create.sh
      - name: Run scaling tests
        run: pytest tests/cluster/test_scaling.py -v
      - name: Cleanup
        if: always()
        run: ./scripts/test-cluster-destroy.sh

  load-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to staging
        run: ./scripts/deploy-staging.sh
      - name: Run k6 load tests
        run: k6 run tests/load/baseline.js
      - name: Analyze results
        run: python3 tests/analyze_results.py
```

## Testing scripts structure

```
tests/
├── cluster/                    # Cluster-level integration tests
│   ├── test_isolation.py       # Tenant isolation tests (T1.*)
│   ├── test_scaling.py         # Scaling tests (T2.*)
│   ├── test_routing.py         # Routing tests (T3.*)
│   ├── test_security.py        # Security tests (T4.*)
│   └── verify_scaling.py       # Helper to verify scaling state
├── load/                       # k6 load test scripts
│   ├── baseline.js             # Baseline load test (T5.1)
│   ├── spike.js                # Spike test (T5.2)
│   ├── sustained.js            # 24h sustained load (T5.3)
│   ├── concurrent-tenants.js   # 100 concurrent tenants (T5.5)
│   └── scale-up.js             # Scale-up load pattern
├── chaos/                      # Chaos engineering tests
│   ├── test_pod_failure.py     # Pod failure tests (T6.1)
│   ├── test_node_failure.py    # Node failure tests (T6.2)
│   ├── test_az_failure.py      # AZ failure tests (T6.3)
│   └── test_network_partition.py # Network partition (T6.6)
├── manifests/                  # Test-specific manifests
│   ├── network-isolation-test.yaml
│   └── chaos-test-pods.yaml
├── fixtures/                   # Test data and fixtures
│   ├── tenants.yaml            # Sample tenant configs
│   └── load-scenarios.yaml     # Load test scenarios
└── integration/                # End-to-end integration tests
    ├── test_smoke.py           # Basic smoke tests
    └── test_full_flow.py       # Complete user flow tests

scripts/
├── test-cluster-create.sh      # Create local test cluster
├── test-cluster-destroy.sh     # Teardown test cluster
├── deploy-staging.sh           # Deploy to staging
└── run-tests.sh                # Test orchestration script
```

## Key testing tools

### Load testing
- **k6**: HTTP load testing with JavaScript DSL
- **locust**: Python-based load testing (alternative)
- **hey**: Simple HTTP load generator for quick tests

### Chaos testing
- **chaos-mesh**: Kubernetes-native chaos engineering
- **litmus**: Chaos workflows for K8s
- **kubectl drain/delete**: Simple manual chaos

### Monitoring during tests
- **Prometheus**: Metrics collection
- **Grafana**: Visualization dashboards
- **Jaeger**: Distributed tracing
- **kubectl top**: Quick resource usage

### Test orchestration
- **pytest**: Python test framework
- **pytest-xdist**: Parallel test execution
- **pytest-html**: HTML test reports

## Test data requirements

### Tenant provisioning
- 100 test tenants across tiers (small: 70, medium: 25, large: 5)
- Pre-populated data sets (10MB, 100MB, 1GB per tier)
- Realistic entity graphs (100-10000 nodes)

### Load patterns
- **Chat sessions**: WebSocket connections, 5-10 messages/session
- **Batch ingestion**: Document uploads, 10-100 docs/batch
- **Background jobs**: Parsing, embedding generation
- **Idle tenants**: Zero activity for 15+ minutes

## Success criteria

Architecture passes testing if:

1. **Isolation**: 100% isolation verification (zero cross-tenant access)
2. **Scaling**: Scale 0→N in <90s, N→0 in <10min, no flapping
3. **Routing**: 100% routing accuracy, <20% distribution skew
4. **Security**: All keys encrypted, audit logs complete, pod security enforced
5. **Performance**: p95 <500ms baseline, p95 <1s under spike
6. **Resilience**: <60s recovery from node/pod failure, zero data loss

## Test schedule

### Pre-merge (PR validation)
- Isolation tests (T1.*)
- Basic scaling tests (T2.1, T2.2)
- Security tests (T4.*)
- Duration: ~15 minutes

### Nightly (staging cluster)
- Full scaling suite (T2.*)
- Routing tests (T3.*)
- Performance baseline (T5.1)
- Chaos tests (T6.1, T6.2)
- Duration: ~2 hours

### Weekly (staging cluster)
- Sustained load (T5.3) - 24 hours
- Multi-tenant scaling (T5.5)
- AZ failure tests (T6.3)
- Full chaos suite (T6.*)
- Duration: ~30 hours

### Pre-production (staging cluster)
- All tests (T1.*-T6.*)
- Duration: ~48 hours
- Requires: Sign-off from 2 engineers

## Observability during testing

### Metrics to monitor
- Request latency (p50, p95, p99)
- Error rate (5xx, timeout)
- Pod count per StatefulSet
- Memory/CPU usage per pod
- NATS queue depth
- RocksDB compaction stats
- Network throughput per pod

### Dashboards
- **Testing Overview**: Real-time test progress
- **Tenant Isolation**: Cross-tenant access attempts (should be zero)
- **Scaling Behavior**: Pod count vs load over time
- **Performance**: Latency histograms, error rates
- **Resource Usage**: CPU, memory, disk per tier

### Alerts during tests
- Any cross-tenant access (immediate failure)
- Error rate >1% (investigate)
- Scaling lag >2min (tune KEDA)
- Memory leak detected (pod restart count increasing)

## Next steps

1. Implement test scripts in `tests/cluster/` directory
2. Create k6 load test scripts in `tests/load/`
3. Set up staging cluster with production-like topology
4. Integrate tests into CI/CD pipeline
5. Create Grafana dashboards for test monitoring
6. Run initial test suite, tune architecture based on results
7. Document test results and establish baseline SLOs
