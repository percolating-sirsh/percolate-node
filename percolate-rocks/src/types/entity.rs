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
        let now = chrono::Utc::now().to_rfc3339();
        Self {
            system: SystemFields {
                id,
                entity_type,
                created_at: now.clone(),
                modified_at: now,
                deleted_at: None,
                edges: vec![],
            },
            properties,
        }
    }

    /// Get embedding vector if present in properties.
    ///
    /// # Returns
    ///
    /// `Some(&[f32])` if embedding field exists, `None` otherwise
    pub fn get_embedding(&self) -> Option<Vec<f32>> {
        self.properties
            .get("embedding")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_f64().map(|f| f as f32))
                    .collect()
            })
    }

    /// Get alternative embedding vector if present.
    ///
    /// # Returns
    ///
    /// `Some(&[f32])` if embedding_alt field exists, `None` otherwise
    pub fn get_alt_embedding(&self) -> Option<Vec<f32>> {
        self.properties
            .get("embedding_alt")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_f64().map(|f| f as f32))
                    .collect()
            })
    }

    /// Mark entity as deleted (soft delete).
    ///
    /// Sets `deleted_at` timestamp to current time.
    pub fn mark_deleted(&mut self) {
        self.system.deleted_at = Some(chrono::Utc::now().to_rfc3339());
        self.system.modified_at = chrono::Utc::now().to_rfc3339();
    }

    /// Check if entity is soft deleted.
    ///
    /// # Returns
    ///
    /// `true` if `deleted_at` is not null
    pub fn is_deleted(&self) -> bool {
        self.system.deleted_at.is_some()
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
        Self {
            src,
            dst,
            rel_type,
            data: EdgeData {
                properties: HashMap::new(),
                created_at: chrono::Utc::now().to_rfc3339(),
            },
        }
    }

    /// Add property to edge.
    ///
    /// # Arguments
    ///
    /// * `key` - Property name
    /// * `value` - Property value
    pub fn add_property(&mut self, key: String, value: serde_json::Value) {
        self.data.properties.insert(key, value);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_entity_creation() {
        let id = Uuid::new_v4();
        let properties = json!({
            "title": "Test Article",
            "content": "Test content"
        });

        let entity = Entity::new(id, "articles".to_string(), properties.clone());

        assert_eq!(entity.system.id, id);
        assert_eq!(entity.system.entity_type, "articles");
        assert_eq!(entity.properties, properties);
        assert!(entity.system.deleted_at.is_none());
        assert_eq!(entity.system.edges.len(), 0);
        assert!(!entity.system.created_at.is_empty());
        assert!(!entity.system.modified_at.is_empty());
    }

    #[test]
    fn test_entity_serialization() {
        let id = Uuid::new_v4();
        let entity = Entity::new(
            id,
            "articles".to_string(),
            json!({"title": "Test"}),
        );

        let serialized = serde_json::to_string(&entity).unwrap();
        let deserialized: Entity = serde_json::from_str(&serialized).unwrap();

        assert_eq!(deserialized.system.id, id);
        assert_eq!(deserialized.system.entity_type, "articles");
    }

    #[test]
    fn test_entity_soft_delete() {
        let mut entity = Entity::new(
            Uuid::new_v4(),
            "articles".to_string(),
            json!({"title": "Test"}),
        );

        assert!(!entity.is_deleted());

        entity.mark_deleted();

        assert!(entity.is_deleted());
        assert!(entity.system.deleted_at.is_some());
    }

    #[test]
    fn test_entity_embeddings() {
        let entity = Entity::new(
            Uuid::new_v4(),
            "articles".to_string(),
            json!({
                "title": "Test",
                "embedding": [0.1, 0.5, -0.2],
                "embedding_alt": [0.2, 0.6, -0.3]
            }),
        );

        let embedding = entity.get_embedding().unwrap();
        assert_eq!(embedding.len(), 3);
        assert_eq!(embedding[0], 0.1);

        let alt_embedding = entity.get_alt_embedding().unwrap();
        assert_eq!(alt_embedding.len(), 3);
        assert_eq!(alt_embedding[0], 0.2);
    }

    #[test]
    fn test_entity_no_embeddings() {
        let entity = Entity::new(
            Uuid::new_v4(),
            "articles".to_string(),
            json!({"title": "Test"}),
        );

        assert!(entity.get_embedding().is_none());
        assert!(entity.get_alt_embedding().is_none());
    }

    #[test]
    fn test_edge_creation() {
        let src = Uuid::new_v4();
        let dst = Uuid::new_v4();

        let edge = Edge::new(src, dst, "authored".to_string());

        assert_eq!(edge.src, src);
        assert_eq!(edge.dst, dst);
        assert_eq!(edge.rel_type, "authored");
        assert!(!edge.data.created_at.is_empty());
        assert_eq!(edge.data.properties.len(), 0);
    }

    #[test]
    fn test_edge_properties() {
        let mut edge = Edge::new(
            Uuid::new_v4(),
            Uuid::new_v4(),
            "references".to_string(),
        );

        edge.add_property("weight".to_string(), json!(0.8));
        edge.add_property("context".to_string(), json!("citation"));

        assert_eq!(edge.data.properties.len(), 2);
        assert_eq!(edge.data.properties.get("weight").unwrap(), &json!(0.8));
    }
}
