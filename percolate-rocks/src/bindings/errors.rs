//! Error conversions from Rust to Python.

use pyo3::prelude::*;
use pyo3::exceptions::{PyValueError, PyIOError, PyRuntimeError};
use crate::types::DatabaseError;

/// Convert DatabaseError to PyErr.
impl From<DatabaseError> for PyErr {
    fn from(err: DatabaseError) -> PyErr {
        match err {
            DatabaseError::EntityNotFound(_) => PyValueError::new_err(err.to_string()),
            DatabaseError::SchemaNotFound(_) => PyValueError::new_err(err.to_string()),
            DatabaseError::ValidationError(_) => PyValueError::new_err(err.to_string()),
            DatabaseError::InvalidKey(_) => PyValueError::new_err(err.to_string()),
            DatabaseError::IoError(_) => PyIOError::new_err(err.to_string()),
            _ => PyRuntimeError::new_err(err.to_string()),
        }
    }
}

/// Create custom Python exception types.
pub fn create_exception_types(py: Python, m: &PyModule) -> PyResult<()> {
    // TODO: Create custom exception classes
    Ok(())
}
