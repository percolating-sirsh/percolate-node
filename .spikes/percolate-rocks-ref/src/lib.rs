//! Percolate Rocks - Rust REM database with PyO3 bindings.

pub mod config;
pub mod embeddings;
pub mod memory;
pub mod models;
pub mod query;
mod storage;
mod types;
mod utils;

#[cfg(feature = "pyo3")]
mod bindings;

// Re-export main types
pub use memory::Database;
pub use types::{Direction, Edge, Entity};

// PyO3 module for Python bindings
#[cfg(feature = "pyo3")]
use pyo3::prelude::*;

#[cfg(feature = "pyo3")]
#[pymodule]
fn _core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<bindings::PyDatabase>()?;
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    Ok(())
}
