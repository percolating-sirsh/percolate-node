//! Built-in data models for REM database.
//!
//! These models mirror the Python Pydantic models and use schemars
//! to generate JSON Schema compatible with the schema registry.

use chrono::{DateTime, Utc};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// System-managed fields for all entities.
///
/// All tables inherit these fields automatically.
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct SystemFields {
    /// Unique identifier
    #[serde(default = "Uuid::new_v4")]
    pub id: Uuid,

    /// Creation timestamp
    #[serde(default = "Utc::now")]
    pub created_at: DateTime<Utc>,

    /// Last modification timestamp
    #[serde(default = "Utc::now")]
    pub modified_at: DateTime<Utc>,

    /// Soft delete timestamp
    #[serde(skip_serializing_if = "Option::is_none")]
    pub deleted_at: Option<DateTime<Utc>>,

    /// Graph edges (other entity IDs or qualified keys)
    #[serde(default)]
    pub edges: Vec<String>,
}

impl Default for SystemFields {
    fn default() -> Self {
        Self {
            id: Uuid::new_v4(),
            created_at: Utc::now(),
            modified_at: Utc::now(),
            deleted_at: None,
            edges: Vec::new(),
        }
    }
}

/// Chunked, embedded content from documents.
///
/// Used for general-purpose document storage with vector embeddings.
/// Supports flexible schema via metadata dict.
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct Resource {
    #[serde(flatten)]
    pub system: SystemFields,

    /// Resource name or title
    pub name: String,

    /// Full text content (auto-embedded)
    pub content: String,

    /// Resource category/type
    #[serde(skip_serializing_if = "Option::is_none")]
    pub category: Option<String>,

    /// Arbitrary metadata (stored as JSON string for schema compatibility)
    #[serde(default, skip_serializing_if = "Option::is_none")]
    #[schemars(skip)]
    pub metadata: Option<serde_json::Value>,

    /// Vector embedding (384-dim from all-MiniLM-L6-v2)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub embedding: Option<Vec<f32>>,

    /// Alternative vector embedding (768-dim from all-mpnet-base-v2)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub embedding_alt: Option<Vec<f32>>,

    /// Ordering within category
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ordinal: Option<i32>,

    /// Source URI or reference
    #[serde(skip_serializing_if = "Option::is_none")]
    pub uri: Option<String>,
}

impl Resource {
    /// Create new resource.
    pub fn new(name: String, content: String) -> Self {
        Self {
            system: SystemFields::default(),
            name,
            content,
            category: None,
            metadata: None,
            embedding: None,
            embedding_alt: None,
            ordinal: None,
            uri: None,
        }
    }

    /// Get schema metadata for registration.
    pub fn schema_metadata() -> SchemaMetadata {
        SchemaMetadata {
            fully_qualified_name: "rem.system.Resource".to_string(),
            short_name: "resource".to_string(),
            version: "1.0.0".to_string(),
            category: "system".to_string(),
            indexed_fields: vec!["category".to_string(), "name".to_string()],
            embedding_provider: Some("all-MiniLM-L6-v2".to_string()),
            embedding_provider_alt: Some("all-mpnet-base-v2".to_string()),
        }
    }
}

/// Schema metadata for model registration.
#[derive(Debug, Clone)]
pub struct SchemaMetadata {
    pub fully_qualified_name: String,
    pub short_name: String,
    pub version: String,
    pub category: String,
    pub indexed_fields: Vec<String>,
    pub embedding_provider: Option<String>,
    pub embedding_provider_alt: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_resource_creation() {
        let resource = Resource::new("Test".to_string(), "Content".to_string());
        assert_eq!(resource.name, "Test");
        assert_eq!(resource.content, "Content");
        assert!(resource.system.deleted_at.is_none());
    }

    #[test]
    fn test_resource_json_schema() {
        let schema = schemars::schema_for!(Resource);
        let json = serde_json::to_string_pretty(&schema).unwrap();

        // Verify schema contains expected fields
        assert!(json.contains("name"));
        assert!(json.contains("content"));
        assert!(json.contains("embedding"));
    }
}
