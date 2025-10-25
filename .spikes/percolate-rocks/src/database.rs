//! High-level database API combining storage and schema registry.
//!
//! This is the main entry point for database operations.

use crate::schema::{SchemaRegistry, register_builtin_schemas};
use crate::storage::Storage;
use crate::types::{Result, Entity, Edge, DatabaseError};
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

    /// Batch insert multiple entities (optimized for bulk loading).
    ///
    /// # Arguments
    ///
    /// * `tenant_id` - Tenant identifier
    /// * `table` - Table/schema name
    /// * `entities` - Vector of entity data objects
    ///
    /// # Returns
    ///
    /// Vector of inserted entity UUIDs (in same order as input)
    ///
    /// # Errors
    ///
    /// Returns error if schema not found or any validation fails.
    /// On error, entire batch is rolled back (no partial inserts).
    ///
    /// # Performance
    ///
    /// Uses RocksDB write batch for atomic, efficient bulk inserts.
    /// Significantly faster than individual inserts for large datasets.
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// let people = vec![
    ///     json!({"name": "Alice", "age": 30}),
    ///     json!({"name": "Bob", "age": 25}),
    ///     json!({"name": "Charlie", "age": 35}),
    /// ];
    /// let ids = db.batch_insert("tenant1", "person", people)?;
    /// assert_eq!(ids.len(), 3);
    /// ```
    pub fn batch_insert(
        &self,
        tenant_id: &str,
        table: &str,
        entities: Vec<serde_json::Value>,
    ) -> Result<Vec<uuid::Uuid>> {
        use crate::types::{DatabaseError, generate_uuid};
        use crate::schema::{SchemaValidator, PydanticSchemaParser};
        use rocksdb::WriteBatch;

        // Get schema once
        let registry = self.registry.read()
            .map_err(|e| DatabaseError::InternalError(format!("Lock error: {}", e)))?;

        let schema = registry.get(table)?;
        let validator = SchemaValidator::new(schema.clone())?;
        let key_field_opt = PydanticSchemaParser::extract_key_field(schema);
        let key_field = key_field_opt.as_deref();

        // Validate all entities first (fail fast before writing)
        for data in &entities {
            validator.validate(data)?;
        }

        // Prepare batch write
        let mut batch = WriteBatch::default();
        let mut ids = Vec::with_capacity(entities.len());

        for data in entities {
            // Generate deterministic UUID
            let id = generate_uuid(table, &data, key_field);
            ids.push(id);

            // Create entity with system fields
            let entity = Entity::new(id, table.to_string(), data.clone());

            // Serialize entity
            let entity_key = crate::storage::keys::encode_entity_key(tenant_id, id);
            let entity_value = serde_json::to_vec(&entity)?;

            // Add to batch
            let cf = self.storage.cf_handle(crate::storage::column_families::CF_ENTITIES);
            batch.put_cf(&cf, &entity_key, &entity_value);

            // Add key index to batch
            if let Some(key_value) = extract_key_value(&entity.properties, key_field) {
                let index_key = crate::storage::keys::encode_key_index(tenant_id, &key_value, id);
                let index_value = serde_json::json!({"type": table}).to_string();
                let cf_key_index = self.storage.cf_handle(crate::storage::column_families::CF_KEY_INDEX);
                batch.put_cf(&cf_key_index, &index_key, index_value.as_bytes());
            }
        }

        // Write batch atomically
        self.storage.db().write(batch)
            .map_err(|e| DatabaseError::StorageError(e))?;

        Ok(ids)
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

    /// List entities in a table with optional filters.
    ///
    /// # Arguments
    ///
    /// * `tenant_id` - Tenant identifier
    /// * `table` - Table/schema name to scan
    /// * `include_deleted` - Include soft-deleted entities (default: false)
    /// * `limit` - Maximum number of entities to return (optional)
    ///
    /// # Returns
    ///
    /// Vector of entities matching criteria
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// // List all active persons
    /// let persons = db.list("tenant1", "person", false, None)?;
    ///
    /// // List first 10 entities including deleted
    /// let all = db.list("tenant1", "person", true, Some(10))?;
    /// ```
    pub fn list(
        &self,
        tenant_id: &str,
        table: &str,
        include_deleted: bool,
        limit: Option<usize>,
    ) -> Result<Vec<Entity>> {
        use rocksdb::IteratorMode;

        // Scan prefix: entity:{tenant_id}:
        let prefix = format!("entity:{}:", tenant_id).into_bytes();
        let cf = self.storage.cf_handle(crate::storage::column_families::CF_ENTITIES);

        let iter = self.storage.db().iterator_cf(
            &cf,
            IteratorMode::From(&prefix, rocksdb::Direction::Forward),
        );

        let mut entities = Vec::new();
        let mut count = 0;

        for item in iter {
            let (key, value) = item.map_err(|e| crate::types::DatabaseError::StorageError(e))?;

            // Check if key still matches prefix
            if !key.starts_with(&prefix) {
                break;
            }

            // Deserialize entity
            let entity: Entity = serde_json::from_slice(&value)?;

            // Filter by table type
            if entity.system.entity_type != table {
                continue;
            }

            // Filter deleted entities unless explicitly included
            if !include_deleted && entity.is_deleted() {
                continue;
            }

            entities.push(entity);
            count += 1;

            // Check limit
            if let Some(max) = limit {
                if count >= max {
                    break;
                }
            }
        }

        Ok(entities)
    }

    /// Count entities in a table.
    ///
    /// # Arguments
    ///
    /// * `tenant_id` - Tenant identifier
    /// * `table` - Table/schema name
    /// * `include_deleted` - Include soft-deleted entities (default: false)
    ///
    /// # Returns
    ///
    /// Number of entities matching criteria
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// let count = db.count("tenant1", "person", false)?;
    /// println!("Active persons: {}", count);
    /// ```
    pub fn count(&self, tenant_id: &str, table: &str, include_deleted: bool) -> Result<usize> {
        use rocksdb::IteratorMode;

        let prefix = format!("entity:{}:", tenant_id).into_bytes();
        let cf = self.storage.cf_handle(crate::storage::column_families::CF_ENTITIES);

        let iter = self.storage.db().iterator_cf(
            &cf,
            IteratorMode::From(&prefix, rocksdb::Direction::Forward),
        );

        let mut count = 0;

        for item in iter {
            let (key, value) = item.map_err(|e| crate::types::DatabaseError::StorageError(e))?;

            if !key.starts_with(&prefix) {
                break;
            }

            let entity: Entity = serde_json::from_slice(&value)?;

            if entity.system.entity_type != table {
                continue;
            }

            if !include_deleted && entity.is_deleted() {
                continue;
            }

            count += 1;
        }

        Ok(count)
    }

    /// Check if entity exists.
    ///
    /// # Arguments
    ///
    /// * `tenant_id` - Tenant identifier
    /// * `entity_id` - Entity UUID
    ///
    /// # Returns
    ///
    /// `true` if entity exists, `false` otherwise
    ///
    /// # Note
    ///
    /// More efficient than `get()` when you only need to check existence.
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// if db.exists("tenant1", entity_id)? {
    ///     println!("Entity exists");
    /// }
    /// ```
    pub fn exists(&self, tenant_id: &str, entity_id: uuid::Uuid) -> Result<bool> {
        let key = crate::storage::keys::encode_entity_key(tenant_id, entity_id);

        let value = self.storage.get(
            crate::storage::column_families::CF_ENTITIES,
            &key,
        )?;

        Ok(value.is_some())
    }

    /// Add edge between entities.
    ///
    /// # Arguments
    ///
    /// * `tenant_id` - Tenant identifier
    /// * `src_id` - Source entity UUID
    /// * `dst_id` - Destination entity UUID
    /// * `rel_type` - Relationship type (e.g., "authored", "references")
    /// * `properties` - Optional edge properties
    ///
    /// # Returns
    ///
    /// Created edge
    ///
    /// # Errors
    ///
    /// Returns error if entities don't exist
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// db.add_edge("tenant1", author_id, article_id, "authored", None)?;
    /// db.add_edge("tenant1", article1_id, article2_id, "references",
    ///     Some(json!({"weight": 0.8})))?;
    /// ```
    pub fn add_edge(
        &self,
        tenant_id: &str,
        src_id: uuid::Uuid,
        dst_id: uuid::Uuid,
        rel_type: &str,
        properties: Option<serde_json::Value>,
    ) -> Result<Edge> {
        use crate::types::{DatabaseError, Edge};

        // Verify both entities exist
        if !self.exists(tenant_id, src_id)? {
            return Err(DatabaseError::EntityNotFound(src_id));
        }
        if !self.exists(tenant_id, dst_id)? {
            return Err(DatabaseError::EntityNotFound(dst_id));
        }

        // Create edge
        let mut edge = Edge::new(src_id, dst_id, rel_type.to_string());

        // Add properties if provided
        if let Some(props) = properties {
            if let Some(obj) = props.as_object() {
                for (key, value) in obj {
                    edge.add_property(key.clone(), value.clone());
                }
            }
        }

        // Serialize edge
        let edge_value = serde_json::to_vec(&edge)?;

        // Store in forward CF (src → dst)
        let forward_key = crate::storage::keys::encode_edge_key(src_id, dst_id, rel_type);
        let cf_edges = self.storage.cf_handle(crate::storage::column_families::CF_EDGES);
        self.storage.db().put_cf(&cf_edges, &forward_key, &edge_value)
            .map_err(|e| DatabaseError::StorageError(e))?;

        // Store in reverse CF (dst ← src)
        let reverse_key = crate::storage::keys::encode_reverse_edge_key(dst_id, src_id, rel_type);
        let cf_edges_reverse = self.storage.cf_handle(crate::storage::column_families::CF_EDGES_REVERSE);
        self.storage.db().put_cf(&cf_edges_reverse, &reverse_key, &edge_value)
            .map_err(|e| DatabaseError::StorageError(e))?;

        Ok(edge)
    }

    /// Get outgoing edges from an entity.
    ///
    /// # Arguments
    ///
    /// * `src_id` - Source entity UUID
    /// * `rel_type` - Optional relationship type filter
    ///
    /// # Returns
    ///
    /// Vector of outgoing edges
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// // Get all outgoing edges
    /// let edges = db.get_edges(author_id, None)?;
    ///
    /// // Get only "authored" edges
    /// let authored = db.get_edges(author_id, Some("authored"))?;
    /// ```
    pub fn get_edges(&self, src_id: uuid::Uuid, rel_type: Option<&str>) -> Result<Vec<Edge>> {
        use rocksdb::IteratorMode;

        // Prefix: src:{uuid}:
        let prefix = format!("src:{}:", src_id).into_bytes();
        let cf = self.storage.cf_handle(crate::storage::column_families::CF_EDGES);

        let iter = self.storage.db().iterator_cf(
            &cf,
            IteratorMode::From(&prefix, rocksdb::Direction::Forward),
        );

        let mut edges = Vec::new();

        for item in iter {
            let (key, value) = item.map_err(|e| crate::types::DatabaseError::StorageError(e))?;

            if !key.starts_with(&prefix) {
                break;
            }

            // Deserialize edge
            let edge: Edge = serde_json::from_slice(&value)?;

            // Filter by rel_type if specified
            if let Some(rel) = rel_type {
                if edge.rel_type != rel {
                    continue;
                }
            }

            edges.push(edge);
        }

        Ok(edges)
    }

    /// Get incoming edges to an entity.
    ///
    /// # Arguments
    ///
    /// * `dst_id` - Destination entity UUID
    /// * `rel_type` - Optional relationship type filter
    ///
    /// # Returns
    ///
    /// Vector of incoming edges
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// // Get all incoming edges
    /// let edges = db.get_incoming_edges(article_id, None)?;
    ///
    /// // Get only "references" edges
    /// let refs = db.get_incoming_edges(article_id, Some("references"))?;
    /// ```
    pub fn get_incoming_edges(&self, dst_id: uuid::Uuid, rel_type: Option<&str>) -> Result<Vec<Edge>> {
        use rocksdb::IteratorMode;

        // Prefix: dst:{uuid}:
        let prefix = format!("dst:{}:", dst_id).into_bytes();
        let cf = self.storage.cf_handle(crate::storage::column_families::CF_EDGES_REVERSE);

        let iter = self.storage.db().iterator_cf(
            &cf,
            IteratorMode::From(&prefix, rocksdb::Direction::Forward),
        );

        let mut edges = Vec::new();

        for item in iter {
            let (key, value) = item.map_err(|e| crate::types::DatabaseError::StorageError(e))?;

            if !key.starts_with(&prefix) {
                break;
            }

            // Deserialize edge
            let edge: Edge = serde_json::from_slice(&value)?;

            // Filter by rel_type if specified
            if let Some(rel) = rel_type {
                if edge.rel_type != rel {
                    continue;
                }
            }

            edges.push(edge);
        }

        Ok(edges)
    }

    /// Delete edge between entities.
    ///
    /// # Arguments
    ///
    /// * `src_id` - Source entity UUID
    /// * `dst_id` - Destination entity UUID
    /// * `rel_type` - Relationship type
    ///
    /// # Returns
    ///
    /// Ok if edge was deleted or didn't exist
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// db.delete_edge(author_id, article_id, "authored")?;
    /// ```
    pub fn delete_edge(&self, src_id: uuid::Uuid, dst_id: uuid::Uuid, rel_type: &str) -> Result<()> {
        use crate::types::DatabaseError;

        // Delete from forward CF
        let forward_key = crate::storage::keys::encode_edge_key(src_id, dst_id, rel_type);
        let cf_edges = self.storage.cf_handle(crate::storage::column_families::CF_EDGES);
        self.storage.db().delete_cf(&cf_edges, &forward_key)
            .map_err(|e| DatabaseError::StorageError(e))?;

        // Delete from reverse CF
        let reverse_key = crate::storage::keys::encode_reverse_edge_key(dst_id, src_id, rel_type);
        let cf_edges_reverse = self.storage.cf_handle(crate::storage::column_families::CF_EDGES_REVERSE);
        self.storage.db().delete_cf(&cf_edges_reverse, &reverse_key)
            .map_err(|e| DatabaseError::StorageError(e))?;

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

    /// Breadth-first traversal from starting entity.
    ///
    /// # Arguments
    ///
    /// * `start_id` - Starting entity UUID
    /// * `direction` - Traversal direction (out/in/both)
    /// * `depth` - Maximum traversal depth
    /// * `rel_type` - Optional relationship type filter
    ///
    /// # Returns
    ///
    /// Vector of entity UUIDs in BFS order
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError` if traversal fails
    pub fn traverse_bfs(
        &self,
        start_id: uuid::Uuid,
        direction: crate::graph::TraversalDirection,
        depth: usize,
        rel_type: Option<&str>,
    ) -> Result<Vec<uuid::Uuid>> {
        let traversal = crate::graph::GraphTraversal::new(self as &dyn crate::graph::EdgeProvider);
        traversal.bfs(start_id, direction, depth, rel_type)
    }

    /// Depth-first traversal from starting entity.
    ///
    /// # Arguments
    ///
    /// * `start_id` - Starting entity UUID
    /// * `direction` - Traversal direction (out/in/both)
    /// * `depth` - Maximum traversal depth
    /// * `rel_type` - Optional relationship type filter
    ///
    /// # Returns
    ///
    /// Vector of entity UUIDs in DFS order
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError` if traversal fails
    pub fn traverse_dfs(
        &self,
        start_id: uuid::Uuid,
        direction: crate::graph::TraversalDirection,
        depth: usize,
        rel_type: Option<&str>,
    ) -> Result<Vec<uuid::Uuid>> {
        let traversal = crate::graph::GraphTraversal::new(self as &dyn crate::graph::EdgeProvider);
        traversal.dfs(start_id, direction, depth, rel_type)
    }

    /// Find shortest path between two entities.
    ///
    /// # Arguments
    ///
    /// * `start_id` - Starting entity UUID
    /// * `end_id` - Target entity UUID
    /// * `direction` - Traversal direction (out/in/both)
    /// * `max_depth` - Maximum search depth
    ///
    /// # Returns
    ///
    /// Vector of entity UUIDs representing path, or empty if no path found
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError` if search fails
    pub fn shortest_path(
        &self,
        start_id: uuid::Uuid,
        end_id: uuid::Uuid,
        direction: crate::graph::TraversalDirection,
        max_depth: usize,
    ) -> Result<Vec<uuid::Uuid>> {
        let traversal = crate::graph::GraphTraversal::new(self as &dyn crate::graph::EdgeProvider);
        traversal.shortest_path(start_id, end_id, direction, max_depth)
    }
}

/// Implement EdgeProvider trait for Database.
impl crate::graph::EdgeProvider for Database {
    fn get_outgoing(&self, node: uuid::Uuid, rel_type: Option<&str>) -> Result<Vec<Edge>> {
        self.get_edges(node, rel_type)
    }

    fn get_incoming(&self, node: uuid::Uuid, rel_type: Option<&str>) -> Result<Vec<Edge>> {
        self.get_incoming_edges(node, rel_type)
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

    #[test]
    fn test_list_entities() {
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

        // Insert multiple entities
        db.insert("tenant1", "person", serde_json::json!({"name": "Alice"})).unwrap();
        db.insert("tenant1", "person", serde_json::json!({"name": "Bob"})).unwrap();
        db.insert("tenant1", "person", serde_json::json!({"name": "Charlie"})).unwrap();

        // List all persons
        let entities = db.list("tenant1", "person", false, None).unwrap();
        assert_eq!(entities.len(), 3);

        let names: Vec<&str> = entities
            .iter()
            .map(|e| e.properties.get("name").unwrap().as_str().unwrap())
            .collect();

        assert!(names.contains(&"Alice"));
        assert!(names.contains(&"Bob"));
        assert!(names.contains(&"Charlie"));
    }

    #[test]
    fn test_list_with_limit() {
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

        // Insert multiple entities
        for i in 0..10 {
            db.insert("tenant1", "person", serde_json::json!({"name": format!("Person {}", i)})).unwrap();
        }

        // List with limit
        let entities = db.list("tenant1", "person", false, Some(5)).unwrap();
        assert_eq!(entities.len(), 5);
    }

    #[test]
    fn test_list_excludes_deleted() {
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

        // Insert entities
        let id1 = db.insert("tenant1", "person", serde_json::json!({"name": "Alice"})).unwrap();
        db.insert("tenant1", "person", serde_json::json!({"name": "Bob"})).unwrap();

        // Soft delete one entity
        db.delete("tenant1", id1).unwrap();

        // List without deleted entities
        let entities = db.list("tenant1", "person", false, None).unwrap();
        assert_eq!(entities.len(), 1);
        assert_eq!(entities[0].properties.get("name").unwrap(), "Bob");

        // List with deleted entities
        let all_entities = db.list("tenant1", "person", true, None).unwrap();
        assert_eq!(all_entities.len(), 2);
    }

    #[test]
    fn test_list_tenant_isolation() {
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

        // Insert entities in different tenants
        db.insert("tenant1", "person", serde_json::json!({"name": "Alice"})).unwrap();
        db.insert("tenant1", "person", serde_json::json!({"name": "Bob"})).unwrap();
        db.insert("tenant2", "person", serde_json::json!({"name": "Charlie"})).unwrap();

        // List for tenant1
        let entities1 = db.list("tenant1", "person", false, None).unwrap();
        assert_eq!(entities1.len(), 2);

        // List for tenant2
        let entities2 = db.list("tenant2", "person", false, None).unwrap();
        assert_eq!(entities2.len(), 1);
    }

    #[test]
    fn test_list_filters_by_table() {
        let db = Database::open_temp().unwrap();

        // Register multiple schemas
        let person_schema = serde_json::json!({
            "title": "Person",
            "version": "1.0.0",
            "short_name": "person",
            "properties": {"name": {"type": "string"}},
            "required": ["name"]
        });

        let project_schema = serde_json::json!({
            "title": "Project",
            "version": "1.0.0",
            "short_name": "project",
            "properties": {"name": {"type": "string"}},
            "required": ["name"]
        });

        db.register_schema("person", person_schema).unwrap();
        db.register_schema("project", project_schema).unwrap();

        // Insert entities in different tables
        db.insert("tenant1", "person", serde_json::json!({"name": "Alice"})).unwrap();
        db.insert("tenant1", "person", serde_json::json!({"name": "Bob"})).unwrap();
        db.insert("tenant1", "project", serde_json::json!({"name": "Project X"})).unwrap();

        // List only persons
        let persons = db.list("tenant1", "person", false, None).unwrap();
        assert_eq!(persons.len(), 2);

        // List only projects
        let projects = db.list("tenant1", "project", false, None).unwrap();
        assert_eq!(projects.len(), 1);
    }

    #[test]
    fn test_batch_insert() {
        let db = Database::open_temp().unwrap();

        // Register schema
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

        // Batch insert
        let people = vec![
            serde_json::json!({"name": "Alice", "age": 30}),
            serde_json::json!({"name": "Bob", "age": 25}),
            serde_json::json!({"name": "Charlie", "age": 35}),
        ];

        let ids = db.batch_insert("tenant1", "person", people).unwrap();
        assert_eq!(ids.len(), 3);

        // Verify all entities were inserted
        let entities = db.list("tenant1", "person", false, None).unwrap();
        assert_eq!(entities.len(), 3);

        // Verify IDs match
        for id in &ids {
            assert!(db.exists("tenant1", *id).unwrap());
        }
    }

    #[test]
    fn test_batch_insert_validation_failure() {
        let db = Database::open_temp().unwrap();

        // Register schema with strict validation
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

        // Batch with one invalid entity (missing required field)
        let people = vec![
            serde_json::json!({"name": "Alice", "age": 30}),
            serde_json::json!({"name": "Bob"}),  // Missing required "age"
            serde_json::json!({"name": "Charlie", "age": 35}),
        ];

        let result = db.batch_insert("tenant1", "person", people);
        assert!(result.is_err());

        // No entities should be inserted (atomic rollback)
        let entities = db.list("tenant1", "person", false, None).unwrap();
        assert_eq!(entities.len(), 0);
    }

    #[test]
    fn test_batch_insert_deterministic_uuids() {
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

        // Batch insert
        let users = vec![
            serde_json::json!({"email": "alice@example.com", "name": "Alice"}),
            serde_json::json!({"email": "bob@example.com", "name": "Bob"}),
        ];

        let ids = db.batch_insert("tenant1", "user", users).unwrap();

        // Insert same data again
        let users2 = vec![
            serde_json::json!({"email": "alice@example.com", "name": "Alice"}),
            serde_json::json!({"email": "bob@example.com", "name": "Bob"}),
        ];

        let ids2 = db.batch_insert("tenant1", "user", users2).unwrap();

        // Same data should generate same UUIDs
        assert_eq!(ids, ids2);
    }

    #[test]
    fn test_count() {
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

        // Initially zero
        assert_eq!(db.count("tenant1", "person", false).unwrap(), 0);

        // Insert entities
        db.insert("tenant1", "person", serde_json::json!({"name": "Alice"})).unwrap();
        db.insert("tenant1", "person", serde_json::json!({"name": "Bob"})).unwrap();
        db.insert("tenant1", "person", serde_json::json!({"name": "Charlie"})).unwrap();

        // Count should be 3
        assert_eq!(db.count("tenant1", "person", false).unwrap(), 3);
    }

    #[test]
    fn test_count_excludes_deleted() {
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

        // Insert entities
        let id1 = db.insert("tenant1", "person", serde_json::json!({"name": "Alice"})).unwrap();
        db.insert("tenant1", "person", serde_json::json!({"name": "Bob"})).unwrap();

        // Soft delete one
        db.delete("tenant1", id1).unwrap();

        // Count without deleted
        assert_eq!(db.count("tenant1", "person", false).unwrap(), 1);

        // Count with deleted
        assert_eq!(db.count("tenant1", "person", true).unwrap(), 2);
    }

    #[test]
    fn test_exists() {
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
        let id = db.insert("tenant1", "person", serde_json::json!({"name": "Alice"})).unwrap();

        // Should exist
        assert!(db.exists("tenant1", id).unwrap());

        // Non-existent UUID
        assert!(!db.exists("tenant1", uuid::Uuid::new_v4()).unwrap());

        // Hard delete
        db.hard_delete("tenant1", id).unwrap();

        // Should not exist
        assert!(!db.exists("tenant1", id).unwrap());
    }

    #[test]
    fn test_exists_with_soft_delete() {
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
        let id = db.insert("tenant1", "person", serde_json::json!({"name": "Alice"})).unwrap();

        // Soft delete
        db.delete("tenant1", id).unwrap();

        // Should still exist (soft deleted)
        assert!(db.exists("tenant1", id).unwrap());
    }

    #[test]
    fn test_add_edge() {
        let db = Database::open_temp().unwrap();

        // Register schema
        let schema = serde_json::json!({
            "title": "Person",
            "version": "1.0.0",
            "short_name": "person",
            "properties": {"name": {"type": "string"}},
            "required": ["name"]
        });

        db.register_schema("person", schema).unwrap();

        // Insert entities
        let alice_id = db.insert("tenant1", "person", serde_json::json!({"name": "Alice"})).unwrap();
        let bob_id = db.insert("tenant1", "person", serde_json::json!({"name": "Bob"})).unwrap();

        // Add edge
        let edge = db.add_edge("tenant1", alice_id, bob_id, "knows", None).unwrap();

        assert_eq!(edge.src, alice_id);
        assert_eq!(edge.dst, bob_id);
        assert_eq!(edge.rel_type, "knows");
    }

    #[test]
    fn test_add_edge_with_properties() {
        let db = Database::open_temp().unwrap();

        // Register schema
        let schema = serde_json::json!({
            "title": "Person",
            "version": "1.0.0",
            "short_name": "person",
            "properties": {"name": {"type": "string"}},
            "required": ["name"]
        });

        db.register_schema("person", schema).unwrap();

        // Insert entities
        let alice_id = db.insert("tenant1", "person", serde_json::json!({"name": "Alice"})).unwrap();
        let bob_id = db.insert("tenant1", "person", serde_json::json!({"name": "Bob"})).unwrap();

        // Add edge with properties
        let props = serde_json::json!({"weight": 0.8, "since": "2020-01-01"});
        let edge = db.add_edge("tenant1", alice_id, bob_id, "knows", Some(props)).unwrap();

        assert_eq!(edge.data.properties.get("weight").unwrap(), &serde_json::json!(0.8));
        assert_eq!(edge.data.properties.get("since").unwrap(), "2020-01-01");
    }

    #[test]
    fn test_add_edge_nonexistent_entity() {
        let db = Database::open_temp().unwrap();

        // Register schema
        let schema = serde_json::json!({
            "title": "Person",
            "version": "1.0.0",
            "short_name": "person",
            "properties": {"name": {"type": "string"}},
            "required": ["name"]
        });

        db.register_schema("person", schema).unwrap();

        // Insert one entity
        let alice_id = db.insert("tenant1", "person", serde_json::json!({"name": "Alice"})).unwrap();

        // Try to add edge to nonexistent entity
        let result = db.add_edge("tenant1", alice_id, uuid::Uuid::new_v4(), "knows", None);
        assert!(result.is_err());
    }

    #[test]
    fn test_get_edges() {
        let db = Database::open_temp().unwrap();

        // Register schema
        let schema = serde_json::json!({
            "title": "Person",
            "version": "1.0.0",
            "short_name": "person",
            "properties": {"name": {"type": "string"}},
            "required": ["name"]
        });

        db.register_schema("person", schema).unwrap();

        // Insert entities
        let alice_id = db.insert("tenant1", "person", serde_json::json!({"name": "Alice"})).unwrap();
        let bob_id = db.insert("tenant1", "person", serde_json::json!({"name": "Bob"})).unwrap();
        let charlie_id = db.insert("tenant1", "person", serde_json::json!({"name": "Charlie"})).unwrap();

        // Add edges
        db.add_edge("tenant1", alice_id, bob_id, "knows", None).unwrap();
        db.add_edge("tenant1", alice_id, charlie_id, "knows", None).unwrap();
        db.add_edge("tenant1", alice_id, bob_id, "likes", None).unwrap();

        // Get all outgoing edges
        let edges = db.get_edges(alice_id, None).unwrap();
        assert_eq!(edges.len(), 3);

        // Get only "knows" edges
        let knows_edges = db.get_edges(alice_id, Some("knows")).unwrap();
        assert_eq!(knows_edges.len(), 2);

        // Get only "likes" edges
        let likes_edges = db.get_edges(alice_id, Some("likes")).unwrap();
        assert_eq!(likes_edges.len(), 1);
    }

    #[test]
    fn test_get_incoming_edges() {
        let db = Database::open_temp().unwrap();

        // Register schema
        let schema = serde_json::json!({
            "title": "Person",
            "version": "1.0.0",
            "short_name": "person",
            "properties": {"name": {"type": "string"}},
            "required": ["name"]
        });

        db.register_schema("person", schema).unwrap();

        // Insert entities
        let alice_id = db.insert("tenant1", "person", serde_json::json!({"name": "Alice"})).unwrap();
        let bob_id = db.insert("tenant1", "person", serde_json::json!({"name": "Bob"})).unwrap();
        let charlie_id = db.insert("tenant1", "person", serde_json::json!({"name": "Charlie"})).unwrap();

        // Add edges (multiple entities pointing to Bob)
        db.add_edge("tenant1", alice_id, bob_id, "knows", None).unwrap();
        db.add_edge("tenant1", charlie_id, bob_id, "knows", None).unwrap();

        // Get incoming edges to Bob
        let edges = db.get_incoming_edges(bob_id, None).unwrap();
        assert_eq!(edges.len(), 2);

        // Check sources
        let sources: Vec<uuid::Uuid> = edges.iter().map(|e| e.src).collect();
        assert!(sources.contains(&alice_id));
        assert!(sources.contains(&charlie_id));
    }

    #[test]
    fn test_delete_edge() {
        let db = Database::open_temp().unwrap();

        // Register schema
        let schema = serde_json::json!({
            "title": "Person",
            "version": "1.0.0",
            "short_name": "person",
            "properties": {"name": {"type": "string"}},
            "required": ["name"]
        });

        db.register_schema("person", schema).unwrap();

        // Insert entities
        let alice_id = db.insert("tenant1", "person", serde_json::json!({"name": "Alice"})).unwrap();
        let bob_id = db.insert("tenant1", "person", serde_json::json!({"name": "Bob"})).unwrap();

        // Add edge
        db.add_edge("tenant1", alice_id, bob_id, "knows", None).unwrap();

        // Verify edge exists
        let edges = db.get_edges(alice_id, None).unwrap();
        assert_eq!(edges.len(), 1);

        // Delete edge
        db.delete_edge(alice_id, bob_id, "knows").unwrap();

        // Verify edge is gone
        let edges = db.get_edges(alice_id, None).unwrap();
        assert_eq!(edges.len(), 0);

        // Also gone from reverse index
        let incoming = db.get_incoming_edges(bob_id, None).unwrap();
        assert_eq!(incoming.len(), 0);
    }

    #[test]
    fn test_bidirectional_edges() {
        let db = Database::open_temp().unwrap();

        // Register schema
        let schema = serde_json::json!({
            "title": "Person",
            "version": "1.0.0",
            "short_name": "person",
            "properties": {"name": {"type": "string"}},
            "required": ["name"]
        });

        db.register_schema("person", schema).unwrap();

        // Insert entities
        let alice_id = db.insert("tenant1", "person", serde_json::json!({"name": "Alice"})).unwrap();
        let bob_id = db.insert("tenant1", "person", serde_json::json!({"name": "Bob"})).unwrap();

        // Add edge
        db.add_edge("tenant1", alice_id, bob_id, "knows", None).unwrap();

        // Query from both directions
        let outgoing = db.get_edges(alice_id, None).unwrap();
        let incoming = db.get_incoming_edges(bob_id, None).unwrap();

        assert_eq!(outgoing.len(), 1);
        assert_eq!(incoming.len(), 1);

        // Both should have same data
        assert_eq!(outgoing[0].src, incoming[0].src);
        assert_eq!(outgoing[0].dst, incoming[0].dst);
        assert_eq!(outgoing[0].rel_type, incoming[0].rel_type);
    }

    #[test]
    fn test_traverse_bfs() {
        let db = Database::open_temp().unwrap();

        // Register schema
        let schema = serde_json::json!({
            "title": "Person",
            "version": "1.0.0",
            "short_name": "person",
            "properties": {"name": {"type": "string"}},
            "required": ["name"]
        });

        db.register_schema("person", schema).unwrap();

        // Create a graph: A -> B -> C -> D
        let a = db.insert("tenant1", "person", serde_json::json!({"name": "A"})).unwrap();
        let b = db.insert("tenant1", "person", serde_json::json!({"name": "B"})).unwrap();
        let c = db.insert("tenant1", "person", serde_json::json!({"name": "C"})).unwrap();
        let d = db.insert("tenant1", "person", serde_json::json!({"name": "D"})).unwrap();

        db.add_edge("tenant1", a, b, "knows", None).unwrap();
        db.add_edge("tenant1", b, c, "knows", None).unwrap();
        db.add_edge("tenant1", c, d, "knows", None).unwrap();

        // BFS from A with depth 2 should find A, B, C
        let result = db.traverse_bfs(a, crate::graph::TraversalDirection::Out, 2, None).unwrap();
        assert_eq!(result.len(), 3);
        assert_eq!(result[0], a);
        assert_eq!(result[1], b);
        assert_eq!(result[2], c);

        // BFS from A with depth 3 should find all
        let result = db.traverse_bfs(a, crate::graph::TraversalDirection::Out, 3, None).unwrap();
        assert_eq!(result.len(), 4);
    }

    #[test]
    fn test_traverse_dfs() {
        let db = Database::open_temp().unwrap();

        // Register schema
        let schema = serde_json::json!({
            "title": "Person",
            "version": "1.0.0",
            "short_name": "person",
            "properties": {"name": {"type": "string"}},
            "required": ["name"]
        });

        db.register_schema("person", schema).unwrap();

        // Create a graph: A -> B, A -> C
        let a = db.insert("tenant1", "person", serde_json::json!({"name": "A"})).unwrap();
        let b = db.insert("tenant1", "person", serde_json::json!({"name": "B"})).unwrap();
        let c = db.insert("tenant1", "person", serde_json::json!({"name": "C"})).unwrap();

        db.add_edge("tenant1", a, b, "knows", None).unwrap();
        db.add_edge("tenant1", a, c, "knows", None).unwrap();

        // DFS from A should find all 3
        let result = db.traverse_dfs(a, crate::graph::TraversalDirection::Out, 2, None).unwrap();
        assert_eq!(result.len(), 3);
        assert_eq!(result[0], a);
        // B and C order depends on edge insertion order
    }

    #[test]
    fn test_traverse_incoming() {
        let db = Database::open_temp().unwrap();

        // Register schema
        let schema = serde_json::json!({
            "title": "Person",
            "version": "1.0.0",
            "short_name": "person",
            "properties": {"name": {"type": "string"}},
            "required": ["name"]
        });

        db.register_schema("person", schema).unwrap();

        // Create a graph: A -> C, B -> C
        let a = db.insert("tenant1", "person", serde_json::json!({"name": "A"})).unwrap();
        let b = db.insert("tenant1", "person", serde_json::json!({"name": "B"})).unwrap();
        let c = db.insert("tenant1", "person", serde_json::json!({"name": "C"})).unwrap();

        db.add_edge("tenant1", a, c, "knows", None).unwrap();
        db.add_edge("tenant1", b, c, "knows", None).unwrap();

        // Traverse incoming from C should find C, A, B
        let result = db.traverse_bfs(c, crate::graph::TraversalDirection::In, 2, None).unwrap();
        assert_eq!(result.len(), 3);
        assert_eq!(result[0], c);
        assert!(result.contains(&a));
        assert!(result.contains(&b));
    }

    #[test]
    fn test_shortest_path() {
        let db = Database::open_temp().unwrap();

        // Register schema
        let schema = serde_json::json!({
            "title": "Person",
            "version": "1.0.0",
            "short_name": "person",
            "properties": {"name": {"type": "string"}},
            "required": ["name"]
        });

        db.register_schema("person", schema).unwrap();

        // Create a graph: A -> B -> C -> D
        let a = db.insert("tenant1", "person", serde_json::json!({"name": "A"})).unwrap();
        let b = db.insert("tenant1", "person", serde_json::json!({"name": "B"})).unwrap();
        let c = db.insert("tenant1", "person", serde_json::json!({"name": "C"})).unwrap();
        let d = db.insert("tenant1", "person", serde_json::json!({"name": "D"})).unwrap();

        db.add_edge("tenant1", a, b, "knows", None).unwrap();
        db.add_edge("tenant1", b, c, "knows", None).unwrap();
        db.add_edge("tenant1", c, d, "knows", None).unwrap();

        // Find path from A to D
        let path = db.shortest_path(a, d, crate::graph::TraversalDirection::Out, 5).unwrap();
        assert_eq!(path.len(), 4);
        assert_eq!(path[0], a);
        assert_eq!(path[1], b);
        assert_eq!(path[2], c);
        assert_eq!(path[3], d);

        // No path exists (wrong direction)
        let path = db.shortest_path(d, a, crate::graph::TraversalDirection::Out, 5).unwrap();
        assert_eq!(path.len(), 0);
    }

    #[test]
    fn test_shortest_path_not_found() {
        let db = Database::open_temp().unwrap();

        // Register schema
        let schema = serde_json::json!({
            "title": "Person",
            "version": "1.0.0",
            "short_name": "person",
            "properties": {"name": {"type": "string"}},
            "required": ["name"]
        });

        db.register_schema("person", schema).unwrap();

        // Create two disconnected nodes
        let a = db.insert("tenant1", "person", serde_json::json!({"name": "A"})).unwrap();
        let b = db.insert("tenant1", "person", serde_json::json!({"name": "B"})).unwrap();

        // No path should exist
        let path = db.shortest_path(a, b, crate::graph::TraversalDirection::Out, 5).unwrap();
        assert_eq!(path.len(), 0);
    }

    #[test]
    fn test_traverse_with_rel_type_filter() {
        let db = Database::open_temp().unwrap();

        // Register schema
        let schema = serde_json::json!({
            "title": "Person",
            "version": "1.0.0",
            "short_name": "person",
            "properties": {"name": {"type": "string"}},
            "required": ["name"]
        });

        db.register_schema("person", schema).unwrap();

        // Create a graph with different relationship types
        let a = db.insert("tenant1", "person", serde_json::json!({"name": "A"})).unwrap();
        let b = db.insert("tenant1", "person", serde_json::json!({"name": "B"})).unwrap();
        let c = db.insert("tenant1", "person", serde_json::json!({"name": "C"})).unwrap();

        db.add_edge("tenant1", a, b, "knows", None).unwrap();
        db.add_edge("tenant1", a, c, "works_with", None).unwrap();

        // Only follow "knows" edges
        let result = db.traverse_bfs(a, crate::graph::TraversalDirection::Out, 2, Some("knows")).unwrap();
        assert_eq!(result.len(), 2); // A and B only
        assert!(result.contains(&a));
        assert!(result.contains(&b));
        assert!(!result.contains(&c));
    }
}
