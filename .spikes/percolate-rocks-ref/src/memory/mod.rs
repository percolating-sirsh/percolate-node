//! REM memory layer.

mod database;
mod entities;
mod schema;

pub use database::Database;
pub use entities::EntityStore;
pub use schema::{Schema, SchemaRegistry};
