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
COPY pyproject.toml uv.lock* ./
# Copy readme (handle both cases)
COPY [Rr][Ee][Aa][Dd][Mm][Ee].md ./README.md

# Copy source code (needed for building the package)
COPY src/ ./src/

# Create virtual environment
RUN uv venv

# Install all dependencies from lock file (or pyproject.toml if no lock)
# Use --no-editable to actually install the package (not symlink)
RUN if [ -f uv.lock ]; then \
        uv sync --frozen --no-editable; \
    else \
        uv pip install -e .; \
    fi

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
      org.opencontainers.image.title="Percolate" \
      org.opencontainers.image.description="Privacy-first personal AI infrastructure - main API service"

WORKDIR /app

# Install ONLY runtime dependencies
# Add any system dependencies needed at runtime here
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy application and venv from builder
COPY --from=builder /app /app

# Create directories for storage
RUN mkdir -p /app/.fs/agents /app/.fs/memory /app/.fs/uploads

# Expose API port
EXPOSE 8000

# Set environment for uv cache (avoid permission issues)
ENV UV_CACHE_DIR=/app/.cache/uv

# Set default storage paths
ENV PERCOLATE_STORAGE_PATH=/app/.fs
ENV PERCOLATE_AGENTS_PATH=/app/.fs/agents
ENV PERCOLATE_MEMORY_PATH=/app/.fs/memory

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command runs API server
CMD [".venv/bin/uvicorn", "percolate.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
