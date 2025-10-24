//! Error types for REM database.

use thiserror::Error;

pub type Result<T> = std::result::Result<T, DatabaseError>;

#[derive(Error, Debug)]
pub enum DatabaseError {
    #[error("Schema not found: {0}")]
    SchemaNotFound(String),

    #[error("Entity not found: {0}")]
    EntityNotFound(uuid::Uuid),

    #[error("Validation error: {0}")]
    ValidationError(String),

    #[error("Query error: {0}")]
    QueryError(String),

    #[error("Storage error: {0}")]
    StorageError(String),

    #[error("Serialization error: {0}")]
    SerializationError(String),

    #[error("RocksDB error: {0}")]
    RocksDbError(#[from] rocksdb::Error),

    #[error("JSON error: {0}")]
    JsonError(#[from] serde_json::Error),

    #[error("Bincode error: {0}")]
    BincodeError(#[from] bincode::Error),

    #[error("UUID error: {0}")]
    UuidError(#[from] uuid::Error),

    #[error("JSON Schema error: {0}")]
    JsonSchemaError(String),

    #[error("Embedding error: {0}")]
    EmbeddingError(String),

    #[error("Configuration error: {0}")]
    ConfigError(String),

    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),

    #[error("Internal error: {0}")]
    InternalError(String),
}

impl From<jsonschema::ValidationError<'_>> for DatabaseError {
    fn from(err: jsonschema::ValidationError) -> Self {
        DatabaseError::ValidationError(err.to_string())
    }
}
