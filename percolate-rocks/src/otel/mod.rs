//! OpenTelemetry instrumentation for REM database.
//!
//! Follows OpenTelemetry semantic conventions for database operations:
//! - https://opentelemetry.io/docs/specs/semconv/database/database-spans/
//!
//! # Database Semantic Conventions
//!
//! **Span naming**: `{db.operation.name} {target}`
//! - Example: `get articles`, `scan resources`, `put entities`
//!
//! **Required attributes**:
//! - `db.system.name`: Always `"rocksdb"`
//!
//! **Conditionally required**:
//! - `db.collection.name`: Entity type (schema name)
//! - `db.namespace`: Database path or tenant ID
//! - `db.operation.name`: Operation type (get, put, scan, delete, etc.)
//!
//! **Recommended**:
//! - `db.query.text`: For SQL-like queries
//! - `server.address`: Database file path
//!
//! # Background Job Conventions
//!
//! For background operations (indexing, embedding, compaction):
//! - Use `INTERNAL` span kind
//! - Custom attributes: `job.type`, `job.status`, `job.batch_size`
//!
//! # Example
//!
//! ```rust,ignore
//! use percolate_rocks::otel::{db_span, DbOperation};
//!
//! let span = db_span(DbOperation::Get, "articles", Some("tenant-123"));
//! let _guard = span.entered();
//!
//! // Perform database operation
//! let entity = storage.get(key)?;
//! ```

pub mod db;
pub mod background;
pub mod context;

pub use db::{db_span, db_query_span, record_db_metrics, DbOperation};
pub use background::{background_span, record_background_metrics, BackgroundJobType};
pub use context::{attach_trace_context, extract_trace_context, TraceContext};
