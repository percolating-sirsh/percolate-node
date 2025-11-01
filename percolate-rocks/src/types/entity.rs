//! Entity and edge data structures.
//!
//! Core data types representing entities (nodes) and edges (relationships) in the REM database.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

/// Inline edge representation (stored in entity JSON).
///
/// Used when `edge_storage_mode: "inline"` (default).
/// Edges are stored directly in the entity's edges array.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct InlineEdge {
    /// Destination entity UUID
    pub dst: Uuid,

    /// Relationship type (e.g., "authored", "references", "member_of")
    pub rel_type: String,

    /// Edge properties (optional metadata)
    #[serde(default)]
    pub properties: HashMap<String, serde_json::Value>,

    /// Edge creation timestamp
    pub created_at: String,
}

impl InlineEdge {
    /// Create a new inline edge.
    ///
    /// # Arguments
    ///
    /// * `dst` - Destination entity UUID
    /// * `rel_type` - Relationship type
    ///
    /// # Returns
    ///
    /// New `InlineEdge` with timestamp initialized
    pub fn new(dst: Uuid, rel_type: String) -> Self {
        Self {
            dst,
            rel_type,
            properties: HashMap::new(),
            created_at: chrono::Utc::now().to_rfc3339(),
        }
    }

    /// Create edge with properties.
    ///
    /// # Arguments
    ///
    /// * `dst` - Destination entity UUID
    /// * `rel_type` - Relationship type
    /// * `properties` - Edge metadata
    pub fn with_properties(
        dst: Uuid,
        rel_type: String,
        properties: HashMap<String, serde_json::Value>,
    ) -> Self {
        Self {
            dst,
            rel_type,
            properties,
            created_at: chrono::Utc::now().to_rfc3339(),
        }
    }

    /// Get unique key for this edge (dst + rel_type).
    ///
    /// Used for merging edges during upsert.
    pub fn key(&self) -> (Uuid, String) {
        (self.dst, self.rel_type.clone())
    }
}

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

    /// Graph edges (inline mode).
    ///
    /// **Storage Modes:**
    /// - `"inline"` (default): Edges stored here as array of InlineEdge objects
    /// - `"indexed"`: Empty array, edges stored in RocksDB column families
    ///
    /// **Inline Mode Format:**
    /// ```json
    /// "edges": [
    ///   {
    ///     "dst": "uuid",
    ///     "rel_type": "authored",
    ///     "properties": {"since": "2024-01-01"},
    ///     "created_at": "2024-01-01T00:00:00Z"
    ///   }
    /// ]
    /// ```
    ///
    /// **Indexed Mode:**
    /// Edges stored separately in `edges` and `edges_reverse` column families.
    /// This field remains empty. Use `EdgeManager` for CRUD operations.
    ///
    /// Configure in schema `json_schema_extra`:
    /// ```python
    /// model_config = ConfigDict(
    ///     json_schema_extra={
    ///         "edge_storage_mode": "inline"  # or "indexed"
    ///     }
    /// )
    /// ```
    #[serde(default)]
    pub edges: Vec<InlineEdge>,
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

    /// Add or update inline edge.
    ///
    /// If edge with same (dst, rel_type) exists, updates its properties.
    /// Otherwise, adds new edge.
    ///
    /// # Arguments
    ///
    /// * `edge` - Inline edge to add/update
    ///
    /// # Note
    ///
    /// Only applicable for inline edge storage mode.
    /// For indexed mode, use `EdgeManager` instead.
    pub fn add_edge(&mut self, edge: InlineEdge) {
        // Find existing edge with same (dst, rel_type)
        if let Some(existing) = self.system.edges.iter_mut()
            .find(|e| e.key() == edge.key()) {
            // Update existing edge properties
            existing.properties = edge.properties;
            existing.created_at = edge.created_at;
        } else {
            // Add new edge
            self.system.edges.push(edge);
        }

        // Update modified timestamp
        self.system.modified_at = chrono::Utc::now().to_rfc3339();
    }

    /// Remove inline edge by destination and relationship type.
    ///
    /// # Arguments
    ///
    /// * `dst` - Destination entity UUID
    /// * `rel_type` - Relationship type
    ///
    /// # Returns
    ///
    /// `true` if edge was removed, `false` if not found
    pub fn remove_edge(&mut self, dst: Uuid, rel_type: &str) -> bool {
        let initial_len = self.system.edges.len();
        self.system.edges.retain(|e| !(e.dst == dst && e.rel_type == rel_type));
        let removed = self.system.edges.len() < initial_len;

        if removed {
            self.system.modified_at = chrono::Utc::now().to_rfc3339();
        }

        removed
    }

    /// Get inline edges by relationship type.
    ///
    /// # Arguments
    ///
    /// * `rel_type` - Relationship type filter (None for all edges)
    ///
    /// # Returns
    ///
    /// Vector of edges matching the filter
    pub fn get_edges(&self, rel_type: Option<&str>) -> Vec<&InlineEdge> {
        match rel_type {
            Some(rt) => self.system.edges.iter().filter(|e| e.rel_type == rt).collect(),
            None => self.system.edges.iter().collect(),
        }
    }

    /// Merge edges from another entity during upsert.
    ///
    /// **Merge Strategy:**
    /// - Edges are identified by (dst, rel_type) key
    /// - Existing edges are updated with new properties
    /// - New edges are appended
    /// - No edges are deleted (explicit remove required)
    ///
    /// # Arguments
    ///
    /// * `other_edges` - Edges from incoming entity
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// // Existing entity has: [Edge{dst: A, rel: "friend"}]
    /// // New entity has:      [Edge{dst: A, rel: "friend", props: {since: "2024"}}, Edge{dst: B, rel: "colleague"}]
    /// entity.merge_edges(new_edges);
    /// // Result:              [Edge{dst: A, rel: "friend", props: {since: "2024"}}, Edge{dst: B, rel: "colleague"}]
    /// ```
    pub fn merge_edges(&mut self, other_edges: Vec<InlineEdge>) {
        for edge in other_edges {
            self.add_edge(edge);
        }
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
