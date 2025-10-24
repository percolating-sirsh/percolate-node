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
        let storage = Arc::new(Storage::open(path)?);

        // Initialize schema registry
        let mut registry = SchemaRegistry::new();

        // Register builtin schemas (schemas, documents, resources)
        register_builtin_schemas(&mut registry)?;

        let db = Self {
            storage,
            registry: Arc::new(RwLock::new(registry)),
        };

        // Load persisted schemas from storage
        db.load_schemas_from_storage()?;

        Ok(db)
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
        // Register in memory
        {
            let mut registry = self.registry.write()
                .map_err(|e| crate::types::DatabaseError::InternalError(format!("Lock error: {}", e)))?;

            registry.register(name, schema.clone())?;
        }

        // Persist to storage (unless it's a system schema)
        use crate::schema::PydanticSchemaParser;
        use crate::schema::SchemaCategory;

        let category = PydanticSchemaParser::extract_category(&schema);
        if category != SchemaCategory::System {
            self.persist_schema(name, &schema)?;
        }

        Ok(())
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

    /// Insert entity with schema validation and deterministic UUID.
    ///
    /// # Arguments
    ///
    /// * `tenant_id` - Tenant identifier
    /// * `table` - Table/schema name
    /// * `data` - Entity data
    ///
    /// # Returns
    ///
    /// Entity UUID (deterministic if key field present)
    ///
    /// # Errors
    ///
    /// Returns error if schema not found or validation fails
    ///
    /// # Features
    ///
    /// - ✅ Schema validation (JSON Schema)
    /// - ✅ Deterministic UUID generation (based on key_field)
    /// - ⏳ Embedding generation (TODO)
    /// - ⏳ Index creation (TODO)
    /// - ⏳ Key index update (TODO)
    pub fn insert(&self, tenant_id: &str, table: &str, data: serde_json::Value) -> Result<uuid::Uuid> {
        use crate::types::{DatabaseError, generate_uuid};
        use crate::schema::{SchemaValidator, PydanticSchemaParser};

        // Get schema
        let registry = self.registry.read()
            .map_err(|e| DatabaseError::InternalError(format!("Lock error: {}", e)))?;

        let schema = registry.get(table)?;

        // Validate data against schema
        let validator = SchemaValidator::new(schema.clone())?;
        validator.validate(&data)?;

        // Extract key_field from schema
        let key_field_opt = PydanticSchemaParser::extract_key_field(schema);
        let key_field = key_field_opt.as_deref();

        // Generate deterministic UUID
        let id = generate_uuid(table, &data, key_field);

        // Create entity with system fields
        let entity = Entity::new(id, table.to_string(), data);

        // Serialize and store
        let key = crate::storage::keys::encode_entity_key(tenant_id, id);
        let value = serde_json::to_vec(&entity)?;

        self.storage.put(
            crate::storage::column_families::CF_ENTITIES,
            &key,
            &value,
        )?;

        // TODO: Update key index for reverse lookups
        // TODO: Generate embeddings if configured
        // TODO: Create field indexes if configured

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

    /// Load persisted schemas from storage.
    ///
    /// # Returns
    ///
    /// Ok if schemas loaded successfully
    ///
    /// # Errors
    ///
    /// Returns error if schema loading fails
    ///
    /// # Note
    ///
    /// This is called automatically when opening the database.
    /// System schemas are not loaded (already registered in-memory).
    fn load_schemas_from_storage(&self) -> Result<()> {
        use rocksdb::IteratorMode;

        // Get column family handle
        let cf = self.storage.cf_handle(crate::storage::column_families::CF_ENTITIES);

        // Iterate over all entities with prefix "entity:default:"
        let prefix = b"entity:default:";
        let iter = self.storage.db().iterator_cf(
            &cf,
            IteratorMode::From(prefix, rocksdb::Direction::Forward),
        );

        for item in iter {
            let (key, value) = item.map_err(|e| crate::types::DatabaseError::StorageError(e))?;

            // Check if key still matches prefix
            if !key.starts_with(prefix) {
                break;
            }

            // Deserialize entity
            let entity: Entity = serde_json::from_slice(&value)?;

            // Only load schema entities (not other types)
            if entity.system.entity_type != "schemas" {
                continue;
            }

            // Extract schema data
            let props = &entity.properties;
            let short_name = props.get("short_name")
                .and_then(|v| v.as_str())
                .ok_or_else(|| crate::types::DatabaseError::ValidationError(
                    "Schema entity missing 'short_name'".into()
                ))?;

            let schema = props.get("schema")
                .ok_or_else(|| crate::types::DatabaseError::ValidationError(
                    "Schema entity missing 'schema' field".into()
                ))?;

            // Register in memory (skip persistence since it's already persisted)
            let mut registry = self.registry.write()
                .map_err(|e| crate::types::DatabaseError::InternalError(format!("Lock error: {}", e)))?;

            registry.register(short_name, schema.clone())?;
        }

        Ok(())
    }

    /// Persist schema to storage (schemas table).
    ///
    /// # Arguments
    ///
    /// * `name` - Schema name
    /// * `schema` - JSON Schema
    ///
    /// # Returns
    ///
    /// Ok if schema persisted successfully
    ///
    /// # Errors
    ///
    /// Returns error if persistence fails
    fn persist_schema(&self, name: &str, schema: &serde_json::Value) -> Result<()> {
        use crate::schema::PydanticSchemaParser;
        use crate::types::generate_uuid;

        // Extract schema metadata
        let version = PydanticSchemaParser::extract_version(schema)
            .ok_or_else(|| crate::types::DatabaseError::ValidationError(
                "Schema missing 'version' field".into()
            ))?;

        let description = PydanticSchemaParser::extract_description(schema)
            .unwrap_or_else(|| "No description".to_string());

        let category = PydanticSchemaParser::extract_category(schema);

        // Create schema entity
        let schema_data = serde_json::json!({
            "short_name": name,
            "name": PydanticSchemaParser::extract_fqn(schema).unwrap_or_else(|| name.to_string()),
            "version": version,
            "schema": schema,
            "description": description,
            "category": category.as_str(),
        });

        // Generate deterministic UUID (using "name" field)
        let id = generate_uuid("schemas", &schema_data, Some("name"));

        // Create entity
        let entity = Entity::new(id, "schemas".to_string(), schema_data);

        // Serialize and store
        let key = crate::storage::keys::encode_entity_key("default", id);
        let value = serde_json::to_vec(&entity)?;

        self.storage.put(
            crate::storage::column_families::CF_ENTITIES,
            &key,
            &value,
        )?;

        Ok(())
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
