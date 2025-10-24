//! Error types for REM database operations.
//!
//! Uses `thiserror` for ergonomic error definitions with automatic `From` implementations.

use thiserror::Error;
use uuid::Uuid;

/// Comprehensive error type for all database operations.
///
/// Provides detailed error messages with context for debugging and user feedback.
#[derive(Error, Debug)]
pub enum DatabaseError {
    /// Entity not found by ID
    #[error("Entity not found: {0}")]
    EntityNotFound(Uuid),

    /// Schema not registered
    #[error("Schema not registered: {0}")]
    SchemaNotFound(String),

    /// Schema validation failed
    #[error("Schema validation failed: {0}")]
    ValidationError(String),

    /// Invalid key format
    #[error("Invalid key format: {0}")]
    InvalidKey(String),

    /// Embedding generation failed
    #[error("Embedding generation failed: {0}")]
    EmbeddingError(String),

    /// Vector search failed
    #[error("Vector search failed: {0}")]
    SearchError(String),

    /// SQL parsing failed
    #[error("SQL parsing failed: {0}")]
    ParseError(String),

    /// Query execution failed
    #[error("Query execution failed: {0}")]
    QueryError(String),

    /// Graph traversal failed
    #[error("Graph traversal failed: {0}")]
    GraphError(String),

    /// Replication error
    #[error("Replication error: {0}")]
    ReplicationError(String),

    /// WAL (Write-Ahead Log) error
    #[error("WAL error: {0}")]
    WalError(String),

    /// Export operation failed
    #[error("Export failed: {0}")]
    ExportError(String),

    /// Document ingestion failed
    #[error("Ingest failed: {0}")]
    IngestError(String),

    /// LLM query building failed
    #[error("LLM query building failed: {0}")]
    LlmError(String),

    /// Storage layer error (RocksDB)
    #[error("Storage error: {0}")]
    StorageError(#[from] rocksdb::Error),

    /// JSON serialization/deserialization error
    #[error("JSON error: {0}")]
    JsonError(#[from] serde_json::Error),

    /// Bincode serialization error
    #[error("Bincode error: {0}")]
    BincodeError(#[from] bincode::Error),

    /// I/O error
    #[error("I/O error: {0}")]
    IoError(#[from] std::io::Error),

    /// HTTP client error (for embedding APIs)
    #[error("HTTP error: {0}")]
    HttpError(#[from] reqwest::Error),

    /// gRPC error (for replication)
    #[error("gRPC error: {0}")]
    GrpcError(String),

    /// Configuration error
    #[error("Configuration error: {0}")]
    ConfigError(String),

    /// Internal error (should not happen)
    #[error("Internal error: {0}")]
    InternalError(String),
}

impl DatabaseError {
    /// Create a validation error with context.
    ///
    /// # Arguments
    ///
    /// * `msg` - Error message
    ///
    /// # Returns
    ///
    /// `DatabaseError::ValidationError`
    pub fn validation(msg: impl Into<String>) -> Self {
        Self::ValidationError(msg.into())
    }

    /// Create a query error with context.
    ///
    /// # Arguments
    ///
    /// * `msg` - Error message
    ///
    /// # Returns
    ///
    /// `DatabaseError::QueryError`
    pub fn query(msg: impl Into<String>) -> Self {
        Self::QueryError(msg.into())
    }

    /// Check if error is recoverable.
    ///
    /// # Returns
    ///
    /// `true` if operation can be retried, `false` otherwise
    pub fn is_recoverable(&self) -> bool {
        matches!(
            self,
            Self::HttpError(_) | Self::ReplicationError(_) | Self::GrpcError(_)
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_error_creation() {
        let uuid = Uuid::new_v4();
        let err = DatabaseError::EntityNotFound(uuid);
        assert_eq!(err.to_string(), format!("Entity not found: {}", uuid));

        let err = DatabaseError::validation("Invalid field");
        assert_eq!(err.to_string(), "Schema validation failed: Invalid field");

        let err = DatabaseError::query("Parse failed");
        assert_eq!(err.to_string(), "Query execution failed: Parse failed");
    }

    #[test]
    fn test_error_from_conversions() {
        // Test JSON error conversion
        let json_err = serde_json::from_str::<serde_json::Value>("invalid json");
        assert!(json_err.is_err());
        let db_err: DatabaseError = json_err.unwrap_err().into();
        assert!(matches!(db_err, DatabaseError::JsonError(_)));

        // Test I/O error conversion
        let io_err = std::io::Error::new(std::io::ErrorKind::NotFound, "file not found");
        let db_err: DatabaseError = io_err.into();
        assert!(matches!(db_err, DatabaseError::IoError(_)));
    }

    #[test]
    fn test_is_recoverable() {
        let recoverable = DatabaseError::ReplicationError("network timeout".to_string());
        assert!(recoverable.is_recoverable());

        let non_recoverable = DatabaseError::ValidationError("invalid schema".to_string());
        assert!(!non_recoverable.is_recoverable());

        let non_recoverable = DatabaseError::EntityNotFound(Uuid::new_v4());
        assert!(!non_recoverable.is_recoverable());
    }
}
