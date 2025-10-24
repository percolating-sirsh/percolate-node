//! Main database interface.

use crate::embeddings::EmbeddingProvider;
use crate::memory::{EntityStore, SchemaRegistry};
use crate::storage::Storage;
use crate::types::{DatabaseError, Entity, Result};
use std::path::Path;
use std::sync::Arc;
use uuid::Uuid;

/// REM Database.
pub struct Database {
    pub tenant_id: String,
    storage: Storage,
    entity_store: EntityStore,
    schema_registry: Arc<SchemaRegistry>,
    pub embedding_provider: Option<Arc<EmbeddingProvider>>,
}

impl Database {
    /// Open database for tenant.
    pub fn open<P: AsRef<Path>>(path: P, tenant_id: &str) -> Result<Self> {
        Self::open_with_embeddings(path, tenant_id, true)
    }

    /// Open database with optional embedding support.
    pub fn open_with_embeddings<P: AsRef<Path>>(
        path: P,
        tenant_id: &str,
        enable_embeddings: bool,
    ) -> Result<Self> {
        let storage = Storage::open(path)?;
        let entity_store = EntityStore::new(storage.clone());
        let schema_registry = Arc::new(SchemaRegistry::new());

        let embedding_provider = if enable_embeddings {
            Some(Arc::new(EmbeddingProvider::new()?))
        } else {
            None
        };

        let db = Self {
            tenant_id: tenant_id.to_string(),
            storage,
            entity_store,
            schema_registry,
            embedding_provider,
        };

        // Load persisted schemas from database
        db.load_schemas()?;

        Ok(db)
    }

    /// Load all schemas from database entities.
    fn load_schemas(&self) -> Result<()> {
        // Scan for all schema entities
        let schema_entities = self.entity_store.scan_by_type(&self.tenant_id, "schema")?;

        for entity in schema_entities {
            // Extract schema name (from fully_qualified_name or short_name or fallback)
            let name = entity
                .properties
                .get("fully_qualified_name")
                .or_else(|| entity.properties.get("short_name"))
                .or_else(|| entity.properties.get("name"))
                .and_then(|v| v.as_str())
                .unwrap_or("unnamed")
                .to_string();

            // Extract REM-specific fields
            let indexed_fields = entity
                .properties
                .get("indexed_fields")
                .and_then(|v| v.as_array())
                .map(|arr| {
                    arr.iter()
                        .filter_map(|v| v.as_str().map(String::from))
                        .collect()
                })
                .unwrap_or_default();

            let embedding_fields = entity
                .properties
                .get("embedding_fields")
                .and_then(|v| v.as_array())
                .map(|arr| {
                    arr.iter()
                        .filter_map(|v| v.as_str().map(String::from))
                        .collect()
                })
                .unwrap_or_default();

            // The entire entity.properties IS the Pydantic JSON blob
            let schema = crate::memory::Schema::new(
                name,
                entity.properties.clone(),
                indexed_fields,
                embedding_fields,
            );
            self.schema_registry.register(schema)?;
        }

        Ok(())
    }

    /// Insert entity (synchronous - no embeddings).
    pub fn insert_entity(&self, table: &str, properties: serde_json::Value) -> Result<Uuid> {
        // Validate against schema
        self.schema_registry.validate(table, &properties)?;

        // Create entity
        let entity = Entity::new(table.to_string(), properties);
        let entity_id = entity.id;

        // Store entity
        self.entity_store.insert(&self.tenant_id, &entity)?;

        Ok(entity_id)
    }

    /// Insert entity with automatic embedding generation (async).
    pub async fn insert_entity_with_embedding(
        &self,
        table: &str,
        mut properties: serde_json::Value,
    ) -> Result<Uuid> {
        // Validate against schema
        self.schema_registry.validate(table, &properties)?;

        // Get schema to check embedding fields
        let schema = self.schema_registry.get(table)?;

        // Auto-generate embeddings for specified fields
        if let Some(provider) = &self.embedding_provider {
            for field_name in &schema.embedding_fields {
                // Check if field exists and doesn't already have an embedding
                if let Some(field_value) = properties.get(field_name) {
                    if let Some(text) = field_value.as_str() {
                        // Generate embedding
                        let embedding = provider.embed(text).await?;

                        // Store in `embedding` field (primary embedding)
                        if field_name == "content" || field_name == "description" {
                            properties
                                .as_object_mut()
                                .unwrap()
                                .insert("embedding".to_string(), serde_json::json!(embedding));
                        }
                    }
                }
            }
        }

        // Create entity
        let entity = Entity::new(table.to_string(), properties);
        let entity_id = entity.id;

        // Store entity
        self.entity_store.insert(&self.tenant_id, &entity)?;

        Ok(entity_id)
    }

    /// Get entity by ID.
    pub fn get_entity(&self, entity_id: Uuid) -> Result<Option<Entity>> {
        self.entity_store.get(&self.tenant_id, entity_id)
    }

    /// Delete entity.
    pub fn delete_entity(&self, entity_id: Uuid) -> Result<()> {
        self.entity_store.delete(&self.tenant_id, entity_id)
    }

    /// Scan all entities.
    pub fn scan_entities(&self) -> Result<Vec<Entity>> {
        self.entity_store.scan(&self.tenant_id)
    }

    /// Scan entities by type (table).
    pub fn scan_entities_by_type(&self, table: &str) -> Result<Vec<Entity>> {
        self.entity_store.scan_by_type(&self.tenant_id, table)
    }

    /// Register schema and persist it as an entity.
    ///
    /// Stores the full Pydantic JSON blob as entity properties with REM-specific extensions.
    /// Uses fully_qualified_name as key field for deterministic ID generation.
    ///
    /// # Arguments
    ///
    /// * `name` - Schema name (used if fully_qualified_name not in pydantic_schema)
    /// * `pydantic_schema` - Full Pydantic JSON blob (output from model_dump_json())
    /// * `indexed_fields` - REM extension: fields to index
    /// * `embedding_fields` - REM extension: fields to embed
    pub fn register_schema(
        &self,
        name: String,
        pydantic_schema: serde_json::Value,
        indexed_fields: Vec<String>,
        embedding_fields: Vec<String>,
    ) -> Result<()> {
        // Extract fully_qualified_name for deterministic ID (fallback to name)
        let fqn = pydantic_schema
            .get("fully_qualified_name")
            .or_else(|| pydantic_schema.get("short_name"))
            .and_then(|v| v.as_str())
            .unwrap_or(&name)
            .to_string();

        // Merge Pydantic JSON with REM extensions
        let mut schema_properties = if let Some(obj) = pydantic_schema.as_object() {
            obj.clone()
        } else {
            // If not an object, wrap it
            let mut map = serde_json::Map::new();
            map.insert("properties".to_string(), pydantic_schema);
            map
        };

        // Add REM-specific fields
        schema_properties.insert(
            "indexed_fields".to_string(),
            serde_json::to_value(&indexed_fields)?,
        );
        schema_properties.insert(
            "embedding_fields".to_string(),
            serde_json::to_value(&embedding_fields)?,
        );

        // Ensure name fields exist
        if !schema_properties.contains_key("fully_qualified_name") {
            schema_properties.insert("fully_qualified_name".to_string(), serde_json::json!(fqn));
        }
        if !schema_properties.contains_key("short_name") {
            schema_properties.insert("short_name".to_string(), serde_json::json!(name.clone()));
        }

        let full_properties = serde_json::Value::Object(schema_properties);

        // Register in memory
        let schema = crate::memory::Schema::new(
            name.clone(),
            full_properties.clone(),
            indexed_fields,
            embedding_fields,
        );
        self.schema_registry.register(schema)?;

        // Create deterministic ID from fully_qualified_name (key field)
        let hash = blake3::hash(fqn.as_bytes());
        let hash_bytes = hash.as_bytes();
        let mut uuid_bytes = [0u8; 16];
        uuid_bytes.copy_from_slice(&hash_bytes[0..16]);
        let schema_id = Uuid::from_bytes(uuid_bytes);

        // Store as entity (properties = full Pydantic JSON blob)
        let mut entity = Entity::new("schema".to_string(), full_properties);
        entity.id = schema_id;

        self.entity_store.insert(&self.tenant_id, &entity)?;

        Ok(())
    }

    /// Get schema.
    pub fn get_schema(&self, name: &str) -> Result<crate::memory::Schema> {
        self.schema_registry.get(name)
    }

    /// List schemas.
    pub fn list_schemas(&self) -> Vec<String> {
        self.schema_registry.list()
    }

    /// Batch insert entities with automatic embedding generation (async).
    ///
    /// This is the preferred method for inserting multiple entities efficiently.
    /// Embeddings are generated in a single batch API call.
    ///
    /// # Arguments
    ///
    /// * `table` - Schema/table name
    /// * `entities` - Vector of entity properties
    /// * `key_field` - Optional field to use as key (defaults to "id" or "name")
    ///
    /// # Returns
    ///
    /// Vector of UUIDs for the inserted entities
    pub async fn batch_insert_with_embedding(
        &self,
        table: &str,
        entities: Vec<serde_json::Value>,
        key_field: Option<&str>,
    ) -> Result<Vec<Uuid>> {
        if entities.is_empty() {
            return Ok(Vec::new());
        }

        // Validate all entities against schema
        for properties in &entities {
            self.schema_registry.validate(table, properties)?;
        }

        // Get schema to check embedding fields
        let schema = self.schema_registry.get(table)?;

        // Prepare entities with embeddings
        let mut prepared_entities = entities;

        // Auto-generate embeddings for specified fields (batch)
        if let Some(provider) = &self.embedding_provider {
            if !schema.embedding_fields.is_empty() {
                // Collect all texts that need embeddings
                let mut texts_to_embed: Vec<String> = Vec::new();
                let mut embed_indices: Vec<usize> = Vec::new();

                for (idx, properties) in prepared_entities.iter().enumerate() {
                    // Check primary embedding field (content or description)
                    for field_name in &schema.embedding_fields {
                        if let Some(field_value) = properties.get(field_name) {
                            if let Some(text) = field_value.as_str() {
                                if field_name == "content" || field_name == "description" {
                                    texts_to_embed.push(text.to_string());
                                    embed_indices.push(idx);
                                    break; // Only one embedding per entity
                                }
                            }
                        }
                    }
                }

                // Batch generate embeddings
                if !texts_to_embed.is_empty() {
                    let embeddings = provider.embed_batch(texts_to_embed).await?;

                    // Insert embeddings back into entity properties
                    for (emb_idx, entity_idx) in embed_indices.iter().enumerate() {
                        if let Some(obj) = prepared_entities[*entity_idx].as_object_mut() {
                            obj.insert(
                                "embedding".to_string(),
                                serde_json::json!(embeddings[emb_idx]),
                            );
                        }
                    }
                }
            }
        }

        // Create and insert all entities
        let mut entity_ids = Vec::with_capacity(prepared_entities.len());

        for properties in prepared_entities {
            // Determine key field with precedence: uri -> key_field -> name -> id
            let actual_key_field = if properties.get("uri").is_some() {
                "uri"
            } else if let Some(kf) = key_field {
                if properties.get(kf).is_some() {
                    kf
                } else if properties.get("name").is_some() {
                    "name"
                } else {
                    "id"
                }
            } else if properties.get("name").is_some() {
                "name"
            } else {
                "id"
            };

            // Check if entity should use a specific ID based on key field
            let entity_id = if actual_key_field == "uri" {
                // Special handling for resources: hash uri + chunk ordinal
                if let Some(uri_value) = properties.get("uri") {
                    if let Some(uri_str) = uri_value.as_str() {
                        // Get chunk ordinal (default to 0)
                        let chunk_ordinal = properties
                            .get("chunk_ordinal")
                            .and_then(|v| v.as_u64())
                            .unwrap_or(0);

                        // Create deterministic ID from uri + chunk ordinal
                        let key_string = format!("{}:{}", uri_str, chunk_ordinal);
                        let hash = blake3::hash(key_string.as_bytes());
                        let hash_bytes = hash.as_bytes();
                        let mut uuid_bytes = [0u8; 16];
                        uuid_bytes.copy_from_slice(&hash_bytes[0..16]);
                        Uuid::from_bytes(uuid_bytes)
                    } else {
                        Uuid::new_v4() // Fallback to random
                    }
                } else {
                    Uuid::new_v4() // Fallback to random
                }
            } else if actual_key_field != "id" {
                // Hash the key field value to create a deterministic UUID
                if let Some(key_value) = properties.get(actual_key_field) {
                    if let Some(key_str) = key_value.as_str() {
                        // Create UUID from hash of key (take first 16 bytes)
                        let hash = blake3::hash(key_str.as_bytes());
                        let hash_bytes = hash.as_bytes();
                        let mut uuid_bytes = [0u8; 16];
                        uuid_bytes.copy_from_slice(&hash_bytes[0..16]);
                        Uuid::from_bytes(uuid_bytes)
                    } else {
                        Uuid::new_v4() // Fallback to random
                    }
                } else {
                    Uuid::new_v4() // Fallback to random
                }
            } else if let Some(id_value) = properties.get("id") {
                // Try to parse existing ID field
                if let Some(id_str) = id_value.as_str() {
                    Uuid::parse_str(id_str).unwrap_or_else(|_| Uuid::new_v4())
                } else {
                    Uuid::new_v4()
                }
            } else {
                Uuid::new_v4()
            };

            // Create entity with specified or generated ID
            let mut entity = Entity::new(table.to_string(), properties);
            entity.id = entity_id;

            // Store entity
            self.entity_store.insert(&self.tenant_id, &entity)?;
            entity_ids.push(entity_id);
        }

        Ok(entity_ids)
    }

    /// Count total schemas.
    pub fn count_schemas(&self) -> Result<usize> {
        let schema_entities = self.entity_store.scan_by_type(&self.tenant_id, "schema")?;
        Ok(schema_entities.len())
    }

    /// Auto-detect schema based on natural language query.
    ///
    /// Strategy:
    /// 1. If count < threshold (10), load all schemas and let LLM choose
    /// 2. If count >= threshold, use semantic search on schema descriptions
    ///
    /// Returns schema names and descriptions for LLM to choose from.
    pub async fn auto_detect_schema(&self, query: &str, max_results: usize) -> Result<Vec<(String, String)>> {
        let count = self.count_schemas()?;
        const THRESHOLD: usize = 10;

        if count <= THRESHOLD {
            // Load all schemas with descriptions
            let schema_entities = self.entity_store.scan_by_type(&self.tenant_id, "schema")?;
            Ok(schema_entities
                .into_iter()
                .map(|entity| {
                    let name = entity.properties
                        .get("fully_qualified_name")
                        .or_else(|| entity.properties.get("short_name"))
                        .or_else(|| entity.properties.get("name"))
                        .and_then(|v| v.as_str())
                        .unwrap_or("unnamed")
                        .to_string();
                    let desc = entity.properties
                        .get("description")
                        .and_then(|v| v.as_str())
                        .unwrap_or("No description")
                        .to_string();
                    (name, desc)
                })
                .collect())
        } else {
            // Use semantic search on schema descriptions
            let results = self.search("schema", query, max_results).await?;
            Ok(results
                .into_iter()
                .map(|(entity, _score)| {
                    let name = entity.properties
                        .get("fully_qualified_name")
                        .or_else(|| entity.properties.get("short_name"))
                        .or_else(|| entity.properties.get("name"))
                        .and_then(|v| v.as_str())
                        .unwrap_or("unnamed")
                        .to_string();
                    let desc = entity.properties
                        .get("description")
                        .and_then(|v| v.as_str())
                        .unwrap_or("No description")
                        .to_string();
                    (name, desc)
                })
                .collect())
        }
    }

    /// Semantic search using embeddings.
    ///
    /// Returns entities with similarity scores, sorted by relevance.
    pub async fn search(&self, table: &str, query: &str, top_k: usize) -> Result<Vec<(Entity, f32)>> {
        use crate::embeddings::cosine_similarity;

        if let Some(provider) = &self.embedding_provider {
            // Generate query embedding
            let query_embedding = provider.embed(query).await?;

            // Get entities of specified type
            let entities = if table == "*" {
                self.entity_store.scan(&self.tenant_id)?
            } else {
                self.entity_store.scan_by_type(&self.tenant_id, table)?
            };

            // Calculate similarity for each entity with embedding
            let mut results: Vec<_> = entities
                .iter()
                .filter_map(|entity| {
                    if let Some(emb_value) = entity.properties.get("embedding") {
                        if let Some(emb_array) = emb_value.as_array() {
                            let embedding: Vec<f32> = emb_array
                                .iter()
                                .filter_map(|v| v.as_f64().map(|f| f as f32))
                                .collect();

                            if embedding.len() == query_embedding.len() {
                                let score = cosine_similarity(&query_embedding, &embedding);
                                return Some((entity.clone(), score));
                            }
                        }
                    }
                    None
                })
                .collect();

            // Sort by score descending
            results.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
            results.truncate(top_k);

            Ok(results)
        } else {
            Err(DatabaseError::EmbeddingError("Embedding provider not available".to_string()))
        }
    }
}
