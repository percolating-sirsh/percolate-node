//! LLM-powered natural language query builder.
//!
//! Converts user questions to executable database queries using OpenAI API.

use crate::types::{DatabaseError, Result};
use serde::{Deserialize, Serialize};
use serde_json::json;

/// Query type determined by LLM.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum QueryType {
    /// Direct lookup by ID, key, name, or URI
    KeyValue,
    /// SQL SELECT with WHERE predicates
    Sql,
    /// Semantic vector search
    Vector,
}

/// Structured output from LLM query builder.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QueryResult {
    /// Type of query to execute
    pub query_type: QueryType,

    /// Generated query string
    pub query: String,

    /// Confidence in query correctness (0-1)
    pub confidence: f32,

    /// Explanation if confidence < 0.8
    #[serde(skip_serializing_if = "Option::is_none")]
    pub explanation: Option<String>,

    /// Follow-up question for staged retrieval
    #[serde(skip_serializing_if = "Option::is_none")]
    pub follow_up_question: Option<String>,

    /// Fallback query if primary returns no results
    #[serde(skip_serializing_if = "Option::is_none")]
    pub fallback_query: Option<String>,
}

/// Natural language to query builder using OpenAI API.
pub struct QueryBuilder {
    api_key: String,
    model: String,
    base_url: String,
    client: reqwest::Client,
}

impl QueryBuilder {
    /// Create new query builder.
    ///
    /// # Arguments
    ///
    /// * `api_key` - OpenAI API key (or None to use OPENAI_API_KEY env var)
    /// * `model` - Model name (defaults to gpt-4-turbo-preview)
    pub fn new(api_key: Option<String>, model: Option<String>) -> Result<Self> {
        let api_key = api_key
            .or_else(|| std::env::var("OPENAI_API_KEY").ok())
            .ok_or_else(|| DatabaseError::ConfigError("OpenAI API key required (set OPENAI_API_KEY env var)".to_string()))?;

        Ok(Self {
            api_key,
            model: model.unwrap_or_else(|| "gpt-4-turbo-preview".to_string()),
            base_url: "https://api.openai.com/v1".to_string(),
            client: reqwest::Client::new(),
        })
    }

    /// Build query from natural language.
    ///
    /// # Arguments
    ///
    /// * `natural_language` - User's natural language query
    /// * `schema` - Entity schema (JSON Schema format)
    /// * `table` - Target table name
    /// * `max_stages` - Maximum retrieval stages for fallbacks
    pub async fn build_query(
        &self,
        natural_language: &str,
        schema: &serde_json::Value,
        table: &str,
        max_stages: usize,
    ) -> Result<QueryResult> {
        let prompt = self.build_prompt(natural_language, schema, table, max_stages);
        let response = self.call_llm(&prompt).await?;
        self.parse_response(&response)
    }

    /// Build prompt for LLM.
    fn build_prompt(
        &self,
        natural_language: &str,
        schema: &serde_json::Value,
        table: &str,
        max_stages: usize,
    ) -> String {
        let empty_map = serde_json::Map::new();
        let schema_fields = schema
            .get("properties")
            .and_then(|p| p.as_object())
            .unwrap_or(&empty_map);

        let field_descriptions = schema_fields
            .iter()
            .map(|(name, props)| {
                let type_str = props.get("type").and_then(|t| t.as_str()).unwrap_or("unknown");
                let desc = props.get("description").and_then(|d| d.as_str()).unwrap_or("No description");
                format!("  - {}: {} - {}", name, type_str, desc)
            })
            .collect::<Vec<_>>()
            .join("\n");

        format!(
            r#"You are a query builder for the REM database system.

USER QUERY: "{}"

TARGET TABLE: {}

SCHEMA:
{}

QUERY TYPES:
1. **key_value**: Direct lookup by primary key (id field)
   - Use when user provides exact ID or unique identifier
   - Example: "get resource abc-123" → SELECT * FROM resources WHERE id = 'abc-123'

2. **sql**: SQL SELECT with predicates
   - Use for field-based filtering (equality, comparisons, IN)
   - Example: "resources with category tutorial" → SELECT * FROM resources WHERE category = 'tutorial'

3. **vector**: Semantic similarity search using embeddings
   - Use for conceptual or meaning-based queries
   - Syntax: WHERE embedding.cosine("query text") or embedding.inner_product("query text")
   - Example: "resources about programming" → SELECT * FROM resources WHERE embedding.cosine("programming") LIMIT 10

DISTANCE METRICS:
- Use cosine for sentence-transformers models (default)
- Use inner_product for normalized embeddings (OpenAI models)

QUERY STRATEGY:
1. Prefer simplest query type that will work (key_value > sql > vector)
2. If confidence < 0.8, provide explanation
3. Suggest fallback query if primary might return no results
4. Maximum {} retrieval stages allowed

OUTPUT FORMAT (JSON):
{{
  "query_type": "key_value" | "sql" | "vector",
  "query": "SELECT ...",
  "confidence": 0.0-1.0,
  "explanation": "Optional explanation if confidence < 0.8",
  "follow_up_question": "Optional follow-up for staged retrieval",
  "fallback_query": "Optional fallback if no results"
}}

Generate the query now:"#,
            natural_language, table, field_descriptions, max_stages
        )
    }

    /// Call OpenAI API with structured output.
    async fn call_llm(&self, prompt: &str) -> Result<String> {
        let response = self
            .client
            .post(format!("{}/chat/completions", self.base_url))
            .header("Authorization", format!("Bearer {}", self.api_key))
            .header("Content-Type", "application/json")
            .json(&json!({
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
            }))
            .send()
            .await
            .map_err(|e| DatabaseError::QueryError(format!("OpenAI API request failed: {}", e)))?;

        let data: serde_json::Value = response
            .json()
            .await
            .map_err(|e| DatabaseError::QueryError(format!("Failed to parse OpenAI response: {}", e)))?;

        data.get("choices")
            .and_then(|c| c.get(0))
            .and_then(|c| c.get("message"))
            .and_then(|m| m.get("content"))
            .and_then(|c| c.as_str())
            .ok_or_else(|| DatabaseError::QueryError("Invalid OpenAI API response".to_string()))
            .map(|s| s.to_string())
    }

    /// Parse LLM JSON response.
    fn parse_response(&self, response: &str) -> Result<QueryResult> {
        serde_json::from_str(response)
            .map_err(|e| DatabaseError::QueryError(format!("Failed to parse query result: {}", e)))
    }
}
