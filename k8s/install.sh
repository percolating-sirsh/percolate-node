#!/bin/bash
set -euo pipefail

# Percolate Kubernetes cluster installation script
# This script installs all prerequisites and deploys Percolate using GitOps

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAMESPACE="${PERCOLATE_NAMESPACE:-percolate}"
ARGOCD_NAMESPACE="argocd"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl not found. Please install kubectl."
        exit 1
    fi

    # Check cluster connectivity
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster. Check your kubeconfig."
        exit 1
    fi

    log_info "Prerequisites check passed."
}

install_istio() {
    log_info "Checking Istio installation..."

    if kubectl get namespace istio-system &> /dev/null; then
        log_info "Istio already installed."
        return 0
    fi

    log_warn "Istio not found. Install Istio before continuing:"
    log_warn "  curl -L https://istio.io/downloadIstio | sh -"
    log_warn "  cd istio-*/bin"
    log_warn "  ./istioctl install --set profile=default -y"
    read -p "Press enter to continue once Istio is installed..."
}

install_keda() {
    log_info "Checking KEDA installation..."

    if kubectl get namespace keda &> /dev/null; then
        log_info "KEDA already installed."
        return 0
    fi

    log_warn "KEDA not found. Installing KEDA..."
    kubectl apply --server-side -f https://github.com/kedacore/keda/releases/download/v2.13.0/keda-2.13.0.yaml

    log_info "Waiting for KEDA to be ready..."
    kubectl wait --for=condition=available --timeout=300s \
        deployment/keda-operator -n keda || true

    log_info "KEDA installed successfully."
}

install_argocd() {
    log_info "Installing Argo CD..."

    kubectl apply -k "${SCRIPT_DIR}/argocd/"

    log_info "Waiting for Argo CD to be ready..."
    kubectl wait --for=condition=available --timeout=300s \
        deployment/argocd-server -n ${ARGOCD_NAMESPACE}

    log_info "Argo CD installed successfully."
}

get_argocd_password() {
    log_info "Retrieving Argo CD admin password..."

    PASSWORD=$(kubectl -n ${ARGOCD_NAMESPACE} get secret argocd-initial-admin-secret \
        -o jsonpath="{.data.password}" | base64 -d)

    echo ""
    log_info "Argo CD Credentials:"
    echo "  URL: https://localhost:8080 (after port-forward)"
    echo "  Username: admin"
    echo "  Password: ${PASSWORD}"
    echo ""
}

port_forward_argocd() {
    log_info "Setting up port-forward to Argo CD..."
    echo ""
    log_info "Run the following command in a separate terminal:"
    echo "  kubectl port-forward svc/argocd-server -n ${ARGOCD_NAMESPACE} 8080:443"
    echo ""
    log_info "Then access Argo CD at: https://localhost:8080"
}

create_s3_secret() {
    log_info "Creating S3 credentials secret..."

    if kubectl get secret s3-credentials -n ${NAMESPACE} &> /dev/null; then
        log_info "S3 credentials secret already exists."
        return 0
    fi

    log_warn "S3 credentials not found. Please provide S3 configuration:"

    read -p "S3 Endpoint (e.g., https://s3.hetzner.cloud): " S3_ENDPOINT
    read -p "S3 Access Key: " S3_ACCESS_KEY
    read -sp "S3 Secret Key: " S3_SECRET_KEY
    echo ""

    kubectl create secret generic s3-credentials \
        --namespace ${NAMESPACE} \
        --from-literal=endpoint="${S3_ENDPOINT}" \
        --from-literal=access_key="${S3_ACCESS_KEY}" \
        --from-literal=secret_key="${S3_SECRET_KEY}"

    log_info "S3 credentials secret created."
}

verify_applications() {
    log_info "Verifying Argo CD Applications..."

    sleep 10  # Give ApplicationSets time to generate Applications

    APPS=$(kubectl get applications -n ${ARGOCD_NAMESPACE} -l app=percolate -o name | wc -l)

    if [ "$APPS" -gt 0 ]; then
        log_info "Found ${APPS} Percolate applications:"
        kubectl get applications -n ${ARGOCD_NAMESPACE} -l app=percolate
    else
        log_warn "No applications found yet. Check ApplicationSets:"
        kubectl get applicationsets -n ${ARGOCD_NAMESPACE}
    fi
}

main() {
    echo "=========================================="
    echo "Percolate Kubernetes Installation"
    echo "=========================================="
    echo ""

    check_prerequisites
    install_istio
    install_keda
    install_argocd
    get_argocd_password
    create_s3_secret
    verify_applications

    echo ""
    log_info "Installation complete!"
    echo ""
    log_info "Next steps:"
    echo "  1. Port-forward to Argo CD:"
    echo "     kubectl port-forward svc/argocd-server -n ${ARGOCD_NAMESPACE} 8080:443"
    echo ""
    echo "  2. Access Argo CD UI at https://localhost:8080"
    echo ""
    echo "  3. Monitor application sync status:"
    echo "     kubectl get applications -n ${ARGOCD_NAMESPACE} -w"
    echo ""
    echo "  4. Check deployed resources:"
    echo "     kubectl get all -n ${NAMESPACE}"
    echo ""
}

main "$@"
