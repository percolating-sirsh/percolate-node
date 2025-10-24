//! Entity types.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Entity {
    /// Unique entity ID
    pub id: Uuid,

    /// Entity type (table name)
    #[serde(rename = "type")]
    pub entity_type: String,

    /// Entity properties (JSON)
    pub properties: serde_json::Value,

    /// Default embedding (384-dim typically)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub embedding: Option<Vec<f32>>,

    /// Alternative embedding (768-dim typically)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub embedding_alt: Option<Vec<f32>>,

    /// Edge references
    #[serde(default)]
    pub edges: Vec<EdgeRef>,

    /// Creation timestamp
    pub created_at: DateTime<Utc>,

    /// Last modification timestamp
    pub modified_at: DateTime<Utc>,

    /// Soft delete timestamp
    #[serde(skip_serializing_if = "Option::is_none")]
    pub deleted_at: Option<DateTime<Utc>>,
}

impl Entity {
    /// Create new entity.
    pub fn new(entity_type: String, properties: serde_json::Value) -> Self {
        let now = Utc::now();
        Self {
            id: Uuid::new_v4(),
            entity_type,
            properties,
            embedding: None,
            embedding_alt: None,
            edges: Vec::new(),
            created_at: now,
            modified_at: now,
            deleted_at: None,
        }
    }

    /// Check if entity is deleted.
    pub fn is_deleted(&self) -> bool {
        self.deleted_at.is_some()
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EdgeRef {
    pub entity_id: Uuid,
    pub edge_type: String,
    pub direction: Direction,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Edge {
    pub src_id: Uuid,
    pub dst_id: Uuid,
    pub edge_type: String,
    pub properties: serde_json::Value,
    pub created_at: DateTime<Utc>,
}

impl Edge {
    /// Create new edge.
    pub fn new(
        src_id: Uuid,
        dst_id: Uuid,
        edge_type: String,
        properties: serde_json::Value,
    ) -> Self {
        Self {
            src_id,
            dst_id,
            edge_type,
            properties,
            created_at: Utc::now(),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Direction {
    Incoming,
    Outgoing,
    Both,
}
