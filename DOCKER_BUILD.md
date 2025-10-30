# Docker image builds

Build documentation for Percolate Docker images with multi-platform support.

## Quick reference

**Registry**: `percolationlabs` on Docker Hub

**Images**:
- `percolate/percolate` - Main API service
- `percolate/percolate-reading` - Document parsing and reading service

**Supported platforms**:
- `linux/amd64` (x86_64)
- `linux/arm64` (ARM64, Apple Silicon)

## Prerequisites

### Docker Buildx setup

Docker Buildx is required for multi-platform builds. It comes bundled with Docker Desktop.

```bash
# Verify buildx is available
docker buildx version

# Create and use a new builder instance
docker buildx create --name percolate-builder --use

# Bootstrap the builder
docker buildx inspect --bootstrap
```

### Docker Hub authentication

```bash
# Login to Docker Hub
docker login

# Verify authentication
docker info | grep Username
```

## Building images

### Main API service (percolate)

**Location**: `percolate/Dockerfile`

**Multi-platform build and push**:
```bash
cd percolate

# Build for both amd64 and arm64, push to registry
docker buildx build --platform linux/amd64,linux/arm64 \
  -t percolate/percolate:latest \
  -t percolate/percolate:v0.3.2 \
  --push .
```

**Single platform build (local testing)**:
```bash
cd percolate

# Build for current platform only
docker build -t percolate/percolate:latest .

# Test locally
docker run -p 8000:8000 percolate/percolate:latest
```

**Build with metadata**:
```bash
cd percolate

docker buildx build --platform linux/amd64,linux/arm64 \
  -t percolate/percolate:latest \
  -t percolate/percolate:v0.3.2 \
  --build-arg VERSION=v0.3.2 \
  --build-arg BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ") \
  --build-arg GIT_COMMIT=$(git rev-parse --short HEAD) \
  --push .
```

### Reading service (percolate-reading)

**Location**: `percolate-reading/Dockerfile`

**Multi-platform build and push**:
```bash
cd percolate-reading

# Build for both amd64 and arm64, push to registry
docker buildx build --platform linux/amd64,linux/arm64 \
  -t percolate/percolate-reading:latest \
  -t percolate/percolate-reading:v0.3.2 \
  --push .
```

**Single platform build (local testing)**:
```bash
cd percolate-reading

# Build for current platform only
docker build -t percolate/percolate-reading:latest .

# Test locally
docker run -p 8001:8001 percolate/percolate-reading:latest
```

**Build with metadata**:
```bash
cd percolate-reading

docker buildx build --platform linux/amd64,linux/arm64 \
  -t percolate/percolate-reading:latest \
  -t percolate/percolate-reading:v0.3.2 \
  --build-arg VERSION=v0.3.2 \
  --build-arg BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ") \
  --build-arg GIT_COMMIT=$(git rev-parse --short HEAD) \
  --push .
```

## Build automation script

Create `scripts/build-docker.sh`:

```bash
#!/bin/bash
set -euo pipefail

VERSION=${1:-latest}
GIT_COMMIT=$(git rev-parse --short HEAD)
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "Building Percolate Docker images"
echo "Version: ${VERSION}"
echo "Commit: ${GIT_COMMIT}"
echo "Date: ${BUILD_DATE}"

# Build percolate main API
echo ""
echo "Building percolate..."
cd percolate
docker buildx build --platform linux/amd64,linux/arm64 \
  -t percolate/percolate:latest \
  -t percolate/percolate:${VERSION} \
  --build-arg VERSION=${VERSION} \
  --build-arg BUILD_DATE=${BUILD_DATE} \
  --build-arg GIT_COMMIT=${GIT_COMMIT} \
  --push .
cd ..

# Build percolate-reading service
echo ""
echo "Building percolate-reading..."
cd percolate-reading
docker buildx build --platform linux/amd64,linux/arm64 \
  -t percolate/percolate-reading:latest \
  -t percolate/percolate-reading:${VERSION} \
  --build-arg VERSION=${VERSION} \
  --build-arg BUILD_DATE=${BUILD_DATE} \
  --build-arg GIT_COMMIT=${GIT_COMMIT} \
  --push .
cd ..

echo ""
echo "Build complete!"
echo "Images pushed:"
echo "  - percolate/percolate:${VERSION}"
echo "  - percolate/percolate-reading:${VERSION}"
```

**Usage**:
```bash
# Build and push with version tag
./scripts/build-docker.sh v0.3.2

# Build and push as latest
./scripts/build-docker.sh latest
```

## Tagging strategy

### Version tags
- `latest` - Latest stable release
- `v0.3.2` - Specific version (semantic versioning)
- `v0.3` - Minor version
- `v0` - Major version

### Development tags
- `dev` - Development builds (unstable)
- `main` - Builds from main branch
- `pr-123` - Pull request builds

### Example tagging
```bash
# Release v0.3.2
docker buildx build --platform linux/amd64,linux/arm64 \
  -t percolate/percolate:latest \
  -t percolate/percolate:v0.3.2 \
  -t percolate/percolate:v0.3 \
  -t percolate/percolate:v0 \
  --push .

# Development build
docker buildx build --platform linux/amd64,linux/arm64 \
  -t percolate/percolate:dev \
  --push .
```

## Image verification

### Inspect image metadata
```bash
# View image labels
docker inspect percolate/percolate:latest | jq '.[0].Config.Labels'

# View image platforms
docker buildx imagetools inspect percolate/percolate:latest
```

### Test image locally
```bash
# Pull and run
docker pull percolate/percolate:latest
docker run -p 8000:8000 percolate/percolate:latest

# Check health
curl http://localhost:8000/health
```

## CI/CD integration

### GitHub Actions workflow

See `.github/workflows/build-percolate.yml` and `.github/workflows/build-reading.yml`.

**Workflow triggers**:
- Push to `main` branch → build `latest` and `main` tags
- Push tag `v*` → build versioned release
- Pull request → build `pr-<number>` tag (no push)

**Example workflow excerpt**:
```yaml
- name: Build and push Docker image
  uses: docker/build-push-action@v5
  with:
    context: ./percolate
    platforms: linux/amd64,linux/arm64
    push: true
    tags: |
      percolate/percolate:latest
      percolate/percolate:${{ github.ref_name }}
    build-args: |
      VERSION=${{ github.ref_name }}
      BUILD_DATE=${{ steps.date.outputs.date }}
      GIT_COMMIT=${{ github.sha }}
```

## Kubernetes deployment

After building and pushing images, update Kubernetes manifests:

```bash
# Update image tags in manifests
kubectl set image statefulset/api-small \
  api=percolate/percolate:v0.3.2 \
  -n percolate

kubectl set image deployment/gateway \
  gateway=percolate/percolate-reading:v0.3.2 \
  -n percolate
```

Or update via Kustomize:
```yaml
# k8s/overlays/production/kustomization.yaml
images:
- name: percolate/percolate
  newTag: v0.3.2
- name: percolate/percolate-reading
  newTag: v0.3.2
```

## Troubleshooting

### Buildx not available
```bash
# Install buildx plugin
docker buildx install

# Or use Docker Desktop (includes buildx)
```

### Multi-platform build fails
```bash
# Ensure QEMU emulators are installed
docker run --privileged --rm tonistiigi/binfmt --install all

# Verify platforms
docker buildx ls
```

### Authentication errors
```bash
# Re-authenticate with Docker Hub
docker logout
docker login

# Check credentials
cat ~/.docker/config.json
```

### Build cache issues
```bash
# Clear build cache
docker buildx prune -af

# Build without cache
docker buildx build --no-cache ...
```

## Security considerations

### Image scanning

```bash
# Scan for vulnerabilities (requires Docker Scout or Trivy)
docker scout cves percolate/percolate:latest

# Or with Trivy
trivy image percolate/percolate:latest
```

### Supply chain security

- Use official base images (`python:3.12-slim`)
- Pin dependency versions in `uv.lock`
- Use multi-stage builds (smaller attack surface)
- Run as non-root user
- Read-only root filesystem

### Secrets management

**Never** include secrets in Docker images. Use:
- Kubernetes Secrets
- OpenBao/Vault
- Environment variables at runtime

## Image size optimization

Current image sizes (approximate):
- `percolate`: ~300MB (base) + ~150MB (dependencies)
- `percolate-reading`: ~400MB (includes tesseract, pandoc)

**Optimization tips**:
1. Use `.dockerignore` to exclude unnecessary files
2. Multi-stage builds (already implemented)
3. Minimize runtime dependencies
4. Use `slim` base images (already implemented)

## References

- [Docker Buildx documentation](https://docs.docker.com/buildx/working-with-buildx/)
- [Multi-platform images](https://docs.docker.com/build/building/multi-platform/)
- [Docker Hub percolationlabs](https://hub.docker.com/u/percolationlabs)
- [GitHub Actions Docker build](https://github.com/docker/build-push-action)
