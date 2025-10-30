# =============================================================================
# Percolate Reading Service
# =============================================================================
#
# IMPORTANT: We use TWO registries:
#   - ghcr.io/percolate/percolate-reading (GitHub Container Registry - CI/CD)
#   - percolate/percolate-reading (Docker Hub - manual testing/development)
#
# Multi-platform build command (Docker Hub):
#   docker buildx build --platform linux/amd64,linux/arm64 \
#     -t percolate/percolate-reading:latest \
#     -t percolate/percolate-reading:v0.3.2 \
#     --push .
#
# Multi-platform build command (GHCR - production):
#   docker buildx build --platform linux/amd64,linux/arm64 \
#     -t ghcr.io/percolate/percolate-reading:latest \
#     -t ghcr.io/percolate/percolate-reading:v0.3.2 \
#     --push .
#
# Single platform build (local testing):
#   docker build -t percolate/percolate-reading:latest .
#
# =============================================================================
# Builder Stage - Install dependencies with build tools
# =============================================================================
FROM python:3.12-slim AS builder

WORKDIR /app

# Install system dependencies and build tools
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml uv.lock ./
# Copy readme (handles both readme.md and README.md)
COPY readme.md ./README.md

# Copy source code (needed for building the package)
COPY src/ ./src/

# Create virtual environment
RUN uv venv

# Install all dependencies from lock file
# Use --no-editable to actually install the package (not symlink)
RUN uv sync --frozen --no-editable

# =============================================================================
# Runtime Stage - Minimal runtime dependencies only
# =============================================================================
FROM python:3.12-slim

# Build arguments
ARG VERSION=dev
ARG BUILD_DATE
ARG GIT_COMMIT

# Add labels
LABEL version="${VERSION}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${GIT_COMMIT}" \
      org.opencontainers.image.title="Percolate Reading" \
      org.opencontainers.image.description="Document parsing and processing service"

WORKDIR /app

# Install ONLY runtime dependencies (no build-essential)
# tesseract-ocr: OCR support
# pandoc: Document conversion (future)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    pandoc \
    && rm -rf /var/lib/apt/lists/*

# Copy application and venv from builder
COPY --from=builder /app /app

# Create directories for storage
RUN mkdir -p /app/.fs/parse-jobs /app/.fs/reader-db /app/.fs/model-cache

# Expose API port
EXPOSE 8001

# Set environment for uv cache (avoid permission issues)
ENV UV_CACHE_DIR=/app/.cache/uv

# Set default storage paths
ENV PERCOLATE_READING_STORAGE_PATH=/app/.fs/parse-jobs
ENV PERCOLATE_READING_DB_PATH=/app/.fs/reader-db
ENV PERCOLATE_READING_MODEL_CACHE_DIR=/app/.fs/model-cache

# Default command runs gateway mode
# Override with docker run command for worker mode
CMD [".venv/bin/python", "-m", "percolate_reading.cli.main", "serve"]
