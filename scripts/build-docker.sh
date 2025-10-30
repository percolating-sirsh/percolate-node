#!/bin/bash
set -euo pipefail

# Percolate Docker multi-platform build script
# Builds and pushes both percolate and percolate-reading images

VERSION=${1:-latest}
GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
PUSH=${PUSH:-true}

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Percolate Docker Multi-Platform Build${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}Configuration:${NC}"
echo "  Version: ${VERSION}"
echo "  Commit: ${GIT_COMMIT}"
echo "  Date: ${BUILD_DATE}"
echo "  Push: ${PUSH}"
echo ""

# Check prerequisites
if ! command -v docker &> /dev/null; then
    echo "Error: docker not found"
    exit 1
fi

if ! docker buildx version &> /dev/null; then
    echo "Error: docker buildx not available"
    echo "Install with: docker buildx install"
    exit 1
fi

# Ensure buildx builder exists and is running
if ! docker buildx ls | grep -q percolate-builder; then
    echo -e "${YELLOW}Creating buildx builder 'percolate-builder'...${NC}"
    docker buildx create --name percolate-builder --use
    docker buildx inspect --bootstrap
else
    echo -e "${GREEN}Using existing buildx builder 'percolate-builder'${NC}"
    docker buildx use percolate-builder
fi

# Build arguments
PLATFORMS="linux/amd64,linux/arm64"
BUILD_ARGS="--build-arg VERSION=${VERSION} --build-arg BUILD_DATE=${BUILD_DATE} --build-arg GIT_COMMIT=${GIT_COMMIT}"

# Determine push flag
if [ "${PUSH}" = "true" ]; then
    PUSH_FLAG="--push"
    echo -e "${YELLOW}Images will be pushed to registry${NC}"
else
    PUSH_FLAG="--load"
    echo -e "${YELLOW}Images will be loaded locally (single platform only)${NC}"
    PLATFORMS="linux/amd64"  # --load only supports single platform
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Building percolate (main API)${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

cd percolate

docker buildx build \
    --platform ${PLATFORMS} \
    -t percolate/percolate:latest \
    -t percolate/percolate:${VERSION} \
    ${BUILD_ARGS} \
    ${PUSH_FLAG} \
    .

cd ..

echo ""
echo -e "${GREEN}✓ percolate build complete${NC}"
echo ""

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Building percolate-reading${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

cd percolate-reading

docker buildx build \
    --platform ${PLATFORMS} \
    -t percolate/percolate-reading:latest \
    -t percolate/percolate-reading:${VERSION} \
    ${BUILD_ARGS} \
    ${PUSH_FLAG} \
    .

cd ..

echo ""
echo -e "${GREEN}✓ percolate-reading build complete${NC}"
echo ""

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Build Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}Images built successfully:${NC}"
echo "  percolate/percolate:${VERSION}"
echo "  percolate/percolate-reading:${VERSION}"
echo ""

if [ "${PUSH}" = "true" ]; then
    echo -e "${GREEN}Images pushed to Docker Hub${NC}"
    echo ""
    echo "Verify images:"
    echo "  docker buildx imagetools inspect percolate/percolate:${VERSION}"
    echo "  docker buildx imagetools inspect percolate/percolate-reading:${VERSION}"
else
    echo -e "${GREEN}Images loaded locally${NC}"
    echo ""
    echo "Test images:"
    echo "  docker run -p 8000:8000 percolate/percolate:${VERSION}"
    echo "  docker run -p 8001:8001 percolate/percolate-reading:${VERSION}"
fi

echo ""
echo -e "${GREEN}Build complete!${NC}"
