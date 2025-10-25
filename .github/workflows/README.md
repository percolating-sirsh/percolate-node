# GitHub Actions workflows

This directory contains CI/CD workflows for the Percolation monorepo.

## Workflows

### Build workflows (RC tags)

Triggered by `{project}-v*-rc*` tags:

- **`build-rocks.yml`** - Build Python wheels for percolate-rocks, publish to Test PyPI
- **`build-reading.yml`** - Build Docker images for percolate-reading, push to GHCR with CalVer tags
- **`build-percolate.yml`** - Build Docker images for percolate, push to GHCR with CalVer tags

### Release workflows (production tags)

Triggered by `{project}-v*` tags (no RC suffix):

- **`release-rocks.yml`** - Promote percolate-rocks to production PyPI, sign with Sigstore
- **`release-reading.yml`** - Retag percolate-reading images, update K8s manifests (TODO)
- **`release-percolate.yml`** - Retag percolate images, update K8s manifests (TODO)

## Status

### ✅ Fully implemented

- **percolate-rocks build:** Complete wheel building and Test PyPI publishing
- **percolate-rocks release:** Complete PyPI publishing with Sigstore signing
- **Docker builds:** Complete multi-platform Docker builds with Trivy scanning

### ⚠️ Partially implemented (TODO)

- **Docker releases:** Retagging logic needs implementation (currently placeholder)
- **Cosign signing:** Docker image signing not yet implemented
- **SBOM generation:** Docker SBOM generation not yet implemented
- **K8s manifest updates:** GitOps automation not yet implemented (null-op placeholder)

## Usage

See [SETUP_CI.md](../../SETUP_CI.md) for complete setup guide.

### Quick start

```bash
# Build RC
git tag percolate-rocks-v0.2.0-rc1
git push origin percolate-rocks-v0.2.0-rc1

# Promote to production
git tag percolate-rocks-v0.2.0
git push origin percolate-rocks-v0.2.0
```

## Implementation notes

### uv Docker pattern

All Python projects use the same uv build pattern:

```dockerfile
# Builder: uv venv + uv sync --frozen --no-editable
FROM python:3.12-slim AS builder
RUN uv venv && uv sync --frozen --no-editable

# Runtime: Copy entire /app (including .venv/)
FROM python:3.12-slim
COPY --from=builder /app /app
CMD [".venv/bin/python", "-m", "module"]
```

**Key points:**
- Don't activate venv - use `.venv/bin/python` directly
- Copy entire `/app` to preserve venv structure
- `--no-editable` ensures package is installed, not symlinked

### Version sources

Each project has a single source of truth for versions:

- **percolate-rocks:** `Cargo.toml` and `pyproject.toml` (must match!)
- **percolate-reading:** `pyproject.toml`
- **percolate:** `src/percolate/version.py`

Workflows validate tags match source versions before building.

### CalVer tagging

RC builds use CalVer for traceability:

Format: `YYYY.MM.DD.HHMM-build.N-vVERSION-SHA-ARCH`

Example: `percolate:2025.10.25.1430-build.123-v0.1.0-abc1234-amd64`

Production releases use clean semantic versions:

Format: `VERSION-ARCH`

Example: `percolate:0.1.0-amd64`

## TODO items

### High priority

1. **Implement Docker release retagging** (release-reading.yml, release-percolate.yml)
   - Find latest RC CalVer tag via GHCR API
   - Pull RC image
   - Retag with clean semantic version
   - Push to GHCR

2. **Add Cosign signing** (release workflows)
   - Install Cosign
   - Get GitHub OIDC token
   - Sign images with keyless signing
   - Verify signatures

3. **Add SBOM generation** (release workflows)
   - Install `syft` or `bom`
   - Generate SBOM (SPDX or CycloneDX format)
   - Attach as Cosign attestation
   - Verify attestations

### Medium priority

4. **Implement K8s manifest updates** (release workflows)
   - Clone manifest repository
   - Update image tags in deployment YAML
   - Commit and push changes
   - Link to Argo CD application

5. **Add multi-arch manifest lists**
   - Create manifest list combining amd64/arm64
   - Push to GHCR
   - Allow architecture-agnostic pulls

### Low priority

6. **Add automated changelog generation**
   - Use conventional commits
   - Generate CHANGELOG.md
   - Include in GitHub releases

7. **Add Slack/Discord notifications**
   - Notify on successful releases
   - Alert on failed builds
   - Include deployment status

## Reference

Based on p8fs-modules CI/CD implementation:
- Multi-stage Docker builds
- CalVer + semantic versioning
- Trivy security scanning
- Cosign keyless signing
- GitOps manifest updates

See [CI.md](../../CI.md) for full release strategy.
