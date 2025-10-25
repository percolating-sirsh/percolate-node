//! Schema registry for managing Pydantic schemas.

use crate::types::Result;
use crate::schema::category::SchemaCategory;
use std::collections::HashMap;

/// Schema metadata for tracking versions and categories.
#[derive(Debug, Clone)]
pub struct SchemaMetadata {
    /// Schema name
    pub name: String,
    /// Semantic version
    pub version: String,
    /// Schema category
    pub category: SchemaCategory,
    /// Full JSON Schema
    pub schema: serde_json::Value,
}

/// Schema registry for managing entity schemas.
///
/// Tracks schemas by name and organizes them by category.
/// Supports semantic schema search when >10 schemas registered.
pub struct SchemaRegistry {
    /// Schema storage by name
    schemas: HashMap<String, SchemaMetadata>,

    /// Schema organization by category
    categories: HashMap<SchemaCategory, Vec<String>>,

    /// Version history (schema_name -> versions)
    versions: HashMap<String, Vec<String>>,
}

impl SchemaRegistry {
    /// Create new schema registry.
    pub fn new() -> Self {
        Self {
            schemas: HashMap::new(),
            categories: HashMap::new(),
            versions: HashMap::new(),
        }
    }

    /// Register schema from JSON Schema.
    ///
    /// # Arguments
    ///
    /// * `name` - Schema name
    /// * `schema` - JSON Schema
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::ValidationError` if schema is invalid
    pub fn register(&mut self, name: &str, schema: serde_json::Value) -> Result<()> {
        use crate::schema::pydantic::PydanticSchemaParser;
        use crate::types::DatabaseError;

        // Extract version
        let version = PydanticSchemaParser::extract_version(&schema)
            .ok_or_else(|| DatabaseError::ValidationError("Schema missing 'version' field".into()))?;

        // Extract category (defaults to User)
        let category = PydanticSchemaParser::extract_category(&schema);

        // Check version compatibility if schema already exists
        if self.has(name) {
            self.check_version_compatibility(name, &version)?;
        }

        // Create metadata
        let metadata = SchemaMetadata {
            name: name.to_string(),
            version: version.clone(),
            category,
            schema,
        };

        // Store schema
        self.schemas.insert(name.to_string(), metadata);

        // Update category index
        self.categories
            .entry(category)
            .or_insert_with(Vec::new)
            .push(name.to_string());

        // Update version history
        self.versions
            .entry(name.to_string())
            .or_insert_with(Vec::new)
            .push(version);

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
    pub fn get(&self, name: &str) -> Result<&serde_json::Value> {
        self.schemas
            .get(name)
            .map(|meta| &meta.schema)
            .ok_or_else(|| crate::types::DatabaseError::SchemaNotFound(name.to_string()))
    }

    /// List all registered schemas.
    ///
    /// # Returns
    ///
    /// Vector of schema names
    pub fn list(&self) -> Vec<String> {
        self.schemas.keys().cloned().collect()
    }

    /// Extract embedding fields from schema.
    ///
    /// # Arguments
    ///
    /// * `name` - Schema name
    ///
    /// # Returns
    ///
    /// Vector of field names to embed
    pub fn get_embedding_fields(&self, name: &str) -> Result<Vec<String>> {
        use crate::schema::pydantic::PydanticSchemaParser;
        let schema = self.get(name)?;
        Ok(PydanticSchemaParser::extract_embedding_fields(schema))
    }

    /// Extract indexed fields from schema.
    ///
    /// # Arguments
    ///
    /// * `name` - Schema name
    ///
    /// # Returns
    ///
    /// Vector of field names to index
    pub fn get_indexed_fields(&self, name: &str) -> Result<Vec<String>> {
        use crate::schema::pydantic::PydanticSchemaParser;
        let schema = self.get(name)?;
        Ok(PydanticSchemaParser::extract_indexed_fields(schema))
    }

    /// Extract key field from schema.
    ///
    /// # Arguments
    ///
    /// * `name` - Schema name
    ///
    /// # Returns
    ///
    /// Key field name if configured
    pub fn get_key_field(&self, name: &str) -> Result<Option<String>> {
        use crate::schema::pydantic::PydanticSchemaParser;
        let schema = self.get(name)?;
        Ok(PydanticSchemaParser::extract_key_field(schema))
    }

    /// Embed schema description for semantic schema discovery.
    ///
    /// # Arguments
    ///
    /// * `name` - Schema name
    /// * `embedder` - Embedding provider
    ///
    /// # Returns
    ///
    /// Embedding vector
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::EmbeddingError` if embedding fails
    ///
    /// # Note
    ///
    /// Used for semantic schema search when >10 schemas registered.
    /// Embeddings stored in separate HNSW index: `{db_path}/indexes/_schemas.hnsw`
    pub async fn embed_schema_description(
        &self,
        name: &str,
        embedder: &dyn crate::embeddings::provider::EmbeddingProvider,
    ) -> Result<Vec<f32>> {
        todo!("Implement SchemaRegistry::embed_schema_description")
    }

    /// Find schemas by semantic similarity to query.
    ///
    /// # Arguments
    ///
    /// * `query` - Search query
    /// * `top_k` - Number of schemas to return
    /// * `embedder` - Embedding provider
    ///
    /// # Returns
    ///
    /// Vector of (schema_name, similarity_score) tuples
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::SearchError` if search fails
    ///
    /// # Usage
    ///
    /// Only used when registered schema count > P8_SCHEMA_BRUTE_FORCE_LIMIT (default: 10)
    pub async fn search_schemas_by_similarity(
        &self,
        query: &str,
        top_k: usize,
        embedder: &dyn crate::embeddings::provider::EmbeddingProvider,
    ) -> Result<Vec<(String, f32)>> {
        todo!("Implement SchemaRegistry::search_schemas_by_similarity")
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
    pub fn has(&self, name: &str) -> bool {
        self.schemas.contains_key(name)
    }

    /// Get schema category.
    ///
    /// # Arguments
    ///
    /// * `name` - Schema name
    ///
    /// # Returns
    ///
    /// Schema category
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::SchemaNotFound` if schema doesn't exist
    pub fn get_category(&self, name: &str) -> Result<SchemaCategory> {
        self.schemas
            .get(name)
            .map(|meta| meta.category)
            .ok_or_else(|| crate::types::DatabaseError::SchemaNotFound(name.to_string()))
    }

    /// List schemas by category.
    ///
    /// # Arguments
    ///
    /// * `category` - Schema category filter
    ///
    /// # Returns
    ///
    /// Vector of schema names in category
    ///
    /// # Example
    ///
    /// ```
    /// let agents = registry.list_by_category(SchemaCategory::Agents);
    /// // Returns: ["carrier.agents.cda_mapper", "carrier.agents.error_classifier"]
    /// ```
    pub fn list_by_category(&self, category: SchemaCategory) -> Vec<String> {
        self.categories
            .get(&category)
            .map(|schemas| schemas.clone())
            .unwrap_or_default()
    }

    /// Check schema version compatibility.
    ///
    /// # Arguments
    ///
    /// * `name` - Schema name
    /// * `new_version` - New version to register
    ///
    /// # Returns
    ///
    /// Ok if compatible (minor/patch bump), Err if breaking change detected
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::ValidationError` if version is incompatible
    ///
    /// # Version Compatibility Rules
    ///
    /// - Major version bump (1.x.x → 2.x.x): Breaking change (requires migration)
    /// - Minor version bump (x.1.x → x.2.x): New optional fields (backward compatible)
    /// - Patch version bump (x.x.1 → x.x.2): Documentation/description changes only
    ///
    /// # Example
    ///
    /// ```
    /// // Current: 1.0.0
    /// registry.check_version_compatibility("articles", "1.1.0")?; // OK - minor bump
    /// registry.check_version_compatibility("articles", "2.0.0")?; // Error - breaking
    /// ```
    pub fn check_version_compatibility(&self, name: &str, new_version: &str) -> Result<()> {
        use crate::types::DatabaseError;

        let current_meta = self.schemas.get(name)
            .ok_or_else(|| DatabaseError::SchemaNotFound(name.to_string()))?;

        let current = &current_meta.version;

        // Parse versions (major.minor.patch)
        let parse_version = |v: &str| -> Result<(u32, u32, u32)> {
            let parts: Vec<&str> = v.split('.').collect();
            if parts.len() != 3 {
                return Err(DatabaseError::ValidationError(
                    format!("Invalid version format: {}", v)
                ));
            }
            let major = parts[0].parse().map_err(|_|
                DatabaseError::ValidationError(format!("Invalid major version: {}", parts[0])))?;
            let minor = parts[1].parse().map_err(|_|
                DatabaseError::ValidationError(format!("Invalid minor version: {}", parts[1])))?;
            let patch = parts[2].parse().map_err(|_|
                DatabaseError::ValidationError(format!("Invalid patch version: {}", parts[2])))?;
            Ok((major, minor, patch))
        };

        let (cur_major, _cur_minor, _cur_patch) = parse_version(current)?;
        let (new_major, _new_minor, _new_patch) = parse_version(new_version)?;

        // Check for breaking changes (major version bump)
        if new_major > cur_major {
            return Err(DatabaseError::ValidationError(
                format!(
                    "Breaking change detected: {} -> {} (major version bump requires migration)",
                    current, new_version
                )
            ));
        }

        Ok(())
    }

    /// Get all versions of a schema.
    ///
    /// # Arguments
    ///
    /// * `name` - Schema name
    ///
    /// # Returns
    ///
    /// Vector of versions (semantic versioning, sorted)
    ///
    /// # Example
    ///
    /// ```
    /// let versions = registry.get_versions("articles");
    /// // Returns: ["1.0.0", "1.1.0", "1.2.0"]
    /// ```
    pub fn get_versions(&self, name: &str) -> Vec<String> {
        self.versions
            .get(name)
            .map(|versions| versions.clone())
            .unwrap_or_default()
    }

    /// Count registered schemas.
    ///
    /// # Returns
    ///
    /// Total number of registered schemas
    pub fn count(&self) -> usize {
        self.schemas.len()
    }

    /// Count schemas by category.
    ///
    /// # Arguments
    ///
    /// * `category` - Schema category
    ///
    /// # Returns
    ///
    /// Number of schemas in category
    pub fn count_by_category(&self, category: SchemaCategory) -> usize {
        self.categories
            .get(&category)
            .map(|schemas| schemas.len())
            .unwrap_or(0)
    }

    /// Remove schema by name.
    ///
    /// # Arguments
    ///
    /// * `name` - Schema name
    ///
    /// # Returns
    ///
    /// Removed schema metadata
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::SchemaNotFound` if schema doesn't exist
    /// Returns `DatabaseError::ValidationError` if trying to remove system schema
    ///
    /// # Note
    ///
    /// System schemas (category="system") cannot be removed.
    pub fn remove(&mut self, name: &str) -> Result<SchemaMetadata> {
        use crate::types::DatabaseError;

        let meta = self.schemas.get(name)
            .ok_or_else(|| DatabaseError::SchemaNotFound(name.to_string()))?;

        // Prevent removal of system schemas
        if meta.category == SchemaCategory::System {
            return Err(DatabaseError::ValidationError(
                format!("Cannot remove system schema: {}", name)
            ));
        }

        // Remove from schemas
        let metadata = self.schemas.remove(name)
            .ok_or_else(|| DatabaseError::SchemaNotFound(name.to_string()))?;

        // Remove from category index
        if let Some(schemas) = self.categories.get_mut(&metadata.category) {
            schemas.retain(|s| s != name);
        }

        // Remove from version history
        self.versions.remove(name);

        Ok(metadata)
    }
}
