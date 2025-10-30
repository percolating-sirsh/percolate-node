//! PyO3 Python bindings.
//!
//! Thin translation layer between Python and Rust.

use crate::otel::TraceContext;
use pyo3::prelude::*;

pub mod database;
pub mod types;
pub mod errors;
pub mod async_ops;

pub use database::PyDatabase;
pub use types::*;
pub use errors::*;

/// Register Python module with all bindings.
///
/// # Arguments
///
/// * `py` - Python interpreter
/// * `m` - Python module
///
/// # Errors
///
/// Returns `PyErr` if registration fails
pub fn register_module(py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<PyDatabase>()?;
    m.add_class::<PyEntity>()?;
    m.add_class::<PyEdge>()?;
    m.add_class::<PySearchResult>()?;
    m.add_class::<PyWalStatus>()?;
    m.add_class::<PyReplicationStatus>()?;
    m.add_class::<PyQueryPlan>()?;
    m.add_class::<TraceContext>()?;
    Ok(())
}
