//! Type conversions between Python and Rust.

use pyo3::prelude::*;
use crate::types::{Entity, Edge};

/// Python wrapper for Entity.
#[pyclass(name = "Entity")]
#[derive(Clone)]
pub struct PyEntity {
    pub inner: Entity,
}

#[pymethods]
impl PyEntity {
    /// Get entity ID.
    #[getter]
    fn id(&self) -> String {
        self.inner.system.id.to_string()
    }

    /// Get entity type.
    #[getter]
    fn entity_type(&self) -> String {
        self.inner.system.entity_type.clone()
    }

    /// Get entity properties as dict.
    #[getter]
    fn properties(&self, py: Python) -> PyResult<PyObject> {
        todo!("Implement PyEntity::properties")
    }

    /// Check if deleted.
    fn is_deleted(&self) -> bool {
        self.inner.is_deleted()
    }
}

/// Python wrapper for Edge.
#[pyclass(name = "Edge")]
#[derive(Clone)]
pub struct PyEdge {
    pub inner: Edge,
}

#[pymethods]
impl PyEdge {
    /// Get source UUID.
    #[getter]
    fn src(&self) -> String {
        self.inner.src.to_string()
    }

    /// Get destination UUID.
    #[getter]
    fn dst(&self) -> String {
        self.inner.dst.to_string()
    }

    /// Get relationship type.
    #[getter]
    fn rel_type(&self) -> String {
        self.inner.rel_type.clone()
    }
}

/// Python wrapper for search result.
#[pyclass(name = "SearchResult")]
pub struct PySearchResult {
    pub entity: PyEntity,
    pub score: f32,
}

#[pymethods]
impl PySearchResult {
    #[getter]
    fn entity(&self) -> PyEntity {
        self.entity.clone()
    }

    #[getter]
    fn score(&self) -> f32 {
        self.score
    }
}

/// Python wrapper for WAL status.
#[pyclass(name = "WalStatus")]
pub struct PyWalStatus {
    pub sequence: u64,
    pub entries: usize,
    pub size_bytes: usize,
}

#[pymethods]
impl PyWalStatus {
    #[getter]
    fn sequence(&self) -> u64 {
        self.sequence
    }

    #[getter]
    fn entries(&self) -> usize {
        self.entries
    }

    #[getter]
    fn size_bytes(&self) -> usize {
        self.size_bytes
    }
}

/// Python wrapper for replication status.
#[pyclass(name = "ReplicationStatus")]
pub struct PyReplicationStatus {
    pub connected: bool,
    pub local_seq: u64,
    pub primary_seq: u64,
    pub lag_ms: u64,
}

#[pymethods]
impl PyReplicationStatus {
    #[getter]
    fn connected(&self) -> bool {
        self.connected
    }

    #[getter]
    fn lag_ms(&self) -> u64 {
        self.lag_ms
    }
}

/// Python wrapper for query plan.
#[pyclass(name = "QueryPlan")]
pub struct PyQueryPlan {
    pub query: String,
    pub confidence: f64,
    pub reasoning: String,
    pub requires_search: bool,
}

#[pymethods]
impl PyQueryPlan {
    #[getter]
    fn query(&self) -> String {
        self.query.clone()
    }

    #[getter]
    fn confidence(&self) -> f64 {
        self.confidence
    }

    #[getter]
    fn reasoning(&self) -> String {
        self.reasoning.clone()
    }

    #[getter]
    fn requires_search(&self) -> bool {
        self.requires_search
    }

    fn is_confident(&self) -> bool {
        self.confidence >= 0.8
    }
}
