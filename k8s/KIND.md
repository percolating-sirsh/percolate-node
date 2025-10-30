# Kind (Kubernetes in Docker) local testing

Local testing setup for Percolate on Kind with minimal resource consumption.

## Overview

This guide shows how to deploy Percolate on a local Kind cluster with scaled-down resources for development and testing. The setup is designed to run on a developer laptop with 8-16GB RAM.

**What you'll get**:
- Local Kubernetes cluster (Kind)
- Single-tier deployment (small tier only)
- Minimal replicas (1 per component)
- Reduced resource limits
- Local image loading (no registry push)
- Port-forwarding for access

**Resource budget**:
- Kind control plane: ~500MB
- Percolate infrastructure: ~1.5GB (OpenBao, NATS, Redis, Gateway)
- Percolate API: ~1GB per replica
- Percolate Worker: ~2GB per replica
- **Total**: ~5GB for full stack

## Prerequisites

```bash
# Install Kind
brew install kind  # macOS
# Or: curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64

# Install kubectl
brew install kubectl

# Install Helm (optional, for some components)
brew install helm

# Verify installations
kind version
kubectl version --client
```

## Quick start

### Option 1: Automated setup (easiest)

```bash
# Run the Kind setup script
./k8s/kind-setup.sh

# This will:
# - Create Kind cluster with local registry
# - Install Istio (minimal profile)
# - Install KEDA
# - Build and load Docker images locally
# - Deploy Percolate with minimal resources
# - Set up port-forwards
```

### Option 2: Manual setup

See sections below for step-by-step instructions.

## Step 1: Create Kind cluster

### Basic cluster

```bash
# Create cluster with single node
kind create cluster --name percolate-dev

# Verify cluster
kubectl cluster-info --context kind-percolate-dev
```

### Cluster with local registry

For faster image loading, create a local registry:

```bash
# Create local registry
docker run -d --restart=always \
  -p 5001:5000 \
  --name kind-registry \
  registry:2

# Create Kind cluster with registry
cat <<EOF | kind create cluster --name percolate-dev --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  kubeadmConfigPatches:
  - |
    kind: InitConfiguration
    nodeRegistration:
      kubeletExtraArgs:
        node-labels: "ingress-ready=true"
  extraPortMappings:
  - containerPort: 80
    hostPort: 80
    protocol: TCP
  - containerPort: 443
    hostPort: 443
    protocol: TCP
  - containerPort: 8000
    hostPort: 8000
    protocol: TCP
containerdConfigPatches:
- |-
  [plugins."io.containerd.grpc.v1.cri".registry.mirrors."localhost:5001"]
    endpoint = ["http://kind-registry:5000"]
EOF

# Connect registry to Kind network
docker network connect kind kind-registry || true

# Document local registry
kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: local-registry-hosting
  namespace: kube-public
data:
  localRegistryHosting.v1: |
    host: "localhost:5001"
    help: "https://kind.sigs.k8s.io/docs/user/local-registry/"
EOF
```

## Step 2: Install prerequisites

### Install Istio (minimal profile)

```bash
# Download istioctl
curl -L https://istio.io/downloadIstio | ISTIO_VERSION=1.20.0 sh -
cd istio-1.20.0

# Install minimal profile for Kind
bin/istioctl install --set profile=minimal -y

# Enable sidecar injection (optional)
kubectl label namespace default istio-injection=enabled

cd ..
```

### Install KEDA

```bash
# Install KEDA (lightweight version)
kubectl apply --server-side -f https://github.com/kedacore/keda/releases/download/v2.13.0/keda-2.13.0.yaml

# Wait for KEDA to be ready
kubectl wait --for=condition=available --timeout=120s \
  deployment/keda-operator -n keda
```

### Install metrics-server (for HPA)

```bash
# Required for KEDA to query metrics
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Patch for Kind (disable TLS verification)
kubectl patch deployment metrics-server -n kube-system --type='json' \
  -p='[{"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-insecure-tls"}]'
```

## Step 3: Build and load images

### Option A: Build locally and load into Kind

```bash
# Build images locally (single platform, no push)
cd percolate
docker build -t localhost:5001/percolate:dev .
cd ..

cd percolate-reading
docker build -t localhost:5001/percolate-reading:dev .
cd ..

# Load images into Kind cluster
kind load docker-image localhost:5001/percolate:dev --name percolate-dev
kind load docker-image localhost:5001/percolate-reading:dev --name percolate-dev
```

### Option B: Use local registry

```bash
# Build and push to local registry
cd percolate
docker build -t localhost:5001/percolate:dev .
docker push localhost:5001/percolate:dev
cd ..

cd percolate-reading
docker build -t localhost:5001/percolate-reading:dev .
docker push localhost:5001/percolate-reading:dev
cd ..
```

## Step 4: Deploy Percolate (minimal resources)

### Create minimal overlay

Create `k8s/overlays/kind/kustomization.yaml`:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: percolate

resources:
- ../../base

# Use local images
images:
- name: percolate/percolate
  newName: localhost:5001/percolate
  newTag: dev
- name: percolate/percolate-reading
  newName: localhost:5001/percolate-reading
  newTag: dev

# Minimal resources for local testing
patches:
# Scale down OpenBao
- target:
    kind: StatefulSet
    name: openbao
  patch: |-
    - op: replace
      path: /spec/replicas
      value: 1
    - op: replace
      path: /spec/template/spec/containers/0/resources/requests/memory
      value: "256Mi"
    - op: replace
      path: /spec/template/spec/containers/0/resources/limits/memory
      value: "512Mi"

# Scale down NATS
- target:
    kind: StatefulSet
    name: nats
  patch: |-
    - op: replace
      path: /spec/replicas
      value: 1

# Scale down Gateway
- target:
    kind: Deployment
    name: gateway
  patch: |-
    - op: replace
      path: /spec/replicas
      value: 1
    - op: replace
      path: /spec/template/spec/containers/0/resources/requests/memory
      value: "256Mi"
    - op: replace
      path: /spec/template/spec/containers/0/resources/limits/memory
      value: "512Mi"

# Use emptyDir instead of PVC for testing
- target:
    kind: StatefulSet
  patch: |-
    - op: remove
      path: /spec/volumeClaimTemplates
    - op: add
      path: /spec/template/spec/volumes
      value:
      - name: data
        emptyDir: {}
```

### Deploy infrastructure

```bash
# Create namespace
kubectl create namespace percolate

# Create S3 secret (use MinIO or skip for local testing)
kubectl create secret generic s3-credentials \
  --namespace percolate \
  --from-literal=endpoint=http://minio.percolate.svc.cluster.local:9000 \
  --from-literal=access_key=minioadmin \
  --from-literal=secret_key=minioadmin

# Deploy infrastructure
kubectl apply -k k8s/overlays/kind/

# Wait for infrastructure to be ready
kubectl wait --for=condition=ready pod -l app=openbao -n percolate --timeout=120s
kubectl wait --for=condition=ready pod -l app=redis -n percolate --timeout=120s
kubectl wait --for=condition=ready pod -l app=nats -n percolate --timeout=120s
```

### Deploy single tier (small only)

```bash
# Deploy small tier with minimal resources
kubectl apply -k k8s/overlays/tiers/small/

# Override with minimal resources
kubectl patch statefulset api-small -n percolate --type='json' \
  -p='[
    {"op": "replace", "path": "/spec/replicas", "value": 1},
    {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/memory", "value": "512Mi"},
    {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory", "value": "1Gi"}
  ]'

kubectl patch statefulset worker-small -n percolate --type='json' \
  -p='[
    {"op": "replace", "path": "/spec/replicas", "value": 1},
    {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/memory", "value": "1Gi"},
    {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory", "value": "2Gi"}
  ]'

# Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app=api -n percolate --timeout=300s
kubectl wait --for=condition=ready pod -l app=worker -n percolate --timeout=300s
```

## Step 5: Access services

### Port-forward to services

```bash
# Gateway (API entrypoint)
kubectl port-forward -n percolate svc/gateway 8000:80 &

# API direct access
kubectl port-forward -n percolate svc/api-small 8001:8000 &

# OpenBao UI
kubectl port-forward -n percolate svc/openbao 8200:8200 &

# NATS monitoring
kubectl port-forward -n percolate svc/nats 8222:8222 &

# Redis CLI
kubectl port-forward -n percolate svc/redis 6379:6379 &
```

### Test API

```bash
# Health check
curl http://localhost:8000/health

# Chat completion (if implemented)
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hello"}],
    "model": "claude-haiku-4-5-20251001"
  }'
```

## Resource monitoring

### Check resource usage

```bash
# Overall cluster resources
kubectl top nodes

# Pod resources in percolate namespace
kubectl top pods -n percolate

# Detailed pod resource requests/limits
kubectl describe nodes | grep -A 5 "Allocated resources"

# Memory usage by pod
kubectl top pods -n percolate --sort-by=memory
```

### Expected resource usage (Kind)

| Component | Replicas | Memory Request | Memory Limit | Actual Usage |
|-----------|----------|----------------|--------------|--------------|
| OpenBao   | 1        | 256Mi          | 512Mi        | ~300Mi       |
| NATS      | 1        | 128Mi          | 256Mi        | ~150Mi       |
| Redis     | 1        | 128Mi          | 256Mi        | ~100Mi       |
| Gateway   | 1        | 256Mi          | 512Mi        | ~200Mi       |
| API       | 1        | 512Mi          | 1Gi          | ~600Mi       |
| Worker    | 0→1      | 1Gi            | 2Gi          | ~1.2Gi       |
| **Total** | **6**    | **~2.3GB**     | **~4.5GB**   | **~2.5GB**   |

## Testing scenarios

### Test 1: Smoke test

```bash
# Run smoke test suite
kubectl apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: smoke-test
  namespace: percolate
spec:
  containers:
  - name: test
    image: curlimages/curl:latest
    command: ["sh", "-c"]
    args:
    - |
      set -e
      echo "Testing gateway health..."
      curl -f http://gateway.percolate.svc.cluster.local/health
      echo "Testing API health..."
      curl -f http://api-small.percolate.svc.cluster.local:8000/health
      echo "All tests passed!"
  restartPolicy: Never
EOF

# Check test results
kubectl logs -n percolate smoke-test
```

### Test 2: Scale worker on NATS message

```bash
# Publish test message to NATS
kubectl run -it --rm nats-pub --image=natsio/nats-box:latest --restart=Never -- \
  nats pub percolate.jobs.small.test '{"test": "message"}'

# Watch worker scale up
kubectl get pods -n percolate -l app=worker -w

# Check KEDA scaler status
kubectl get scaledobjects -n percolate
kubectl describe scaledobject worker-small-scaler -n percolate
```

### Test 3: Memory pressure test

```bash
# Generate load on API
kubectl run -it --rm load-test --image=williamyeh/hey:latest --restart=Never -- \
  -n 1000 -c 10 http://gateway.percolate.svc.cluster.local/health

# Monitor memory during load
watch kubectl top pods -n percolate
```

### Test 4: Pod restart resilience

```bash
# Delete API pod
kubectl delete pod -n percolate -l app=api

# Watch automatic recreation
kubectl get pods -n percolate -l app=api -w

# Verify service continues working
curl http://localhost:8000/health
```

## Debugging

### Check pod logs

```bash
# Gateway logs
kubectl logs -n percolate -l app=gateway -f

# API logs
kubectl logs -n percolate -l app=api -f

# Worker logs
kubectl logs -n percolate -l app=worker -f

# OpenBao logs
kubectl logs -n percolate -l app=openbao -f
```

### Check pod status

```bash
# Get pod details
kubectl describe pod -n percolate -l app=api

# Check events
kubectl get events -n percolate --sort-by='.lastTimestamp'

# Check resource constraints
kubectl describe node | grep -A 10 "Allocated resources"
```

### Access pod shell

```bash
# Exec into API pod
kubectl exec -it -n percolate -l app=api -- /bin/bash

# Exec into worker pod
kubectl exec -it -n percolate -l app=worker -- /bin/bash
```

### Check Istio sidecar injection

```bash
# Verify sidecars are injected
kubectl get pods -n percolate -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[*].name}{"\n"}{end}'

# Expected: Each pod should have 'istio-proxy' container
```

## Cleanup

### Delete Percolate deployment

```bash
# Delete all Percolate resources
kubectl delete namespace percolate

# Or delete specific deployments
kubectl delete -k k8s/overlays/kind/
kubectl delete -k k8s/overlays/tiers/small/
```

### Delete Kind cluster

```bash
# Delete cluster
kind delete cluster --name percolate-dev

# Delete local registry
docker stop kind-registry
docker rm kind-registry
```

## Troubleshooting

### Images not loading

```bash
# Verify images in Kind
docker exec -it percolate-dev-control-plane crictl images | grep percolate

# Reload images
kind load docker-image localhost:5001/percolate:dev --name percolate-dev
```

### Pods stuck in Pending

```bash
# Check resource constraints
kubectl describe pod -n percolate <pod-name>

# Check PVC issues (if using)
kubectl get pvc -n percolate

# Reduce resource requests
kubectl patch statefulset <name> -n percolate --type='json' \
  -p='[{"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/memory", "value": "256Mi"}]'
```

### KEDA not scaling

```bash
# Check KEDA operator logs
kubectl logs -n keda -l app=keda-operator

# Check ScaledObject status
kubectl describe scaledobject -n percolate worker-small-scaler

# Manually trigger scale
kubectl scale statefulset worker-small -n percolate --replicas=1
```

### Istio issues

```bash
# Check Istio installation
istioctl verify-install

# Check sidecar injection
kubectl get namespace percolate -o yaml | grep istio-injection

# Disable Istio for testing
kubectl label namespace percolate istio-injection=disabled --overwrite
kubectl rollout restart deployment -n percolate
```

## Performance tips

### Reduce startup time

1. **Pre-pull images**: Build images before creating cluster
2. **Use local registry**: Faster than loading into Kind
3. **Disable probes temporarily**: Remove liveness/readiness for faster startup
4. **Use smaller base images**: Switch to `alpine` variants if available

### Reduce memory usage

1. **Single replica**: Run only 1 pod per component
2. **EmptyDir volumes**: Avoid PVC overhead for testing
3. **Disable Istio**: Remove sidecar injection (~50MB per pod)
4. **Minimal JVM heap**: Set Java heap limits for NATS/OpenBao

### Speed up development cycle

```bash
# Quick rebuild and reload
docker build -t localhost:5001/percolate:dev percolate/ && \
  kind load docker-image localhost:5001/percolate:dev --name percolate-dev && \
  kubectl rollout restart statefulset api-small -n percolate
```

## Alternative: Lightweight stack (no Istio/KEDA)

For even lighter resource usage, skip Istio and KEDA:

```bash
# Create minimal Kind cluster
kind create cluster --name percolate-minimal

# Deploy only infrastructure (no service mesh)
kubectl apply -f k8s/base/namespace.yaml
kubectl apply -f k8s/base/config.yaml
kubectl apply -f k8s/base/redis-deployment.yaml
kubectl apply -f k8s/base/nats-statefulset.yaml
kubectl apply -f k8s/base/gateway-deployment.yaml

# Deploy single API pod (no StatefulSet)
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  namespace: percolate
spec:
  replicas: 1
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
    spec:
      containers:
      - name: api
        image: localhost:5001/percolate:dev
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
EOF
```

**Memory usage**: ~1.5GB total (vs ~4GB with full stack)

## References

- [Kind documentation](https://kind.sigs.k8s.io/)
- [Kind local registry](https://kind.sigs.k8s.io/docs/user/local-registry/)
- [Istio minimal profile](https://istio.io/latest/docs/setup/additional-setup/config-profiles/)
- [KEDA documentation](https://keda.sh/docs/latest/deploy/)
