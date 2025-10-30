# Percolate Kubernetes manifests

Kubernetes deployment manifests for Percolate multi-tenant system using Kustomize overlays and Argo CD ApplicationSets.

## Architecture

- **Shared resource pool**: All tenants share namespaces, pods, nodes
- **Application-layer isolation**: Tenant data isolated via separate RocksDB instances
- **Tiered capacity**: API pods (1-4GB) for reads, Worker pods (8-32GB) for file processing
- **DRY with Kustomize**: Single source of truth with tier-specific overlays
- **GitOps with Argo CD**: Automated deployment via ApplicationSets

See [system.md](system.md) for detailed architecture and [testing-plan.md](testing-plan.md) for test strategy.

## Prerequisites

- Kubernetes cluster 1.27+ (tested on 1.29)
- kubectl configured with cluster access
- Storage class `regional-ssd` available (or modify in manifests)
- Istio service mesh installed ([installation guide](https://istio.io/latest/docs/setup/install/))
- KEDA installed ([installation guide](https://keda.sh/docs/latest/deploy/))
- Cert-manager (optional, for TLS): `kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml`

## Directory structure

```
k8s/
├── base/                          # Core infrastructure (SoT)
│   ├── namespace.yaml
│   ├── config.yaml               # ConfigMap for app settings
│   ├── openbao-statefulset.yaml
│   ├── redis-deployment.yaml
│   ├── nats-statefulset.yaml
│   ├── otel-collector.yaml
│   ├── gateway-deployment.yaml
│   ├── istio-config.yaml
│   └── keda-scaledobjects.yaml
├── components/                    # Reusable component templates
│   ├── api/
│   │   ├── statefulset.yaml      # Base API StatefulSet
│   │   └── kustomization.yaml
│   └── worker/
│       ├── statefulset.yaml      # Base Worker StatefulSet
│       └── kustomization.yaml
├── overlays/
│   ├── tiers/                    # Tier-specific overlays
│   │   ├── small/
│   │   │   └── kustomization.yaml  # Patches for small tier
│   │   ├── medium/
│   │   │   └── kustomization.yaml  # Patches for medium tier
│   │   └── large/
│   │       └── kustomization.yaml  # Patches for large tier
│   ├── dev/
│   │   └── kustomization.yaml    # Development overrides
│   ├── staging/
│   │   └── kustomization.yaml    # Staging overrides
│   └── production/
│       └── kustomization.yaml    # Production overrides
└── argocd/
    ├── install.yaml              # Argo CD installation
    ├── kustomization.yaml        # Argo CD Kustomize config
    ├── applicationset.yaml       # ApplicationSets for Percolate
    ├── ingress.yaml              # Argo CD ingress (optional)
    └── README.md                 # Argo CD setup guide
```

## Tier specifications

Generated from single source with Kustomize patches:

| Tier   | API CPU | API RAM | API Storage | Worker CPU | Worker RAM | Worker Storage |
|--------|---------|---------|-------------|------------|------------|----------------|
| Small  | 1 core  | 1GB     | 50GB        | 4 cores    | 8GB        | 50GB           |
| Medium | 2 cores | 2GB     | 100GB       | 8 cores    | 16GB       | 100GB          |
| Large  | 4 cores | 4GB     | 200GB       | 16 cores   | 32GB       | 200GB          |

## Quick start

### Local testing with Kind

For local development and testing on your laptop:

```bash
# Create Kind cluster with minimal resources (~5GB RAM)
./k8s/kind-setup.sh

# This will:
# - Create Kind cluster with local registry
# - Install Istio (minimal profile) and KEDA
# - Build and load images locally
# - Deploy single tier with reduced resources
# - Set up port-forwards to services
```

**Access services**:
- Gateway: http://localhost:8000
- API: http://localhost:8001

See [KIND.md](KIND.md) for detailed local testing guide, resource tuning, and troubleshooting.

### Option 0: Automated installation (production cluster)

```bash
# Run the installation script
./k8s/install.sh

# This will:
# - Check prerequisites (kubectl, cluster access)
# - Install Istio (if not present)
# - Install KEDA
# - Install Argo CD
# - Create S3 credentials secret
# - Deploy all Percolate components via GitOps
```

### Option 1: Manual deployment with Kustomize

```bash
# 1. Deploy infrastructure
kubectl apply -k k8s/base/

# 2. Deploy all tiers
kubectl apply -k k8s/overlays/tiers/small/
kubectl apply -k k8s/overlays/tiers/medium/
kubectl apply -k k8s/overlays/tiers/large/
```

### Option 2: GitOps with Argo CD (recommended)

```bash
# 1. Install Argo CD
kubectl apply -k k8s/argocd/

# 2. Wait for Argo CD to be ready
kubectl wait --for=condition=available --timeout=300s \
  deployment/argocd-server -n argocd

# 3. Get initial admin password
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d

# 4. Access Argo CD UI
kubectl port-forward svc/argocd-server -n argocd 8080:443
# Open https://localhost:8080

# The ApplicationSets will automatically:
# - Deploy infrastructure (percolate-infra)
# - Deploy all tiers (percolate-small, percolate-medium, percolate-large)
# - Configure KEDA scalers for each tier
```

See [argocd/README.md](argocd/README.md) for detailed Argo CD setup and configuration.

## Kustomize overlay system

### How it works

1. **Base components** (`k8s/components/`): Template StatefulSets with default values
2. **Tier overlays** (`k8s/overlays/tiers/`): JSON patches for CPU, memory, storage per tier
3. **Environment overlays** (`k8s/overlays/{dev,staging,production}/`): Environment-specific overrides

### Example: Adding a new tier

Create `k8s/overlays/tiers/xlarge/kustomization.yaml`:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: percolate
nameSuffix: -xlarge
commonLabels:
  tier: xlarge

resources:
- ../../../components/api
- ../../../components/worker

patches:
- target:
    kind: StatefulSet
    name: api
  patch: |-
    - op: replace
      path: /spec/template/spec/containers/0/resources/requests/cpu
      value: "8000m"
    - op: replace
      path: /spec/template/spec/containers/0/resources/requests/memory
      value: "8Gi"
    # ... more patches
```

### Preview changes

```bash
# See what will be deployed for small tier
kubectl kustomize k8s/overlays/tiers/small/

# Compare tiers
diff <(kubectl kustomize k8s/overlays/tiers/small/) \
     <(kubectl kustomize k8s/overlays/tiers/medium/)
```

## Argo CD ApplicationSets

### Generator patterns

**Infrastructure ApplicationSet**: Single instance
```yaml
generators:
- list:
    elements:
    - cluster: in-cluster
      environment: production
```

**Tier ApplicationSet**: Matrix generator for all tiers
```yaml
generators:
- matrix:
    generators:
    - list:
        elements:
        - tier: small
        - tier: medium
        - tier: large
    - list:
        elements:
        - cluster: in-cluster
```

### Benefits

1. **DRY**: Define tiers once, generate all Applications
2. **Consistency**: All tiers use same template
3. **Easy expansion**: Add new tier = one list item
4. **Multi-cluster**: Change cluster list to deploy to multiple clusters

### Multi-cluster example

```yaml
generators:
- list:
    elements:
    - cluster: us-east-1
      server: https://k8s-us-east-1.example.com
    - cluster: eu-west-1
      server: https://k8s-eu-west-1.example.com
```

## Configuration management

### Base configuration

Edit `k8s/base/config.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: percolate-config
data:
  log_level: "info"
  default_model: "claude-sonnet-4-5-20250929"
  enable_moments_feed: "true"
```

### Environment-specific overrides

Create `k8s/overlays/production/config-patch.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: percolate-config
data:
  log_level: "error"
  enable_debug_endpoints: "false"
```

Reference in `k8s/overlays/production/kustomization.yaml`:

```yaml
patches:
- path: config-patch.yaml
```

## Secrets management

Create S3 credentials (not in Git):

```bash
kubectl create secret generic s3-credentials \
  --namespace percolate \
  --from-literal=endpoint=https://s3.hetzner.cloud \
  --from-literal=access_key=$S3_ACCESS_KEY \
  --from-literal=secret_key=$S3_SECRET_KEY

# Or use sealed-secrets for GitOps
kubeseal --format yaml < s3-secret.yaml > s3-sealed-secret.yaml
```

## Testing overlays

```bash
# Validate Kustomize build
kubectl kustomize k8s/overlays/tiers/small/ --enable-helm

# Dry-run apply
kubectl apply -k k8s/overlays/tiers/small/ --dry-run=client

# Apply with diff
kubectl diff -k k8s/overlays/tiers/small/
```

## Argo CD best practices

### Sync waves

Add annotations to control deployment order:

```yaml
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "1"  # Deploy after wave 0
```

Example waves:
- Wave 0: Namespace, ConfigMap, Secrets
- Wave 1: Infrastructure (OpenBao, NATS, Redis)
- Wave 2: Application (Gateway, API, Worker)
- Wave 3: KEDA ScaledObjects

### Health checks

Argo CD automatically monitors:
- Pod status
- StatefulSet replicas
- Service endpoints

Custom health check example:

```yaml
metadata:
  annotations:
    argocd.argoproj.io/health-check-timeout: "300"
```

### Ignore differences

Already configured for StatefulSet replicas (managed by KEDA):

```yaml
ignoreDifferences:
- group: apps
  kind: StatefulSet
  jsonPointers:
  - /spec/replicas
```

## Monitoring deployments

### Via Argo CD UI

```bash
# Forward Argo CD UI
kubectl port-forward -n argocd svc/argocd-server 8080:443

# Open https://localhost:8080
```

### Via CLI

```bash
# List applications
argocd app list

# Get application status
argocd app get percolate-small

# Sync application
argocd app sync percolate-small

# View diff
argocd app diff percolate-small
```

### Via kubectl

```bash
# Watch all pods in percolate namespace
kubectl get pods -n percolate -w

# Check StatefulSet status
kubectl get statefulsets -n percolate

# View KEDA scaled objects
kubectl get scaledobjects -n percolate
```

## Scaling configuration

KEDA ScaledObjects generated per tier via ApplicationSet:

| Tier   | API Threshold | Worker Lag | API Max | Worker Max | Cooldown |
|--------|---------------|------------|---------|------------|----------|
| Small  | 5 tenants     | 5 jobs     | 10      | 5          | 300s/600s|
| Medium | 10 tenants    | 5 jobs     | 20      | 10         | 300s/600s|
| Large  | 20 tenants    | 5 jobs     | 30      | 15         | 300s/600s|

## Troubleshooting

### Overlay not applying

```bash
# Check kustomization syntax
kubectl kustomize k8s/overlays/tiers/small/ | kubeval

# Verify patch paths
kubectl kustomize k8s/overlays/tiers/small/ | grep -A 5 "cpu"
```

### Argo CD sync issues

```bash
# Check application status
argocd app get percolate-small

# View sync errors
kubectl get application percolate-small -n argocd -o yaml

# Manual sync with prune
argocd app sync percolate-small --prune
```

### Missing resources

```bash
# Verify ApplicationSet generated all apps
kubectl get applications -n argocd | grep percolate

# Check ApplicationSet status
kubectl get applicationset -n argocd percolate-tiers -o yaml
```

## Advanced: Multi-environment deployment

### Structure

```
k8s/overlays/
├── dev/
│   ├── kustomization.yaml
│   └── patches/
│       ├── replicas.yaml       # Scale down to 1
│       └── resources.yaml      # Reduce requests
├── staging/
│   ├── kustomization.yaml
│   └── patches/
│       ├── ingress.yaml        # staging.percolate.io
│       └── config.yaml         # Staging config
└── production/
    ├── kustomization.yaml
    └── patches/
        ├── ingress.yaml        # api.percolate.io
        ├── replicas.yaml       # Min replicas = 2
        └── topology.yaml       # Multi-AZ spread
```

### Argo CD ApplicationSet for environments

```yaml
generators:
- matrix:
    generators:
    - list:
        elements:
        - environment: dev
          cluster: dev-cluster
        - environment: staging
          cluster: staging-cluster
        - environment: production
          cluster: prod-cluster
    - list:
        elements:
        - tier: small
        - tier: medium
        - tier: large
template:
  metadata:
    name: 'percolate-{{tier}}-{{environment}}'
  spec:
    source:
      path: 'k8s/overlays/{{environment}}'
      kustomize:
        namePrefix: '{{tier}}-'
```

This generates 9 applications:
- percolate-small-dev
- percolate-medium-dev
- percolate-large-dev
- (same for staging and production)

## Docker image builds

Percolate uses multi-platform Docker images hosted on Docker Hub:
- `percolate/percolate` - Main API service
- `percolate/percolate-reading` - Document parsing service

### Building images

**Quick build (both services)**:
```bash
# Build and push both images with version tag
./scripts/build-docker.sh v0.3.2

# Build locally without pushing
PUSH=false ./scripts/build-docker.sh latest
```

**Individual service builds**:
```bash
# Build percolate (main API)
cd percolate
docker buildx build --platform linux/amd64,linux/arm64 \
  -t percolate/percolate:latest \
  -t percolate/percolate:v0.3.2 \
  --push .

# Build percolate-reading
cd percolate-reading
docker buildx build --platform linux/amd64,linux/arm64 \
  -t percolate/percolate-reading:latest \
  -t percolate/percolate-reading:v0.3.2 \
  --push .
```

### Updating Kubernetes manifests

After pushing new images, update the image tags:

**Option 1: Via Kustomize**
```yaml
# k8s/overlays/production/kustomization.yaml
images:
- name: percolate/percolate
  newTag: v0.3.2
- name: percolate/percolate-reading
  newTag: v0.3.2
```

**Option 2: Via kubectl**
```bash
kubectl set image statefulset/api-small \
  api=percolate/percolate:v0.3.2 \
  -n percolate

kubectl set image deployment/gateway \
  gateway=percolate/percolate-reading:v0.3.2 \
  -n percolate
```

**Option 3: Via Argo CD**
```bash
# Argo CD will automatically sync if using image updater
# Or manually trigger sync
argocd app sync percolate-small
```

See [DOCKER_BUILD.md](../DOCKER_BUILD.md) for detailed build documentation.

## References

- [Kustomize documentation](https://kustomize.io/)
- [Argo CD ApplicationSet](https://argo-cd.readthedocs.io/en/stable/user-guide/application-set/)
- [KEDA documentation](https://keda.sh/)
- [Istio traffic management](https://istio.io/latest/docs/concepts/traffic-management/)
- [Docker Buildx](https://docs.docker.com/buildx/working-with-buildx/)
- [Percolate Docker Hub](https://hub.docker.com/u/percolationlabs)
