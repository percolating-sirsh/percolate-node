//! Percolate REM Database - Rust core library
//!
//! High-performance embedded database combining:
//! - Vector search with HNSW indexing (200x faster than naive scan)
//! - Graph queries with bidirectional edges
//! - SQL predicates on indexed fields
//!
//! This library provides PyO3 bindings for Python integration.

use pyo3::prelude::*;

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
pub mod bindings;

/// PyO3 module definition for Python integration.
///
/// Exposes the Rust implementation as `rem_db._rust` Python module.
#[pymodule]
fn _rust(py: Python, m: &PyModule) -> PyResult<()> {
    bindings::register_module(py, m)?;
    Ok(())
}
