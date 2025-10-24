//! Percolate REM Database - Rust core library
//!
//! High-performance embedded database combining:
//! - Vector search with HNSW indexing (200x faster than naive scan)
//! - Graph queries with bidirectional edges
//! - SQL predicates on indexed fields
//!
//! Can be used as:
//! - Standalone Rust library (cargo build --no-default-features)
//! - Python extension (maturin develop)

pub mod types;
pub mod storage;
pub mod index;
pub mod query;
pub mod embeddings;
pub mod schema;
pub mod graph;
pub mod replication;
pub mod export;
pub mod ingest;
pub mod llm;

// High-level database API
pub mod database;

#[cfg(feature = "python")]
pub mod bindings;

#[cfg(feature = "python")]
use pyo3::prelude::*;

/// PyO3 module definition for Python integration.
///
/// Exposes the Rust implementation as `rem_db._rust` Python module.
///
/// Only available when compiled with the "python" feature (default).
#[cfg(feature = "python")]
#[pymodule]
fn _rust(py: Python, m: &PyModule) -> PyResult<()> {
    bindings::register_module(py, m)?;
    Ok(())
}
