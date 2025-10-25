//! REM (Resources-Entities-Moments) memory engine
//!
//! This module implements the core memory system with pluggable storage providers.
//!
//! Providers:
//! - RocksDB (default): Embedded, per-tenant isolation
//! - PostgreSQL (enterprise): Shared database, multi-tenant
//!
//! # Query Layer
//!
//! Provides SQL-like predicate interface for flexible queries:
//!
//! ```rust
//! use percolate_rust::memory::{Query, Predicate};
//!
//! let query = Query::new()
//!     .filter(Predicate::Eq("status".into(), Value::String("active".into())))
//!     .filter(Predicate::Gt("age".into(), Value::from(18)))
//!     .order_by("created_at".into(), Order::Desc)
//!     .limit(100);
//! ```

use pyo3::prelude::*;
use std::path::Path;
use thiserror::Error;

pub mod entities;
pub mod moments;
pub mod resources;
pub mod search;

// Storage providers
pub mod provider;
pub mod providers {
    pub mod rocksdb;
    pub mod postgres;
}

// Query layer
pub mod predicates;
pub mod query;

#[derive(Error, Debug)]
pub enum MemoryError {
    #[error("Resource not found: {0}")]
    ResourceNotFound(String),

    #[error("Entity not found: {0}")]
    EntityNotFound(String),

    #[error("Database error: {0}")]
    DatabaseError(String),

    #[error("Invalid tenant: {0}")]
    InvalidTenant(String),
}

pub type Result<T> = std::result::Result<T, MemoryError>;

/// Memory engine for REM operations
///
/// # Example
///
/// ```python
/// from percolate_core import MemoryEngine
///
/// memory = MemoryEngine(db_path="./data/db", tenant_id="user-123")
/// resource_id = memory.create_resource({"content": "Hello"})
/// ```
#[pyclass]
pub struct MemoryEngine {
    db_path: String,
    tenant_id: String,
}

#[pymethods]
impl MemoryEngine {
    /// Initialize memory engine for a tenant
    #[new]
    pub fn new(db_path: String, tenant_id: String) -> PyResult<Self> {
        // Validate paths and initialize RocksDB
        // Implementation placeholder
        Ok(Self { db_path, tenant_id })
    }

    /// Create a resource
    pub fn create_resource(&self, content: String) -> PyResult<String> {
        // Implementation placeholder
        Ok(uuid::Uuid::new_v4().to_string())
    }

    /// Get a resource by ID
    pub fn get_resource(&self, resource_id: String) -> PyResult<String> {
        // Implementation placeholder
        Ok(format!("Resource: {}", resource_id))
    }

    /// Search resources semantically
    pub fn search_resources(&self, query: String, limit: usize) -> PyResult<Vec<String>> {
        // Implementation placeholder
        Ok(vec![])
    }
}
