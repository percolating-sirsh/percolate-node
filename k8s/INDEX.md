# Kubernetes Documentation Index

## Overview Documents

- **[README.md](README.md)** - Main entry point, quick start, deployment options
- **[system.md](system.md)** - Complete architecture documentation (database-first design)

## Testing & Development

- **[test-topology.md](test-topology.md)** - Lightweight topology testing (3GB, recommended)
  - Tests: Database-first architecture, tenant affinity, KEDA scaling
  - Includes: [test-topology/](test-topology/) directory with manifests and Docker images
  - Observability: [test-topology/OBSERVABILITY.md](test-topology/OBSERVABILITY.md)

- **[kind.md](kind.md)** - Full stack local testing (5GB)
  - Complete production-like deployment on Kind
  - Includes: OpenBao, NATS, Redis, Gateway, multiple tiers

## Deployment

- **[install.sh](install.sh)** - Automated production cluster installation
- **[kind-setup.sh](kind-setup.sh)** - Automated Kind cluster setup (full stack)

## GitOps

- **[argocd/README.md](argocd/README.md)** - Argo CD setup and configuration
- **[argocd/applicationset.yaml](argocd/applicationset.yaml)** - ApplicationSet for tier deployment

## Manifest Structure

```
k8s/
├── base/              # Core infrastructure manifests
├── components/        # Reusable component templates
│   ├── api/          # Database node templates
│   └── worker/       # Worker node templates
├── overlays/         # Environment-specific overlays
│   ├── tiers/       # Tier-specific patches (small, medium, large)
│   └── kind/        # Kind-specific minimal resources
└── test-topology/   # Topology testing environment
    ├── images/      # Test Docker images
    └── manifests/   # Test manifests
```

## Archive

Old documentation versions (for reference only):
- **[archive/system.md](archive/system.md)** - Previous architecture (gateway-centric)
- **[archive/test-topology.md](archive/test-topology.md)** - Previous test setup
- **[archive/testing-plan.md](archive/testing-plan.md)** - Original test plan

## Quick Navigation

**For local development:**
1. Start with [test-topology.md](test-topology.md) for quick topology validation
2. Use [kind.md](kind.md) for full stack testing

**For production deployment:**
1. Read [system.md](system.md) for architecture understanding
2. Use [install.sh](install.sh) or [argocd/README.md](argocd/README.md) for deployment

**For understanding observability:**
1. Read [test-topology/OBSERVABILITY.md](test-topology/OBSERVABILITY.md) for metrics architecture
2. Shows OpenTelemetry + Prometheus + KEDA integration
