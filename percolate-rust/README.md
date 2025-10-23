# Percolate Core (Rust)

Rust implementation of performance-critical Percolate components:
- **REM Memory Engine**: RocksDB-backed Resources-Entities-Moments storage
- **Embeddings**: Vector operations and HNSW indexing
- **Parsers**: Fast document parsing (PDF, Excel)
- **Crypto**: Cryptographic primitives (Ed25519, ChaCha20-Poly1305, HKDF)

## Structure

```
percolate-core/
├── src/
│   ├── lib.rs              # Python bindings (PyO3)
│   ├── memory/             # REM engine
│   │   ├── mod.rs
│   │   ├── resources.rs
│   │   ├── entities.rs
│   │   ├── moments.rs
│   │   ├── rocksdb.rs
│   │   └── search.rs
│   ├── embeddings/         # Vector operations
│   │   ├── mod.rs
│   │   ├── models.rs
│   │   └── index.rs
│   ├── parsers/            # Document parsing
│   │   ├── mod.rs
│   │   ├── pdf.rs
│   │   └── excel.rs
│   └── crypto/             # Cryptographic primitives
│       ├── mod.rs
│       ├── keys.rs
│       ├── encryption.rs
│       └── kdf.rs
├── tests/                  # Integration tests
├── benches/                # Performance benchmarks
└── Cargo.toml              # Project manifest
```

## Development

### Build

```bash
# Build library
cargo build --release

# Build Python extension
maturin build --release
```

### Testing

```bash
# Run tests
cargo test

# Run tests with output
cargo test -- --nocapture

# Run specific test
cargo test test_create_resource
```

### Benchmarking

```bash
# Run benchmarks
cargo bench

# Run specific benchmark
cargo bench memory_bench
```

### Code Quality

```bash
# Format
cargo fmt

# Lint
cargo clippy -- -D warnings

# Check
cargo check
```

## Python Integration

This library is exposed to Python via PyO3:

```python
from percolate_core import MemoryEngine, Resource

# Initialize memory engine
memory = MemoryEngine(db_path="./data/percolate.db", tenant_id="user-123")

# Create resource
resource = Resource(content="Hello, world!", metadata={"source": "test"})
resource_id = memory.create_resource(resource)

# Search
results = memory.search_resources(query="Hello", limit=10)
```

## Design Principles

### Performance
- Zero-copy operations where possible
- Async I/O with Tokio
- Efficient serialization with serde
- Batch operations for writes

### Safety
- Leverage Rust's type system
- No `unwrap()` in library code
- Use `Result<T, E>` for fallible operations
- Document panic conditions

### Testing
- Unit tests alongside implementation
- Integration tests in `tests/`
- Property-based testing with proptest
- Benchmarks with criterion

## Dependencies

### Core
- **rocksdb**: Embedded key-value store
- **tokio**: Async runtime
- **serde**: Serialization framework
- **pyo3**: Python bindings

### Crypto
- **ed25519-dalek**: Ed25519 signatures
- **chacha20poly1305**: AEAD encryption
- **sha2**: SHA-256 hashing
- **hkdf**: Key derivation

### Development
- **criterion**: Benchmarking framework
- **proptest**: Property-based testing
- **tempfile**: Temporary files for tests
