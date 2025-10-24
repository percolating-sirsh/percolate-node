//! Core data types for REM database.
//!
//! Defines fundamental types used throughout the system:
//! - `Entity`: Core data structure with system fields
//! - `Edge`: Graph relationship between entities
//! - `DatabaseError`: Error types for all operations
//! - `Result`: Convenient result type alias

pub mod entity;
pub mod error;
pub mod result;

pub use entity::{Entity, Edge, EdgeData, SystemFields};
pub use error::DatabaseError;
pub use result::Result;
