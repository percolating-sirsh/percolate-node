//! LLM-powered edge extraction for REM indexing.
//!
//! Extracts relationship edges from document content to build knowledge graph connections.
//! This is the E (Entities/relationships) in REM indexing.

use crate::types::{Result, DatabaseError, InlineEdge};
use crate::llm::query_builder::LlmQueryBuilder;
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::collections::HashMap;

/// Edge extraction plan from document content.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EdgePlan {
    /// Array of inline edges extracted from the document
    pub edges: Vec<EdgeSpec>,

    /// Summary of edge extraction results
    pub summary: EdgeSummary,
}

/// Edge specification (before converting to InlineEdge).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EdgeSpec {
    /// Destination entity UUID
    pub dst: String,

    /// Relationship type
    pub rel_type: String,

    /// Edge metadata and context
    #[serde(default)]
    pub properties: HashMap<String, serde_json::Value>,

    /// ISO 8601 timestamp
    pub created_at: String,
}

impl EdgeSpec {
    /// Convert to InlineEdge with validation.
    ///
    /// # Returns
    ///
    /// `Result<InlineEdge>` if dst is valid UUID
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::ValidationError` if dst is not valid UUID
    pub fn to_inline_edge(&self) -> Result<InlineEdge> {
        let dst_uuid = uuid::Uuid::parse_str(&self.dst)
            .map_err(|e| DatabaseError::ValidationError(
                format!("Invalid UUID in edge dst: {}", e)
            ))?;

        Ok(InlineEdge {
            dst: dst_uuid,
            rel_type: self.rel_type.clone(),
            properties: self.properties.clone(),
            created_at: self.created_at.clone(),
        })
    }
}

/// Summary of edge extraction.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EdgeSummary {
    /// Total number of edges extracted
    pub total_edges: usize,

    /// List of unique relationship types found
    pub relationship_types: Vec<String>,

    /// Average confidence score across all edges
    pub avg_confidence: f64,
}

/// LLM-powered edge builder.
pub struct LlmEdgeBuilder {
    query_builder: LlmQueryBuilder,
}

impl LlmEdgeBuilder {
    /// Create new edge builder.
    ///
    /// # Arguments
    ///
    /// * `api_key` - API key (OpenAI or Anthropic)
    /// * `model` - LLM model name
    ///
    /// # Returns
    ///
    /// New `LlmEdgeBuilder`
    pub fn new(api_key: String, model: String) -> Self {
        Self {
            query_builder: LlmQueryBuilder::new(api_key, model),
        }
    }

    /// Create from environment variables.
    ///
    /// Uses `P8_DEFAULT_LLM` for model (default: "gpt-4-turbo")
    /// Uses `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` based on model
    ///
    /// # Errors
    ///
    /// Returns error if API key not found in environment
    pub fn from_env() -> Result<Self> {
        Ok(Self {
            query_builder: LlmQueryBuilder::from_env()?,
        })
    }

    /// Extract relationship edges from document content.
    ///
    /// # Arguments
    ///
    /// * `content` - Document content (text, markdown, etc.)
    /// * `context` - Optional context about the document (file name, type, etc.)
    ///
    /// # Returns
    ///
    /// `EdgePlan` with extracted edges and summary
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::LlmError` if generation fails
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// let builder = LlmEdgeBuilder::from_env()?;
    /// let plan = builder.extract_edges(
    ///     "This document references Design Doc 001...",
    ///     Some("architecture/rem-database.md")
    /// ).await?;
    ///
    /// for edge in plan.edges {
    ///     println!("Found edge: {} -> {}", edge.rel_type, edge.dst);
    /// }
    /// ```
    pub async fn extract_edges(
        &self,
        content: &str,
        context: Option<&str>,
    ) -> Result<EdgePlan> {
        // Build system prompt
        let system_prompt = Self::build_system_prompt();

        // Build user prompt with content
        let user_prompt = Self::build_user_prompt(content, context);

        // Call LLM
        let response = self.call_llm(&system_prompt, &user_prompt).await?;

        // Parse response as EdgePlan
        let plan: EdgePlan = serde_json::from_str(&response)
            .map_err(|e| DatabaseError::LlmError(
                format!("Failed to parse edge plan: {}\nResponse: {}", e, response)
            ))?;

        // Validate edges
        for edge in &plan.edges {
            // Validate UUID format
            uuid::Uuid::parse_str(&edge.dst)
                .map_err(|e| DatabaseError::ValidationError(
                    format!("Invalid UUID in edge dst: {}", e)
                ))?;
        }

        Ok(plan)
    }

    /// Call LLM API (delegates to query_builder).
    async fn call_llm(&self, system_prompt: &str, user_prompt: &str) -> Result<String> {
        // Delegate to query_builder's call_llm method
        // This handles OpenAI, Anthropic, Cerebras providers
        self.query_builder.call_llm(system_prompt, user_prompt).await
    }

    /// Build system prompt for edge extraction.
    fn build_system_prompt() -> String {
        r#"You are an edge extraction specialist that identifies relationships between documents and entities.

Your role is to analyze content and extract semantic relationships in the form of inline edges.

**Analysis Process:**

1. **Content Analysis:**
   - Read the document content carefully
   - Identify mentions of other entities (documents, people, systems, concepts)
   - Determine relationship types based on context

2. **Edge Generation:**
   - Create edges with dst UUID, rel_type, and properties
   - Add confidence scores based on clarity of relationship
   - Include context in edge properties where helpful

**Relationship Types:**
- references: Document references another document
- authored_by: Document created by person/system
- depends_on: Technical dependency
- implements: Implementation of specification
- extends: Extension or elaboration
- supersedes: Replaces older document
- related_to: Generic relationship
- part_of: Component of larger whole
- mentions: Brief mention
- cites: Academic citation
- derived_from: Derived work

**Important Notes:**
- Only generate edges for relationships you can clearly identify
- Use placeholder UUIDs in format 12345678-1234-5678-9abc-XXXXXXXXXXXX
- Be conservative with confidence scores (0.0-1.0)
- Group related edges by relationship type

**Output Format:**
Return a JSON object matching this schema:
{
  "edges": [
    {
      "dst": "12345678-1234-5678-9abc-123456789001",
      "rel_type": "references",
      "properties": {
        "confidence": 0.95,
        "context": "Description of relationship"
      },
      "created_at": "2024-01-15T10:00:00Z"
    }
  ],
  "summary": {
    "total_edges": 1,
    "relationship_types": ["references"],
    "avg_confidence": 0.95
  }
}

Return ONLY valid JSON. No markdown code blocks or explanations."#.to_string()
    }

    /// Build user prompt with document content.
    fn build_user_prompt(content: &str, context: Option<&str>) -> String {
        let context_str = context
            .map(|c| format!("\n\n**Document Context:** {}\n", c))
            .unwrap_or_default();

        format!(
            r#"Extract relationship edges from the following document:{context_str}

**Document Content:**
```
{content}
```

Analyze the content and identify all clear, explicit relationships. Generate edges with valid UUIDs (use placeholder format), relationship types, and confidence scores.

Return JSON only."#,
            context_str = context_str,
            content = content
        )
    }

    /// Get JSON Schema for EdgePlan struct.
    fn get_edge_plan_schema() -> serde_json::Value {
        json!({
            "type": "object",
            "properties": {
                "edges": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "dst": {
                                "type": "string",
                                "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
                            },
                            "rel_type": {
                                "type": "string",
                                "enum": [
                                    "references", "authored_by", "depends_on", "implements",
                                    "extends", "supersedes", "related_to", "part_of",
                                    "mentions", "cites", "derived_from"
                                ]
                            },
                            "properties": {
                                "type": "object",
                                "additionalProperties": true
                            },
                            "created_at": {
                                "type": "string",
                                "format": "date-time"
                            }
                        },
                        "required": ["dst", "rel_type", "created_at"]
                    }
                },
                "summary": {
                    "type": "object",
                    "properties": {
                        "total_edges": {"type": "integer"},
                        "relationship_types": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "avg_confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1
                        }
                    },
                    "required": ["total_edges", "relationship_types", "avg_confidence"]
                }
            },
            "required": ["edges", "summary"]
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_edge_spec_to_inline_edge() {
        let spec = EdgeSpec {
            dst: "550e8400-e29b-41d4-a716-446655440000".to_string(),
            rel_type: "references".to_string(),
            properties: HashMap::new(),
            created_at: "2024-01-15T10:00:00Z".to_string(),
        };

        let inline_edge = spec.to_inline_edge().unwrap();
        assert_eq!(inline_edge.rel_type, "references");
    }

    #[test]
    fn test_edge_spec_invalid_uuid() {
        let spec = EdgeSpec {
            dst: "invalid-uuid".to_string(),
            rel_type: "references".to_string(),
            properties: HashMap::new(),
            created_at: "2024-01-15T10:00:00Z".to_string(),
        };

        assert!(spec.to_inline_edge().is_err());
    }

    #[test]
    fn test_system_prompt_generation() {
        let prompt = LlmEdgeBuilder::build_system_prompt();
        assert!(prompt.contains("edge extraction"));
        assert!(prompt.contains("relationship types"));
    }

    #[test]
    fn test_user_prompt_generation() {
        let content = "This document references Design Doc 001";
        let context = Some("architecture/rem-database.md");

        let prompt = LlmEdgeBuilder::build_user_prompt(content, context);
        assert!(prompt.contains(content));
        assert!(prompt.contains("architecture/rem-database.md"));
    }
}
