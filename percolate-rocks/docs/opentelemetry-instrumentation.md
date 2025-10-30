# OpenTelemetry Instrumentation

This document describes the OpenTelemetry instrumentation added to percolate-rocks.

## Overview

The Rust layer (percolate-rocks) is instrumented with OpenTelemetry using the `tracing` and `tracing-opentelemetry` crates. This provides:

1. **Database semantic conventions** for RocksDB operations
2. **Background job spans** for indexing and embedding operations
3. **Trace context propagation** from Python to Rust

## Architecture

### Instrumentation Location

**Instrumented in Rust** (not Python) for the following reasons:

1. **Complete visibility**: Captures actual Rust execution time, not just Python FFI overhead
2. **Performance accuracy**: Measures where the work happens (RocksDB, vector search, parsing)
3. **Zero-copy overhead**: Minimal performance impact on hot paths
4. **Async-aware**: Properly tracks tokio task boundaries

### Python Layer Role

The Python layer:
1. **Propagates trace context** from FastAPI requests to Rust
2. **Adds high-level spans** for orchestration logic (agent execution, API routing)
3. **Passes trace context** through PyO3 bindings

## Database Semantic Conventions

Following official OpenTelemetry standards:
- https://opentelemetry.io/docs/specs/semconv/database/database-spans/

### Span Naming

Pattern: `{db.operation.name} {target}`

Examples:
- `get articles`
- `put entities`
- `scan resources`
- `batch_write`

### Required Attributes

- `db.system.name`: Always `"rocksdb"`

### Conditionally Required Attributes

- `db.collection.name`: Entity type/schema name (e.g., "articles", "entities")
- `db.namespace`: Database path or tenant ID
- `db.operation.name`: Operation type (get, put, scan, delete, etc.)

### Recommended Attributes

- `db.query.text`: For SQL-like queries
- `server.address`: Database file path
- `db.response.returned_rows`: Number of results returned
- `db.response.affected_rows`: Number of rows modified

## Instrumented Operations

### RocksDB Storage Operations

**File**: `src/storage/db.rs`

Instrumented functions:
- `Storage::get()` - Get single value (span: "get {cf_name}")
- `Storage::put()` - Put single value (span: "put {cf_name}")
- `Storage::delete()` - Delete single value (span: "delete {cf_name}")

**File**: `src/storage/batch.rs`

Instrumented functions:
- `BatchWriter::commit()` - Batch write (span: "batch_write")

### Background Jobs

**File**: `src/admin/indexing.rs`

Instrumented functions:
- `IndexManager::rebuild_hnsw_index()` - HNSW index rebuild (span: "index.build hnsw")
- `IndexManager::rebuild_field_indexes()` - Field index rebuild (span: "index.field.rebuild {schema}")
- `IndexManager::rebuild_key_index()` - Key index rebuild (span: "index.key.rebuild all")

**File**: `src/storage/worker.rs`

Instrumented background tasks:
- `Task::SaveIndex` - Save HNSW index (span: "index.save {schema}")
- `Task::LoadIndex` - Load HNSW index (span: "index.load {schema}")
- `Task::GenerateEmbeddings` - Generate embeddings (span: "embedding.generate {schema}")
- `Task::FlushWal` - Flush WAL (span: "wal.flush wal")
- `Task::CompactCF` - Compact column family (span: "db.compact {cf_name}")

**File**: `src/embeddings/batch.rs`

Instrumented functions:
- `BatchEmbedder::embed_batch()` - Batch embedding (span: "embedding.generate batch")

## Background Job Conventions

Since there are no official OpenTelemetry semantic conventions for background jobs yet, we use:

- **Span kind**: `INTERNAL`
- **Custom attributes**:
  - `job.type`: Type of background job (e.g., "index.build", "embedding.generate")
  - `job.target`: Target resource (schema name, CF name, etc.)
  - `job.batch_size`: Number of items processed
  - `job.duration_ms`: Processing duration in milliseconds
  - `job.status`: Job status ("success", "failed", "partial")

## Trace Context Propagation

### Python to Rust

**Python side** (`percolate/src/memory/resources.py`):

```python
from opentelemetry import trace
from opentelemetry.propagate import inject

def store_resource(tenant_id: str, resource_id: str, data: bytes) -> None:
    """Store resource with trace propagation."""
    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span("memory.store_resource") as span:
        span.set_attribute("tenant_id", tenant_id)

        # Extract trace context to pass to Rust
        carrier = {}
        inject(carrier)

        # Call Rust with trace context
        _percolate_rocks.store_resource_with_trace(
            tenant_id,
            resource_id,
            data,
            carrier  # Pass W3C Trace Context headers
        )
```

**Rust side** (`src/bindings/database.rs`):

```rust
use crate::otel::{attach_trace_context, TraceContext};

#[pyfunction]
fn store_resource_with_trace(
    tenant_id: String,
    resource_id: String,
    data: Vec<u8>,
    trace_context: Option<TraceContext>,
) -> PyResult<()> {
    // Attach trace context (if provided)
    let _guard = attach_trace_context(trace_context);

    // Now all database operations will be child spans
    store_resource(&tenant_id, &resource_id, &data)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))
}
```

### TraceContext Type

**File**: `src/otel/context.rs`

The `TraceContext` class is a PyO3-exposed type that carries W3C Trace Context headers:

```rust
#[pyclass]
pub struct TraceContext {
    /// W3C Trace Context headers
    /// Standard keys: "traceparent", "tracestate"
    pub headers: HashMap<String, String>,
}
```

This is registered in the Python module and can be used from Python:

```python
from percolate_rocks import TraceContext

# Create trace context from OpenTelemetry propagation
carrier = {}
inject(carrier)
trace_ctx = TraceContext(carrier)

# Pass to Rust functions
db.insert_with_trace("articles", data, trace_ctx)
```

## Usage Examples

### Database Operation with Span

```rust
use crate::otel::{db_span, DbOperation, record_db_metrics};

pub fn get_entity(&self, entity_id: Uuid) -> Result<Option<Entity>> {
    // Create database span with semantic conventions
    let _span = db_span(DbOperation::Get, Some("entities"), Some("tenant-123")).entered();

    // Perform operation
    let result = self.storage.get(CF_ENTITIES, &key)?;

    // Record metrics
    if result.is_some() {
        record_db_metrics(Some(1), None);
    }

    Ok(result)
}
```

### Background Job with Metrics

```rust
use crate::otel::{background_span, record_background_metrics, BackgroundJobType};
use std::time::Instant;

pub async fn rebuild_hnsw_index(&self) -> Result<()> {
    let _span = background_span(BackgroundJobType::IndexBuild, "hnsw").entered();

    let start = Instant::now();
    record_background_metrics(None, None, "started");

    // Perform index rebuild
    let vector_count = build_index()?;

    // Record success metrics
    let duration_ms = start.elapsed().as_millis() as u64;
    record_background_metrics(Some(vector_count), Some(duration_ms), "success");

    Ok(())
}
```

### SQL Query Span

```rust
use crate::otel::db_query_span;

pub fn execute_query(&self, sql: &str) -> Result<Vec<Entity>> {
    let _span = db_query_span(sql, "articles", Some("tenant-123")).entered();

    // Execute query
    let results = self.query_executor.execute(sql)?;

    Ok(results)
}
```

## Dependencies

Added to `Cargo.toml`:

```toml
# Observability
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter", "json"] }
tracing-opentelemetry = "0.27"
opentelemetry = { version = "0.27", features = ["trace"] }
opentelemetry_sdk = { version = "0.27", features = ["trace", "rt-tokio"] }
opentelemetry-otlp = { version = "0.27", features = ["trace", "grpc-tonic"] }
opentelemetry-semantic-conventions = "0.27"
```

## Module Structure

```
src/otel/
├── mod.rs           # Module exports
├── db.rs            # Database semantic conventions
├── background.rs    # Background job conventions
└── context.rs       # Trace context propagation (PyO3)
```

## Next Steps

To complete the integration:

1. **Initialize OpenTelemetry in Python**:
   ```python
   from opentelemetry import trace
   from opentelemetry.sdk.trace import TracerProvider
   from opentelemetry.sdk.trace.export import BatchSpanProcessor
   from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

   # Set up OTLP exporter
   provider = TracerProvider()
   processor = BatchSpanProcessor(OTLPSpanExporter())
   provider.add_span_processor(processor)
   trace.set_tracer_provider(provider)
   ```

2. **Initialize tracing-opentelemetry in Rust**:
   ```rust
   use opentelemetry::global;
   use opentelemetry_sdk::trace::TracerProvider;
   use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

   // Set up OpenTelemetry tracer
   let tracer = opentelemetry_otlp::new_pipeline()
       .tracing()
       .with_exporter(opentelemetry_otlp::new_exporter().tonic())
       .install_batch(opentelemetry_sdk::runtime::Tokio)?;

   // Set up tracing subscriber with OpenTelemetry layer
   tracing_subscriber::registry()
       .with(tracing_opentelemetry::layer().with_tracer(tracer))
       .with(tracing_subscriber::fmt::layer())
       .init();
   ```

3. **Update Python bindings** to accept `TraceContext` parameter in all major operations

4. **Add integration tests** to verify trace context flows correctly from Python to Rust

## Performance Impact

The instrumentation is designed for minimal overhead:

- **Zero-cost when disabled**: Tracing spans are zero-cost abstractions when not active
- **Minimal allocation**: Span creation is lightweight (stack-allocated guard)
- **Async-aware**: No blocking operations in hot paths
- **Lazy evaluation**: Span fields only evaluated if span is recorded

Estimated overhead: **< 1% CPU, < 5% latency** in production with reasonable sampling rates.

## Observability Benefits

With this instrumentation, you can:

1. **Trace database operations** end-to-end from Python API to RocksDB
2. **Monitor background job performance** (indexing, embedding generation)
3. **Identify performance bottlenecks** in hot paths
4. **Track distributed traces** across services
5. **Debug production issues** with detailed span context
6. **Analyze query patterns** and optimize based on actual usage

## References

- [OpenTelemetry Database Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/database/database-spans/)
- [tracing crate documentation](https://docs.rs/tracing)
- [tracing-opentelemetry](https://docs.rs/tracing-opentelemetry)
- [W3C Trace Context](https://www.w3.org/TR/trace-context/)
