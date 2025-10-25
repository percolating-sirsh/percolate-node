# CI/CD setup guide

Complete guide to configure GitHub Actions CI/CD for the Percolation monorepo.

## Prerequisites

- GitHub repository: `percolation-labs/percolate` (or your fork)
- Admin access to repository settings
- PyPI account (for percolate-rocks)
- GitHub Container Registry (GHCR) access (automatic with GitHub)

## Step 1: Configure repository settings

### 1.1 Enable GitHub Actions

**Settings → Actions → General**

- ✅ **Allow all actions and reusable workflows**
- ✅ **Workflow permissions:** Read and write permissions
- ✅ **Allow GitHub Actions to create and approve pull requests**

### 1.2 Configure branch protection (optional but recommended)

**Settings → Branches → Branch protection rules**

Add rule for `main` branch:
- ✅ Require pull request reviews before merging (1 approver)
- ✅ Require status checks to pass before merging
  - Add checks: `build-rocks`, `build-reading`, `build-percolate`
- ✅ Require branches to be up to date before merging
- ✅ Include administrators

### 1.3 Enable GitHub Packages

**Settings → Packages**

- ✅ Container registry enabled (should be automatic)
- Verify visibility: Public or Private (recommend: Public for open source)

## Step 2: Configure secrets

### 2.1 PyPI credentials (for percolate-rocks)

**Settings → Secrets and variables → Actions → New repository secret**

#### Option A: API Token (simpler)

1. Go to [PyPI Account Settings](https://pypi.org/manage/account/)
2. Create API token:
   - **Token name:** `GitHub Actions - percolate-rocks`
   - **Scope:** Project: percolate-rocks (or entire account)
3. Copy token (starts with `pypi-...`)
4. Add to GitHub:
   - **Name:** `PYPI_API_TOKEN`
   - **Value:** `pypi-AgE...` (paste full token)

5. Repeat for Test PyPI:
   - Go to [Test PyPI](https://test.pypi.org/manage/account/)
   - Create token
   - Add to GitHub:
     - **Name:** `TEST_PYPI_API_TOKEN`
     - **Value:** `pypi-AgE...`

#### Option B: Trusted Publisher (recommended, keyless)

1. Go to [PyPI project settings](https://pypi.org/manage/project/percolate-rocks/settings/publishing/)
2. Add trusted publisher:
   - **Repository owner:** `percolation-labs` (your GitHub org/user)
   - **Repository name:** `percolate`
   - **Workflow name:** `release-rocks.yml`
   - **Environment:** (leave blank)
3. Repeat for Test PyPI if needed

With trusted publishing, no `PYPI_API_TOKEN` needed! GitHub OIDC handles authentication.

### 2.2 GitOps manifest repository access (TODO)

When K8s manifest updates are implemented, you'll need:

**Name:** `PERCOLATE_GIT_PAT`
**Value:** Personal Access Token with `repo` scope

**To create:**
1. Go to [GitHub Settings → Developer Settings → Personal Access Tokens → Tokens (classic)](https://github.com/settings/tokens)
2. Generate new token (classic)
3. Name: `Percolate CI - Manifest Updates`
4. Scopes:
   - ✅ `repo` (Full control of private repositories)
5. Generate and copy token
6. Add to repository secrets as `PERCOLATE_GIT_PAT`

**Note:** This is only needed once manifest automation is implemented (currently TODO).

### 2.3 Verify GITHUB_TOKEN permissions

The `GITHUB_TOKEN` is automatically provided and has these permissions enabled in workflows:
- `contents: read` - Read repository contents
- `contents: write` - Create releases
- `packages: write` - Push to GHCR
- `id-token: write` - OIDC for signing

No manual configuration needed!

## Step 3: Initialize version tracking

Each project uses its own version source. Ensure they match your tags:

### percolate-rocks

**File:** `percolate-rocks/Cargo.toml` and `percolate-rocks/pyproject.toml`

```toml
[package]
version = "0.2.0"  # Cargo.toml

[project]
version = "0.2.0"  # pyproject.toml (must match!)
```

### percolate-reading

**File:** `percolate-reading/pyproject.toml`

```toml
[project]
version = "0.1.0"
```

### percolate

**File:** `percolate/src/percolate/version.py`

```python
__version__ = "0.1.0"
```

## Step 4: Test the workflows

### 4.1 Test percolate-rocks (PyPI)

```bash
# Ensure version is correct
cd percolate-rocks
grep 'version = ' Cargo.toml pyproject.toml

# Tag RC (triggers build)
git tag percolate-rocks-v0.2.0-rc1
git push origin percolate-rocks-v0.2.0-rc1

# Monitor build: https://github.com/percolation-labs/percolate/actions
```

Expected outcome:
- ✅ Build wheels for all platforms
- ✅ Run tests
- ✅ Publish to Test PyPI
- ✅ Artifacts uploaded

Verify on Test PyPI: https://test.pypi.org/project/percolate-rocks/

### 4.2 Test percolate-reading (Docker)

```bash
# Ensure version is correct
cd percolate-reading
grep 'version = ' pyproject.toml

# Tag RC (triggers build)
git tag percolate-reading-v0.1.0-rc1
git push origin percolate-reading-v0.1.0-rc1

# Monitor build: https://github.com/percolation-labs/percolate/actions
```

Expected outcome:
- ✅ Build Docker images (amd64, arm64)
- ✅ Run tests and Trivy scan
- ✅ Push to GHCR with CalVer tags
- ✅ Metadata artifacts uploaded

Verify on GHCR: https://github.com/percolation-labs/percolate/pkgs/container/percolate-reading

### 4.3 Test percolate (Docker)

```bash
# Ensure version is correct
cd percolate
grep '__version__' src/percolate/version.py

# Tag RC (triggers build)
git tag percolate-v0.1.0-rc1
git push origin percolate-v0.1.0-rc1

# Monitor build: https://github.com/percolation-labs/percolate/actions
```

Expected outcome:
- ✅ Build Docker images (amd64, arm64)
- ✅ Run tests and Trivy scan
- ✅ Push to GHCR with CalVer tags
- ✅ Metadata artifacts uploaded

Verify on GHCR: https://github.com/percolation-labs/percolate/pkgs/container/percolate

## Step 5: Promote RC to production

After testing RC builds, promote to production:

### percolate-rocks

```bash
# Tag production release (triggers release workflow)
git tag percolate-rocks-v0.2.0
git push origin percolate-rocks-v0.2.0
```

Expected outcome:
- ✅ Find latest RC build
- ✅ Rebuild wheels for production
- ✅ Publish to production PyPI
- ✅ Sign with Sigstore
- ✅ Generate SBOM
- ✅ Create GitHub Release

Verify: https://pypi.org/project/percolate-rocks/

### percolate-reading

```bash
# Tag production release
git tag percolate-reading-v0.1.0
git push origin percolate-reading-v0.1.0
```

Expected outcome:
- ✅ Find latest RC images
- ⚠️  Retag images (TODO: needs implementation)
- ⚠️  Sign with Cosign (TODO)
- ⚠️  Generate SBOM (TODO)
- ⚠️  Update K8s manifests (TODO)
- ✅ Create GitHub Release

**Note:** Docker release workflows have placeholders. Core retagging logic needs implementation.

### percolate

```bash
# Tag production release
git tag percolate-v0.1.0
git push origin percolate-v0.1.0
```

Expected outcome: Same as percolate-reading (TODO items apply).

## Step 6: Verify releases

### PyPI package (percolate-rocks)

```bash
# Install from PyPI
pip install percolate-rocks==0.2.0

# Verify import
python3 -c "import rem_db; print(rem_db.__version__)"

# Verify signature (if signed)
pip install sigstore
sigstore verify identity percolate_rocks-*.whl \
  --cert-identity https://github.com/percolation-labs/percolate/.github/workflows/release-rocks.yml \
  --cert-oidc-issuer https://token.actions.githubusercontent.com
```

### Docker images

```bash
# Pull from GHCR
docker pull ghcr.io/percolation-labs/percolate-reading:0.1.0-amd64
docker pull ghcr.io/percolation-labs/percolate:0.1.0-amd64

# Test run
docker run --rm ghcr.io/percolation-labs/percolate-reading:0.1.0-amd64 percolate-reading --version
docker run --rm ghcr.io/percolation-labs/percolate:0.1.0-amd64 .venv/bin/percolate --version
```

## Troubleshooting

### Build workflow doesn't trigger

**Cause:** Tag doesn't match expected pattern

**Solution:**
- Check tag format: `{project}-v{X}.{Y}.{Z}-rc{N}` for builds
- Check tag format: `{project}-v{X}.{Y}.{Z}` for releases
- Use `git tag -l` to list tags and verify

### Version mismatch error

**Cause:** Tag version doesn't match source files

**Solution:**
```bash
# percolate-rocks: Update both files
sed -i '' 's/^version = .*/version = "0.2.0"/' percolate-rocks/Cargo.toml
sed -i '' 's/^version = .*/version = "0.2.0"/' percolate-rocks/pyproject.toml

# percolate-reading
sed -i '' 's/^version = .*/version = "0.1.0"/' percolate-reading/pyproject.toml

# percolate
sed -i '' 's/__version__ = .*/__version__ = "0.1.0"/' percolate/src/percolate/version.py
```

Commit, push, then create tag.

### PyPI authentication fails

**Cause:** Token invalid or trusted publisher not configured

**Solution:**
1. Verify secret name: `PYPI_API_TOKEN` (exact, case-sensitive)
2. Check token hasn't expired on PyPI
3. Try trusted publisher instead (no token needed)
4. For trusted publisher, verify workflow name matches exactly

### Docker build fails with permission denied

**Cause:** GITHUB_TOKEN doesn't have packages:write

**Solution:**
- Check workflow permissions block includes `packages: write`
- Verify repository settings allow Actions to write packages

### Trivy scan fails with vulnerabilities

**Cause:** Critical/High vulnerabilities found in image

**Solution:**
1. Review Trivy output in workflow logs
2. Update base image: `python:3.12-slim`
3. Update dependencies: `uv lock --upgrade`
4. If false positive, add to `.trivyignore`

### Image not found during release

**Cause:** No RC build exists for the version

**Solution:**
1. Create RC tag first: `{project}-v{VERSION}-rc1`
2. Wait for build to complete
3. Verify images exist in GHCR
4. Then create production tag

## Next steps

### Implement Docker release retagging

The release workflows for Docker images (`release-reading.yml`, `release-percolate.yml`) have TODO placeholders:

1. **Image discovery:** Query GHCR API to find latest RC CalVer tag
2. **Pull and retag:** Pull RC image, retag with clean version, push
3. **Sign with Cosign:** Implement keyless signing with GitHub OIDC
4. **Generate SBOM:** Use `syft` or `bom` to generate SBOM
5. **Attach SBOM:** Use Cosign to attach SBOM as attestation

Reference implementation: `.github/workflows/release.yml` in p8fs-modules

### Implement K8s manifest updates

Add GitOps automation to release workflows:

1. Clone manifest repository (using `PERCOLATE_GIT_PAT`)
2. Update image tags in deployment YAML files
3. Commit and push changes
4. Argo CD auto-syncs (if configured)

Reference implementation: `update-manifests` job in p8fs-modules

### Add multi-arch Docker manifest

Currently images are tagged per-architecture (`-amd64`, `-arm64`). Add manifest lists:

```bash
# Create manifest list pointing to both architectures
docker manifest create ghcr.io/org/percolate:0.1.0 \
  ghcr.io/org/percolate:0.1.0-amd64 \
  ghcr.io/org/percolate:0.1.0-arm64
docker manifest push ghcr.io/org/percolate:0.1.0
```

This allows users to `docker pull ghcr.io/org/percolate:0.1.0` without specifying architecture.

## Security best practices

### Secrets management

- ✅ Use repository secrets, not hardcoded values
- ✅ Use trusted publishing for PyPI (keyless)
- ✅ Use GitHub OIDC for Cosign (keyless)
- ✅ Rotate PATs every 90 days
- ❌ Never commit secrets to git

### Image signing

- ✅ Sign all production images with Cosign
- ✅ Attach SBOMs as in-toto attestations
- ✅ Use Rekor transparency log
- ✅ Verify signatures in deployment pipelines

### Trivy scanning

- ✅ Scan all images before push
- ✅ Fail builds on CRITICAL vulnerabilities
- ✅ Review HIGH vulnerabilities (fail or waive)
- ✅ Keep `.trivyignore` up to date with justifications

## Support

- **CI.md:** Full release strategy documentation
- **GitHub Actions logs:** Detailed build logs and errors
- **GitHub Discussions:** Ask questions and share feedback
- **Issues:** Report bugs or request features
