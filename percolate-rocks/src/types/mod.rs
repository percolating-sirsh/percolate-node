//! Core data types for REM database.
//!
//! Defines fundamental types used throughout the system:
//! - `Entity`: Core data structure with system fields
//! - `Edge`: Graph relationship between entities
//! - `DatabaseError`: Error types for all operations
//! - `Result`: Convenient result type alias
//! - `generate_uuid`: Deterministic UUID generation

pub mod entity;
pub mod error;
pub mod result;
pub mod uuid_gen;

pub use entity::{Entity, Edge, EdgeData, SystemFields, InlineEdge};
pub use error::DatabaseError;
pub use result::Result;
pub use uuid_gen::generate_uuid;
