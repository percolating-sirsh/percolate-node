//! Built-in system schemas.
//!
//! Automatically registered on database initialization:
//! - `schemas` - Schema registry with embeddings for discovery
//! - `documents` - Uploaded documents (no embeddings)
//! - `resources` - Chunked documents with embeddings

use crate::types::Result;
use crate::schema::registry::SchemaRegistry;
use serde_json::json;

/// Register all built-in system schemas.
///
/// Called automatically on database initialization.
/// Schemas are registered with category="system" and cannot be deleted.
///
/// # Arguments
///
/// * `registry` - Schema registry
///
/// # Errors
///
/// Returns `DatabaseError::ValidationError` if schema registration fails
///
/// # Registered Schemas
///
/// 1. **schemas** - Schema registry table
///    - Stores registered schema definitions
///    - Has embeddings for semantic schema search
///    - Indexed by: short_name, name
///    - Key field: name (deterministic UUID)
///
/// 2. **documents** - Original uploaded documents
///    - Stores document metadata before chunking
///    - No embeddings (only chunks are embedded)
///    - Indexed by: content_type, category, file_hash
///    - Key field: uri (deterministic UUID)
///
/// 3. **resources** - Chunked documents with embeddings
///    - Searchable document chunks
///    - Has embeddings for semantic search
///    - Indexed by: content_type, category, document_id, active_start_time, active_end_time
///    - Key field: uri (deterministic UUID with chunk_ordinal)
///
/// # Example
///
/// ```
/// let mut registry = SchemaRegistry::new();
/// register_builtin_schemas(&mut registry)?;
/// assert!(registry.has("schemas"));
/// assert!(registry.has("documents"));
/// assert!(registry.has("resources"));
/// ```
pub fn register_builtin_schemas(registry: &mut SchemaRegistry) -> Result<()> {
    todo!("Implement register_builtin_schemas")
}

/// Get schemas table schema definition.
///
/// # Returns
///
/// JSON Schema for `schemas` table
///
/// # Schema Fields
///
/// - `short_name` (string): Table name (e.g., "articles")
/// - `name` (string): Unique schema identifier (e.g., "myapp.resources.Article")
/// - `version` (string): Semantic version
/// - `schema` (object): Full JSON Schema definition
/// - `description` (string): Schema description (used for semantic search)
/// - `category` (string): Schema category (system/agents/public/user)
///
/// # json_schema_extra
///
/// - `embedding_fields`: ["description"] - Embed description for schema discovery
/// - `indexed_fields`: ["short_name", "name", "category"] - Fast lookups
/// - `key_field`: "name" - Deterministic UUID from schema name
///
/// # System Fields (auto-added)
///
/// - `id` (UUID), `entity_type`, `created_at`, `modified_at`, `deleted_at`, `edges`
///
/// # Embedding Fields (auto-added)
///
/// - `embedding` (array[float32]) - Embedded schema description
pub fn schemas_table_schema() -> serde_json::Value {
    json!({
        "title": "Schema",
        "description": "Registered schema definitions for entity validation and indexing",
        "version": "1.0.0",
        "short_name": "schemas",
        "name": "rem_db.builtin.Schema",

        "json_schema_extra": {
            // Embedding configuration (for semantic schema search)
            "embedding_fields": ["description"],
            "embedding_provider": "default",

            // Indexing configuration
            "indexed_fields": ["short_name", "name", "category"],

            // Key field (deterministic UUID)
            "key_field": "name",

            // Schema metadata
            "category": "system",
            "fully_qualified_name": "rem_db.builtin.Schema"
        },

        "properties": {
            "short_name": {
                "type": "string",
                "description": "Table name (snake_case, e.g., 'articles')"
            },
            "name": {
                "type": "string",
                "description": "Unique schema identifier (e.g., 'myapp.resources.Article')"
            },
            "version": {
                "type": "string",
                "description": "Semantic version (e.g., '1.0.0')"
            },
            "schema": {
                "type": "object",
                "description": "Full JSON Schema definition"
            },
            "description": {
                "type": "string",
                "description": "Schema description (embedded for semantic search)"
            },
            "category": {
                "type": "string",
                "enum": ["system", "agents", "public", "user"],
                "description": "Schema category for organization and permissions"
            }
        },

        "required": ["short_name", "name", "version", "schema", "description", "category"]
    })
}

/// Get documents table schema definition.
///
/// # Returns
///
/// JSON Schema for `documents` table
///
/// # Schema Fields
///
/// - `name` (string): Document name (e.g., "Python Tutorial.pdf")
/// - `uri` (string): Source URI or file path (unique)
/// - `content_type` (string): MIME type (e.g., "application/pdf")
/// - `file_size` (integer): File size in bytes
/// - `file_hash` (string): SHA256 hash of file content
/// - `category` (string): Document category
/// - `tags` (array[string]): Topic tags
/// - `sentiment_tags` (array[string]): Sentiment/tone tags
/// - `active_start_time` (datetime): Validity period start
/// - `active_end_time` (datetime): Validity period end
/// - `chunk_count` (integer): Number of chunks created
/// - `metadata` (object): Arbitrary metadata
///
/// # json_schema_extra
///
/// - `embedding_fields`: [] - No embeddings (only chunks are embedded)
/// - `indexed_fields`: ["content_type", "category", "file_hash"] - Fast lookups
/// - `key_field`: "uri" - Deterministic UUID from URI
///
/// # Note
///
/// Documents are NOT embedded. Only their chunks (resources) have embeddings.
pub fn documents_table_schema() -> serde_json::Value {
    json!({
        "title": "Document",
        "description": "Original uploaded documents before chunking",
        "version": "1.0.0",
        "short_name": "documents",
        "name": "rem_db.builtin.Document",

        "json_schema_extra": {
            // No embeddings (only chunks are embedded)
            "embedding_fields": [],

            // Indexing configuration
            "indexed_fields": ["content_type", "category", "file_hash"],

            // Key field (deterministic UUID)
            "key_field": "uri",

            // Schema metadata
            "category": "system",
            "fully_qualified_name": "rem_db.builtin.Document"
        },

        "properties": {
            "name": {
                "type": "string",
                "description": "Document name (e.g., 'Python Tutorial.pdf')"
            },
            "uri": {
                "type": "string",
                "format": "uri",
                "description": "Source URI or file path (unique identifier)"
            },
            "content_type": {
                "type": "string",
                "description": "MIME type (e.g., 'application/pdf', 'text/markdown')"
            },
            "file_size": {
                "type": "integer",
                "description": "File size in bytes"
            },
            "file_hash": {
                "type": "string",
                "description": "SHA256 hash of file content (for deduplication)"
            },
            "category": {
                "type": "string",
                "description": "Document category (e.g., 'tutorial', 'reference')"
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Topic tags for filtering",
                "default": []
            },
            "sentiment_tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Sentiment/tone tags",
                "default": []
            },
            "active_start_time": {
                "type": "string",
                "format": "date-time",
                "description": "Validity period start (ISO 8601)"
            },
            "active_end_time": {
                "type": "string",
                "format": "date-time",
                "description": "Validity period end (ISO 8601)"
            },
            "chunk_count": {
                "type": "integer",
                "description": "Number of chunks created from this document",
                "default": 0
            },
            "metadata": {
                "type": "object",
                "description": "Arbitrary metadata (author, version, etc.)"
            }
        },

        "required": ["name", "uri"]
    })
}

/// Get resources table schema definition.
///
/// # Returns
///
/// JSON Schema for `resources` table
///
/// # Schema Fields
///
/// - `name` (string): Chunk name (e.g., "Python Tutorial - Section 1")
/// - `content` (string): Chunk content (text extracted from document)
/// - `uri` (string): Source document URI (links back to document)
/// - `chunk_ordinal` (integer): Chunk index (0-based, sequential)
/// - `content_type` (string): MIME type (inherited from document)
/// - `category` (string): Content category (inherited from document)
/// - `tags` (array[string]): Topic tags (inherited from document)
/// - `sentiment_tags` (array[string]): Sentiment/tone tags
/// - `active_start_time` (datetime): Validity period start
/// - `active_end_time` (datetime): Validity period end
/// - `document_id` (UUID): Reference to parent document
/// - `metadata` (object): Chunk-specific metadata (page, section, etc.)
///
/// # json_schema_extra
///
/// - `embedding_fields`: ["content"] - Embed content for semantic search
/// - `indexed_fields`: ["content_type", "category", "document_id", "active_start_time", "active_end_time"]
/// - `key_field`: "uri" - Deterministic UUID from URI + chunk_ordinal
///
/// # Note
///
/// Resources are the searchable chunks. Each has an embedding for semantic search.
pub fn resources_table_schema() -> serde_json::Value {
    json!({
        "title": "Resource",
        "description": "Searchable document chunks with embeddings for semantic search",
        "version": "1.0.0",
        "short_name": "resources",
        "name": "rem_db.builtin.Resource",

        "json_schema_extra": {
            // Embedding configuration (for semantic search)
            "embedding_fields": ["content"],
            "embedding_provider": "default",

            // Indexing configuration
            "indexed_fields": [
                "content_type",
                "category",
                "document_id",
                "active_start_time",
                "active_end_time"
            ],

            // Key field (deterministic UUID from URI + chunk_ordinal)
            "key_field": "uri",

            // Schema metadata
            "category": "system",
            "fully_qualified_name": "rem_db.builtin.Resource"
        },

        "properties": {
            "name": {
                "type": "string",
                "description": "Chunk name (e.g., 'Python Tutorial - Section 1')"
            },
            "content": {
                "type": "string",
                "description": "Chunk content (text extracted from document)"
            },
            "uri": {
                "type": "string",
                "format": "uri",
                "description": "Source document URI (links back to document)"
            },
            "chunk_ordinal": {
                "type": "integer",
                "description": "Chunk index (0-based, sequential within document)",
                "default": 0
            },
            "content_type": {
                "type": "string",
                "description": "MIME type (inherited from document)"
            },
            "category": {
                "type": "string",
                "description": "Content category (inherited from document)"
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Topic tags (inherited from document)",
                "default": []
            },
            "sentiment_tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Sentiment/tone tags",
                "default": []
            },
            "active_start_time": {
                "type": "string",
                "format": "date-time",
                "description": "Validity period start (ISO 8601)"
            },
            "active_end_time": {
                "type": "string",
                "format": "date-time",
                "description": "Validity period end (ISO 8601)"
            },
            "document_id": {
                "type": "string",
                "format": "uuid",
                "description": "Reference to parent document UUID"
            },
            "metadata": {
                "type": "object",
                "description": "Chunk-specific metadata (page number, section heading, etc.)"
            }
        },

        "required": ["name", "content", "uri", "chunk_ordinal"]
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_schemas_table_schema() {
        let schema = schemas_table_schema();
        assert_eq!(schema["short_name"], "schemas");
        assert_eq!(schema["json_schema_extra"]["category"], "system");
        assert_eq!(
            schema["json_schema_extra"]["embedding_fields"][0],
            "description"
        );
    }

    #[test]
    fn test_documents_table_schema() {
        let schema = documents_table_schema();
        assert_eq!(schema["short_name"], "documents");
        assert_eq!(schema["json_schema_extra"]["category"], "system");
        // Documents have NO embeddings
        assert_eq!(
            schema["json_schema_extra"]["embedding_fields"]
                .as_array()
                .unwrap()
                .len(),
            0
        );
    }

    #[test]
    fn test_resources_table_schema() {
        let schema = resources_table_schema();
        assert_eq!(schema["short_name"], "resources");
        assert_eq!(schema["json_schema_extra"]["category"], "system");
        // Resources have embeddings on content
        assert_eq!(
            schema["json_schema_extra"]["embedding_fields"][0],
            "content"
        );
    }
}
