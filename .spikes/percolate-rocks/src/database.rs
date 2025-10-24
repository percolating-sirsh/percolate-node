//! High-level database API combining storage and schema registry.
//!
//! This is the main entry point for database operations.

use crate::schema::{SchemaRegistry, register_builtin_schemas};
use crate::storage::Storage;
use crate::types::{Result, Entity};
use std::path::Path;
use std::sync::{Arc, RwLock};

/// High-level database with storage and schema registry.
///
/// Thread-safe and optimized for concurrent access.
pub struct Database {
    storage: Arc<Storage>,
    registry: Arc<RwLock<SchemaRegistry>>,
}

impl Database {
    /// Open database at path.
    ///
    /// # Arguments
    ///
    /// * `path` - Database directory path
    ///
    /// # Returns
    ///
    /// `Database` instance with builtin schemas registered
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::StorageError` if RocksDB fails to open
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// let db = Database::open("./data")?;
    /// ```
    pub fn open<P: AsRef<Path>>(path: P) -> Result<Self> {
        // Open storage layer
        let storage = Storage::open(path)?;

        // Initialize schema registry
        let mut registry = SchemaRegistry::new();

        // Register builtin schemas (schemas, documents, resources)
        register_builtin_schemas(&mut registry)?;

        Ok(Self {
            storage: Arc::new(storage),
            registry: Arc::new(RwLock::new(registry)),
        })
    }

    /// Open database in memory for testing.
    ///
    /// # Returns
    ///
    /// `Database` instance with in-memory backend
    pub fn open_temp() -> Result<Self> {
        let storage = Storage::open_temp()?;

        let mut registry = SchemaRegistry::new();
        register_builtin_schemas(&mut registry)?;

        Ok(Self {
            storage: Arc::new(storage),
            registry: Arc::new(RwLock::new(registry)),
        })
    }

    /// Register schema from JSON Schema.
    ///
    /// # Arguments
    ///
    /// * `name` - Schema name (short_name from schema)
    /// * `schema` - JSON Schema
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::ValidationError` if schema is invalid
    pub fn register_schema(&self, name: &str, schema: serde_json::Value) -> Result<()> {
        let mut registry = self.registry.write()
            .map_err(|e| crate::types::DatabaseError::InternalError(format!("Lock error: {}", e)))?;

        registry.register(name, schema)
    }

    /// Get schema by name.
    ///
    /// # Arguments
    ///
    /// * `name` - Schema name
    ///
    /// # Returns
    ///
    /// Schema JSON if found
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::SchemaNotFound` if schema doesn't exist
    pub fn get_schema(&self, name: &str) -> Result<serde_json::Value> {
        let registry = self.registry.read()
            .map_err(|e| crate::types::DatabaseError::InternalError(format!("Lock error: {}", e)))?;

        registry.get(name).map(|s| s.clone())
    }

    /// List all registered schemas.
    ///
    /// # Returns
    ///
    /// Vector of schema names
    pub fn list_schemas(&self) -> Result<Vec<String>> {
        let registry = self.registry.read()
            .map_err(|e| crate::types::DatabaseError::InternalError(format!("Lock error: {}", e)))?;

        Ok(registry.list())
    }

    /// Check if schema exists.
    ///
    /// # Arguments
    ///
    /// * `name` - Schema name
    ///
    /// # Returns
    ///
    /// `true` if schema is registered
    pub fn has_schema(&self, name: &str) -> bool {
        if let Ok(registry) = self.registry.read() {
            registry.has(name)
        } else {
            false
        }
    }

    /// Get storage instance (for low-level operations).
    ///
    /// # Returns
    ///
    /// Arc reference to storage
    pub fn storage(&self) -> Arc<Storage> {
        Arc::clone(&self.storage)
    }

    /// Get schema registry (for advanced operations).
    ///
    /// # Returns
    ///
    /// Arc reference to schema registry
    pub fn registry(&self) -> Arc<RwLock<SchemaRegistry>> {
        Arc::clone(&self.registry)
    }

    /// Insert entity (placeholder - needs validation and embedding).
    ///
    /// # Arguments
    ///
    /// * `tenant_id` - Tenant identifier
    /// * `table` - Table/schema name
    /// * `data` - Entity data
    ///
    /// # Returns
    ///
    /// Entity UUID
    ///
    /// # Errors
    ///
    /// Returns error if schema not found or validation fails
    ///
    /// # TODO
    ///
    /// - Validate against schema
    /// - Generate deterministic UUID based on key_field
    /// - Generate embeddings if configured
    /// - Create indexes if configured
    pub fn insert(&self, tenant_id: &str, table: &str, data: serde_json::Value) -> Result<uuid::Uuid> {
        use crate::types::DatabaseError;

        // Check schema exists
        if !self.has_schema(table) {
            return Err(DatabaseError::SchemaNotFound(table.to_string()));
        }

        // TODO: Schema validation
        // TODO: Deterministic UUID generation
        // TODO: Embedding generation
        // TODO: Index creation

        // For now: just create entity and store
        let id = uuid::Uuid::new_v4();
        let entity = Entity::new(id, table.to_string(), data);

        // Serialize and store
        let key = crate::storage::keys::encode_entity_key(tenant_id, id);
        let value = serde_json::to_vec(&entity)?;

        self.storage.put(
            crate::storage::column_families::CF_ENTITIES,
            &key,
            &value,
        )?;

        Ok(id)
    }

    /// Get entity by ID (placeholder).
    ///
    /// # Arguments
    ///
    /// * `tenant_id` - Tenant identifier
    /// * `entity_id` - Entity UUID
    ///
    /// # Returns
    ///
    /// `Some(Entity)` if found, `None` otherwise
    pub fn get(&self, tenant_id: &str, entity_id: uuid::Uuid) -> Result<Option<Entity>> {
        let key = crate::storage::keys::encode_entity_key(tenant_id, entity_id);

        let value = self.storage.get(
            crate::storage::column_families::CF_ENTITIES,
            &key,
        )?;

        match value {
            Some(data) => Ok(Some(serde_json::from_slice(&data)?)),
            None => Ok(None),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_database_open_temp() {
        let db = Database::open_temp().unwrap();

        // Should have builtin schemas
        assert!(db.has_schema("schemas"));
        assert!(db.has_schema("documents"));
        assert!(db.has_schema("resources"));
    }

    #[test]
    fn test_list_schemas() {
        let db = Database::open_temp().unwrap();
        let schemas = db.list_schemas().unwrap();

        assert_eq!(schemas.len(), 3);
        assert!(schemas.contains(&"schemas".to_string()));
        assert!(schemas.contains(&"documents".to_string()));
        assert!(schemas.contains(&"resources".to_string()));
    }

    #[test]
    fn test_register_schema() {
        let db = Database::open_temp().unwrap();

        let schema = serde_json::json!({
            "title": "Article",
            "description": "Test article schema",
            "version": "1.0.0",
            "short_name": "articles",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Article title"
                }
            },
            "required": ["title"]
        });

        db.register_schema("articles", schema).unwrap();
        assert!(db.has_schema("articles"));
    }
}
