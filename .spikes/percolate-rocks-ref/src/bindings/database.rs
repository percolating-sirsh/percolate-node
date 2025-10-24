//! Python database bindings.

use crate::memory::Database;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use std::sync::Arc;

/// Python-wrapped REM Database.
#[pyclass(name = "REMDatabase")]
pub struct PyDatabase {
    inner: Arc<Database>,
}

#[pymethods]
impl PyDatabase {
    #[new]
    #[pyo3(signature = (tenant_id, path, enable_embeddings=true))]
    pub fn new(tenant_id: String, path: String, enable_embeddings: bool) -> PyResult<Self> {
        let db = Database::open_with_embeddings(&path, &tenant_id, enable_embeddings)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

        Ok(Self {
            inner: Arc::new(db),
        })
    }

    /// Insert entity.
    #[pyo3(text_signature = "($self, table, properties)")]
    pub fn insert(&self, table: String, properties: &PyDict) -> PyResult<String> {
        let props: serde_json::Value = pythonize::depythonize(properties)?;

        let entity_id = self
            .inner
            .insert_entity(&table, props)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

        Ok(entity_id.to_string())
    }

    /// Get entity by ID.
    #[pyo3(text_signature = "($self, entity_id)")]
    pub fn get(&self, py: Python, entity_id: String) -> PyResult<Option<PyObject>> {
        let id = uuid::Uuid::parse_str(&entity_id)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))?;

        let entity = self
            .inner
            .get_entity(id)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

        match entity {
            Some(e) => {
                let py_obj = pythonize::pythonize(py, &e)?;
                Ok(Some(py_obj))
            }
            None => Ok(None),
        }
    }

    /// Register schema.
    #[pyo3(signature = (name, schema, indexed_fields=None, embedding_fields=None))]
    pub fn register_schema(
        &self,
        name: String,
        schema: &PyDict,
        indexed_fields: Option<Vec<String>>,
        embedding_fields: Option<Vec<String>>,
    ) -> PyResult<()> {
        let schema_value: serde_json::Value = pythonize::depythonize(schema)?;

        self.inner
            .register_schema(
                name,
                schema_value,
                indexed_fields.unwrap_or_default(),
                embedding_fields.unwrap_or_default(),
            )
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

        Ok(())
    }

    /// Scan all entities.
    pub fn scan(&self, py: Python) -> PyResult<PyObject> {
        let entities = self
            .inner
            .scan_entities()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

        let py_list = PyList::empty(py);
        for entity in entities {
            let py_dict = pythonize::pythonize(py, &entity)?;
            py_list.append(py_dict)?;
        }

        Ok(py_list.into())
    }

    /// List schemas.
    pub fn list_schemas(&self) -> Vec<String> {
        self.inner.list_schemas()
    }

    /// Insert entity with automatic embedding generation (async).
    #[cfg(feature = "async")]
    pub fn insert_with_embedding<'p>(
        &self,
        py: Python<'p>,
        table: String,
        properties: &PyDict,
    ) -> PyResult<&'p PyAny> {
        let props: serde_json::Value = pythonize::depythonize(properties)?;
        let inner = self.inner.clone();

        pyo3_asyncio::tokio::future_into_py(py, async move {
            let entity_id = inner
                .insert_entity_with_embedding(&table, props)
                .await
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

            Ok(entity_id.to_string())
        })
    }

    /// Scan entities by type.
    pub fn scan_by_type(&self, py: Python, table: String) -> PyResult<PyObject> {
        let entities = self
            .inner
            .scan_entities_by_type(&table)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

        let py_list = PyList::empty(py);
        for entity in entities {
            let py_dict = pythonize::pythonize(py, &entity)?;
            py_list.append(py_dict)?;
        }

        Ok(py_list.into())
    }

    /// Get schema.
    pub fn get_schema(&self, py: Python, name: String) -> PyResult<PyObject> {
        let schema = self
            .inner
            .get_schema(&name)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

        pythonize::pythonize(py, &schema).map_err(Into::into)
    }

    /// Delete entity.
    pub fn delete(&self, entity_id: String) -> PyResult<()> {
        let id = uuid::Uuid::parse_str(&entity_id)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))?;

        self.inner
            .delete_entity(id)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

        Ok(())
    }

    /// Check if embeddings are enabled.
    pub fn has_embeddings(&self) -> bool {
        self.inner.embedding_provider.is_some()
    }

    /// Batch insert entities with automatic embedding generation (async).
    ///
    /// This is the preferred method for inserting multiple entities efficiently.
    /// Embeddings are generated in a single batch API call.
    ///
    /// Args:
    ///     table: Schema/table name
    ///     entities: List of entity dictionaries
    ///     key_field: Optional field to use as key (defaults to "id")
    ///
    /// Returns:
    ///     List of entity IDs (as strings)
    #[cfg(feature = "async")]
    #[pyo3(signature = (table, entities, key_field=None))]
    pub fn batch_insert<'p>(
        &self,
        py: Python<'p>,
        table: String,
        entities: &PyList,
        key_field: Option<String>,
    ) -> PyResult<&'p PyAny> {
        // Convert Python list of dicts to Vec<serde_json::Value>
        let mut entity_values = Vec::new();
        for item in entities.iter() {
            let dict = item.downcast::<PyDict>()?;
            let value: serde_json::Value = pythonize::depythonize(dict)?;
            entity_values.push(value);
        }

        let inner = self.inner.clone();
        let key_field_opt = key_field.as_deref().map(|s| s.to_string());

        pyo3_asyncio::tokio::future_into_py(py, async move {
            let entity_ids = inner
                .batch_insert_with_embedding(&table, entity_values, key_field_opt.as_deref())
                .await
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e.to_string()))?;

            // Convert UUIDs to strings
            let id_strings: Vec<String> = entity_ids.iter().map(|id| id.to_string()).collect();

            Python::with_gil(|py| Ok(id_strings.into_py(py)))
        })
    }
}
