# PyPI Publishing Guide for percolate-rocks

## Summary

**percolate-rocks is now ready for PyPI!**

Users can `pip install percolate-rocks` and use it immediately **without downloading any models**. Embeddings are optional and only download models (~100MB) when explicitly enabled.

## Key Features

✅ **Optional embeddings** - Works without any model downloads by default
✅ **Model caching** - Models cached to `~/.p8/models/` (via `HF_HOME`)
✅ **Fast installation** - Only Rust binary wheel, no Python dependencies
✅ **OpenAI-compatible** - Can use OpenAI embeddings instead of local models
✅ **Multi-platform** - maturin builds wheels for Linux, macOS, Windows

## Usage Modes

### Mode 1: Without embeddings (default, fastest)

```python
from percolate_rocks import REMDatabase

# No model downloads - immediate start
db = REMDatabase("tenant", "./db", enable_embeddings=False)

# Use with OpenAI or other embedding services
# (embeddings managed externally)
```

### Mode 2: With local embeddings

```python
from percolate_rocks import REMDatabase

# Downloads model to ~/.p8/models/ on first use
db = REMDatabase("tenant", "./db", enable_embeddings=True)

# Automatic embedding generation
entity_id = await db.insert_with_embedding(
    "resources",
    {"content": "This text will be embedded automatically"}
)
```

### Mode 3: Custom model cache location

```bash
# Set before importing
export HF_HOME=/custom/path/to/models
```

```python
from percolate_rocks import REMDatabase

db = REMDatabase("tenant", "./db", enable_embeddings=True)
# Models will be cached to /custom/path/to/models/
```

## Publishing to PyPI

### 1. Update metadata in pyproject.toml

```toml
[project]
name = "percolate-rocks"
version = "0.1.0"
description = "Fast REM database with Rust backend and optional embeddings"
readme = "README.md"
requires-python = ">=3.8"
dependencies = []
license = {text = "MIT"}
authors = [
    {name = "Your Name", email = "your@email.com"}
]
keywords = ["database", "embeddings", "rust", "rocksdb", "vector-database"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Rust",
]

[project.urls]
Homepage = "https://github.com/yourusername/percolate-rocks"
Documentation = "https://github.com/yourusername/percolate-rocks/blob/main/README.md"
Repository = "https://github.com/yourusername/percolate-rocks"
Issues = "https://github.com/yourusername/percolate-rocks/issues"
```

### 2. Build wheels for multiple platforms

Using GitHub Actions or local builds:

```bash
# macOS ARM64 (M1/M2)
maturin build --release --features pyo3,async --target aarch64-apple-darwin

# macOS x86_64 (Intel)
maturin build --release --features pyo3,async --target x86_64-apple-darwin

# Linux x86_64 (manylinux)
docker run --rm -v $(pwd):/io ghcr.io/pyo3/maturin build --release --features pyo3,async

# Windows x86_64
maturin build --release --features pyo3,async --target x86_64-pc-windows-msvc
```

Or use maturin's CI tool:

```bash
maturin upload --repository testpypi dist/*
```

### 3. Test on TestPyPI

```bash
# Upload to TestPyPI
maturin publish --repository testpypi

# Install and test
pip install --index-url https://test.pypi.org/simple/ percolate-rocks
python -c "from percolate_rocks import REMDatabase; print('✓ Works!')"
```

### 4. Publish to PyPI

```bash
# Build all wheels
maturin build --release --features pyo3,async

# Publish to PyPI
maturin publish
```

## Installation for end users

```bash
# Basic installation (no dependencies)
pip install percolate-rocks

# With optional embedding models (first use downloads ~100MB)
pip install percolate-rocks
export ENABLE_EMBEDDINGS=true  # or pass enable_embeddings=True
```

## Model Download Details

When `enable_embeddings=True`:

1. **Model**: sentence-transformers/all-MiniLM-L6-v2
2. **Size**: ~100MB (ONNX format)
3. **Location**: `~/.p8/models/` (or `$HF_HOME`)
4. **Download**: Only on first use
5. **Reuse**: Cached for all future uses

## FAQ

### Q: Do I need to download models to use percolate-rocks?

**A: No!** By default, embeddings are enabled but the package works fine without them. You can:
- Use `enable_embeddings=False` for no model downloads
- Use OpenAI or other embedding services externally
- Only enable local embeddings when needed

### Q: Where are models cached?

**A:** Models are cached to `~/.p8/models/` by default (via `HF_HOME` environment variable). You can change this:

```bash
export HF_HOME=/custom/path
```

### Q: Can I use my own embedding model?

**A:** Currently only `sentence-transformers/all-MiniLM-L6-v2` is supported. In the future, we'll support:
- Custom model names
- OpenAI embeddings
- Cohere embeddings
- Custom embedding providers

### Q: What happens if model download fails?

**A:** The database constructor will raise a `RuntimeError` with details. The database works fine without embeddings - just set `enable_embeddings=False`.

### Q: Can I pre-download models?

**A:** Yes! Set `HF_HOME` and run:

```python
from percolate_rocks import REMDatabase
import tempfile

# This will download the model
with tempfile.TemporaryDirectory() as tmpdir:
    db = REMDatabase("test", tmpdir, enable_embeddings=True)
    print("Model downloaded!")
```

## Next Steps

After publishing to PyPI:

1. **Documentation**: Add detailed docs to README.md
2. **Examples**: Add more usage examples
3. **OpenAI integration**: Add support for OpenAI embeddings
4. **Custom models**: Support other embedding models
5. **Model preloading**: Provide CLI to pre-download models

## Summary

**You're ready to publish!** The package:

✅ Installs quickly (no model downloads by default)
✅ Works immediately (embeddings optional)
✅ Caches models efficiently (~/.p8/models/)
✅ Supports external embedding services
✅ Has proper Python type stubs
✅ Builds for multiple platforms

Just update pyproject.toml metadata and run `maturin publish`!
