//! Natural language to SQL/SEARCH query builder.

use crate::types::{Result, DatabaseError};
use crate::llm::planner::{QueryPlan, QueryResult, QueryIntent};
use serde::Deserialize;
use serde_json::json;
use reqwest::Client;

/// LLM provider type.
#[derive(Debug, Clone)]
pub enum LlmProvider {
    OpenAI,
    Anthropic,
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
    /// Uses `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` based on model
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
    async fn call_llm(&self, system_prompt: &str, user_prompt: &str) -> Result<String> {
        match self.provider {
            LlmProvider::OpenAI => self.call_openai(system_prompt, user_prompt).await,
            LlmProvider::Anthropic => self.call_anthropic(system_prompt, user_prompt).await,
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
            .map_err(|e| DatabaseError::LlmError(format!("Failed to parse Anthropic response: {}", e)))?;

        Ok(parsed.content.first()
            .ok_or_else(|| DatabaseError::LlmError("No response from Anthropic".to_string()))?
            .text.clone())
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
                intent: QueryIntent::EntityLookup,
                query: format!("LOOKUP '{}'", question),
                confidence: 1.0,
                reasoning: "Exact identifier pattern detected".to_string(),
                explanation: None,
                requires_search: false,
                parameters: json!({"key": question}),
                next_steps: vec![],
            });
        }

        let system_prompt = r#"You are a query planning expert for a semantic database with extended SQL syntax.

Your task is to convert natural language questions into executable queries.

Available query types and syntax:
1. **EntityLookup**: `LOOKUP 'key1', 'key2'` - Global key search for identifiers
2. **Select**: `SELECT * FROM table WHERE conditions` - Standard SQL
3. **Search**: `SEARCH 'query' IN table [WHERE ...] [LIMIT n]` - Semantic vector search
4. **Hybrid**: `SEARCH 'query' IN table WHERE field='value'` - Semantic + filters
5. **Traverse**: `TRAVERSE FROM 'uuid' DEPTH n DIRECTION out [TYPE 'rel']` - Graph navigation
6. **Aggregate**: `SELECT COUNT(*) FROM table` - SQL aggregations

Output ONLY valid JSON matching this schema:
{
  "intent": "Select|Search|Hybrid|Traverse|Aggregate|EntityLookup",
  "query": "Extended SQL syntax",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation of intent detection",
  "explanation": "Required if confidence < 0.6, otherwise null",
  "requires_search": true|false,
  "parameters": {"key": "value"},
  "next_steps": ["action1", "action2"]
}

Confidence scoring:
- 1.0: Exact ID lookup (use LOOKUP syntax)
- 0.8-0.95: Clear field-based SQL query
- 0.6-0.8: Semantic/vector search (use SEARCH syntax)
- < 0.6: Ambiguous (MUST provide explanation)

Examples:
- "user-123" → LOOKUP 'user-123'
- "Show users where role = admin" → SELECT * FROM users WHERE role = 'admin'
- "Find articles about Rust" → SEARCH 'Rust' IN articles
- "Recent Python tutorials" → SEARCH 'Python tutorials' IN articles WHERE created_at > '2024-01-01'
- "Who authored this document?" → TRAVERSE FROM 'doc-uuid' DEPTH 1 DIRECTION in TYPE 'authored'

Be concise. Output JSON only."#;

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
