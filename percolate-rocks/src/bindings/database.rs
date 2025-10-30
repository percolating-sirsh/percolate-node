//! Database PyO3 wrapper (main API).

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use crate::database::Database as RustDatabase;
use crate::types::Entity;
use std::sync::Arc;
use std::path::PathBuf;

/// Get default database path from environment or home directory.
///
/// Resolution order:
/// 1. P8_DB_PATH environment variable
/// 2. P8_HOME/db environment variable
/// 3. ~/.p8/db (default)
fn get_default_db_path() -> PathBuf {
    if let Ok(db_path) = std::env::var("P8_DB_PATH") {
        return PathBuf::from(shellexpand::tilde(&db_path).to_string());
    }

    if let Ok(p8_home) = std::env::var("P8_HOME") {
        let mut path = PathBuf::from(shellexpand::tilde(&p8_home).to_string());
        path.push("db");
        return path;
    }

    // Default to ~/.p8/db
    let home = std::env::var("HOME")
        .unwrap_or_else(|_| "/tmp".to_string());
    let mut path = PathBuf::from(home);
    path.push(".p8");
    path.push("db");
    path
}

/// Get tenant ID from environment or default to single-user mode.
///
/// Resolution order:
/// 1. P8_TENANT_ID environment variable
/// 2. "default" (single-user mode)
fn get_tenant_id() -> String {
    std::env::var("P8_TENANT_ID")
        .unwrap_or_else(|_| "default".to_string())
}

/// Python wrapper for Database.
///
/// Exposes high-level API to Python with automatic type conversions.
#[pyclass(name = "Database")]
pub struct PyDatabase {
    inner: Arc<RustDatabase>,
    tenant_id: String,
}

#[pymethods]
impl PyDatabase {
    /// Create new database using defaults.
    ///
    /// Path resolution:
    /// 1. P8_DB_PATH environment variable
    /// 2. P8_HOME/db environment variable
    /// 3. ~/.p8/db (default)
    ///
    /// Tenant ID resolution:
    /// 1. P8_TENANT_ID environment variable
    /// 2. "default" (single-user mode)
    ///
    /// # Returns
    ///
    /// New `PyDatabase` instance
    #[new]
    fn new() -> PyResult<Self> {
        let path = get_default_db_path();
        let tenant_id = get_tenant_id();

        let db = RustDatabase::open(&path)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to open database: {}", e)))?;

        Ok(Self {
            inner: Arc::new(db),
            tenant_id,
        })
    }

    /// Register schema from JSON.
    ///
    /// # Arguments
    ///
    /// * `name` - Schema name
    /// * `schema_json` - JSON Schema string
    fn register_schema(&mut self, name: String, schema_json: String) -> PyResult<()> {
        let schema: serde_json::Value = serde_json::from_str(&schema_json)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid JSON schema: {}", e)))?;

        self.inner.register_schema(&name, schema)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to register schema: {}", e)))?;

        Ok(())
    }

    /// Insert entity.
    ///
    /// # Arguments
    ///
    /// * `table` - Table/schema name
    /// * `data` - Entity data (Python dict)
    ///
    /// # Returns
    ///
    /// Entity UUID as string
    fn insert(&self, table: String, data: &PyDict) -> PyResult<String> {
        // Use pythonize to convert PyDict -> serde_json::Value
        let value: serde_json::Value = pythonize::depythonize(data)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Failed to convert data: {}", e)))?;

        let uuid = self.inner.insert(&self.tenant_id, &table, value)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to insert: {}", e)))?;

        Ok(uuid.to_string())
    }

    /// Batch insert entities.
    ///
    /// # Arguments
    ///
    /// * `table` - Table/schema name
    /// * `entities` - List of entity dicts
    ///
    /// # Returns
    ///
    /// List of entity UUIDs
    fn insert_batch(&self, table: String, entities: &PyList) -> PyResult<Vec<String>> {
        let mut uuids = Vec::new();

        for item in entities.iter() {
            let dict = item.downcast::<PyDict>()?;
            let value: serde_json::Value = pythonize::depythonize(dict)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Failed to convert data: {}", e)))?;

            let uuid = self.inner.insert(&self.tenant_id, &table, value)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to insert: {}", e)))?;

            uuids.push(uuid.to_string());
        }

        Ok(uuids)
    }

    /// Get entity by ID.
    ///
    /// # Arguments
    ///
    /// * `entity_id` - Entity UUID string
    ///
    /// # Returns
    ///
    /// Entity dict or None
    fn get(&self, py: Python<'_>, entity_id: String) -> PyResult<Option<PyObject>> {
        let uuid = uuid::Uuid::parse_str(&entity_id)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid UUID: {}", e)))?;

        let entity = self.inner.get(&self.tenant_id, uuid)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to get entity: {}", e)))?;

        match entity {
            Some(ent) => {
                // Convert Entity to Python dict
                let dict = entity_to_pydict(py, &ent)?;
                Ok(Some(dict.into()))
            }
            None => Ok(None),
        }
    }

    /// Lookup entity by key.
    ///
    /// # Arguments
    ///
    /// * `table` - Table/schema name
    /// * `key_value` - Key field value
    ///
    /// # Returns
    ///
    /// List of matching entities
    fn lookup(&self, py: Python<'_>, table: String, key_value: String) -> PyResult<Vec<PyObject>> {
        let entity = self.inner.get_by_key(&self.tenant_id, &table, &key_value)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to lookup: {}", e)))?;

        match entity {
            Some(ent) => {
                let dict = entity_to_pydict(py, &ent)?;
                Ok(vec![dict.into()])
            }
            None => Ok(vec![]),
        }
    }

    /// Search entities by semantic similarity.
    ///
    /// # Arguments
    ///
    /// * `query` - Search query text
    /// * `schema` - Schema name to search
    /// * `top_k` - Number of results
    ///
    /// # Returns
    ///
    /// List of (entity, score) tuples
    fn search(&self, py: Python<'_>, query: String, schema: String, top_k: usize) -> PyResult<Vec<PyObject>> {
        // Search is async, need to run in async runtime
        let inner = self.inner.clone();
        let tenant_id = self.tenant_id.clone();

        let results = py.allow_threads(|| {
            tokio::runtime::Runtime::new()
                .unwrap()
                .block_on(async {
                    inner.search(&tenant_id, &schema, &query, top_k).await
                })
        })
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Search failed: {}", e)))?;

        // Convert results to Python list of (entity, score) tuples
        let mut py_results = Vec::new();
        for (entity, score) in results {
            let entity_dict = entity_to_pydict(py, &entity)?;
            let tuple = (entity_dict, score).to_object(py);
            py_results.push(tuple);
        }

        Ok(py_results)
    }

    /// Execute SQL query.
    ///
    /// # Arguments
    ///
    /// * `sql` - SQL query string
    ///
    /// # Returns
    ///
    /// List of matching entities
    fn query(&self, py: Python<'_>, sql: String) -> PyResult<PyObject> {
        let result = self.inner.query_sql(&self.tenant_id, &sql)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Query failed: {}", e)))?;

        // Convert JSON Value to Python object
        pythonize::pythonize(py, &result)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to convert result: {}", e)))
    }

    /// Execute natural language query.
    ///
    /// # Arguments
    ///
    /// * `question` - Natural language question
    /// * `execute` - Execute query or just plan
    /// * `schema_hint` - Optional schema name hint
    ///
    /// # Returns
    ///
    /// Query results or plan
    fn ask(&self, py: Python<'_>, question: String, execute: bool, schema_hint: Option<String>) -> PyResult<PyObject> {
        use crate::llm::query_builder::LlmQueryBuilder;

        // Get API key from environment
        let api_key = std::env::var("OPENAI_API_KEY")
            .or_else(|_| std::env::var("ANTHROPIC_API_KEY"))
            .map_err(|_| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "No API key found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY environment variable."
            ))?;

        // Determine model and provider
        let model = std::env::var("P8_DEFAULT_LLM").unwrap_or_else(|_| "gpt-4-turbo".to_string());

        // Build query plan
        let builder = LlmQueryBuilder::from_env()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to create query builder: {}", e)))?;

        // Get schema context
        let schema_context = if let Some(ref schema) = schema_hint {
            format!("Schema: {}", schema)
        } else {
            "General query".to_string()
        };

        let inner = self.inner.clone();
        let tenant_id = self.tenant_id.clone();
        let schema_hint_clone = schema_hint.clone();

        let result = py.allow_threads(|| {
            tokio::runtime::Runtime::new()
                .unwrap()
                .block_on(async {
                    let plan = builder.plan_query(&question, &schema_context).await?;

                    if !execute {
                        // Just return plan
                        return Ok(serde_json::to_value(&plan)?);
                    }

                    // Execute based on intent
                    match plan.intent {
                        crate::llm::planner::QueryIntent::Select => {
                            inner.query_sql(&tenant_id, &plan.query)
                        }
                        crate::llm::planner::QueryIntent::EntityLookup => {
                            let key = plan.parameters["key"].as_str().unwrap();
                            let schema = schema_hint_clone.as_deref().unwrap_or("resources");
                            match inner.get_by_key(&tenant_id, schema, key)? {
                                Some(entity) => Ok(serde_json::to_value(&entity)?),
                                None => Ok(serde_json::Value::Array(vec![])),
                            }
                        }
                        crate::llm::planner::QueryIntent::Search => {
                            let schema = schema_hint_clone.as_deref().unwrap_or("resources");
                            let top_k = plan.parameters.get("top_k")
                                .and_then(|v| v.as_u64())
                                .unwrap_or(10) as usize;
                            let results = inner.search(&tenant_id, schema, &plan.query, top_k).await?;
                            Ok(serde_json::to_value(&results)?)
                        }
                        _ => {
                            Err(crate::types::DatabaseError::NotImplemented(
                                "Query intent not yet supported".to_string()
                            ))
                        }
                    }
                })
        })
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Query failed: {}", e)))?;

        pythonize::pythonize(py, &result)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to convert result: {}", e)))
    }

    /// List all registered schemas.
    ///
    /// # Returns
    ///
    /// List of schema names
    fn list_schemas(&self) -> PyResult<Vec<String>> {
        self.inner.list_schemas()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to list schemas: {}", e)))
    }

    /// Get schema by name.
    ///
    /// # Arguments
    ///
    /// * `name` - Schema name
    ///
    /// # Returns
    ///
    /// Schema JSON string
    fn get_schema(&self, py: Python<'_>, name: String) -> PyResult<PyObject> {
        let schema = self.inner.get_schema(&name)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to get schema: {}", e)))?;

        pythonize::pythonize(py, &schema)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to convert schema: {}", e)))
    }

    /// Graph traversal from entity.
    ///
    /// # Arguments
    ///
    /// * `start_id` - Starting entity UUID
    /// * `direction` - Traversal direction ("out", "in", "both")
    /// * `depth` - Maximum depth
    ///
    /// # Returns
    ///
    /// List of entity UUIDs
    fn traverse(&self, start_id: String, direction: String, depth: usize) -> PyResult<Vec<String>> {
        let uuid = uuid::Uuid::parse_str(&start_id)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid UUID: {}", e)))?;

        let dir = match direction.as_str() {
            "out" => crate::graph::TraversalDirection::Out,
            "in" => crate::graph::TraversalDirection::In,
            "both" => crate::graph::TraversalDirection::Both,
            _ => return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "direction must be 'out', 'in', or 'both'"
            )),
        };

        let uuids = self.inner.traverse_bfs(uuid, dir, depth, None)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Traversal failed: {}", e)))?;

        Ok(uuids.into_iter().map(|u| u.to_string()).collect())
    }

    /// Export entities to file.
    ///
    /// # Arguments
    ///
    /// * `table` - Table name
    /// * `path` - Output file path
    /// * `format` - Export format ("parquet", "csv", "jsonl")
    fn export(&self, table: String, path: String, format: String) -> PyResult<()> {
        // Get all entities from table
        let entities = self.inner.list(&self.tenant_id, &table, false, None)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to list entities: {}", e)))?;

        // Export based on format
        match format.as_str() {
            "parquet" => {
                crate::export::ParquetExporter::export(&entities, &path)
                    .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Export failed: {}", e)))?;
            }
            "csv" => {
                crate::export::CsvExporter::export(&entities, &path)
                    .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Export failed: {}", e)))?;
            }
            "jsonl" => {
                crate::export::JsonlExporter::export(&entities, &path)
                    .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Export failed: {}", e)))?;
            }
            _ => return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "format must be 'parquet', 'csv', or 'jsonl'"
            )),
        }

        Ok(())
    }

    /// Ingest document file.
    ///
    /// # Arguments
    ///
    /// * `file_path` - Document file path
    /// * `schema` - Target schema name
    ///
    /// # Returns
    ///
    /// List of created entity UUIDs
    fn ingest(&self, file_path: String, schema: String) -> PyResult<Vec<String>> {
        use std::fs;
        use std::path::Path;

        // Read file
        let content = fs::read_to_string(&file_path)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Failed to read file: {}", e)))?;

        let path = Path::new(&file_path);
        let file_name = path.file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("unknown");

        // Simple chunking: split by paragraphs (double newline)
        let chunks: Vec<&str> = content
            .split("\n\n")
            .filter(|s| !s.trim().is_empty())
            .collect();

        let mut uuids = Vec::new();

        // Insert each chunk as a separate entity
        for (i, chunk) in chunks.iter().enumerate() {
            let mut data = serde_json::Map::new();
            data.insert("content".to_string(), serde_json::Value::String(chunk.to_string()));
            data.insert("uri".to_string(), serde_json::Value::String(file_path.clone()));
            data.insert("chunk_ordinal".to_string(), serde_json::Value::Number(i.into()));
            data.insert("name".to_string(), serde_json::Value::String(format!("{} (chunk {})", file_name, i)));

            let json_value = serde_json::Value::Object(data);
            let uuid = self.inner.insert(&self.tenant_id, &schema, json_value)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to insert chunk: {}", e)))?;

            uuids.push(uuid.to_string());
        }

        Ok(uuids)
    }

    /// Upsert collection of Pydantic models.
    ///
    /// Automatically detects schema name from model and inserts/updates entities.
    ///
    /// # Arguments
    ///
    /// * `models` - List of Pydantic model instances (dicts)
    ///
    /// # Returns
    ///
    /// List of entity UUIDs
    ///
    /// # Example
    ///
    /// ```python
    /// from pydantic import BaseModel
    ///
    /// class Session(BaseModel):
    ///     name: str
    ///     user_id: str
    ///
    /// sessions = [Session(name="s1", user_id="u1"), Session(name="s2", user_id="u2")]
    /// db.upsert(sessions)
    /// ```
    fn upsert(&self, models: &PyList) -> PyResult<Vec<String>> {
        let mut uuids = Vec::new();

        for item in models.iter() {
            // Extract schema name from __class__.__name__ or use "entities" as default
            let schema = if let Ok(class) = item.getattr("__class__") {
                if let Ok(name) = class.getattr("__name__") {
                    name.extract::<String>().unwrap_or_else(|_| "entities".to_string())
                } else {
                    "entities".to_string()
                }
            } else {
                "entities".to_string()
            };

            // Convert to dict - try direct downcast first, then call model_dump() for Pydantic models
            let model_dict = if let Ok(dict) = item.downcast::<PyDict>() {
                // Already a dict
                dict
            } else {
                // Try calling model_dump() to convert Pydantic model to dict
                if let Ok(dump_method) = item.getattr("model_dump") {
                    let dumped = dump_method.call0()?;
                    dumped.downcast::<PyDict>()?
                } else {
                    return Err(PyErr::new::<pyo3::exceptions::PyTypeError, _>(
                        format!("Item must be a Pydantic model or dict, got {}", schema)
                    ));
                }
            };

            // Convert to JSON value
            let value: serde_json::Value = pythonize::depythonize(model_dict)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Failed to convert model: {}", e)))?;

            // Insert (upsert is handled by deterministic UUID generation)
            let uuid = self.inner.insert(&self.tenant_id, &schema, value)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to upsert: {}", e)))?;

            uuids.push(uuid.to_string());
        }

        Ok(uuids)
    }

    /// Close database.
    fn close(&mut self) -> PyResult<()> {
        // Database closes automatically on drop
        Ok(())
    }
}

/// Helper function to convert Entity to Python dict.
fn entity_to_pydict(py: Python<'_>, entity: &Entity) -> PyResult<PyObject> {
    // Convert the entity's properties to a Python dict
    pythonize::pythonize(py, &entity.properties)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to convert entity: {}", e)))
}
