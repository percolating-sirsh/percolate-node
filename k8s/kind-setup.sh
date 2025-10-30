#!/bin/bash
set -euo pipefail

# Percolate Kind (Kubernetes in Docker) setup script
# Creates local test cluster with minimal resources

CLUSTER_NAME="${CLUSTER_NAME:-percolate-dev}"
REGISTRY_NAME="kind-registry"
REGISTRY_PORT="5001"
NAMESPACE="percolate"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_step "Checking prerequisites..."

    if ! command -v kind &> /dev/null; then
        log_error "kind not found. Install with: brew install kind"
        exit 1
    fi

    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl not found. Install with: brew install kubectl"
        exit 1
    fi

    if ! command -v docker &> /dev/null; then
        log_error "docker not found. Install Docker Desktop."
        exit 1
    fi

    log_info "Prerequisites OK"
}

create_local_registry() {
    log_step "Creating local Docker registry..."

    if docker ps -a | grep -q ${REGISTRY_NAME}; then
        log_info "Local registry already exists"
        docker start ${REGISTRY_NAME} 2>/dev/null || true
    else
        docker run -d --restart=always \
            -p ${REGISTRY_PORT}:5000 \
            --name ${REGISTRY_NAME} \
            registry:2
        log_info "Local registry created at localhost:${REGISTRY_PORT}"
    fi
}

create_kind_cluster() {
    log_step "Creating Kind cluster '${CLUSTER_NAME}'..."

    if kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
        log_warn "Cluster '${CLUSTER_NAME}' already exists"
        read -p "Delete and recreate? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            kind delete cluster --name ${CLUSTER_NAME}
        else
            log_info "Using existing cluster"
            kubectl cluster-info --context kind-${CLUSTER_NAME}
            return 0
        fi
    fi

    cat <<EOF | kind create cluster --name ${CLUSTER_NAME} --config=-
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
  [plugins."io.containerd.grpc.v1.cri".registry.mirrors."localhost:${REGISTRY_PORT}"]
    endpoint = ["http://${REGISTRY_NAME}:5000"]
EOF

    # Connect registry to Kind network
    docker network connect kind ${REGISTRY_NAME} 2>/dev/null || true

    # Document local registry
    kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: local-registry-hosting
  namespace: kube-public
data:
  localRegistryHosting.v1: |
    host: "localhost:${REGISTRY_PORT}"
    help: "https://kind.sigs.k8s.io/docs/user/local-registry/"
EOF

    log_info "Cluster created successfully"
    kubectl cluster-info --context kind-${CLUSTER_NAME}
}

install_istio() {
    log_step "Installing Istio (minimal profile)..."

    if kubectl get namespace istio-system &> /dev/null; then
        log_info "Istio already installed"
        return 0
    fi

    if ! command -v istioctl &> /dev/null; then
        log_warn "istioctl not found. Downloading..."
        curl -L https://istio.io/downloadIstio | ISTIO_VERSION=1.20.0 sh -
        export PATH=$PWD/istio-1.20.0/bin:$PATH
    fi

    istioctl install --set profile=minimal -y
    log_info "Istio installed"
}

install_keda() {
    log_step "Installing KEDA..."

    if kubectl get namespace keda &> /dev/null; then
        log_info "KEDA already installed"
        return 0
    fi

    kubectl apply --server-side -f https://github.com/kedacore/keda/releases/download/v2.13.0/keda-2.13.0.yaml

    log_info "Waiting for KEDA to be ready..."
    kubectl wait --for=condition=available --timeout=120s \
        deployment/keda-operator -n keda || log_warn "KEDA not ready yet"

    log_info "KEDA installed"
}

install_metrics_server() {
    log_step "Installing metrics-server..."

    if kubectl get deployment metrics-server -n kube-system &> /dev/null; then
        log_info "metrics-server already installed"
        return 0
    fi

    kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

    # Patch for Kind (disable TLS verification)
    kubectl patch deployment metrics-server -n kube-system --type='json' \
        -p='[{"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-insecure-tls"}]'

    log_info "metrics-server installed"
}

build_and_load_images() {
    log_step "Building and loading Docker images..."

    # Build percolate
    log_info "Building percolate..."
    docker build -t localhost:${REGISTRY_PORT}/percolate:dev percolate/
    docker push localhost:${REGISTRY_PORT}/percolate:dev

    # Build percolate-reading
    log_info "Building percolate-reading..."
    docker build -t localhost:${REGISTRY_PORT}/percolate-reading:dev percolate-reading/
    docker push localhost:${REGISTRY_PORT}/percolate-reading:dev

    log_info "Images built and pushed to local registry"
}

verify_kind_overlay() {
    log_step "Verifying Kind overlay exists..."

    if [ ! -f k8s/overlays/kind/kustomization.yaml ]; then
        log_error "Kind overlay not found at k8s/overlays/kind/kustomization.yaml"
        log_error "This file should be part of the repository"
        exit 1
    fi

    log_info "Kind overlay verified"
}

deploy_percolate() {
    log_step "Deploying Percolate (infrastructure + small tier)..."

    # Create namespace
    kubectl create namespace ${NAMESPACE} 2>/dev/null || true

    # Create S3 secret (placeholder)
    kubectl create secret generic s3-credentials \
        --namespace ${NAMESPACE} \
        --from-literal=endpoint=http://minio.${NAMESPACE}.svc.cluster.local:9000 \
        --from-literal=access_key=minioadmin \
        --from-literal=secret_key=minioadmin \
        --dry-run=client -o yaml | kubectl apply -f -

    # Deploy everything with Kind overlay (infrastructure + small tier)
    kubectl apply -k k8s/overlays/kind/

    log_info "Waiting for infrastructure pods..."
    sleep 10

    kubectl wait --for=condition=ready pod -l app=redis -n ${NAMESPACE} --timeout=120s || log_warn "Redis not ready"

    log_info "Waiting for API pod..."
    kubectl wait --for=condition=ready pod -l app=api -n ${NAMESPACE} --timeout=300s || log_warn "API not ready"

    log_info "Deployment complete"
}

verify_deployment() {
    log_step "Verifying deployment..."

    log_info "Pod status:"
    kubectl get pods -n ${NAMESPACE}

    log_info ""
    log_info "Resource usage:"
    kubectl top pods -n ${NAMESPACE} 2>/dev/null || log_warn "metrics-server not ready yet"

    log_info ""
    log_info "Replica counts:"
    echo "  API: $(kubectl get statefulset api-small -n ${NAMESPACE} -o jsonpath='{.spec.replicas}')"
    echo "  Worker: $(kubectl get statefulset worker-small -n ${NAMESPACE} -o jsonpath='{.spec.replicas}')"
}

setup_port_forwards() {
    log_step "Setting up port-forwards..."

    # Kill existing port-forwards
    pkill -f "kubectl port-forward" 2>/dev/null || true

    log_info "Port-forwards (run in background):"
    echo "  Gateway:  kubectl port-forward -n ${NAMESPACE} svc/gateway 8000:80"
    echo "  API:      kubectl port-forward -n ${NAMESPACE} svc/api-small 8001:8000"
    echo "  Redis:    kubectl port-forward -n ${NAMESPACE} svc/redis 6379:6379"

    # Start port-forwards in background
    kubectl port-forward -n ${NAMESPACE} svc/gateway 8000:80 > /dev/null 2>&1 &
    kubectl port-forward -n ${NAMESPACE} svc/api-small 8001:8000 > /dev/null 2>&1 &

    sleep 2
    log_info "Port-forwards started"
}

show_summary() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Kind Cluster Setup Complete!${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    log_info "Cluster: ${CLUSTER_NAME}"
    log_info "Namespace: ${NAMESPACE}"
    log_info "Registry: localhost:${REGISTRY_PORT}"
    echo ""

    log_info "Access services:"
    echo "  Gateway:  http://localhost:8000"
    echo "  API:      http://localhost:8001"
    echo ""

    log_info "Test API:"
    echo "  curl http://localhost:8000/health"
    echo ""

    log_info "View resources:"
    echo "  kubectl get pods -n ${NAMESPACE}"
    echo "  kubectl top pods -n ${NAMESPACE}"
    echo "  kubectl logs -n ${NAMESPACE} -l app=api -f"
    echo ""

    log_info "Cleanup:"
    echo "  kind delete cluster --name ${CLUSTER_NAME}"
    echo "  docker stop ${REGISTRY_NAME} && docker rm ${REGISTRY_NAME}"
    echo ""
}

main() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Percolate Kind Setup${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    check_prerequisites
    create_local_registry
    create_kind_cluster
    install_metrics_server

    # Optional: Install Istio and KEDA
    read -p "Install Istio? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        install_istio
    fi

    read -p "Install KEDA? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        install_keda
    fi

    build_and_load_images
    verify_kind_overlay
    deploy_percolate
    verify_deployment
    setup_port_forwards
    show_summary

    log_info "Setup complete!"
}

main "$@"
