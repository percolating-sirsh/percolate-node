//! Natural language to SQL/SEARCH query builder.

use crate::types::{Result, DatabaseError};
use crate::llm::planner::{QueryPlan, QueryType, Query, QueryDialect, ExecutionMode, QueryResult};
use serde::Deserialize;
use serde_json::json;
use reqwest::Client;

/// LLM provider type.
#[derive(Debug, Clone)]
pub enum LlmProvider {
    OpenAI,
    Anthropic,
    Cerebras,
}

/// LLM-powered query builder.
pub struct LlmQueryBuilder {
    api_key: String,
    model: String,
    provider: LlmProvider,
    client: Client,
}

/// OpenAI API response for structured output.
#[derive(Debug, Deserialize)]
struct OpenAIResponse {
    choices: Vec<OpenAIChoice>,
}

#[derive(Debug, Deserialize)]
struct OpenAIChoice {
    message: OpenAIMessage,
}

#[derive(Debug, Deserialize)]
struct OpenAIMessage {
    content: String,
}

/// Anthropic API response.
#[derive(Debug, Deserialize)]
struct AnthropicResponse {
    content: Vec<AnthropicContent>,
}

#[derive(Debug, Deserialize)]
struct AnthropicContent {
    text: String,
}

impl LlmQueryBuilder {
    /// Strip markdown code blocks from LLM response.
    ///
    /// Handles:
    /// - ```json ... ```
    /// - ```JSON ... ```
    /// - ``` ... ```
    fn strip_markdown(text: &str) -> String {
        let text = text.trim();

        // Check for ```json ... ``` or ```JSON ... ```
        if text.starts_with("```json") || text.starts_with("```JSON") {
            let start = text.find('\n').map(|i| i + 1).unwrap_or(0);
            let end = text.rfind("```").unwrap_or(text.len());
            return text[start..end].trim().to_string();
        }

        // Check for generic ``` ... ```
        if text.starts_with("```") {
            let start = text.find('\n').map(|i| i + 1).unwrap_or(0);
            let end = text.rfind("```").unwrap_or(text.len());
            return text[start..end].trim().to_string();
        }

        text.to_string()
    }

    /// Create new query builder.
    ///
    /// # Arguments
    ///
    /// * `api_key` - API key (OpenAI or Anthropic)
    /// * `model` - LLM model name (e.g., "gpt-4-turbo", "claude-3-5-sonnet-20241022")
    ///
    /// # Returns
    ///
    /// New `LlmQueryBuilder`
    pub fn new(api_key: String, model: String) -> Self {
        let provider = if model.starts_with("claude") || model.starts_with("anthropic") {
            LlmProvider::Anthropic
        } else if model.starts_with("cerebras") || model.starts_with("llama") {
            LlmProvider::Cerebras
        } else {
            LlmProvider::OpenAI
        };

        Self {
            api_key,
            model,
            provider,
            client: Client::new(),
        }
    }

    /// Create from environment variables.
    ///
    /// Uses `P8_DEFAULT_LLM` for model (default: "gpt-4-turbo")
    /// Uses `CEREBRAS_API_KEY`, `OPENAI_API_KEY`, or `ANTHROPIC_API_KEY` based on model
    ///
    /// # Errors
    ///
    /// Returns error if API key not found in environment
    pub fn from_env() -> Result<Self> {
        let model = std::env::var("P8_DEFAULT_LLM")
            .unwrap_or_else(|_| "gpt-4-turbo".to_string());

        let api_key = if model.starts_with("claude") || model.starts_with("anthropic") {
            std::env::var("ANTHROPIC_API_KEY")
                .map_err(|_| DatabaseError::ConfigError(
                    "ANTHROPIC_API_KEY environment variable not set".to_string()
                ))?
        } else if model.starts_with("cerebras") || model.starts_with("llama") || model.starts_with("qwen") {
            std::env::var("CEREBRAS_API_KEY")
                .map_err(|_| DatabaseError::ConfigError(
                    "CEREBRAS_API_KEY environment variable not set".to_string()
                ))?
        } else {
            std::env::var("OPENAI_API_KEY")
                .map_err(|_| DatabaseError::ConfigError(
                    "OPENAI_API_KEY environment variable not set".to_string()
                ))?
        };

        Ok(Self::new(api_key, model))
    }

    /// Convert natural language question to SQL/SEARCH query.
    ///
    /// # Arguments
    ///
    /// * `question` - Natural language question
    /// * `schema_context` - Schema information for context
    ///
    /// # Returns
    ///
    /// Generated query plan
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::LlmError` if generation fails
    pub async fn build_query(&self, question: &str, schema_context: &str) -> Result<QueryPlan> {
        self.plan_query(question, schema_context).await
    }

    /// Call LLM API with structured output.
    ///
    /// Public method to allow reuse by other LLM-powered modules.
    pub async fn call_llm(&self, system_prompt: &str, user_prompt: &str) -> Result<String> {
        match self.provider {
            LlmProvider::OpenAI => self.call_openai(system_prompt, user_prompt).await,
            LlmProvider::Anthropic => self.call_anthropic(system_prompt, user_prompt).await,
            LlmProvider::Cerebras => self.call_cerebras(system_prompt, user_prompt).await,
        }
    }

    /// Call OpenAI API.
    async fn call_openai(&self, system_prompt: &str, user_prompt: &str) -> Result<String> {
        let response = self.client
            .post("https://api.openai.com/v1/chat/completions")
            .header("Authorization", format!("Bearer {}", self.api_key))
            .header("Content-Type", "application/json")
            .json(&json!({
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1
            }))
            .send()
            .await
            .map_err(|e| DatabaseError::LlmError(format!("OpenAI API error: {}", e)))?;

        let status = response.status();
        let body = response.text().await
            .map_err(|e| DatabaseError::LlmError(format!("Failed to read response: {}", e)))?;

        if !status.is_success() {
            return Err(DatabaseError::LlmError(format!("OpenAI API error {}: {}", status, body)));
        }

        let parsed: OpenAIResponse = serde_json::from_str(&body)
            .map_err(|e| DatabaseError::LlmError(format!("Failed to parse OpenAI response: {}", e)))?;

        Ok(parsed.choices.first()
            .ok_or_else(|| DatabaseError::LlmError("No response from OpenAI".to_string()))?
            .message.content.clone())
    }

    /// Call Anthropic API.
    async fn call_anthropic(&self, system_prompt: &str, user_prompt: &str) -> Result<String> {
        let response = self.client
            .post("https://api.anthropic.com/v1/messages")
            .header("x-api-key", &self.api_key)
            .header("anthropic-version", "2023-06-01")
            .header("Content-Type", "application/json")
            .json(&json!({
                "model": self.model,
                "max_tokens": 4096,
                "system": system_prompt,
                "messages": [
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.1
            }))
            .send()
            .await
            .map_err(|e| DatabaseError::LlmError(format!("Anthropic API error: {}", e)))?;

        let status = response.status();
        let body = response.text().await
            .map_err(|e| DatabaseError::LlmError(format!("Failed to read response: {}", e)))?;

        if !status.is_success() {
            return Err(DatabaseError::LlmError(format!("Anthropic API error {}: {}", status, body)));
        }

        let parsed: AnthropicResponse = serde_json::from_str(&body)
            .map_err(|e| DatabaseError::LlmError(format!("Failed to parse Anthropic response: {}\nBody: {}", e, body)))?;

        let text = parsed.content.first()
            .ok_or_else(|| DatabaseError::LlmError("No response from Anthropic".to_string()))?
            .text.clone();

        // Debug: log the raw response
        eprintln!("Anthropic raw response:\n{}", text);

        // Strip markdown code blocks
        Ok(Self::strip_markdown(&text))
    }

    /// Get JSON Schema for QueryPlan struct.
    fn get_query_plan_schema() -> serde_json::Value {
        json!({
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": ["lookup", "search", "traverse", "sql", "hybrid"]
                },
                "confidence": {"type": "number"},
                "primary_query": {
                    "type": "object",
                    "properties": {
                        "dialect": {"type": "string", "enum": ["rem_sql", "standard_sql"]},
                        "query_string": {"type": "string"},
                        "parameters": {
                            "anyOf": [
                                {
                                    "type": "object",
                                    "properties": {
                                        "keys": {"type": "array", "items": {"type": "string"}}
                                    },
                                    "required": ["keys"],
                                    "additionalProperties": false
                                },
                                {
                                    "type": "object",
                                    "properties": {
                                        "query_text": {"type": "string"},
                                        "schema": {"type": "string"},
                                        "top_k": {"type": "integer"},
                                        "filters": {
                                            "type": "object",
                                            "properties": {},
                                            "additionalProperties": false
                                        }
                                    },
                                    "required": ["query_text", "schema"],
                                    "additionalProperties": false
                                },
                                {
                                    "type": "object",
                                    "properties": {
                                        "entity_id": {"type": "string"},
                                        "relation_type": {"type": "string"},
                                        "direction": {"type": "string", "enum": ["forward", "reverse", "both"]},
                                        "max_depth": {"type": "integer"}
                                    },
                                    "required": ["entity_id", "relation_type", "direction"],
                                    "additionalProperties": false
                                },
                                {
                                    "type": "object",
                                    "properties": {},
                                    "additionalProperties": false
                                }
                            ]
                        }
                    },
                    "required": ["dialect", "query_string", "parameters"],
                    "additionalProperties": false
                },
                "fallback_queries": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "object",
                                "properties": {
                                    "dialect": {"type": "string"},
                                    "query_string": {"type": "string"},
                                    "parameters": {
                                        "anyOf": [
                                            {
                                                "type": "object",
                                                "properties": {
                                                    "keys": {"type": "array", "items": {"type": "string"}}
                                                },
                                                "required": ["keys"],
                                                "additionalProperties": false
                                            },
                                            {
                                                "type": "object",
                                                "properties": {
                                                    "query_text": {"type": "string"},
                                                    "schema": {"type": "string"},
                                                    "top_k": {"type": "integer"},
                                                    "filters": {
                                                        "type": "object",
                                                        "properties": {},
                                                        "additionalProperties": false
                                                    }
                                                },
                                                "required": ["query_text", "schema"],
                                                "additionalProperties": false
                                            },
                                            {
                                                "type": "object",
                                                "properties": {
                                                    "entity_id": {"type": "string"},
                                                    "relation_type": {"type": "string"},
                                                    "direction": {"type": "string", "enum": ["forward", "reverse", "both"]},
                                                    "max_depth": {"type": "integer"}
                                                },
                                                "required": ["entity_id", "relation_type", "direction"],
                                                "additionalProperties": false
                                            },
                                            {
                                                "type": "object",
                                                "properties": {},
                                                "additionalProperties": false
                                            }
                                        ]
                                    }
                                },
                                "required": ["dialect", "query_string", "parameters"],
                                "additionalProperties": false
                            },
                            "trigger": {
                                "type": "string",
                                "enum": ["no_results", "error", "low_quality"]
                            },
                            "confidence": {"type": "number"},
                            "reasoning": {"type": "string"}
                        },
                        "required": ["query", "trigger", "confidence", "reasoning"],
                        "additionalProperties": false
                    }
                },
                "execution_mode": {
                    "type": "string",
                    "enum": ["single_pass", "multi_stage", "adaptive"]
                },
                "schema_hints": {"type": "array", "items": {"type": "string"}},
                "reasoning": {"type": "string"},
                "explanation": {
                    "anyOf": [{"type": "string"}, {"type": "null"}]
                },
                "next_steps": {"type": "array", "items": {"type": "string"}},
                "metadata": {
                    "type": "object",
                    "properties": {
                        "estimated_rows": {
                            "anyOf": [{"type": "integer"}, {"type": "null"}]
                        },
                        "estimated_latency_ms": {
                            "anyOf": [{"type": "integer"}, {"type": "null"}]
                        },
                        "cacheable": {"type": "boolean"}
                    },
                    "required": ["cacheable"],
                    "additionalProperties": false
                }
            },
            "required": [
                "query_type", "confidence", "primary_query", "fallback_queries",
                "execution_mode", "schema_hints", "reasoning", "next_steps", "metadata"
            ],
            "additionalProperties": false
        })
    }

    /// Call Cerebras API (OpenAI-compatible) with strict JSON schema.
    async fn call_cerebras(&self, system_prompt: &str, user_prompt: &str) -> Result<String> {
        let response = self.client
            .post("https://api.cerebras.ai/v1/chat/completions")
            .header("Authorization", format!("Bearer {}", self.api_key))
            .header("Content-Type", "application/json")
            .json(&json!({
                "model": self.model.strip_prefix("cerebras:").unwrap_or(&self.model),
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "query_plan",
                        "strict": true,
                        "schema": Self::get_query_plan_schema()
                    }
                },
                "temperature": 0.1,
                "max_tokens": 4096
            }))
            .send()
            .await
            .map_err(|e| DatabaseError::LlmError(format!("Cerebras API error: {}", e)))?;

        let status = response.status();
        let body = response.text().await
            .map_err(|e| DatabaseError::LlmError(format!("Failed to read response: {}", e)))?;

        if !status.is_success() {
            return Err(DatabaseError::LlmError(format!("Cerebras API error {}: {}", status, body)));
        }

        let parsed: OpenAIResponse = serde_json::from_str(&body)
            .map_err(|e| DatabaseError::LlmError(format!("Failed to parse Cerebras response: {}\nBody: {}", e, body)))?;

        let text = parsed.choices.first()
            .ok_or_else(|| DatabaseError::LlmError("No response from Cerebras".to_string()))?
            .message.content.clone();

        // Debug: log the raw response
        eprintln!("Cerebras raw response:\n{}", text);

        Ok(text)
    }

    /// Generate query plan without executing.
    ///
    /// # Arguments
    ///
    /// * `question` - Natural language question
    /// * `schema_context` - Schema information
    ///
    /// # Returns
    ///
    /// Query plan with confidence score
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::LlmError` if planning fails
    pub async fn plan_query(&self, question: &str, schema_context: &str) -> Result<QueryPlan> {
        // Check if it's a simple entity lookup
        if Self::is_entity_lookup(question) {
            return Ok(QueryPlan {
                query_type: QueryType::Lookup,
                confidence: 1.0,
                primary_query: Query {
                    dialect: QueryDialect::RemSql,
                    query_string: format!("LOOKUP '{}'", question),
                    parameters: json!({"keys": [question]}),
                },
                fallback_queries: vec![],
                execution_mode: ExecutionMode::SinglePass,
                schema_hints: vec![],
                reasoning: "Exact identifier pattern detected".to_string(),
                explanation: None,
                next_steps: vec!["Execute lookup".to_string()],
                metadata: Default::default(),
            });
        }

        let system_prompt = r#"You are a query planner for REM Database. Return ONLY valid JSON matching this EXACT schema:

{
  "query_type": "lookup" | "search" | "traverse" | "sql" | "hybrid",
  "confidence": 0.0-1.0,
  "primary_query": {
    "dialect": "rem_sql",
    "query_string": "LOOKUP 'key' | SEARCH 'text' IN schema | SELECT ...",
    "parameters": { ... }
  },
  "fallback_queries": [
    {
      "query": {
        "dialect": "rem_sql",
        "query_string": "...",
        "parameters": { ... }
      },
      "trigger": "no_results" | "error" | "low_quality",
      "confidence": 0.0-1.0,
      "reasoning": "Why this fallback"
    }
  ],
  "execution_mode": "single_pass" | "multi_stage" | "adaptive",
  "schema_hints": [],
  "reasoning": "Brief explanation",
  "explanation": null,
  "next_steps": ["step1", "step2"],
  "metadata": {
    "estimated_rows": null,
    "estimated_latency_ms": null,
    "cacheable": true
  }
}

REM SQL DIALECT:
- LOOKUP 'key1', 'key2' - Key-based lookup (uses key_index CF, very fast)
- SEARCH 'text' IN schema [WHERE ...] LIMIT n - Semantic vector search
- TRAVERSE FROM <uuid> DEPTH n DIRECTION in|out|both [TYPE 'rel'] - Graph traversal
- SELECT fields FROM schema [WHERE ...] [ORDER BY ...] [LIMIT n] - SQL (NO JOINS)

RULES:
1. DO NOT guess schema names - if unknown, use LOOKUP (schema-agnostic)
2. Use LOOKUP for identifiers (UUIDs, keys, names) - searches all schemas
3. Use SEARCH for semantic queries when schema provided
4. SQL WHERE predicates ONLY if schema provided
5. TRAVERSE needs start entity (LOOKUP first if only name given)
6. NO JOINs - use TRAVERSE for relationships

CONFIDENCE:
- 1.0: Exact UUID/key lookup
- 0.9-0.95: Clear identifier pattern with schema
- 0.8-0.9: Clear field query with schema
- 0.6-0.8: Semantic search or multiple interpretations
- <0.6: Ambiguous (provide explanation)

PARAMETERS (what to query, not how):
- LOOKUP: {"keys": ["key1", "key2"]}
- SEARCH: {"query_text": "text", "schema": "name", "top_k": 10, "filters": {...}}
- TRAVERSE: {"start_key": "name", "depth": 1-3, "direction": "out|in|both", "edge_type": "rel"}
- SQL: {"schema": "name", "fields": [...], "where": {...}, "order_by": "field", "limit": n}
- HYBRID: {"query_text": "text", "schema": "name", "top_k": 10, "filters": {...}}

OUTPUT: Valid JSON only, no markdown, no explanation outside JSON."#;

        let user_prompt = format!(
            "Question: {}\n\nSchema context:\n{}\n\nGenerate query plan (JSON only):",
            question, schema_context
        );

        let response = self.call_llm(system_prompt, &user_prompt).await?;

        // Parse JSON response
        let plan: QueryPlan = serde_json::from_str(&response)
            .map_err(|e| DatabaseError::LlmError(format!("Failed to parse query plan: {}", e)))?;

        // Validate plan
        if !plan.is_valid() {
            return Err(DatabaseError::LlmError(
                "Invalid query plan: low confidence without explanation".to_string()
            ));
        }

        Ok(plan)
    }

    /// Execute query with multi-stage retrieval.
    ///
    /// # Arguments
    ///
    /// * `question` - Natural language question
    /// * `schema_context` - Schema information
    /// * `max_stages` - Maximum retry stages (1-3)
    ///
    /// # Returns
    ///
    /// Query result with metadata
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::LlmError` if execution fails
    ///
    /// # Algorithm
    ///
    /// 1. Stage 1: Execute primary query
    ///    - If results found → return immediately
    ///    - If no results → proceed to stage 2
    /// 2. Stage 2: Execute fallback query (broader)
    ///    - Relax filters or expand search scope
    ///    - If results found → return with stage metadata
    ///    - If no results → proceed to stage 3 (if max_stages > 2)
    /// 3. Stage N: Final fallback
    ///    - Most generic query (e.g., vector search without filters)
    ///    - Always returns results (may be low relevance)
    pub async fn execute_with_stages(
        &self,
        _question: &str,
        _schema_context: &str,
        _max_stages: usize,
    ) -> Result<QueryResult> {
        // TODO: Implement multi-stage retrieval with database integration
        // This requires Database instance to execute queries
        Err(DatabaseError::LlmError(
            "execute_with_stages not yet implemented - use plan_query + Database.execute".to_string()
        ))
    }

    /// Detect if query is entity lookup pattern.
    ///
    /// # Arguments
    ///
    /// * `question` - User question
    ///
    /// # Returns
    ///
    /// `true` if matches identifier pattern `^\w+[-_]?\w+$`
    ///
    /// # Examples
    ///
    /// - "111213" → true
    /// - "ABS-234" → true
    /// - "bob" → true
    /// - "show me recent articles" → false
    pub fn is_entity_lookup(question: &str) -> bool {
        let trimmed = question.trim();

        // Must be 1-50 characters
        if trimmed.len() > 50 || trimmed.is_empty() {
            return false;
        }

        // Check if it matches identifier pattern: alphanumeric with optional hyphens/underscores
        // Examples: "user-123", "ABS_234", "bob", "111213"
        // NOT: "show me users", "find articles about rust"
        let chars: Vec<char> = trimmed.chars().collect();

        // Must not have spaces
        if trimmed.contains(' ') {
            return false;
        }

        // First char must be alphanumeric
        if !chars[0].is_alphanumeric() {
            return false;
        }

        // All chars must be alphanumeric or hyphen/underscore
        chars.iter().all(|c| c.is_alphanumeric() || *c == '-' || *c == '_')
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_is_entity_lookup() {
        // Should match
        assert!(LlmQueryBuilder::is_entity_lookup("111213"));
        assert!(LlmQueryBuilder::is_entity_lookup("ABS-234"));
        assert!(LlmQueryBuilder::is_entity_lookup("user_123"));
        assert!(LlmQueryBuilder::is_entity_lookup("bob"));
        assert!(LlmQueryBuilder::is_entity_lookup("TAP-1234"));

        // Should not match
        assert!(!LlmQueryBuilder::is_entity_lookup("show me recent articles"));
        assert!(!LlmQueryBuilder::is_entity_lookup("find users"));
        assert!(!LlmQueryBuilder::is_entity_lookup("What is Rust?"));
        assert!(!LlmQueryBuilder::is_entity_lookup(""));
        assert!(!LlmQueryBuilder::is_entity_lookup("a b"));
    }
}
