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

        // Update key index for reverse lookups
        if let Some(key_value) = extract_key_value(&entity.properties, key_field) {
            let index_key = crate::storage::keys::encode_key_index(tenant_id, &key_value, id);
            let index_value = serde_json::json!({"type": table}).to_string();
            self.storage.put(
                crate::storage::column_families::CF_KEY_INDEX,
                &index_key,
                index_value.as_bytes(),
            )?;
        }

        // TODO: Generate embeddings if configured
        // TODO: Create field indexes if configured

        Ok(id)
    }

    /// Get entity by ID.
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

    /// Update entity properties.
    ///
    /// # Arguments
    ///
    /// * `tenant_id` - Tenant identifier
    /// * `entity_id` - Entity UUID to update
    /// * `updates` - JSON object with fields to update (partial or full)
    ///
    /// # Returns
    ///
    /// Updated entity
    ///
    /// # Errors
    ///
    /// Returns error if entity not found or validation fails
    ///
    /// # Features
    ///
    /// - ✅ Partial updates (merge with existing properties)
    /// - ✅ Schema validation on updated entity
    /// - ✅ Updates modified_at timestamp
    /// - ⏳ Re-generate embeddings if embedding fields changed (TODO)
    /// - ⏳ Update field indexes if indexed fields changed (TODO)
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// // Update single field
    /// db.update("tenant1", entity_id, json!({"age": 31}))?;
    ///
    /// // Update multiple fields
    /// db.update("tenant1", entity_id, json!({"age": 31, "status": "active"}))?;
    /// ```
    pub fn update(&self, tenant_id: &str, entity_id: uuid::Uuid, updates: serde_json::Value) -> Result<Entity> {
        use crate::types::DatabaseError;
        use crate::schema::SchemaValidator;

        // Get existing entity
        let mut entity = self.get(tenant_id, entity_id)?
            .ok_or_else(|| DatabaseError::EntityNotFound(entity_id))?;

        // Merge updates into properties
        if let Some(updates_obj) = updates.as_object() {
            if let Some(props_obj) = entity.properties.as_object_mut() {
                for (key, value) in updates_obj {
                    props_obj.insert(key.clone(), value.clone());
                }
            }
        } else {
            // Full replacement if updates is not an object
            entity.properties = updates;
        }

        // Validate updated entity against schema
        let registry = self.registry.read()
            .map_err(|e| DatabaseError::InternalError(format!("Lock error: {}", e)))?;

        let schema = registry.get(&entity.system.entity_type)?;
        let validator = SchemaValidator::new(schema.clone())?;
        validator.validate(&entity.properties)?;

        // Update modified_at timestamp
        entity.system.modified_at = chrono::Utc::now().to_rfc3339();

        // Serialize and store
        let key = crate::storage::keys::encode_entity_key(tenant_id, entity_id);
        let value = serde_json::to_vec(&entity)?;

        self.storage.put(
            crate::storage::column_families::CF_ENTITIES,
            &key,
            &value,
        )?;

        // TODO: Re-generate embeddings if embedding fields changed
        // TODO: Update field indexes if indexed fields changed

        Ok(entity)
    }

    /// Delete entity (soft delete by default).
    ///
    /// # Arguments
    ///
    /// * `tenant_id` - Tenant identifier
    /// * `entity_id` - Entity UUID to delete
    ///
    /// # Returns
    ///
    /// Deleted entity (with deleted_at set)
    ///
    /// # Errors
    ///
    /// Returns error if entity not found
    ///
    /// # Note
    ///
    /// This is a soft delete - sets `deleted_at` timestamp but keeps the entity in storage.
    /// For hard delete (permanent removal), use `hard_delete()`.
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// let deleted = db.delete("tenant1", entity_id)?;
    /// assert!(deleted.is_deleted());
    /// ```
    pub fn delete(&self, tenant_id: &str, entity_id: uuid::Uuid) -> Result<Entity> {
        use crate::types::DatabaseError;

        // Get existing entity
        let mut entity = self.get(tenant_id, entity_id)?
            .ok_or_else(|| DatabaseError::EntityNotFound(entity_id))?;

        // Mark as deleted
        entity.mark_deleted();

        // Serialize and store
        let key = crate::storage::keys::encode_entity_key(tenant_id, entity_id);
        let value = serde_json::to_vec(&entity)?;

        self.storage.put(
            crate::storage::column_families::CF_ENTITIES,
            &key,
            &value,
        )?;

        Ok(entity)
    }

    /// Hard delete entity (permanent removal).
    ///
    /// # Arguments
    ///
    /// * `tenant_id` - Tenant identifier
    /// * `entity_id` - Entity UUID to delete
    ///
    /// # Returns
    ///
    /// Ok if deletion successful
    ///
    /// # Errors
    ///
    /// Returns error if entity not found
    ///
    /// # Warning
    ///
    /// This is a permanent delete - the entity cannot be recovered.
    /// Consider using `delete()` (soft delete) instead.
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// db.hard_delete("tenant1", entity_id)?;
    /// assert!(db.get("tenant1", entity_id)?.is_none());
    /// ```
    pub fn hard_delete(&self, tenant_id: &str, entity_id: uuid::Uuid) -> Result<()> {
        use crate::types::DatabaseError;

        // Verify entity exists
        let entity = self.get(tenant_id, entity_id)?
            .ok_or_else(|| DatabaseError::EntityNotFound(entity_id))?;

        // Delete from entities CF
        let key = crate::storage::keys::encode_entity_key(tenant_id, entity_id);
        self.storage.delete(crate::storage::column_families::CF_ENTITIES, &key)?;

        // Delete from key index if entity has a key value
        let registry = self.registry.read()
            .map_err(|e| DatabaseError::InternalError(format!("Lock error: {}", e)))?;

        let schema = registry.get(&entity.system.entity_type)?;
        let key_field_opt = crate::schema::PydanticSchemaParser::extract_key_field(schema);
        let key_field = key_field_opt.as_deref();

        if let Some(key_value) = extract_key_value(&entity.properties, key_field) {
            let index_key = crate::storage::keys::encode_key_index(tenant_id, &key_value, entity_id);
            self.storage.delete(crate::storage::column_families::CF_KEY_INDEX, &index_key)?;
        }

        // TODO: Delete embeddings from CF_EMBEDDINGS
        // TODO: Delete field indexes from CF_INDEXES
        // TODO: Delete edges from CF_EDGES and CF_EDGES_REVERSE

        Ok(())
    }

    /// Get entity by key field value (reverse lookup).
    ///
    /// # Arguments
    ///
    /// * `tenant_id` - Tenant identifier
    /// * `table` - Table/schema name
    /// * `key_value` - Key field value to lookup
    ///
    /// # Returns
    ///
    /// `Some(Entity)` if found, `None` otherwise
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// // Find person by email
    /// let person = db.get_by_key("tenant1", "person", "alice@example.com")?;
    /// ```
    pub fn get_by_key(&self, tenant_id: &str, table: &str, key_value: &str) -> Result<Option<Entity>> {
        use rocksdb::IteratorMode;

        // Scan prefix: key:{tenant_id}:{key_value}:
        let prefix = format!("key:{}:{}:", tenant_id, key_value).into_bytes();
        let cf = self.storage.cf_handle(crate::storage::column_families::CF_KEY_INDEX);

        let iter = self.storage.db().iterator_cf(
            &cf,
            IteratorMode::From(&prefix, rocksdb::Direction::Forward),
        );

        for item in iter {
            let (key, value) = item.map_err(|e| crate::types::DatabaseError::StorageError(e))?;

            // Check if key still matches prefix
            if !key.starts_with(&prefix) {
                break;
            }

            // Parse index value to check table type
            let index_data: serde_json::Value = serde_json::from_slice(&value)?;
            if index_data.get("type").and_then(|v| v.as_str()) != Some(table) {
                continue; // Different table type
            }

            // Extract entity UUID from key
            let key_str = std::str::from_utf8(&key)
                .map_err(|e| crate::types::DatabaseError::InvalidKey(format!("Invalid UTF-8: {}", e)))?;
            let parts: Vec<&str> = key_str.split(':').collect();
            if parts.len() != 4 {
                continue; // Invalid key format
            }

            let entity_id = uuid::Uuid::parse_str(parts[3])
                .map_err(|e| crate::types::DatabaseError::InvalidKey(format!("Invalid UUID: {}", e)))?;

            // Fetch entity by ID
            return self.get(tenant_id, entity_id);
        }

        Ok(None)
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

/// Extract key value from entity data following same priority as generate_uuid.
///
/// # Arguments
///
/// * `data` - Entity data
/// * `key_field` - Optional custom key field from schema
///
/// # Returns
///
/// Key value string if found, None otherwise
fn extract_key_value(data: &serde_json::Value, key_field: Option<&str>) -> Option<String> {
    // Priority 1: uri (for resources/documents)
    if let Some(uri) = data.get("uri").and_then(|v| v.as_str()) {
        return Some(uri.to_string());
    }

    // Priority 2: Custom key_field from schema
    if let Some(field_name) = key_field {
        if let Some(value) = data.get(field_name) {
            return Some(value_to_string(value));
        }
    }

    // Priority 3: Generic "key" field
    if let Some(key_value) = data.get("key") {
        return Some(value_to_string(key_value));
    }

    // Priority 4: "name" field
    if let Some(name) = data.get("name").and_then(|v| v.as_str()) {
        return Some(name.to_string());
    }

    // Priority 5: No key field (random UUID case)
    None
}

/// Convert JSON value to string for key indexing.
fn value_to_string(value: &serde_json::Value) -> String {
    match value {
        serde_json::Value::String(s) => s.clone(),
        serde_json::Value::Number(n) => n.to_string(),
        serde_json::Value::Bool(b) => b.to_string(),
        _ => value.to_string(),
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

    #[test]
    fn test_get_by_key_with_name_field() {
        let db = Database::open_temp().unwrap();

        // Register schema without explicit key_field
        let schema = serde_json::json!({
            "title": "Person",
            "version": "1.0.0",
            "short_name": "person",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "number"}
            },
            "required": ["name"]
        });

        db.register_schema("person", schema).unwrap();

        // Insert entity with name field
        let data = serde_json::json!({"name": "Alice", "age": 30});
        let id = db.insert("tenant1", "person", data).unwrap();

        // Lookup by name
        let entity = db.get_by_key("tenant1", "person", "Alice").unwrap();
        assert!(entity.is_some());

        let entity = entity.unwrap();
        assert_eq!(entity.system.id, id);
        assert_eq!(entity.properties.get("name").unwrap(), "Alice");
    }

    #[test]
    fn test_get_by_key_with_custom_key_field() {
        let db = Database::open_temp().unwrap();

        // Register schema with custom key_field
        let schema = serde_json::json!({
            "title": "User",
            "version": "1.0.0",
            "short_name": "user",
            "json_schema_extra": {
                "key_field": "email"
            },
            "properties": {
                "email": {"type": "string"},
                "username": {"type": "string"}
            },
            "required": ["email", "username"]
        });

        db.register_schema("user", schema).unwrap();

        // Insert entity
        let data = serde_json::json!({
            "email": "alice@example.com",
            "username": "alice"
        });
        let id = db.insert("tenant1", "user", data).unwrap();

        // Lookup by email
        let entity = db.get_by_key("tenant1", "user", "alice@example.com").unwrap();
        assert!(entity.is_some());

        let entity = entity.unwrap();
        assert_eq!(entity.system.id, id);
        assert_eq!(entity.properties.get("email").unwrap(), "alice@example.com");
    }

    #[test]
    fn test_get_by_key_not_found() {
        let db = Database::open_temp().unwrap();

        // Register schema
        let schema = serde_json::json!({
            "title": "Person",
            "version": "1.0.0",
            "short_name": "person",
            "properties": {
                "name": {"type": "string"}
            },
            "required": ["name"]
        });

        db.register_schema("person", schema).unwrap();

        // Lookup non-existent key
        let entity = db.get_by_key("tenant1", "person", "NonExistent").unwrap();
        assert!(entity.is_none());
    }

    #[test]
    fn test_get_by_key_tenant_isolation() {
        let db = Database::open_temp().unwrap();

        // Register schema
        let schema = serde_json::json!({
            "title": "Person",
            "version": "1.0.0",
            "short_name": "person",
            "properties": {
                "name": {"type": "string"}
            },
            "required": ["name"]
        });

        db.register_schema("person", schema).unwrap();

        // Insert same name in different tenants
        db.insert("tenant1", "person", serde_json::json!({"name": "Alice"})).unwrap();
        db.insert("tenant2", "person", serde_json::json!({"name": "Alice"})).unwrap();

        // Each tenant should only see their own entity
        let entity1 = db.get_by_key("tenant1", "person", "Alice").unwrap();
        let entity2 = db.get_by_key("tenant2", "person", "Alice").unwrap();

        assert!(entity1.is_some());
        assert!(entity2.is_some());

        // UUIDs are the same (deterministic based on entity data alone)
        // but they are stored at different keys: entity:tenant1:{uuid} vs entity:tenant2:{uuid}
        assert_eq!(entity1.as_ref().unwrap().system.id, entity2.as_ref().unwrap().system.id);

        // Verify tenant1 cannot see tenant2's entity by direct get
        let id = entity1.unwrap().system.id;
        let from_tenant1 = db.get("tenant1", id).unwrap();
        let from_tenant2 = db.get("tenant2", id).unwrap();

        assert!(from_tenant1.is_some());
        assert!(from_tenant2.is_some()); // Both exist because same UUID stored under different tenant keys
    }

    #[test]
    fn test_update_partial() {
        let db = Database::open_temp().unwrap();

        // Register schema
        let schema = serde_json::json!({
            "title": "Person",
            "version": "1.0.0",
            "short_name": "person",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "number"},
                "status": {"type": "string"}
            },
            "required": ["name"]
        });

        db.register_schema("person", schema).unwrap();

        // Insert entity
        let data = serde_json::json!({"name": "Alice", "age": 30, "status": "active"});
        let id = db.insert("tenant1", "person", data).unwrap();

        // Partial update - only update age
        let updates = serde_json::json!({"age": 31});
        let updated = db.update("tenant1", id, updates).unwrap();

        assert_eq!(updated.properties.get("name").unwrap(), "Alice");
        assert_eq!(updated.properties.get("age").unwrap(), 31);
        assert_eq!(updated.properties.get("status").unwrap(), "active");
    }

    #[test]
    fn test_update_validation() {
        let db = Database::open_temp().unwrap();

        // Register schema with required field
        let schema = serde_json::json!({
            "title": "Person",
            "version": "1.0.0",
            "short_name": "person",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "number"}
            },
            "required": ["name", "age"]
        });

        db.register_schema("person", schema).unwrap();

        // Insert valid entity
        let data = serde_json::json!({"name": "Alice", "age": 30});
        let id = db.insert("tenant1", "person", data).unwrap();

        // Try to update with invalid data (age as string)
        let updates = serde_json::json!({"age": "thirty"});
        let result = db.update("tenant1", id, updates);

        assert!(result.is_err()); // Should fail validation
    }

    #[test]
    fn test_update_not_found() {
        let db = Database::open_temp().unwrap();

        let updates = serde_json::json!({"age": 31});
        let result = db.update("tenant1", uuid::Uuid::new_v4(), updates);

        assert!(result.is_err()); // Entity not found
    }

    #[test]
    fn test_soft_delete() {
        let db = Database::open_temp().unwrap();

        // Register schema
        let schema = serde_json::json!({
            "title": "Person",
            "version": "1.0.0",
            "short_name": "person",
            "properties": {
                "name": {"type": "string"}
            },
            "required": ["name"]
        });

        db.register_schema("person", schema).unwrap();

        // Insert entity
        let data = serde_json::json!({"name": "Alice"});
        let id = db.insert("tenant1", "person", data).unwrap();

        // Soft delete
        let deleted = db.delete("tenant1", id).unwrap();

        assert!(deleted.is_deleted());
        assert!(deleted.system.deleted_at.is_some());

        // Entity still exists in storage (soft deleted)
        let entity = db.get("tenant1", id).unwrap();
        assert!(entity.is_some());
        assert!(entity.unwrap().is_deleted());
    }

    #[test]
    fn test_hard_delete() {
        let db = Database::open_temp().unwrap();

        // Register schema
        let schema = serde_json::json!({
            "title": "Person",
            "version": "1.0.0",
            "short_name": "person",
            "properties": {
                "name": {"type": "string"}
            },
            "required": ["name"]
        });

        db.register_schema("person", schema).unwrap();

        // Insert entity
        let data = serde_json::json!({"name": "Alice"});
        let id = db.insert("tenant1", "person", data).unwrap();

        // Hard delete
        db.hard_delete("tenant1", id).unwrap();

        // Entity no longer exists
        let entity = db.get("tenant1", id).unwrap();
        assert!(entity.is_none());
    }

    #[test]
    fn test_hard_delete_removes_key_index() {
        let db = Database::open_temp().unwrap();

        // Register schema with key_field
        let schema = serde_json::json!({
            "title": "User",
            "version": "1.0.0",
            "short_name": "user",
            "json_schema_extra": {
                "key_field": "email"
            },
            "properties": {
                "email": {"type": "string"},
                "name": {"type": "string"}
            },
            "required": ["email", "name"]
        });

        db.register_schema("user", schema).unwrap();

        // Insert entity
        let data = serde_json::json!({"email": "alice@example.com", "name": "Alice"});
        let id = db.insert("tenant1", "user", data).unwrap();

        // Verify key lookup works
        let entity = db.get_by_key("tenant1", "user", "alice@example.com").unwrap();
        assert!(entity.is_some());

        // Hard delete
        db.hard_delete("tenant1", id).unwrap();

        // Key lookup should return None
        let entity = db.get_by_key("tenant1", "user", "alice@example.com").unwrap();
        assert!(entity.is_none());
    }
}
