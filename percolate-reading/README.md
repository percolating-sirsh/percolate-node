# Percolate-Reading

Heavy multimedia processing services for Percolate - the **reader node** that handles document parsing, embeddings, OCR, and transcription.

## Overview

Percolate-Reading is a **shared service** in cloud deployments:
- Multiple tenant-specific Percolate (REM) nodes call a shared reading service
- Scales independently from REM nodes
- GPU-accelerated for heavy processing (embeddings, transcription, OCR)
- Stateless design for horizontal scaling

## Deployment Models

### Local (Desktop)

Reading node runs alongside REM node on same machine:
```bash
# Terminal 1: Start REM node
cd percolate
uv run percolate serve

# Terminal 2: Start reading node
cd percolate-reading
uv run percolate-reading serve
```

### Cloud (Shared Service)

Reading nodes deployed separately and shared across tenants:

```
Tenant A Node ──┐
Tenant B Node ──┼──> Reading Service (Kubernetes)
Tenant C Node ──┘     - Load balanced
                      - GPU instances
                      - Auto-scaling
```

**Benefits:**
- Cost-effective: Don't need GPU per tenant
- Scales independently: Add reading capacity based on demand
- Efficient resource utilization: GPU shared across tenants
- Stateless: Easy to scale horizontally

## API Endpoints

### Document Parsing

```bash
# Parse PDF
POST /parse/pdf
Content-Type: multipart/form-data
{
  "file": <binary>,
  "tenant_id": "tenant-123",
  "extract_tables": true,
  "ocr_fallback": true
}

# Parse Excel
POST /parse/excel
Content-Type: multipart/form-data
{
  "file": <binary>,
  "tenant_id": "tenant-123"
}

# Transcribe audio
POST /parse/audio
Content-Type: multipart/form-data
{
  "file": <binary>,
  "tenant_id": "tenant-123",
  "language": "en",
  "diarization": true
}
```

### Embeddings

```bash
# Generate embeddings (batch)
POST /embed/batch
Content-Type: application/json
{
  "texts": ["text1", "text2", ...],
  "model": "nomic-embed-text-v1.5",
  "tenant_id": "tenant-123"
}
```

### OCR

```bash
# Extract text from image
POST /ocr/extract
Content-Type: multipart/form-data
{
  "image": <binary>,
  "tenant_id": "tenant-123",
  "language": "eng"
}
```

### Health

```bash
GET /health
GET /metrics  # Prometheus metrics
```

## Structure

```
percolate-reading/
├── src/percolate_reading/
│   ├── api/                # FastAPI server
│   │   ├── main.py             # Application entry point
│   │   └── routers/            # API route handlers
│   │       ├── parse.py        # Document parsing endpoints
│   │       ├── embed.py        # Embedding endpoints
│   │       └── ocr.py          # OCR endpoints
│   ├── parsers/            # Document parsing implementations
│   │   ├── pdf.py              # PDF parser
│   │   ├── excel.py            # Excel parser
│   │   ├── audio.py            # Audio transcription
│   │   └── models.py           # Parse result models
│   ├── embeddings/         # Embedding model management
│   │   ├── manager.py          # Model loading and caching
│   │   └── models.py           # Supported embedding models
│   ├── ocr/                # OCR services
│   │   ├── tesseract.py        # Tesseract OCR
│   │   └── vision.py           # LLM vision for complex layouts
│   ├── transcription/      # Audio transcription
│   │   ├── whisper.py          # Whisper model
│   │   └── diarization.py      # Speaker diarization
│   ├── cli/                # Command-line interface
│   │   └── main.py             # CLI entry point
│   └── settings.py         # Pydantic settings
└── tests/                  # Test suite
```

## Development

### Setup

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
cd percolate-reading
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# For GPU support (CUDA)
uv pip install -e ".[dev,gpu]"
```

### Running

```bash
# Start reading service
uv run percolate-reading serve --port 8001

# With GPU
uv run percolate-reading serve --port 8001 --device cuda

# With custom models
uv run percolate-reading serve --embedding-model nomic-embed-text-v1.5
```

### Testing

```bash
# Run tests
uv run pytest

# With coverage
uv run pytest --cov=percolate_reading

# Test specific endpoint
uv run pytest tests/api/test_parse.py -v
```

## Configuration

Environment variables (via Pydantic Settings):

```bash
# API
PERCOLATE_READING_HOST=0.0.0.0
PERCOLATE_READING_PORT=8001

# Models
PERCOLATE_READING_EMBEDDING_MODEL=nomic-embed-text-v1.5
PERCOLATE_READING_WHISPER_MODEL=base
PERCOLATE_READING_DEVICE=cpu  # or cuda

# Cache
PERCOLATE_READING_MODEL_CACHE=/var/cache/percolate-reading/models

# Observability
PERCOLATE_READING_OTEL_ENABLED=true
PERCOLATE_READING_OTEL_ENDPOINT=http://localhost:4318
```

## Resource Requirements

### CPU-only (Minimal)

- CPU: 4 cores
- RAM: 8GB
- Disk: 10GB (for models)

### GPU-accelerated (Recommended)

- CPU: 8 cores
- RAM: 16GB
- GPU: NVIDIA with 8GB+ VRAM (e.g., RTX 3060)
- Disk: 20GB (for models)

## Performance

### Throughput (GPU)

| Operation | Throughput | Latency |
|-----------|------------|---------|
| PDF parsing (10 pages) | 50 docs/min | 1-2s |
| Excel parsing (5 sheets) | 100 docs/min | 0.5-1s |
| Audio transcription (1 hour) | 10 files/min | 5-6s |
| Embeddings (batch of 100) | 1000 batches/min | 0.1s |
| OCR (single page) | 200 pages/min | 0.3s |

### Scaling

Horizontal scaling via Kubernetes:
- Stateless design
- Load balanced by gateway
- Auto-scale based on queue depth
- GPU node pools

## Security

### Tenant Isolation

- No persistent storage per tenant
- Tenant ID validated on all requests
- Processing jobs isolated (no shared state)
- Results returned immediately (not stored)

### Data Retention

- No data retained after processing
- Models cached globally (not per-tenant)
- Temporary files cleaned up immediately

## Dependencies

This package depends on `percolate-core` (Rust) for:
- Fast PDF parsing (optional)
- Lightweight crypto operations

See `../percolate-core/` for Rust implementation.
