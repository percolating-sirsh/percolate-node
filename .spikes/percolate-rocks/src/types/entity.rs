//! Entity and edge data structures.
//!
//! Core data types representing entities (nodes) and edges (relationships) in the REM database.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

/// System fields automatically added to all entities.
///
/// These fields are never defined in user schemas - always auto-generated.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SystemFields {
    /// Unique identifier (deterministic or random UUID)
    pub id: Uuid,

    /// Entity type (schema/table name)
    pub entity_type: String,

    /// Creation timestamp (ISO 8601)
    pub created_at: String,

    /// Last modification timestamp (ISO 8601)
    pub modified_at: String,

    /// Soft delete timestamp (ISO 8601), null if not deleted
    pub deleted_at: Option<String>,

    /// Graph edge references (array of edge IDs)
    pub edges: Vec<String>,
}

/// Entity represents a single data record with system fields and user properties.
///
/// # Structure
///
/// - System fields: id, entity_type, timestamps, edges
/// - User properties: Stored as JSON value map
/// - Embeddings: Optional vector embeddings (conditionally added)
///
/// # Example
///
/// ```rust,ignore
/// let entity = Entity {
///     system: SystemFields {
///         id: Uuid::new_v4(),
///         entity_type: "articles".to_string(),
///         created_at: "2025-10-24T10:00:00Z".to_string(),
///         modified_at: "2025-10-24T10:00:00Z".to_string(),
///         deleted_at: None,
///         edges: vec![],
///     },
///     properties: serde_json::json!({
///         "title": "Rust Performance",
///         "content": "Learn about Rust...",
///         "embedding": [0.1, 0.5, -0.2, ...],  // Conditionally added
///     }),
/// };
/// ```
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Entity {
    /// System fields (auto-generated)
    #[serde(flatten)]
    pub system: SystemFields,

    /// User-defined properties (JSON value)
    pub properties: serde_json::Value,
}

impl Entity {
    /// Create a new entity with system fields initialized.
    ///
    /// # Arguments
    ///
    /// * `id` - Unique identifier
    /// * `entity_type` - Schema/table name
    /// * `properties` - User-defined properties
    ///
    /// # Returns
    ///
    /// New `Entity` with timestamps set to current time
    pub fn new(id: Uuid, entity_type: String, properties: serde_json::Value) -> Self {
        todo!("Implement Entity::new")
    }

    /// Get embedding vector if present in properties.
    ///
    /// # Returns
    ///
    /// `Some(&[f32])` if embedding field exists, `None` otherwise
    pub fn get_embedding(&self) -> Option<&[f32]> {
        todo!("Implement Entity::get_embedding")
    }

    /// Get alternative embedding vector if present.
    ///
    /// # Returns
    ///
    /// `Some(&[f32])` if embedding_alt field exists, `None` otherwise
    pub fn get_alt_embedding(&self) -> Option<&[f32]> {
        todo!("Implement Entity::get_alt_embedding")
    }

    /// Mark entity as deleted (soft delete).
    ///
    /// Sets `deleted_at` timestamp to current time.
    pub fn mark_deleted(&mut self) {
        todo!("Implement Entity::mark_deleted")
    }

    /// Check if entity is soft deleted.
    ///
    /// # Returns
    ///
    /// `true` if `deleted_at` is not null
    pub fn is_deleted(&self) -> bool {
        todo!("Implement Entity::is_deleted")
    }
}

/// Edge data for graph relationships.
///
/// Stored in both `edges` and `edges_reverse` column families for bidirectional traversal.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EdgeData {
    /// Edge properties (JSON value)
    pub properties: HashMap<String, serde_json::Value>,

    /// Edge creation timestamp
    pub created_at: String,
}

/// Graph edge connecting two entities.
///
/// # Key Format
///
/// Forward: `src:{uuid}:dst:{uuid}:type:{relation}`
/// Reverse: `dst:{uuid}:src:{uuid}:type:{relation}`
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Edge {
    /// Source entity ID
    pub src: Uuid,

    /// Destination entity ID
    pub dst: Uuid,

    /// Relationship type
    pub rel_type: String,

    /// Edge properties and metadata
    pub data: EdgeData,
}

impl Edge {
    /// Create a new edge.
    ///
    /// # Arguments
    ///
    /// * `src` - Source entity UUID
    /// * `dst` - Destination entity UUID
    /// * `rel_type` - Relationship type (e.g., "authored", "references")
    ///
    /// # Returns
    ///
    /// New `Edge` with timestamp initialized
    pub fn new(src: Uuid, dst: Uuid, rel_type: String) -> Self {
        todo!("Implement Edge::new")
    }

    /// Add property to edge.
    ///
    /// # Arguments
    ///
    /// * `key` - Property name
    /// * `value` - Property value
    pub fn add_property(&mut self, key: String, value: serde_json::Value) {
        todo!("Implement Edge::add_property")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_entity_creation() {
        // TODO: Test entity creation with system fields
    }

    #[test]
    fn test_entity_soft_delete() {
        // TODO: Test soft delete marking
    }

    #[test]
    fn test_edge_creation() {
        // TODO: Test edge creation
    }
}
