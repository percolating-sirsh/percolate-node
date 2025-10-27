//! Agent schema storage and loading
//!
//! Stores agent definitions in RocksDB for background processing.
//! Schemas define the agent's behavior without executable code.
//!
//! # Design Philosophy
//!
//! - **Pure data**: Schemas are JSON, no executable code
//! - **Versioned**: Semantic versioning for schema evolution
//! - **Tenant-scoped**: Schemas are per-tenant for isolation
//! - **Immutable**: Once stored, schemas don't change (version bump instead)
//!
//! # Reference
//!
//! Python schema pattern: `percolate/src/percolate/agents/factory.py`
//! Carrier project pattern: `carrier/schema/agentlets/`

use serde::{Deserialize, Serialize};

/// Agent schema stored in RocksDB
///
/// Defines an agent's behavior as pure data (no code).
/// Stored in RocksDB with key: `agent:{tenant_id}:{agent_name}`
///
/// # Design Notes
///
/// **Schema structure:**
/// - `name`: Unique identifier (e.g., "entity-extractor")
/// - `version`: Semantic version (e.g., "1.0.0")
/// - `system_prompt`: The agent's instructions
/// - `output_schema`: JSON Schema for structured output
/// - `model`: LLM model to use (e.g., "claude-haiku-4-5")
/// - `api_endpoint`: API URL (auto-determined from model if empty)
///
/// **No code, no tools:**
/// This is intentionally minimal - just HTTP client + schema.
/// For full agent framework with MCP tools, use Python layer.
///
/// # Example
///
/// ```json
/// {
///   "name": "entity-extractor",
///   "version": "1.0.0",
///   "system_prompt": "Extract entities from the text...",
///   "output_schema": {
///     "type": "object",
///     "properties": {
///       "entities": {"type": "array", "items": {"type": "string"}},
///       "count": {"type": "integer"}
///     },
///     "required": ["entities", "count"]
///   },
///   "model": "claude-haiku-4-5",
///   "api_endpoint": ""
/// }
/// ```
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentSchema {
    /// Agent name (unique per tenant)
    ///
    /// Convention: lowercase with hyphens (e.g., "entity-extractor")
    pub name: String,

    /// Semantic version
    ///
    /// Format: "major.minor.patch" (e.g., "1.0.0")
    /// Increment when schema changes:
    /// - major: Breaking changes
    /// - minor: New features (backward compatible)
    /// - patch: Bug fixes
    pub version: String,

    /// System prompt (agent's instructions)
    ///
    /// This defines what the agent does. Should be detailed and specific.
    ///
    /// # Example
    ///
    /// ```text
    /// You are an entity extraction specialist.
    /// Extract all named entities from the text including:
    /// - People (names and titles)
    /// - Organizations (companies, institutions)
    /// - Locations (cities, countries, addresses)
    /// - Dates and times
    ///
    /// Return entities as a structured list.
    /// ```
    pub system_prompt: String,

    /// JSON Schema for structured output
    ///
    /// Defines the expected output format. Agent will return JSON
    /// matching this schema.
    ///
    /// # Example
    ///
    /// ```json
    /// {
    ///   "type": "object",
    ///   "properties": {
    ///     "entities": {
    ///       "type": "array",
    ///       "items": {"type": "string"}
    ///     },
    ///     "count": {"type": "integer"}
    ///   },
    ///   "required": ["entities", "count"]
    /// }
    /// ```
    pub output_schema: serde_json::Value,

    /// Model name
    ///
    /// Which LLM to use (e.g., "claude-haiku-4-5", "gpt-4.1").
    /// Should match pricing in client.rs.
    pub model: String,

    /// API endpoint (optional)
    ///
    /// If empty, auto-determined from model name:
    /// - claude-*: https://api.anthropic.com/v1/messages
    /// - gpt-*: https://api.openai.com/v1/chat/completions
    #[serde(default)]
    pub api_endpoint: String,
}

impl AgentSchema {
    /// Load schema from RocksDB
    ///
    /// Retrieves agent schema for a specific tenant.
    ///
    /// # Arguments
    ///
    /// * `db` - RocksDB database handle
    /// * `tenant_id` - Tenant identifier
    /// * `name` - Agent name
    ///
    /// # Returns
    ///
    /// Agent schema if found
    ///
    /// # Errors
    ///
    /// Returns error if:
    /// - Schema not found
    /// - RocksDB read fails
    /// - JSON parsing fails
    ///
    /// # Implementation Notes (Phase 4)
    ///
    /// **Key format:**
    /// ```text
    /// agent:{tenant_id}:{agent_name}
    /// ```
    ///
    /// **Load process:**
    /// ```rust
    /// // 1. Build key
    /// let key = format!("agent:{}:{}", tenant_id, name);
    ///
    /// // 2. Get from RocksDB
    /// let value = db.get(key)?
    ///     .ok_or_else(|| Error::SchemaNotFound(name.to_string()))?;
    ///
    /// // 3. Parse JSON
    /// let schema: AgentSchema = serde_json::from_slice(&value)?;
    ///
    /// // 4. Validate (optional)
    /// if schema.name != name {
    ///     return Err(Error::SchemaMismatch);
    /// }
    ///
    /// Ok(schema)
    /// ```
    ///
    /// # Example
    ///
    /// ```no_run
    /// # use percolate_rocks::agents::AgentSchema;
    /// # use percolate_rocks::database::Database;
    /// # fn example() -> Result<(), Box<dyn std::error::Error>> {
    /// # let db = Database::open("test.db")?;
    /// let schema = AgentSchema::from_db(&db, "tenant-123", "entity-extractor")?;
    /// println!("Loaded agent: {} v{}", schema.name, schema.version);
    /// # Ok(())
    /// # }
    /// ```
    pub fn from_db(
        db: &crate::database::Database,
        tenant_id: &str,
        name: &str,
    ) -> Result<Self, Box<dyn std::error::Error>> {
        // TODO: Implement in Phase 4
        //
        // Steps:
        // 1. Build key: agent:{tenant_id}:{name}
        // 2. Get from RocksDB
        // 3. Parse JSON
        // 4. Validate schema.name matches name
        // 5. Return schema
        todo!("Load agent schema from RocksDB")
    }

    /// Store schema to RocksDB
    ///
    /// Saves agent schema for a specific tenant.
    ///
    /// # Arguments
    ///
    /// * `db` - RocksDB database handle
    /// * `tenant_id` - Tenant identifier
    ///
    /// # Returns
    ///
    /// Ok if stored successfully
    ///
    /// # Errors
    ///
    /// Returns error if:
    /// - JSON serialization fails
    /// - RocksDB write fails
    ///
    /// # Implementation Notes (Phase 4)
    ///
    /// **Key format:**
    /// ```text
    /// agent:{tenant_id}:{agent_name}
    /// ```
    ///
    /// **Store process:**
    /// ```rust
    /// // 1. Build key
    /// let key = format!("agent:{}:{}", tenant_id, self.name);
    ///
    /// // 2. Serialize to JSON
    /// let value = serde_json::to_vec(self)?;
    ///
    /// // 3. Write to RocksDB
    /// db.put(&key, &value)?;
    ///
    /// // 4. Log
    /// tracing::info!(
    ///     tenant_id = tenant_id,
    ///     agent_name = %self.name,
    ///     version = %self.version,
    ///     "Stored agent schema"
    /// );
    ///
    /// Ok(())
    /// ```
    ///
    /// **Versioning:**
    /// - Same name = overwrite (version should be bumped)
    /// - No automatic migration
    /// - Old code may fail with new schema (check version)
    ///
    /// # Example
    ///
    /// ```no_run
    /// # use percolate_rocks::agents::AgentSchema;
    /// # use percolate_rocks::database::Database;
    /// # use serde_json::json;
    /// # fn example() -> Result<(), Box<dyn std::error::Error>> {
    /// # let db = Database::open("test.db")?;
    /// let schema = AgentSchema {
    ///     name: "entity-extractor".to_string(),
    ///     version: "1.0.0".to_string(),
    ///     system_prompt: "Extract entities from text".to_string(),
    ///     output_schema: json!({
    ///         "type": "object",
    ///         "properties": {
    ///             "entities": {"type": "array", "items": {"type": "string"}}
    ///         }
    ///     }),
    ///     model: "claude-haiku-4-5".to_string(),
    ///     api_endpoint: String::new(),
    /// };
    ///
    /// schema.to_db(&db, "tenant-123")?;
    /// # Ok(())
    /// # }
    /// ```
    pub fn to_db(
        &self,
        db: &crate::database::Database,
        tenant_id: &str,
    ) -> Result<(), Box<dyn std::error::Error>> {
        // TODO: Implement in Phase 4
        //
        // Steps:
        // 1. Build key: agent:{tenant_id}:{self.name}
        // 2. Serialize to JSON
        // 3. Write to RocksDB
        // 4. Log storage
        todo!("Store agent schema to RocksDB")
    }

    /// List all schemas for a tenant
    ///
    /// Retrieves all agent schemas belonging to a tenant.
    ///
    /// # Arguments
    ///
    /// * `db` - RocksDB database handle
    /// * `tenant_id` - Tenant identifier
    ///
    /// # Returns
    ///
    /// Vector of agent schemas
    ///
    /// # Errors
    ///
    /// Returns error if RocksDB scan or JSON parsing fails
    ///
    /// # Implementation Notes (Phase 4)
    ///
    /// **Prefix scan:**
    /// ```rust
    /// // 1. Build prefix
    /// let prefix = format!("agent:{}:", tenant_id);
    ///
    /// // 2. Scan RocksDB with prefix
    /// let mut schemas = Vec::new();
    /// for item in db.prefix_iterator(&prefix) {
    ///     let (key, value) = item?;
    ///     let schema: AgentSchema = serde_json::from_slice(&value)?;
    ///     schemas.push(schema);
    /// }
    ///
    /// // 3. Sort by name
    /// schemas.sort_by(|a, b| a.name.cmp(&b.name));
    ///
    /// Ok(schemas)
    /// ```
    ///
    /// # Example
    ///
    /// ```no_run
    /// # use percolate_rocks::agents::AgentSchema;
    /// # use percolate_rocks::database::Database;
    /// # fn example() -> Result<(), Box<dyn std::error::Error>> {
    /// # let db = Database::open("test.db")?;
    /// let schemas = AgentSchema::list(&db, "tenant-123")?;
    /// for schema in schemas {
    ///     println!("{} v{} ({})", schema.name, schema.version, schema.model);
    /// }
    /// # Ok(())
    /// # }
    /// ```
    pub fn list(
        db: &crate::database::Database,
        tenant_id: &str,
    ) -> Result<Vec<Self>, Box<dyn std::error::Error>> {
        // TODO: Implement in Phase 4
        //
        // Steps:
        // 1. Build prefix: agent:{tenant_id}:
        // 2. Scan RocksDB
        // 3. Parse each value as AgentSchema
        // 4. Sort by name
        // 5. Return vec
        todo!("List all agent schemas for tenant")
    }

    /// Delete schema from RocksDB
    ///
    /// Removes agent schema for a specific tenant.
    ///
    /// # Arguments
    ///
    /// * `db` - RocksDB database handle
    /// * `tenant_id` - Tenant identifier
    /// * `name` - Agent name to delete
    ///
    /// # Returns
    ///
    /// Ok if deleted (or didn't exist)
    ///
    /// # Errors
    ///
    /// Returns error if RocksDB delete fails
    ///
    /// # Implementation Notes (Phase 4)
    ///
    /// ```rust
    /// // 1. Build key
    /// let key = format!("agent:{}:{}", tenant_id, name);
    ///
    /// // 2. Delete from RocksDB
    /// db.delete(&key)?;
    ///
    /// // 3. Log
    /// tracing::info!(
    ///     tenant_id = tenant_id,
    ///     agent_name = name,
    ///     "Deleted agent schema"
    /// );
    ///
    /// Ok(())
    /// ```
    ///
    /// # Example
    ///
    /// ```no_run
    /// # use percolate_rocks::agents::AgentSchema;
    /// # use percolate_rocks::database::Database;
    /// # fn example() -> Result<(), Box<dyn std::error::Error>> {
    /// # let db = Database::open("test.db")?;
    /// AgentSchema::delete(&db, "tenant-123", "entity-extractor")?;
    /// # Ok(())
    /// # }
    /// ```
    pub fn delete(
        db: &crate::database::Database,
        tenant_id: &str,
        name: &str,
    ) -> Result<(), Box<dyn std::error::Error>> {
        // TODO: Implement in Phase 4
        //
        // Steps:
        // 1. Build key: agent:{tenant_id}:{name}
        // 2. Delete from RocksDB
        // 3. Log deletion
        todo!("Delete agent schema from RocksDB")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_schema_serialization() {
        let schema = AgentSchema {
            name: "test-agent".to_string(),
            version: "1.0.0".to_string(),
            system_prompt: "Test prompt".to_string(),
            output_schema: serde_json::json!({
                "type": "object",
                "properties": {
                    "result": {"type": "string"}
                }
            }),
            model: "claude-haiku-4-5".to_string(),
            api_endpoint: String::new(),
        };

        // Serialize
        let json = serde_json::to_string(&schema).unwrap();

        // Deserialize
        let parsed: AgentSchema = serde_json::from_str(&json).unwrap();

        assert_eq!(parsed.name, "test-agent");
        assert_eq!(parsed.version, "1.0.0");
        assert_eq!(parsed.model, "claude-haiku-4-5");
    }

    // TODO: Add more tests in Phase 4
    // - test_store_and_load_roundtrip
    // - test_list_schemas
    // - test_delete_schema
    // - test_schema_not_found
}
