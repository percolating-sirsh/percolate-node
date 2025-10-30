#!/bin/bash
set -euo pipefail

# Test topology setup for tenant affinity and scaling validation
# Minimal ~2GB deployment focusing on routing and scaling behavior

CLUSTER_NAME="${CLUSTER_NAME:-test-topology}"
NAMESPACE="percolate-test"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Test Topology Setup${NC}"
echo -e "${BLUE}Tenant Affinity & Scaling Validation${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Create Kind cluster if needed
if ! kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    log_step "Creating Kind cluster..."
    kind create cluster --name ${CLUSTER_NAME}
else
    log_info "Using existing cluster: ${CLUSTER_NAME}"
fi

# Build test images
log_step "Building test images..."

cd images/test-gateway
docker build -t localhost:5001/test-gateway:dev .
cd ../..

cd images/test-api
docker build -t localhost:5001/test-api:dev .
cd ../..

# Load images into Kind
log_step "Loading images into Kind..."
kind load docker-image localhost:5001/test-gateway:dev --name ${CLUSTER_NAME}
kind load docker-image localhost:5001/test-api:dev --name ${CLUSTER_NAME}

# Install Istio (minimal)
if ! kubectl get namespace istio-system &> /dev/null; then
    log_step "Installing Istio (minimal profile)..."
    if ! command -v istioctl &> /dev/null; then
        log_info "Downloading istioctl..."
        curl -L https://istio.io/downloadIstio | ISTIO_VERSION=1.20.0 sh -
        export PATH=$PWD/istio-1.20.0/bin:$PATH
    fi
    istioctl install --set profile=minimal -y
else
    log_info "Istio already installed"
fi

# Install KEDA
if ! kubectl get namespace keda &> /dev/null; then
    log_step "Installing KEDA..."
    kubectl apply -f https://github.com/kedacore/keda/releases/download/v2.13.0/keda-2.13.0.yaml
    kubectl wait --for=condition=available --timeout=120s deployment/keda-operator -n keda || true
else
    log_info "KEDA already installed"
fi

# Create namespace
log_step "Creating namespace..."
kubectl create namespace ${NAMESPACE} 2>/dev/null || true
kubectl label namespace ${NAMESPACE} istio-injection=enabled --overwrite

# Deploy Prometheus
log_step "Deploying Prometheus..."
kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
  namespace: ${NAMESPACE}
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
    scrape_configs:
    - job_name: 'kubernetes-pods'
      kubernetes_sd_configs:
      - role: pod
        namespaces:
          names:
          - ${NAMESPACE}
      relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
        action: replace
        target_label: __metrics_path__
        regex: (.+)
      - source_labels: [__address__, __meta_kubernetes_pod_annotation_prometheus_io_port]
        action: replace
        regex: ([^:]+)(?::\d+)?;(\d+)
        replacement: \$1:\$2
        target_label: __address__
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prometheus
  namespace: ${NAMESPACE}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: prometheus
  template:
    metadata:
      labels:
        app: prometheus
    spec:
      containers:
      - name: prometheus
        image: prom/prometheus:latest
        args:
        - '--config.file=/etc/prometheus/prometheus.yml'
        - '--storage.tsdb.path=/prometheus'
        ports:
        - containerPort: 9090
        volumeMounts:
        - name: config
          mountPath: /etc/prometheus
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 200m
            memory: 512Mi
      volumes:
      - name: config
        configMap:
          name: prometheus-config
---
apiVersion: v1
kind: Service
metadata:
  name: prometheus
  namespace: ${NAMESPACE}
spec:
  ports:
  - port: 9090
    targetPort: 9090
  selector:
    app: prometheus
EOF

# Deploy test gateway
log_step "Deploying test gateway..."
kubectl apply -f - <<EOF
apiVersion: v1
kind: Service
metadata:
  name: test-gateway
  namespace: ${NAMESPACE}
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
  namespace: ${NAMESPACE}
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
        imagePullPolicy: Never
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
          value: "http://test-api-small.${NAMESPACE}.svc.cluster.local:8000"
EOF

# Deploy test API
log_step "Deploying test API..."
kubectl apply -f - <<EOF
apiVersion: v1
kind: Service
metadata:
  name: test-api-small
  namespace: ${NAMESPACE}
  labels:
    app: test-api
    tier: small
spec:
  clusterIP: None
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
  namespace: ${NAMESPACE}
spec:
  serviceName: test-api-small
  replicas: 0
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
        imagePullPolicy: Never
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
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
EOF

# Deploy Istio routing
log_step "Deploying Istio routing rules..."
kubectl apply -f - <<EOF
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: test-api-routing
  namespace: ${NAMESPACE}
spec:
  hosts:
  - test-api-small.${NAMESPACE}.svc.cluster.local
  http:
  - route:
    - destination:
        host: test-api-small.${NAMESPACE}.svc.cluster.local
        port:
          number: 8000
---
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: test-api-affinity
  namespace: ${NAMESPACE}
spec:
  host: test-api-small.${NAMESPACE}.svc.cluster.local
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
EOF

# Deploy KEDA scaler
log_step "Deploying KEDA scaler..."
kubectl apply -f - <<EOF
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: test-api-small-scaler
  namespace: ${NAMESPACE}
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
      serverAddress: http://prometheus.${NAMESPACE}.svc.cluster.local:9090
      metricName: test_active_tenants
      threshold: "2"
      query: |
        sum(test_active_tenants{tier="small"})
EOF

# Wait for gateway
log_step "Waiting for gateway to be ready..."
kubectl wait --for=condition=ready pod -l app=test-gateway -n ${NAMESPACE} --timeout=120s || log_info "Gateway may not be ready yet"

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Test Topology Deployed!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

log_info "Resource usage:"
kubectl top pods -n ${NAMESPACE} 2>/dev/null || log_info "(metrics-server not available)"

echo ""
log_info "Access:"
echo "  kubectl port-forward -n ${NAMESPACE} svc/test-gateway 8080:8080"
echo ""

log_info "Test commands:"
echo "  # Check current state"
echo "  kubectl get pods -n ${NAMESPACE}"
echo ""
echo "  # Simulate tenant A for 2 minutes"
echo "  curl http://localhost:8080/simulate/tenant-a?duration=120"
echo ""
echo "  # Watch scaling"
echo "  watch kubectl get pods -n ${NAMESPACE}"
echo ""
echo "  # Check metrics"
echo "  curl http://localhost:8080/metrics"
echo ""
echo "  # Check KEDA status"
echo "  kubectl get scaledobjects -n ${NAMESPACE}"
echo ""

log_info "Cleanup:"
echo "  kubectl delete namespace ${NAMESPACE}"
echo "  kind delete cluster --name ${CLUSTER_NAME}"
