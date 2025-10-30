# Argo CD installation

Argo CD installation manifests for GitOps deployment of Percolate infrastructure and applications.

## Quick start

### Install Argo CD

```bash
# Apply Argo CD installation
kubectl apply -k k8s/argocd/

# Wait for Argo CD to be ready
kubectl wait --for=condition=available --timeout=300s \
  deployment/argocd-server -n argocd

# Get initial admin password
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d
```

### Access Argo CD UI

**Option 1: Port forward**
```bash
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Open https://localhost:8080
# Username: admin
# Password: (from above command)
```

**Option 2: LoadBalancer (if available)**
```bash
kubectl get svc argocd-server-lb -n argocd

# Access via LoadBalancer external IP
```

**Option 3: Ingress (recommended for production)**
```bash
# Apply ingress manifest (create separately)
kubectl apply -f argocd-ingress.yaml
```

### Change admin password

```bash
# Login via CLI
argocd login localhost:8080

# Change password
argocd account update-password
```

## ApplicationSets

After Argo CD is installed, the ApplicationSets will automatically deploy:

1. **percolate-infrastructure**: Base infrastructure (NATS, Redis, OpenBao, Gateway)
2. **percolate-tiers**: API and Worker StatefulSets for all tiers (small, medium, large)
3. **percolate-keda-scalers**: KEDA ScaledObjects for autoscaling

### Verify ApplicationSets

```bash
# List ApplicationSets
kubectl get applicationsets -n argocd

# List generated Applications
kubectl get applications -n argocd

# Check sync status
argocd app list
```

## Configuration

### Repository credentials

For private repositories, add credentials:

```bash
# Via CLI
argocd repo add https://github.com/percolate/percolate \
  --username <username> \
  --password <token>

# Via declarative YAML
kubectl apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: percolate-repo
  namespace: argocd
  labels:
    argocd.argoproj.io/secret-type: repository
stringData:
  type: git
  url: https://github.com/percolate/percolate
  username: <username>
  password: <token>
EOF
```

### Sync waves

Applications use sync waves to control deployment order:

- **Wave 0**: Namespace, ConfigMaps, Secrets
- **Wave 1**: Infrastructure (OpenBao, NATS, Redis)
- **Wave 2**: Gateway, API, Worker
- **Wave 3**: KEDA ScaledObjects

### Ignore differences

The ApplicationSets already configure ignoreDifferences for:
- `StatefulSet.spec.replicas` (managed by KEDA)

## Manual sync

```bash
# Sync infrastructure
argocd app sync percolate-infra

# Sync specific tier
argocd app sync percolate-small

# Sync all applications
argocd app sync -l app=percolate

# Force refresh
argocd app get percolate-infra --refresh
```

## Troubleshooting

### Applications stuck in OutOfSync

```bash
# Check application status
argocd app get percolate-infra

# View diff
argocd app diff percolate-infra

# Manual sync with prune
argocd app sync percolate-infra --prune
```

### ApplicationSet not generating Applications

```bash
# Check ApplicationSet status
kubectl get applicationset percolate-tiers -n argocd -o yaml

# Check controller logs
kubectl logs -n argocd deployment/argocd-applicationset-controller
```

### Sync fails with permission errors

```bash
# Verify service account permissions
kubectl auth can-i create deployment --as=system:serviceaccount:argocd:argocd-application-controller

# Check RBAC in argocd-rbac-cm ConfigMap
kubectl get configmap argocd-rbac-cm -n argocd -o yaml
```

## Production recommendations

### TLS certificates

```bash
# Option 1: Let's Encrypt via cert-manager
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: argocd-server-tls
  namespace: argocd
spec:
  secretName: argocd-server-tls
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
  - argocd.percolate.io
EOF
```

### High availability

For production, increase replica counts:

```yaml
# Patch argocd-server
kubectl scale deployment argocd-server -n argocd --replicas=3

# Patch argocd-repo-server
kubectl scale deployment argocd-repo-server -n argocd --replicas=3

# Patch argocd-applicationset-controller
kubectl scale deployment argocd-applicationset-controller -n argocd --replicas=2
```

### Monitoring

```bash
# Argo CD exports Prometheus metrics on port 8082
kubectl port-forward svc/argocd-metrics -n argocd 8082:8082

# Check metrics
curl http://localhost:8082/metrics
```

### Backup

```bash
# Backup Argo CD configuration
kubectl get applications,applicationsets -n argocd -o yaml > argocd-backup.yaml

# Backup secrets (encrypt before storing!)
kubectl get secrets -n argocd -o yaml > argocd-secrets.yaml
```

## References

- [Argo CD documentation](https://argo-cd.readthedocs.io/)
- [ApplicationSet documentation](https://argo-cd.readthedocs.io/en/stable/user-guide/application-set/)
- [Argo CD best practices](https://argo-cd.readthedocs.io/en/stable/user-guide/best_practices/)
