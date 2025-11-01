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

/// Chunk text into larger, meaningful segments.
///
/// Groups paragraphs together to create chunks of minimum size (min_chars)
/// while respecting maximum size (max_chars).
///
/// # Arguments
///
/// * `text` - Full document text
/// * `min_chars` - Minimum characters per chunk (default: 500)
/// * `max_chars` - Maximum characters per chunk (default: 2000)
///
/// # Returns
///
/// Vector of text chunks
fn chunk_text(text: &str, min_chars: usize, max_chars: usize) -> Vec<String> {
    let paragraphs: Vec<&str> = text
        .split("\n\n")
        .map(|p| p.trim())
        .filter(|p| !p.is_empty())
        .collect();

    let mut chunks = Vec::new();
    let mut current_chunk = String::new();

    for paragraph in paragraphs {
        // If adding this paragraph would exceed max_chars and we have content, start new chunk
        if !current_chunk.is_empty() && current_chunk.len() + paragraph.len() + 2 > max_chars {
            chunks.push(current_chunk.clone());
            current_chunk.clear();
        }

        // Add paragraph to current chunk
        if !current_chunk.is_empty() {
            current_chunk.push_str("\n\n");
        }
        current_chunk.push_str(paragraph);

        // If we've reached min size, we can consider this a complete chunk
        // (but we'll keep adding until max_chars if paragraphs keep coming)
    }

    // Add final chunk if not empty
    if !current_chunk.is_empty() {
        chunks.push(current_chunk);
    }

    // If we ended up with no chunks (empty document), return single empty chunk
    if chunks.is_empty() {
        chunks.push(String::new());
    }

    chunks
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
    ///
    /// # Performance
    ///
    /// This uses true batch operations:
    /// - Single atomic RocksDB write batch
    /// - Validates all entities before writing (fail-fast)
    /// - Much faster than individual inserts
    fn insert_batch(&self, table: String, entities: &PyList) -> PyResult<Vec<String>> {
        // Convert Python list to Vec<serde_json::Value>
        let mut entity_values = Vec::with_capacity(entities.len());

        for item in entities.iter() {
            let dict = item.downcast::<PyDict>()?;
            let value: serde_json::Value = pythonize::depythonize(dict)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Failed to convert data: {}", e)))?;
            entity_values.push(value);
        }

        // Use Database::batch_insert for atomic batch write
        let uuids = self.inner.batch_insert(&self.tenant_id, &table, entity_values)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to batch insert: {}", e)))?;

        Ok(uuids.iter().map(|u| u.to_string()).collect())
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

    /// Batch get entities by IDs.
    ///
    /// # Arguments
    ///
    /// * `entity_ids` - List of entity UUID strings
    ///
    /// # Returns
    ///
    /// List of entity dicts (None for not found, in same order as input)
    ///
    /// # Performance
    ///
    /// Uses RocksDB multi_get for efficient bulk retrieval.
    /// Much faster than individual get() calls.
    ///
    /// # Example
    ///
    /// ```python
    /// ids = [uuid1, uuid2, uuid3]
    /// entities = db.get_batch(ids)
    /// # entities[0] corresponds to uuid1, etc.
    /// ```
    fn get_batch(&self, py: Python<'_>, entity_ids: Vec<String>) -> PyResult<Vec<Option<PyObject>>> {
        // Parse UUIDs
        let uuids: Result<Vec<_>, _> = entity_ids.iter()
            .map(|id| uuid::Uuid::parse_str(id))
            .collect();

        let uuids = uuids.map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("Invalid UUID: {}", e)
        ))?;

        // Batch get from database
        let entities = self.inner.get_batch(&self.tenant_id, &uuids)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                format!("Failed to batch get: {}", e)
            ))?;

        // Convert to Python objects
        let mut results = Vec::with_capacity(entities.len());
        for entity_opt in entities {
            match entity_opt {
                Some(entity) => {
                    let dict = entity_to_pydict(py, &entity)?;
                    results.push(Some(dict.into()));
                }
                None => results.push(None),
            }
        }

        Ok(results)
    }

    /// Batch lookup entities by key values.
    ///
    /// # Arguments
    ///
    /// * `key_values` - List of key values to lookup
    ///
    /// # Returns
    ///
    /// List of entity lists (one list per key value, in same order as input).
    /// Each inner list contains all entities matching that key.
    ///
    /// # Performance
    ///
    /// More efficient than individual lookup() calls due to batched index scans.
    ///
    /// # Example
    ///
    /// ```python
    /// keys = ["Alice", "Bob", "Charlie"]
    /// results = db.lookup_batch(keys)
    /// # results[0] = all entities with key "Alice"
    /// # results[1] = all entities with key "Bob"
    /// # results[2] = all entities with key "Charlie"
    /// ```
    fn lookup_batch(&self, py: Python<'_>, key_values: Vec<String>) -> PyResult<Vec<Vec<PyObject>>> {
        // Batch lookup from database
        let entities_by_key = self.inner.lookup_batch(&self.tenant_id, &key_values)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                format!("Failed to batch lookup: {}", e)
            ))?;

        // Convert to Python objects
        let mut results = Vec::with_capacity(entities_by_key.len());
        for entities in entities_by_key {
            let mut group = Vec::with_capacity(entities.len());
            for entity in entities {
                let dict = entity_to_pydict(py, &entity)?;
                group.push(dict.into());
            }
            results.push(group);
        }

        Ok(results)
    }

    /// Global lookup by key value across all schemas (anonymous types).
    ///
    /// **Core REM Pattern**: Find entities by natural key without knowing the schema.
    ///
    /// # Arguments
    ///
    /// * `key_value` - Key field value (e.g., "Alice", "alice@example.com")
    ///
    /// # Returns
    ///
    /// List of all matching entities (may be from different schemas)
    ///
    /// # Why Global Lookup?
    ///
    /// - **Anonymous types**: Users don't need to know schema names
    /// - **Natural keys**: "Alice" finds Alice regardless of storage location
    /// - **No SQL/GraphQL**: Avoids requiring schema knowledge upfront
    ///
    /// # Example
    ///
    /// ```python
    /// # Global lookup - finds Alice in ANY schema
    /// results = db.lookup("Alice")
    ///
    /// # Could return multiple entities if "Alice" exists in different schemas
    /// for entity in results:
    ///     print(f"Found in {entity.get('id', 'unknown')}")
    /// ```
    fn lookup(&self, py: Python<'_>, key_value: String) -> PyResult<Vec<PyObject>> {
        let entities = self.inner.lookup_global(&self.tenant_id, &key_value)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Failed to lookup: {}", e)))?;

        let mut results = Vec::new();
        for entity in entities {
            let dict = entity_to_pydict(py, &entity)?;
            results.push(dict.into());
        }

        Ok(results)
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

                    // Execute based on query type
                    match plan.query_type {
                        crate::llm::planner::QueryType::Sql => {
                            inner.query_sql(&tenant_id, &plan.primary_query.query_string)
                        }
                        crate::llm::planner::QueryType::Lookup => {
                            // Extract first key from keys array
                            let keys = plan.primary_query.parameters["keys"]
                                .as_array()
                                .ok_or_else(|| crate::types::DatabaseError::ValidationError(
                                    "LOOKUP requires 'keys' array parameter".to_string()
                                ))?;

                            if let Some(first_key) = keys.first() {
                                let key = first_key.as_str().unwrap_or("");
                                let schema = schema_hint_clone.as_deref().unwrap_or("resources");
                                match inner.get_by_key(&tenant_id, schema, key)? {
                                    Some(entity) => Ok(serde_json::to_value(&entity)?),
                                    None => Ok(serde_json::Value::Array(vec![])),
                                }
                            } else {
                                Ok(serde_json::Value::Array(vec![]))
                            }
                        }
                        crate::llm::planner::QueryType::Search => {
                            let schema = plan.primary_query.parameters.get("schema")
                                .and_then(|v| v.as_str())
                                .unwrap_or(schema_hint_clone.as_deref().unwrap_or("resources"));
                            let query_text = plan.primary_query.parameters.get("query_text")
                                .and_then(|v| v.as_str())
                                .unwrap_or(&plan.primary_query.query_string);
                            let top_k = plan.primary_query.parameters.get("top_k")
                                .and_then(|v| v.as_u64())
                                .unwrap_or(10) as usize;
                            let results = inner.search(&tenant_id, schema, query_text, top_k).await?;
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

    /// Generate query plan from natural language without executing.
    ///
    /// # Arguments
    ///
    /// * `question` - Natural language question
    /// * `schema_context` - Optional schema context for better planning
    ///
    /// # Returns
    ///
    /// QueryPlan JSON object with query_type, confidence, primary_query, fallback_queries, etc.
    ///
    /// # Example
    ///
    /// ```python
    /// # Plan a query
    /// plan = db.plan_query("find articles about rust", "articles")
    /// print(f"Query type: {plan['query_type']}")
    /// print(f"Confidence: {plan['confidence']}")
    /// print(f"Primary query: {plan['primary_query']['query_string']}")
    ///
    /// # Then execute the plan separately if desired
    /// results = db.run_plan(plan)
    /// ```
    fn plan_query(&self, py: Python<'_>, question: String, schema_context: Option<String>) -> PyResult<PyObject> {
        use crate::llm::query_builder::LlmQueryBuilder;

        // Build query plan (uses environment variables for API keys and model)
        let builder = LlmQueryBuilder::from_env()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                format!("Failed to create query builder: {}", e)
            ))?;

        // Format schema context
        let context = schema_context
            .map(|s| format!("Schema: {}", s))
            .unwrap_or_else(|| "General query".to_string());

        // Generate plan asynchronously
        let result: serde_json::Value = py.allow_threads(|| -> crate::types::Result<serde_json::Value> {
            tokio::runtime::Runtime::new()
                .unwrap()
                .block_on(async {
                    let plan = builder.plan_query(&question, &context).await?;
                    Ok(serde_json::to_value(&plan)?)
                })
        })
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
            format!("Query planning failed: {}", e)
        ))?;

        pythonize::pythonize(py, &result)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                format!("Failed to convert plan: {}", e)
            ))
    }

    /// Extract relationship edges from document content using LLM.
    ///
    /// Uses the Rust-native EdgeBuilder to analyze content and identify
    /// relationships to other entities, generating inline edges ready to
    /// append to resources.
    ///
    /// # Arguments
    ///
    /// * `content` - Document content (text, markdown, etc.)
    /// * `context` - Optional context about the document (file name, type, etc.)
    ///
    /// # Returns
    ///
    /// EdgePlan JSON object with:
    /// - edges: Array of inline edges (dst, rel_type, properties, created_at)
    /// - summary: Statistics (total_edges, relationship_types, avg_confidence)
    ///
    /// # Example
    ///
    /// ```python
    /// # Extract edges from document
    /// plan = db.extract_edges(
    ///     content="This document references Design Doc 001...",
    ///     context="architecture/rem-database.md"
    /// )
    ///
    /// # Access edges
    /// for edge in plan['edges']:
    ///     print(f"Found: {edge['rel_type']} -> {edge['dst']}")
    ///
    /// # Append to resource
    /// resource = db.get(resource_id)
    /// resource['edges'] = resource.get('edges', []) + plan['edges']
    /// db.insert('resources', resource)  # Upsert with edge merging
    /// ```
    ///
    /// # Requires
    ///
    /// Environment variables:
    /// - P8_DEFAULT_LLM: LLM model (default: "gpt-4-turbo")
    /// - OPENAI_API_KEY or ANTHROPIC_API_KEY: API key for LLM provider
    fn extract_edges(
        &self,
        py: Python<'_>,
        content: String,
        context: Option<String>,
    ) -> PyResult<PyObject> {
        use crate::llm::edge_builder::LlmEdgeBuilder;

        // Create edge builder (uses environment variables for API keys and model)
        let builder = LlmEdgeBuilder::from_env()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                format!("Failed to create edge builder: {}", e)
            ))?;

        // Extract edges asynchronously
        let result: serde_json::Value = py.allow_threads(|| -> crate::types::Result<serde_json::Value> {
            tokio::runtime::Runtime::new()
                .unwrap()
                .block_on(async {
                    let plan = builder.extract_edges(&content, context.as_deref()).await?;
                    Ok(serde_json::to_value(&plan)?)
                })
        })
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
            format!("Edge extraction failed: {}", e)
        ))?;

        pythonize::pythonize(py, &result)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                format!("Failed to convert edge plan: {}", e)
            ))
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

        // Better chunking: group paragraphs into larger chunks (default ~500 chars min)
        let chunks = chunk_text(&content, 500, 2000);

        let mut uuids = Vec::new();

        // Convert file path to file:// URI
        let uri = if file_path.starts_with("http://") || file_path.starts_with("https://") || file_path.starts_with("file://") {
            file_path.clone()
        } else {
            format!("file://{}", file_path)
        };

        // Insert each chunk as a separate entity
        for (i, chunk) in chunks.iter().enumerate() {
            let mut data = serde_json::Map::new();
            data.insert("content".to_string(), serde_json::Value::String(chunk.to_string()));
            data.insert("uri".to_string(), serde_json::Value::String(uri.clone()));
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
