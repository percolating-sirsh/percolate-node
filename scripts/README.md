# Development scripts

Scripts for version management and release workflows.

## Version bumping

Bump version for a specific project:

```bash
# Patch version (default)
python scripts/bump_version.py percolate

# Minor version
python scripts/bump_version.py percolate --part minor

# Major version
python scripts/bump_version.py percolate --part major

# Dry run
python scripts/bump_version.py percolate-reading --dry-run
```

Show current versions:

```bash
python scripts/bump_version.py show percolate
python scripts/bump_version.py show percolate-reading
python scripts/bump_version.py show percolate-rocks
```

## Creating releases

Check status:

```bash
python scripts/pr.py status
```

Create release commit with tags:

```bash
# Commit and create tags (but don't push)
python scripts/pr.py create

# Commit, tag, and push to trigger builds
python scripts/pr.py create --push

# Skip build tags
python scripts/pr.py create --no-build

# Custom commit message
python scripts/pr.py create --message "Release with new features"
```

## Build workflow

The build process follows this DAG:

```
percolate-rocks (PyPI)
    ↓
    ├─→ percolate (Docker)
    └─→ percolate-reading (Docker)
        ↓
    manifests (K8s)
```

When you push tags, the orchestrator workflow will:

1. Build `percolate-rocks` if version changed
2. Wait for rocks to complete
3. Build `percolate` and `percolate-reading` in parallel (if changed)
4. Update K8s manifests (future)

## Release notes

Release notes are collected from `.release/vX.Y.Z/` directories:

```
percolate/
  .release/
    v0.2.0/
      features.md
      bugfixes.md
      breaking-changes.md
```

The PR script will automatically include these in the commit message.

## Tag formats

- RC builds: `{project}-v{version}-rc{number}`
  - Example: `percolate-v0.2.0-rc1`
  - Triggers build workflows
  - Publishes to production registries (PyPI, GHCR)

- Production: `{project}-v{version}`
  - Example: `percolate-v0.2.0`
  - Triggers release workflows
  - Creates GitHub releases
  - For Docker: retags RC images with clean version
  - For PyPI: package already published (just creates release)
  - Updates K8s manifests (future)

## Dependencies

Install dependencies for scripts:

```bash
pip install typer rich
```
