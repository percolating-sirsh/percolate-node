# Percolate Python Package

Python implementation of Percolate - the API server, agent runtime, and orchestration layer.

## Structure

```
percolate/
├── src/percolate/          # Main package
│   ├── api/                # FastAPI server
│   ├── auth/               # OAuth 2.1 authentication
│   ├── agents/             # Agent-let runtime
│   ├── memory/             # REM database interface (wraps Rust)
│   ├── parsers/            # Document parsing orchestration
│   ├── mcp/                # Model Context Protocol server
│   ├── cli/                # Command-line interface
│   ├── otel/               # OpenTelemetry instrumentation
│   └── settings.py         # Configuration
├── tests/                  # Test suite
│   ├── unit/               # Unit tests
│   └── integration/        # Integration tests
└── pyproject.toml          # Project configuration
```

## Development

### Setup

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
cd percolate
uv venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows
uv pip install -e ".[dev]"
```

### Running

```bash
# Start API server
uv run percolate serve

# CLI commands
uv run percolate --help
```

### Testing

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=percolate --cov-report=html

# Run specific test
uv run pytest tests/unit/agents/test_factory.py -v
```

### Code Quality

```bash
# Format code
uv run black src tests

# Lint
uv run ruff check src tests

# Type check
uv run mypy src
```

## Dependencies

This package depends on `percolate-core` (Rust) for:
- REM memory engine
- Vector embeddings
- Document parsing (fast path)
- Cryptographic operations

See `../percolate-core/` for Rust implementation.
