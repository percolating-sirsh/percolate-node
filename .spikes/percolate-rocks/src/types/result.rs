//! Result type alias for convenient error handling.

use super::error::DatabaseError;

/// Result type alias using `DatabaseError` as the error type.
///
/// Used throughout the codebase for consistent error handling.
///
/// # Example
///
/// ```rust,ignore
/// use crate::types::Result;
///
/// fn insert_entity(data: &str) -> Result<Uuid> {
///     let entity = parse_entity(data)?;  // Propagate DatabaseError
///     storage.insert(&entity)?;          // Automatic conversion
///     Ok(entity.id)
/// }
/// ```
pub type Result<T> = std::result::Result<T, DatabaseError>;
