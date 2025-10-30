//! Database operation instrumentation.
//!
//! Implements OpenTelemetry semantic conventions for RocksDB operations.

use tracing::{span, Level, Span};

/// Database operation types (maps to `db.operation.name`).
#[derive(Debug, Clone, Copy)]
pub enum DbOperation {
    /// Get single entity by key
    Get,
    /// Put single entity
    Put,
    /// Delete single entity
    Delete,
    /// Scan prefix (iterator)
    Scan,
    /// Batch write
    BatchWrite,
    /// Compaction
    Compact,
}

impl DbOperation {
    /// Get operation name as string.
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Get => "get",
            Self::Put => "put",
            Self::Delete => "delete",
            Self::Scan => "scan",
            Self::BatchWrite => "batch_write",
            Self::Compact => "compact",
        }
    }
}

/// Create database operation span with semantic conventions.
///
/// # Arguments
///
/// * `operation` - Database operation type
/// * `collection` - Entity type/schema name (optional)
/// * `namespace` - Tenant ID or database path (optional)
///
/// # Returns
///
/// Tracing span with OpenTelemetry semantic attributes
///
/// # Example
///
/// ```rust,ignore
/// let span = db_span(DbOperation::Get, Some("articles"), Some("tenant-123"));
/// let _guard = span.entered();
/// ```
pub fn db_span(
    operation: DbOperation,
    collection: Option<&str>,
    namespace: Option<&str>,
) -> Span {
    // Span name: "{operation} {collection}" or just "{operation}"
    let span_name = if let Some(coll) = collection {
        format!("{} {}", operation.as_str(), coll)
    } else {
        operation.as_str().to_string()
    };

    let span = span!(
        Level::INFO,
        "db",
        otel.name = %span_name,
        otel.kind = "client",
        db.system.name = "rocksdb",
        db.operation.name = operation.as_str(),
    );

    // Add optional attributes
    if let Some(coll) = collection {
        span.record("db.collection.name", coll);
    }
    if let Some(ns) = namespace {
        span.record("db.namespace", ns);
    }

    span
}

/// Create database query span (for SQL-like queries).
///
/// # Arguments
///
/// * `query_text` - SQL query text (sanitized)
/// * `collection` - Target collection
/// * `namespace` - Tenant ID (optional)
///
/// # Returns
///
/// Tracing span with query attributes
///
/// # Example
///
/// ```rust,ignore
/// let span = db_query_span(
///     "SELECT * FROM articles WHERE category = 'tech'",
///     "articles",
///     Some("tenant-123")
/// );
/// let _guard = span.entered();
/// ```
pub fn db_query_span(
    query_text: &str,
    collection: &str,
    namespace: Option<&str>,
) -> Span {
    let span = span!(
        Level::INFO,
        "db.query",
        otel.name = format!("query {}", collection),
        otel.kind = "client",
        db.system.name = "rocksdb",
        db.operation.name = "query",
        db.collection.name = collection,
        db.query.text = query_text,
    );

    if let Some(ns) = namespace {
        span.record("db.namespace", ns);
    }

    span
}

/// Record database operation metrics in span.
///
/// # Arguments
///
/// * `rows_returned` - Number of rows/entities returned (optional)
/// * `rows_affected` - Number of rows/entities modified (optional)
///
/// # Example
///
/// ```rust,ignore
/// let span = db_span(DbOperation::Scan, Some("articles"), None);
/// let _guard = span.entered();
///
/// let results = scan_entities()?;
/// record_db_metrics(Some(results.len()), None);
/// ```
pub fn record_db_metrics(rows_returned: Option<usize>, rows_affected: Option<usize>) {
    let span = Span::current();
    if let Some(returned) = rows_returned {
        span.record("db.response.returned_rows", returned);
    }
    if let Some(affected) = rows_affected {
        span.record("db.response.affected_rows", affected);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_db_operation_names() {
        assert_eq!(DbOperation::Get.as_str(), "get");
        assert_eq!(DbOperation::Put.as_str(), "put");
        assert_eq!(DbOperation::Scan.as_str(), "scan");
    }

    #[test]
    fn test_db_span_creation() {
        let span = db_span(DbOperation::Get, Some("articles"), Some("tenant-123"));
        assert_eq!(span.metadata().unwrap().name(), "db");
    }
}
