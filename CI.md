# CI/CD strategy for Percolate monorepo

## Overview

The Percolation monorepo contains three independently versioned projects with distinct release cycles:

1. **percolate-rocks**: Rust core + Python bindings → PyPI package
2. **percolate-reading**: Heavy multimedia processing service → Docker images
3. **percolate**: Main API and orchestration layer → Docker images

Each project maintains independent semantic versioning and triggers builds based on its own VERSION file.

## Version management

### Single source of truth

Each project maintains its version in its primary configuration file:

```
percolate-rocks/Cargo.toml         # version = "0.2.0"
percolate-rocks/pyproject.toml     # version = "0.2.0" (must match)
percolate-reading/pyproject.toml   # version = "0.1.0"
percolate/pyproject.toml           # version = "0.1.0"
```

**Important:** percolate-rocks has both files and versions MUST be kept in sync manually.

### Tagging strategy

Tags follow the pattern: `{project}-v{version}[-rc{N}]`

**Release candidates (triggers build):**
```bash
# Build and test, push with CalVer tag
git tag percolate-rocks-v0.2.0-rc1
git tag percolate-reading-v0.1.0-rc1
git tag percolate-v0.1.0-rc1
```

**Production releases (retag and promote):**
```bash
# Retag RC images with clean version, update K8s manifests
git tag percolate-rocks-v0.2.0
git tag percolate-reading-v0.1.0
git tag percolate-v0.1.0
```

## Build pipeline

### Stage 1: Build (RC tags)

Triggered by: `{project}-v*-rc*` tags

**percolate-rocks:**
1. Build Python wheels for multiple platforms (manylinux, macOS, Windows)
2. Run Rust tests (`cargo test`)
3. Run Python integration tests
4. Publish to PyPI (test repository for RC)
5. Store build metadata as artifacts

**percolate-reading and percolate:**
1. Build Docker images (multi-platform: amd64, arm64)
2. Run image tests (container starts, health checks)
3. Security scan with Trivy
4. Push images with CalVer tags: `{project}:YYYY.MM.DD.HHMM-build.N-v{VERSION}-{SHA}-{ARCH}`
5. Store build metadata as artifacts

**CalVer format:**
```
percolate-reading:2025.10.25.1430-build.123-v0.1.0-abc1234-amd64
percolate-reading:2025.10.25.1430-build.123-v0.1.0-abc1234-arm64
percolate:2025.10.25.1430-build.123-v0.1.0-abc1234-amd64
percolate:2025.10.25.1430-build.123-v0.1.0-abc1234-arm64
```

### Stage 2: Release (production tags)

Triggered by: `{project}-v{major}.{minor}.{patch}` tags (no RC suffix)

**percolate-rocks:**
1. Find latest RC build for version from test PyPI
2. Promote to production PyPI repository
3. Generate SBOM and sign with sigstore
4. Create GitHub release with artifacts

**percolate-reading and percolate:**
1. Find latest CalVer-tagged RC images for version
2. Retag with clean semantic version: `{project}:{VERSION}-{ARCH}`
3. Sign images with Cosign (keyless, Sigstore/Fulcio)
4. Generate and attach SBOM (SPDX format)
5. Verify signatures and attestations
6. Update K8s Argo CD application manifests (GitOps)
7. Create GitHub release

**Clean version format:**
```
percolate-reading:0.1.0-amd64
percolate-reading:0.1.0-arm64
percolate:0.1.0-amd64
percolate:0.1.0-arm64
```

### Stage 3: Deployment (TODO - null-op placeholder)

**Current:** Manual deployment via Argo CD UI

**Planned:**
1. Update Argo CD application manifests in `percolate-cloud` repository
2. Manifests stored in `{BASE_PATH}/{application}/`
3. Argo CD auto-syncs or manual promotion
4. Health checks verify deployment

**Applications:**
- `percolate-api`: Main orchestration service (percolate image)
- `percolate-reading`: Multimedia processing workers (percolate-reading image)

## Workflow files

### Build workflows

```
.github/workflows/
├── build-rocks.yml           # percolate-rocks: Build PyPI package
├── build-reading.yml         # percolate-reading: Build Docker images
└── build-percolate.yml       # percolate: Build Docker images
```

Trigger: `on.push.tags: '{project}-v[0-9]+.[0-9]+.[0-9]+-rc*'`

### Release workflows

```
.github/workflows/
├── release-rocks.yml         # percolate-rocks: Promote to PyPI
├── release-reading.yml       # percolate-reading: Retag and deploy
└── release-percolate.yml     # percolate: Retag and deploy
```

Trigger: `on.push.tags: '{project}-v[0-9]+.[0-9]+.[0-9]+'` (no RC)

## Security and provenance

### Signing and attestation

**Docker images:**
- Signed with Cosign (keyless, using GitHub OIDC)
- SBOM generated with `bom` (Kubernetes SIG tool)
- SBOM attached as in-toto attestation
- Signatures stored in Rekor (public transparency log)

**PyPI packages:**
- Signed with sigstore-python
- Provenance attestation (SLSA)
- Uploaded with trusted publisher (GitHub OIDC)

### Verification commands

```bash
# Verify Docker image signature
COSIGN_EXPERIMENTAL=1 cosign verify \
  --certificate-identity-regexp="https://github.com/percolation-labs/percolate" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com" \
  ghcr.io/percolation-labs/percolate:0.1.0-amd64

# Verify SBOM attestation
COSIGN_EXPERIMENTAL=1 cosign verify-attestation \
  --type=spdxjson \
  --certificate-identity-regexp="https://github.com/percolation-labs/percolate" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com" \
  ghcr.io/percolation-labs/percolate:0.1.0-amd64

# Verify PyPI package (once signed)
python -m pip install sigstore
sigstore verify identity percolate-rocks-0.2.0-*.whl \
  --cert-identity https://github.com/percolation-labs/percolate/.github/workflows/release-rocks.yml \
  --cert-oidc-issuer https://token.actions.githubusercontent.com
```

## Required GitHub secrets

### Repository secrets (Settings → Secrets and variables → Actions)

**For Docker builds:**
```
GITHUB_TOKEN                 # Automatically provided by GitHub
                             # Used for: GHCR authentication, API calls
```

**For K8s GitOps updates:**
```
PERCOLATE_GIT_PAT           # Personal Access Token for manifest repo
                            # Scope: repo (full control)
                            # Used for: Pushing manifest updates to percolate-cloud
```

**For PyPI publishing:**
```
PYPI_API_TOKEN              # PyPI API token for production releases
                            # Create at: https://pypi.org/manage/account/token/

TEST_PYPI_API_TOKEN         # Test PyPI token for RC builds
                            # Create at: https://test.pypi.org/manage/account/token/
```

### Organization secrets (optional, for shared use)

If managing multiple repositories, these can be set at organization level:
- `PERCOLATE_GIT_PAT`
- `PYPI_API_TOKEN`
- `TEST_PYPI_API_TOKEN`

### PyPI trusted publisher (recommended)

Instead of API tokens, configure trusted publishers for keyless publishing:

1. Go to PyPI project settings → Publishing
2. Add trusted publisher:
   - **Repository owner:** percolation-labs
   - **Repository name:** percolate
   - **Workflow name:** `release-rocks.yml`
   - **Environment:** (leave blank or specify)

This eliminates the need for `PYPI_API_TOKEN`.

## Repository settings

### Permissions

**Settings → Actions → General → Workflow permissions:**
- ✅ Read and write permissions
- ✅ Allow GitHub Actions to create and approve pull requests (for automated PRs)

**Settings → Actions → General → Fork pull request workflows:**
- ❌ Run workflows from fork pull requests (security risk for secrets)

### Branch protection (recommended)

**main branch:**
- Require pull request reviews (1 approver)
- Require status checks to pass (build workflows)
- Require branches to be up to date
- Include administrators

### Environment protection (optional)

Create environments for staged releases:
- `production` - requires manual approval for release workflows
- `staging` - automatic deployment from RC tags

## Release workflow example

### Scenario: Release percolate-reading v0.1.0

**Step 1: Build and test RC**
```bash
# Update version in pyproject.toml
sed -i '' 's/^version = .*/version = "0.1.0"/' percolate-reading/pyproject.toml
git add percolate-reading/pyproject.toml
git commit -m "Bump percolate-reading to v0.1.0"
git push

# Tag RC (triggers build workflow)
git tag percolate-reading-v0.1.0-rc1
git push origin percolate-reading-v0.1.0-rc1
```

**Step 2: Monitor build**
- GitHub Actions builds Docker images
- Runs tests and security scans
- Pushes CalVer-tagged images: `percolate-reading:2025.10.25.1430-build.123-v0.1.0-abc1234-amd64`

**Step 3: Test RC deployment (manual)**
```bash
# Pull and test RC image
docker pull ghcr.io/percolation-labs/percolate-reading:2025.10.25.1430-build.123-v0.1.0-abc1234-amd64
docker run --rm ghcr.io/percolation-labs/percolate-reading:2025.10.25.1430-build.123-v0.1.0-abc1234-amd64 percolate-reading --version
```

**Step 4: Promote to production**
```bash
# Tag production release (triggers release workflow)
git tag percolate-reading-v0.1.0
git push origin percolate-reading-v0.1.0
```

**Step 5: Release workflow runs**
- Finds latest RC CalVer tag for v0.1.0
- Retags as `percolate-reading:0.1.0-amd64` and `percolate-reading:0.1.0-arm64`
- Signs with Cosign, generates SBOM
- Updates K8s manifests in `percolate-cloud` repository
- Creates GitHub release with notes

**Step 6: Deploy (manual for now)**
- Argo CD detects manifest changes
- Manual sync or auto-sync depending on application config

## Multi-project releases

To release multiple projects simultaneously:

```bash
# Tag all projects with RC
git tag percolate-rocks-v0.2.0-rc1
git tag percolate-reading-v0.1.0-rc1
git tag percolate-v0.1.0-rc1
git push --tags

# Wait for all builds to complete and test

# Promote all to production
git tag percolate-rocks-v0.2.0
git tag percolate-reading-v0.1.0
git tag percolate-v0.1.0
git push --tags
```

Each workflow runs independently in parallel.

## Troubleshooting

### Build fails with "version already exists"

**Cause:** Attempting to rebuild with same version tag

**Solution:**
1. Increment RC number: `{project}-v0.1.0-rc2`
2. Or delete tag and recreate (not recommended for production)

### Image not found during release

**Cause:** No RC build exists for the version being released

**Solution:**
1. Verify RC tag was pushed: `git tag -l '{project}-v*-rc*'`
2. Check build workflow completed successfully
3. Verify CalVer-tagged image exists in GHCR

### Cosign signature verification fails

**Cause:** Image was not signed or signature expired

**Solution:**
1. Check workflow logs for signing step
2. Verify OIDC token was obtained
3. Re-run release workflow to re-sign

### K8s manifest update fails

**Cause:** PAT token invalid or insufficient permissions

**Solution:**
1. Verify `PERCOLATE_GIT_PAT` is set in repository secrets
2. Check PAT has `repo` scope
3. Verify PAT has not expired
4. Test PAT manually: `gh auth login --with-token < token.txt`

## Future improvements

- [ ] Implement Argo CD application updates in release workflow (currently null-op)
- [ ] Add automated rollback on deployment failure
- [ ] Implement canary deployments for percolate-reading
- [ ] Add performance benchmarks to build pipeline
- [ ] Create unified release dashboard (GitHub Pages)
- [ ] Add Slack/Discord notifications for releases
- [ ] Implement automated changelog generation
- [ ] Add integration tests against staging environment
- [ ] Create Docker manifest lists for multi-arch images (single tag for both amd64/arm64)
