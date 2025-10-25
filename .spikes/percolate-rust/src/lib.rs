//! Percolate-Rust - Shared Rust components for Percolate packages
//!
//! This library provides performance-critical implementations used by both:
//! - percolate (REM node)
//! - percolate-reading (Reader node)
//!
//! Components:
//! - REM memory engine with pluggable storage providers
//! - Cryptographic primitives (Ed25519, ChaCha20-Poly1305)
//! - Lightweight embeddings (HNSW)
//! - Fast document parsing
//!
//! # Python Bindings
//!
//! Both percolate and percolate-reading can import this module:
//!
//! ```python
//! # In percolate (REM node)
//! from percolate_rust import MemoryEngine, verify_ed25519_signature
//!
//! # In percolate-reading (Reader node)
//! from percolate_rust import parse_pdf, parse_excel
//! ```

use pyo3::prelude::*;

pub mod crypto;
pub mod embeddings;
pub mod memory;
pub mod parsers;

/// Python module definition
#[pymodule]
fn percolate_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Memory engine (for percolate)
    m.add_class::<memory::MemoryEngine>()?;

    // Query layer types (for percolate)
    // TODO: Add PyO3 bindings for Predicate and Query
    // These will be exposed as Python classes to enable:
    //   from percolate_rust import Query, Predicate
    //   query = Query().filter(Predicate.eq("status", "active"))

    // Crypto functions (for percolate)
    m.add_function(wrap_pyfunction!(crypto::verify_ed25519_signature, m)?)?;

    // Parser functions (for percolate-reading) - Future
    // m.add_function(wrap_pyfunction!(parsers::parse_pdf, m)?)?;
    // m.add_function(wrap_pyfunction!(parsers::parse_excel, m)?)?;

    Ok(())
}
