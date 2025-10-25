# Build and release process

This document describes the build, versioning, and release process for all Percolate projects.

## Quick start

```bash
# 1. Bump versions
python scripts/bump_version.py percolate --part patch
python scripts/bump_version.py percolate-reading --part minor

# 2. Check status
python scripts/pr.py status

# 3. Create release commit and tags
python scripts/pr.py create --push
```

This will:
- Create a commit with version changes and release notes
- Create tags for each changed project
- Push tags to trigger automated builds

## Projects

The repository contains three projects:

1. **percolate-rocks**: RocksDB-based REM database (Rust + PyO3)
   - Published to: PyPI
   - Format: Python wheels

2. **percolate**: Main API service (Python)
   - Published to: GitHub Container Registry (GHCR)
   - Format: Docker images

3. **percolate-reading**: Document processing service (Python)
   - Published to: GitHub Container Registry (GHCR)
   - Format: Docker images

## Build DAG

Projects have dependencies that determine build order:

```
percolate-rocks (PyPI)
    ↓
    ├─→ percolate (Docker)
    └─→ percolate-reading (Docker)
        ↓
    manifests (K8s) [future]
```

The orchestrator workflow (`build-all.yml`) handles this automatically.

## Version management

### Bump version

```bash
# Patch (0.1.0 → 0.1.1)
python scripts/bump_version.py <project>

# Minor (0.1.0 → 0.2.0)
python scripts/bump_version.py <project> --part minor

# Major (0.1.0 → 1.0.0)
python scripts/bump_version.py <project> --part major

# Dry run
python scripts/bump_version.py <project> --dry-run
```

### Show versions

```bash
python scripts/bump_version.py show percolate
python scripts/bump_version.py show percolate-reading
python scripts/bump_version.py show percolate-rocks
```

## Release workflow

### 1. Prepare release

Bump versions and add release notes:

```bash
# Bump versions
python scripts/bump_version.py percolate --part minor
python scripts/bump_version.py percolate-reading --part patch

# Optional: Add release notes
mkdir -p percolate/.release/v0.2.0
echo "## New features\n- Feature 1\n- Feature 2" > percolate/.release/v0.2.0/features.md
```

### 2. Create RC (release candidate)

```bash
# Check status
python scripts/pr.py status

# Create commit and tags
python scripts/pr.py create --push
```

This creates RC tags: `percolate-v0.2.0-rc1`

### 3. Test RC builds

RC builds are published to production registries:
- **percolate-rocks**: PyPI (with -rc suffix in version)
- **percolate/reading**: GHCR with CalVer tags

Pull and test:

```bash
# Test percolate-rocks
pip install percolate-rocks==0.2.0

# Test percolate
docker pull ghcr.io/percolation-labs/percolate:2025.01.15.1430-build.42-v0.2.0-abc123-amd64
```

### 4. Promote to production

Once RC is tested, create production release:

```bash
# Create production tag (no -rc suffix)
git tag percolate-v0.2.0
git tag percolate-rocks-v0.2.0
git push --tags
```

This triggers the release workflow which:
- **percolate-rocks**: Verifies package on PyPI, creates GitHub release
- **percolate/reading**: Retags RC images with clean version, creates GitHub release
- Updates K8s manifests (future)

## Tag formats

### RC tags (release candidates)

Format: `{project}-v{version}-rc{number}`

Examples:
- `percolate-v0.2.0-rc1`
- `percolate-reading-v0.1.5-rc2`
- `percolate-rocks-v0.3.0-rc1`

Triggers: Build workflows

### Production tags

Format: `{project}-v{version}`

Examples:
- `percolate-v0.2.0`
- `percolate-reading-v0.1.5`
- `percolate-rocks-v0.3.0`

Triggers: Release workflows

## Docker images

Images are published to GHCR with two tag strategies:

### RC builds (CalVer tags)

Format: `YYYY.MM.DD.HHMM-build.NUMBER-vVERSION-SHA-ARCH`

Example:
```
ghcr.io/percolation-labs/percolate:2025.01.15.1430-build.42-v0.2.0-abc1234-amd64
```

This provides:
- Temporal ordering (CalVer)
- Build traceability (build number)
- Version association (vVERSION)
- Git commit (SHA)
- Architecture (amd64/arm64)

### Production (semantic version tags)

Format: `VERSION-ARCH`

Example:
```
ghcr.io/percolation-labs/percolate:0.2.0-amd64
```

Clean tags for production use.

## GitHub secrets

Required secrets (see `.github/SECRETS.md` for details):

- **`PYPI_API_TOKEN`**: For publishing percolate-rocks to PyPI

Optional (for future):
- **`K8S_MANIFEST_PAT`**: Update K8s manifests

The `GITHUB_TOKEN` is automatically provided for:
- Docker builds to GHCR
- GitHub releases
- Repository access

## CI/CD workflows

### Build workflows

Triggered by RC tags:

- `build-rocks.yml`: Build Python wheels, publish to PyPI
- `build-percolate.yml`: Build Docker images, publish to GHCR
- `build-reading.yml`: Build Docker images, publish to GHCR
- `build-all.yml`: Orchestrator (handles DAG)

### Release workflows

Triggered by production tags:

- `release-rocks.yml`: Verify PyPI package, create GitHub release
- `release-percolate.yml`: Retag images, update manifests
- `release-reading.yml`: Retag images, update manifests

## Local testing

### Test version bump scripts

```bash
# Install dependencies
pip install typer rich

# Test bump (dry run)
python scripts/bump_version.py percolate --dry-run

# Test PR script
python scripts/pr.py status
```

### Test Docker builds

```bash
# percolate
cd percolate
docker build -t percolate:test .
docker run --rm percolate:test .venv/bin/percolate --version

# percolate-reading
cd percolate-reading
docker build -t percolate-reading:test .
docker run --rm percolate-reading:test echo "Build OK"
```

## Troubleshooting

### Version mismatch errors

If CI fails with version mismatch:

```
❌ Version mismatch!
   Tag version:  0.2.0
   version.py:   0.1.0
```

Fix: Ensure version files are updated before tagging:

```bash
python scripts/bump_version.py percolate --part minor
git add .
git commit -m "Bump version"
git tag percolate-v0.2.0-rc1
```

### Build not triggered

If pushing a tag doesn't trigger workflow:

1. Check tag format matches pattern
2. Verify workflow files are on default branch
3. Check GitHub Actions tab for errors

### Docker build fails

Common issues:

1. **Missing files**: Ensure all source files are committed
2. **UV sync fails**: Check `pyproject.toml` and `uv.lock` are valid
3. **Health check fails**: Verify app starts correctly

## Best practices

1. **Always test RC before production**
   - Create RC tag first
   - Test in staging
   - Promote to prod only after validation

2. **Use release notes**
   - Add notes to `.release/vX.Y.Z/`
   - Organize by type (features, bugs, breaking)
   - Notes included in commit message

3. **Version dependencies correctly**
   - Bump percolate-rocks first if changed
   - Then bump dependent projects
   - Follow semantic versioning

4. **Monitor builds**
   - Check GitHub Actions for each build
   - Verify images appear in GHCR
   - Test images before promoting

5. **Keep branches clean**
   - Squash version bumps if needed
   - Tag from main/master
   - Don't mix feature work with releases
