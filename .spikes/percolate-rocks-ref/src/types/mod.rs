//! Core types for REM database.

pub mod entity;
pub mod error;

pub use entity::{Direction, Edge, Entity};
pub use error::{DatabaseError, Result};
