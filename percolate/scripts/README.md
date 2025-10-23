# Release Scripts for percolate-rem

Project-specific scripts for managing semantic versioning and PyPI publishing.

## Quick Start

```bash
# Bump version and publish (full workflow)
./scripts/release.sh patch  # or minor, major

# Individual operations
./scripts/bump-patch.sh     # Bump patch version only
./scripts/publish.sh        # Publish to PyPI
./scripts/publish.sh test   # Publish to TestPyPI for testing
```

## Scripts

### Version Bumping

**Automatic (recommended):**
```bash
./scripts/bump-patch.sh   # 0.1.0 -> 0.1.1
./scripts/bump-minor.sh   # 0.1.0 -> 0.2.0
./scripts/bump-major.sh   # 0.1.0 -> 1.0.0
```

**Manual (via Python):**
```bash
python scripts/bump_version.py patch
python scripts/bump_version.py minor
python scripts/bump_version.py major
python scripts/bump_version.py --current  # Show current version
```

### Publishing

**Publish to PyPI:**
```bash
./scripts/publish.sh        # Full publish to PyPI
./scripts/publish.sh build  # Build only, no upload
./scripts/publish.sh check  # Run pre-publish checks
```

**Test on TestPyPI first:**
```bash
./scripts/publish.sh test   # Upload to TestPyPI

# Test installation from TestPyPI
uv pip install --index-url https://test.pypi.org/simple/ percolate-rem
```

**Manual (via Python):**
```bash
python scripts/publish.py              # Publish to PyPI
python scripts/publish.py --test       # Publish to TestPyPI
python scripts/publish.py --build-only # Build without publishing
python scripts/publish.py --check      # Run pre-publish checks
```

### Full Release Workflow

The `release.sh` script automates the entire release process:

```bash
./scripts/release.sh patch  # or minor, major
```

This will:
1. Bump the version
2. Commit the version change
3. Create a git tag (e.g., `v0.1.1`)
4. Prompt for confirmation
5. Build and publish to PyPI
6. Optionally push commit and tag to remote

## Version File

The single source of truth for versioning is `src/percolate/version.py`:

```python
__version__ = "0.1.0"
```

This is read by:
- `pyproject.toml` (via hatchling dynamic versioning)
- All version management scripts
- Your application code (import from `percolate.version`)

## PyPI Configuration

### Authentication

Set up PyPI credentials before publishing:

```bash
# Create API token at https://pypi.org/manage/account/token/
# Add to ~/.pypirc
cat > ~/.pypirc << EOF
[pypi]
username = __token__
password = pypi-YOUR-API-TOKEN-HERE

[testpypi]
username = __token__
password = pypi-YOUR-TEST-API-TOKEN-HERE
EOF

chmod 600 ~/.pypirc
```

Or use `uv` environment variables:
```bash
export UV_PUBLISH_TOKEN="pypi-YOUR-API-TOKEN-HERE"
```

### First-Time Setup

1. **Register package name** (if not already taken):
   - Go to https://pypi.org and create account
   - Package name `percolate-rem` must be available

2. **Test on TestPyPI first**:
   ```bash
   ./scripts/publish.sh test
   ```

3. **Publish to PyPI**:
   ```bash
   ./scripts/publish.sh
   ```

## Pre-Publish Checklist

The publish script automatically checks:
- [ ] Git working directory is clean (no uncommitted changes)
- [ ] Current version is tagged in git
- [ ] Old build artifacts are cleaned

Manual checks before releasing:
- [ ] Tests pass (`pytest`)
- [ ] Linting passes (`ruff check`)
- [ ] Type checking passes (`mypy`)
- [ ] CHANGELOG is updated (if you maintain one)
- [ ] README is up to date

## Adapting for Other Projects

These scripts are project-specific but easily portable:

1. **Copy the `scripts/` directory** to your new project
2. **Update version file path** in scripts:
   - `bump_version.py`: Change `VERSION_FILE` path
   - `publish.py`: Change `PROJECT_ROOT` or version file path
3. **Update `pyproject.toml`**:
   - Change `name = "percolate-rem"` to your package name
   - Update `tool.hatch.version.path` to your version file location

Example for `percolate-reader`:
```toml
# pyproject.toml
[project]
name = "percolate-reader"
dynamic = ["version"]

[tool.hatch.version]
path = "src/percolate_reader/version.py"
```

## Troubleshooting

**"Version not tagged" warning:**
```bash
# Create tag manually
VERSION=$(python scripts/bump_version.py --current)
git tag "v$VERSION"
```

**"Working directory has uncommitted changes":**
```bash
# Commit or stash changes first
git status
git add .
git commit -m "Prepare for release"
```

**Build fails:**
```bash
# Check dependencies are installed
uv sync

# Try build-only to see errors
./scripts/publish.sh build
```

**Upload fails with 403:**
- Check your PyPI token is valid
- Verify `~/.pypirc` permissions are 600
- Ensure package name is available (first upload) or you have permissions

**Upload fails with "File already exists":**
- You can't re-upload the same version to PyPI
- Bump the version and try again
- Or use `--skip-existing` flag (not recommended)
