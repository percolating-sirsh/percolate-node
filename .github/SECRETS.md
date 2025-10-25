# GitHub Secrets Configuration

This document lists all secrets required for CI/CD workflows.

## Required secrets

### PyPI publishing (percolate-rocks)

**`PYPI_API_TOKEN`**
- **Purpose**: Publish Python wheels to PyPI (production)
- **Workflow**: `build-rocks.yml`
- **How to create**:
  1. Go to https://pypi.org/manage/account/token/
  2. Create a new API token
  3. Scope: Project-specific for `percolate-rocks`
  4. Add to GitHub: Settings → Secrets → Actions → New repository secret

### Docker registry (percolate, percolate-reading)

**No additional secrets required**

The workflows use `GITHUB_TOKEN` (automatically provided) for:
- Pushing to GitHub Container Registry (GHCR)
- Creating GitHub releases
- Reading repository metadata

**Permissions required** (already configured in workflows):
```yaml
permissions:
  contents: read
  packages: write
  id-token: write
```

## Optional secrets (for future use)

### Kubernetes manifest updates

**`K8S_MANIFEST_PAT`**
- **Purpose**: Update Kubernetes manifests in separate repo
- **Workflow**: `release-percolate.yml`, `release-reading.yml`
- **How to create**:
  1. Go to GitHub Settings → Developer settings → Personal access tokens
  2. Create fine-grained token with:
     - Repository access: `percolation-labs/percolate-cloud`
     - Permissions: `contents: write`
  3. Expiration: Set appropriate expiry
  4. Add to GitHub secrets

### Cosign signing

**No secrets required** - uses keyless signing with GitHub OIDC

The workflows use GitHub's built-in OIDC provider for signing:
```yaml
permissions:
  id-token: write  # For OIDC token
  packages: write  # For writing signatures
```

## How to add secrets

1. Navigate to repository: https://github.com/percolation-labs/percolate
2. Go to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add name and value
5. Click **Add secret**

## Testing secrets

To verify secrets are working:

1. **PyPI token**:
   ```bash
   # Push an RC tag
   git tag percolate-rocks-v0.1.0-rc1
   git push --tags

   # Check workflow: https://github.com/percolation-labs/percolate/actions
   # Should publish to: https://pypi.org/project/percolate-rocks/
   ```

2. **Docker builds**:
   ```bash
   # Push an RC tag
   git tag percolate-v0.1.0-rc1
   git push --tags

   # Check workflow and GHCR package
   # Should appear at: https://github.com/percolation-labs/percolate/pkgs/container/percolate
   ```

## Security notes

- Never commit secrets to the repository
- Rotate tokens periodically
- Use minimal scope for tokens
- For PyPI, prefer project-scoped tokens over account-level
- For GitHub, prefer fine-grained PATs over classic tokens
- Monitor secret usage in audit logs
