# CI/CD implementation TODO list

## Summary

Complete CI/CD infrastructure has been created for the Percolation monorepo with independent release cycles for three projects:

1. **percolate-rocks** (PyPI) - ✅ Fully functional
2. **percolate-reading** (Docker) - ⚠️ Build complete, release needs work
3. **percolate** (Docker) - ⚠️ Build complete, release needs work

## GitHub secrets to configure

Before using the workflows, configure these secrets in GitHub repository settings:

### Required immediately

- **`PYPI_API_TOKEN`** - Production PyPI token for percolate-rocks
  - Get from: https://pypi.org/manage/account/
  - Alternative: Use trusted publisher (keyless, recommended)

- **`TEST_PYPI_API_TOKEN`** - Test PyPI token for RC builds
  - Get from: https://test.pypi.org/manage/account/

### Required later (when manifest updates are implemented)

- **`PERCOLATE_GIT_PAT`** - Personal Access Token for updating K8s manifests
  - Scope: `repo` (full control)
  - Used for: GitOps manifest updates

See [SETUP_CI.md](./SETUP_CI.md) for detailed setup instructions.

## What's working now

### ✅ percolate-rocks (PyPI package)

**Build workflow (build-rocks.yml):**
- Multi-platform wheel building (Linux amd64/arm64, macOS amd64/arm64)
- Rust + Python integration tests
- Publish to Test PyPI
- Artifact storage

**Release workflow (release-rocks.yml):**
- Version validation
- Production PyPI publishing
- Sigstore signing (keyless)
- SBOM generation (CycloneDX)
- GitHub Release creation

**Status:** 🟢 **Ready to use**

### ⚠️ percolate-reading (Docker images)

**Build workflow (build-reading.yml):**
- Multi-platform Docker builds (amd64, arm64)
- Container tests (health checks, CLI)
- Trivy security scanning
- CalVer tagging (YYYY.MM.DD.HHMM-build.N-vVERSION-SHA-ARCH)
- Push to GHCR
- Metadata artifacts

**Release workflow (release-reading.yml):**
- ⚠️ RC image discovery - **TODO: Needs implementation**
- ⚠️ Image retagging - **TODO: Needs implementation**
- ⚠️ Cosign signing - **TODO: Needs implementation**
- ⚠️ SBOM generation - **TODO: Needs implementation**
- ⚠️ K8s manifest updates - **TODO: Null-op placeholder**
- ✅ GitHub Release creation - Working

**Status:** 🟡 **Build works, release needs implementation**

### ⚠️ percolate (Docker images)

**Build workflow (build-percolate.yml):**
- Multi-platform Docker builds (amd64, arm64)
- Container tests (health checks, CLI)
- Trivy security scanning
- CalVer tagging
- Push to GHCR
- Metadata artifacts

**Release workflow (release-percolate.yml):**
- Same status as percolate-reading (TODO items)

**Status:** 🟡 **Build works, release needs implementation**

## TODO items by priority

### 🔴 High priority - Docker release workflows

#### 1. Implement RC image discovery

**File:** `release-reading.yml`, `release-percolate.yml`
**Job:** `find-rc-images`

Currently placeholder. Needs:
- Query GHCR API to find CalVer-tagged images matching version
- Extract digest and tag information
- Pass to retag job

**Example approach:**
```bash
# Use gh CLI to query GHCR
gh api /orgs/percolation-labs/packages/container/percolate-reading/versions \
  | jq -r '.[] | select(.metadata.container.tags[] | contains("v0.1.0")) | .metadata.container.tags[]' \
  | grep "v0.1.0-" | sort -V | tail -1
```

#### 2. Implement image retagging

**File:** `release-reading.yml`, `release-percolate.yml`
**Job:** `retag-images`

Currently placeholder. Needs:
- Pull RC CalVer-tagged image
- Tag with clean semantic version
- Push to GHCR
- Store digest for signing

**Example:**
```bash
docker pull ghcr.io/org/percolate:2025.10.25.1430-build.123-v0.1.0-abc1234-amd64
docker tag ghcr.io/org/percolate:2025.10.25.1430-build.123-v0.1.0-abc1234-amd64 \
           ghcr.io/org/percolate:0.1.0-amd64
docker push ghcr.io/org/percolate:0.1.0-amd64
```

#### 3. Add Cosign image signing

**File:** `release-reading.yml`, `release-percolate.yml`
**Job:** `retag-images`

Add steps after push:
- Install Cosign
- Get GitHub OIDC token
- Sign image with keyless signing
- Verify signature

**Reference:** See `release.yml` in p8fs-modules (lines 206-234)

#### 4. Add SBOM generation and attestation

**File:** `release-reading.yml`, `release-percolate.yml`
**Job:** `retag-images`

Add steps after signing:
- Install `bom` or `syft`
- Generate SBOM (SPDX JSON format)
- Attach SBOM with Cosign attestation
- Verify attestation

**Reference:** See `release.yml` in p8fs-modules (lines 236-293)

### 🟡 Medium priority - GitOps automation

#### 5. Implement K8s manifest updates

**File:** `release-reading.yml`, `release-percolate.yml`
**Job:** `update-manifests`

Currently null-op placeholder. Needs:
- Clone manifest repository (using `PERCOLATE_GIT_PAT`)
- Update image tags in deployment YAML files
- Commit and push changes
- Argo CD will auto-sync

**Reference:** See `release.yml` in p8fs-modules (lines 312-445)

**Configuration needed:**
- `MANIFEST_REPO`: e.g., `percolation-labs/percolate-cloud`
- `MANIFEST_BRANCH`: e.g., `main`
- `BASE_PATH`: e.g., `applications`
- Application directories: `percolate-api/`, `percolate-reading/`

#### 6. Create multi-arch manifest lists

**File:** New step in release workflows

Add manifest list creation:
- Combine amd64 and arm64 images
- Push manifest list to GHCR
- Allows users to pull without specifying architecture

**Example:**
```bash
docker manifest create ghcr.io/org/percolate:0.1.0 \
  ghcr.io/org/percolate:0.1.0-amd64 \
  ghcr.io/org/percolate:0.1.0-arm64
docker manifest push ghcr.io/org/percolate:0.1.0
```

### 🟢 Low priority - Nice to have

#### 7. Add automated changelog generation

Use conventional commits and generate CHANGELOG.md automatically.

#### 8. Add Slack/Discord notifications

Notify on releases and failed builds.

#### 9. Add performance benchmarks

Run benchmarks in CI and track performance over time.

#### 10. Add integration tests against staging

Deploy to staging environment and run full integration tests.

## Testing checklist

Before going to production, test each workflow:

### percolate-rocks

- [ ] Create RC tag: `percolate-rocks-v0.2.0-rc1`
- [ ] Verify Test PyPI publish
- [ ] Test install from Test PyPI
- [ ] Create production tag: `percolate-rocks-v0.2.0`
- [ ] Verify production PyPI publish
- [ ] Verify Sigstore signature
- [ ] Test install from production PyPI

### percolate-reading

- [ ] Create RC tag: `percolate-reading-v0.1.0-rc1`
- [ ] Verify Docker builds (amd64, arm64)
- [ ] Verify GHCR push with CalVer tags
- [ ] Test pull and run image
- [ ] Verify Trivy scan passes
- [ ] Create production tag: `percolate-reading-v0.1.0` (after implementing retag)
- [ ] Verify image retagging
- [ ] Verify Cosign signature (after implementing)
- [ ] Verify SBOM attestation (after implementing)

### percolate

- [ ] Same as percolate-reading

## Files created

```
percolation/
├── CI.md                              # Complete CI/CD strategy documentation
├── SETUP_CI.md                        # Step-by-step setup guide
├── TODO_CI.md                         # This file - implementation TODO list
├── .github/workflows/
│   ├── README.md                      # Workflows overview
│   ├── build-rocks.yml                # ✅ percolate-rocks build (PyPI)
│   ├── release-rocks.yml              # ✅ percolate-rocks release (PyPI)
│   ├── build-reading.yml              # ✅ percolate-reading build (Docker)
│   ├── release-reading.yml            # ⚠️ percolate-reading release (TODO)
│   ├── build-percolate.yml            # ✅ percolate build (Docker)
│   └── release-percolate.yml          # ⚠️ percolate release (TODO)
└── percolate/
    └── Dockerfile                     # ✅ Created using uv Docker pattern
```

## Key design decisions

### Single source of truth for versions

No redundant VERSION files. Each project uses its primary config:
- **percolate-rocks:** `Cargo.toml` + `pyproject.toml` (must match)
- **percolate-reading:** `pyproject.toml`
- **percolate:** `src/percolate/version.py`

### uv Docker pattern

All Dockerfiles follow the same pattern:
1. Builder stage: `uv venv` + `uv sync --frozen --no-editable`
2. Runtime stage: Copy entire `/app` including `.venv/`
3. Execute: Use `.venv/bin/python` directly (no activation)

### CalVer + semantic versioning

- RC builds: CalVer tags for traceability
- Production: Clean semantic version tags
- No tag overwriting - each build gets unique identifier

### Independent release cycles

Each project can release independently:
- Separate tag patterns
- Separate workflows
- No monorepo-wide versioning

## Next steps

1. **Configure GitHub secrets** (see SETUP_CI.md)
2. **Test percolate-rocks workflow** (fully functional)
3. **Implement Docker release retagging** (high priority)
4. **Test Docker workflows** (after implementation)
5. **Implement K8s manifest updates** (medium priority)

## Questions to answer

Before implementing Docker release workflows:

1. **Where are K8s manifests stored?**
   - Repository URL
   - Branch name
   - Directory structure

2. **What Argo CD applications exist?**
   - `percolate-api` (uses percolate image)
   - `percolate-reading` (uses percolate-reading image)
   - Others?

3. **What deployment files need updates?**
   - Deployment YAML paths
   - Image tag field locations
   - Multiple environments?

4. **Do you want multi-arch manifest lists?**
   - Single tag for both architectures
   - Or keep separate `-amd64`/`-arm64` tags?

5. **What SBOM format?**
   - SPDX (used by Kubernetes)
   - CycloneDX (used by OWASP)
   - Both?

## Resources

- **p8fs-modules reference:** `/Users/sirsh/code/p8fs-modules/.github/workflows/`
- **CI strategy:** `CI.md`
- **Setup guide:** `SETUP_CI.md`
- **Workflows:** `.github/workflows/README.md`
- **Docker pattern:** `percolate-reading/Dockerfile` (reference)
