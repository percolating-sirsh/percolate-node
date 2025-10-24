//! Schema registry with JSON Schema validation.

use crate::types::{DatabaseError, Result};
use dashmap::DashMap;
use serde::{Deserialize, Serialize};
use std::sync::Arc;

/// Schema definition for in-memory validation.
///
/// Schemas are stored as regular entities in the database with entity_type="schema".
/// This struct holds the minimal data needed for runtime validation and indexing.
///
/// The full Pydantic JSON blob is stored in the entity properties and reconstructed
/// on load. This ensures full compatibility with Pydantic model_json_schema output.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Schema {
    /// Schema name (from fully_qualified_name or short_name)
    pub name: String,

    /// Full Pydantic JSON blob (stored as-is from entity properties)
    pub raw_schema: serde_json::Value,

    /// REM-specific: Fields to index for fast lookups
    #[serde(default)]
    pub indexed_fields: Vec<String>,

    /// REM-specific: Fields to generate embeddings for
    #[serde(default)]
    pub embedding_fields: Vec<String>,
}

impl Schema {
    /// Create new schema from full Pydantic JSON blob.
    ///
    /// # Arguments
    ///
    /// * `name` - Schema name (from fully_qualified_name or short_name)
    /// * `raw_schema` - Full Pydantic JSON blob (with title, description, properties, etc.)
    /// * `indexed_fields` - Fields to index for fast lookups
    /// * `embedding_fields` - Fields to generate embeddings for
    pub fn new(
        name: String,
        raw_schema: serde_json::Value,
        indexed_fields: Vec<String>,
        embedding_fields: Vec<String>,
    ) -> Self {
        Self {
            name,
            raw_schema,
            indexed_fields,
            embedding_fields,
        }
    }

    /// Extract validation schema (JSON Schema properties).
    ///
    /// Returns the "properties" field from the raw schema for JSONSchema compilation.
    pub fn validation_schema(&self) -> serde_json::Value {
        serde_json::json!({
            "type": "object",
            "properties": self.raw_schema.get("properties").cloned().unwrap_or(serde_json::json!({})),
            "required": self.raw_schema.get("required").cloned().unwrap_or(serde_json::json!([])),
        })
    }
}

/// Schema registry with validation.
pub struct SchemaRegistry {
    schemas: DashMap<String, Schema>,
    validators: DashMap<String, Arc<jsonschema::JSONSchema>>,
}

impl SchemaRegistry {
    /// Create new registry.
    pub fn new() -> Self {
        Self {
            schemas: DashMap::new(),
            validators: DashMap::new(),
        }
    }

    /// Register schema.
    pub fn register(&self, schema: Schema) -> Result<()> {
        // Compile validator from validation schema
        let validation_schema = schema.validation_schema();
        let validator = jsonschema::JSONSchema::compile(&validation_schema)
            .map_err(|e| DatabaseError::JsonSchemaError(e.to_string()))?;

        self.validators
            .insert(schema.name.clone(), Arc::new(validator));
        self.schemas.insert(schema.name.clone(), schema);

        Ok(())
    }

    /// Get schema.
    pub fn get(&self, name: &str) -> Result<Schema> {
        self.schemas
            .get(name)
            .map(|s| s.clone())
            .ok_or_else(|| DatabaseError::SchemaNotFound(name.to_string()))
    }

    /// Validate data against schema.
    pub fn validate(&self, schema_name: &str, data: &serde_json::Value) -> Result<()> {
        let validator = self
            .validators
            .get(schema_name)
            .ok_or_else(|| DatabaseError::SchemaNotFound(schema_name.to_string()))?;

        validator
            .validate(data)
            .map_err(|e| DatabaseError::ValidationError(format!("{:?}", e.collect::<Vec<_>>())))?;

        Ok(())
    }

    /// List all schema names.
    pub fn list(&self) -> Vec<String> {
        self.schemas.iter().map(|e| e.key().clone()).collect()
    }
}

impl Default for SchemaRegistry {
    fn default() -> Self {
        Self::new()
    }
}
