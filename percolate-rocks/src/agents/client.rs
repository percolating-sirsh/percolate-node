//! Minimal HTTP client for LLM APIs
//!
//! This is a lightweight client for making requests to Anthropic, OpenAI, etc.
//! It does NOT implement a full agent framework like Pydantic AI - just HTTP POST requests.
//!
//! # Design Philosophy
//!
//! - **Minimal dependencies**: Only reqwest + serde_json
//! - **Token tracking built-in**: Every request returns (result, usage)
//! - **Model-specific pricing**: Cost calculation for Anthropic, OpenAI
//! - **Structured output**: JSON schema validation via API
//! - **Background processing**: No interactive features, no MCP tools
//!
//! # Use Case
//!
//! This client is ONLY for the dreaming module to make LLM requests during
//! background indexing. For interactive API requests, use the Python layer
//! with Pydantic AI.
//!
//! # Reference
//!
//! Python uses Pydantic AI for full agent orchestration. We just need HTTP.
//! See: `percolate/src/percolate/agents/factory.py`

use serde::{Deserialize, Serialize};

/// Token usage tracking for cost monitoring
///
/// Every LLM request returns this struct alongside the result.
/// This is CRITICAL for cost control in background processing.
///
/// # Example
///
/// ```no_run
/// # use percolate_rocks::agents::TokenUsage;
/// let usage = TokenUsage {
///     input_tokens: 1500,
///     output_tokens: 300,
///     estimated_cost_usd: 0.0012,
///     model: "claude-haiku-4-5".to_string(),
/// };
///
/// println!("Request cost: ${:.4}", usage.estimated_cost_usd);
/// println!("Total tokens: {}", usage.input_tokens + usage.output_tokens);
/// ```
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TokenUsage {
    /// Number of tokens in the input (system prompt + user content)
    pub input_tokens: u32,

    /// Number of tokens in the output (LLM response)
    pub output_tokens: u32,

    /// Estimated cost in USD based on model pricing
    ///
    /// Calculated using current pricing as of 2025:
    /// - claude-haiku-4-5: $0.25/$1.25 per MTok
    /// - claude-sonnet-4-5: $3/$15 per MTok
    /// - gpt-4.1: $2.5/$10 per MTok
    pub estimated_cost_usd: f64,

    /// Model name used for the request
    pub model: String,
}

/// Minimal LLM API client
///
/// Makes HTTP POST requests to LLM APIs (Anthropic, OpenAI) with structured output.
/// Returns both the result and token usage for cost tracking.
///
/// # Design Notes
///
/// - **No full agent framework**: This is not Pydantic AI, just HTTP client
/// - **No MCP tools**: Agents are pure prompt→response, no tool calling
/// - **No session management**: Stateless requests only
/// - **Token tracking required**: Every request must return usage data
///
/// # Supported APIs
///
/// - Anthropic Messages API (claude-* models)
/// - OpenAI Chat Completions API (gpt-* models)
///
/// # Example
///
/// ```no_run
/// # use percolate_rocks::agents::LlmClient;
/// # use serde_json::json;
/// # async fn example() -> Result<(), Box<dyn std::error::Error>> {
/// let client = LlmClient::new("claude-haiku-4-5", "api-key".to_string());
///
/// let output_schema = json!({
///     "type": "object",
///     "properties": {
///         "entities": {"type": "array", "items": {"type": "string"}},
///         "count": {"type": "integer"}
///     },
///     "required": ["entities", "count"]
/// });
///
/// let (result, usage) = client.request(
///     "Extract entities from the text",
///     "Apple and Google are tech companies",
///     &output_schema,
/// ).await?;
///
/// println!("Entities: {:?}", result["entities"]);
/// println!("Cost: ${:.4}", usage.estimated_cost_usd);
/// # Ok(())
/// # }
/// ```
pub struct LlmClient {
    /// Model name (e.g., "claude-haiku-4-5", "gpt-4.1")
    pub(crate) model: String,

    /// API key for authentication
    pub(crate) api_key: String,

    /// API endpoint URL
    ///
    /// Automatically determined from model:
    /// - claude-*: https://api.anthropic.com/v1/messages
    /// - gpt-*: https://api.openai.com/v1/chat/completions
    pub(crate) endpoint: String,

    // HTTP client (reqwest)
    //
    // TODO: Add in Phase 1
    // http_client: reqwest::Client,
}

impl LlmClient {
    /// Create a new LLM client
    ///
    /// # Arguments
    ///
    /// * `model` - Model name (e.g., "claude-haiku-4-5")
    /// * `api_key` - API key for authentication
    ///
    /// # Returns
    ///
    /// Configured client ready to make requests
    ///
    /// # Implementation Notes (Phase 1)
    ///
    /// 1. Parse model name to determine provider (Anthropic vs OpenAI)
    /// 2. Set appropriate endpoint URL
    /// 3. Create reqwest::Client with timeout (30s)
    /// 4. Configure retry policy (3 attempts, exponential backoff)
    /// 5. Set default headers (API key, content-type, user-agent)
    ///
    /// # Example
    ///
    /// ```no_run
    /// # use percolate_rocks::agents::LlmClient;
    /// let client = LlmClient::new(
    ///     "claude-haiku-4-5",
    ///     std::env::var("ANTHROPIC_API_KEY").unwrap()
    /// );
    /// ```
    pub fn new(model: &str, api_key: String) -> Self {
        // TODO: Implement in Phase 1
        // 1. Determine endpoint from model name
        // 2. Create reqwest client with timeout
        // 3. Set up retry policy
        todo!("Create LLM client")
    }

    /// Make LLM request with structured output
    ///
    /// This is the core method for all LLM interactions. It sends a request
    /// to the LLM API and returns both the parsed result and token usage.
    ///
    /// # Arguments
    ///
    /// * `system_prompt` - The agent's system prompt (what role to play)
    /// * `content` - The user content to process (text or JSON)
    /// * `output_schema` - JSON schema for structured output validation
    ///
    /// # Returns
    ///
    /// Tuple of `(result, token_usage)`:
    /// - `result`: Parsed JSON response matching output_schema
    /// - `token_usage`: Token counts and estimated cost
    ///
    /// # Errors
    ///
    /// Returns error if:
    /// - HTTP request fails (network error, timeout)
    /// - API returns error response (invalid key, rate limit)
    /// - Response JSON parsing fails
    /// - Output doesn't match schema
    ///
    /// # Implementation Notes (Phase 1)
    ///
    /// **Request format (Anthropic):**
    /// ```json
    /// {
    ///   "model": "claude-haiku-4-5",
    ///   "max_tokens": 4096,
    ///   "system": "Extract entities from text",
    ///   "messages": [{"role": "user", "content": "..."}],
    ///   "tools": [{
    ///     "name": "output",
    ///     "description": "Structured output",
    ///     "input_schema": { /* JSON schema */ }
    ///   }],
    ///   "tool_choice": {"type": "tool", "name": "output"}
    /// }
    /// ```
    ///
    /// **Request format (OpenAI):**
    /// ```json
    /// {
    ///   "model": "gpt-4.1",
    ///   "messages": [
    ///     {"role": "system", "content": "Extract entities from text"},
    ///     {"role": "user", "content": "..."}
    ///   ],
    ///   "response_format": {
    ///     "type": "json_schema",
    ///     "json_schema": { /* JSON schema */ }
    ///   }
    /// }
    /// ```
    ///
    /// **Response processing:**
    /// 1. Extract content from response
    /// 2. Parse JSON
    /// 3. Extract token usage from response.usage
    /// 4. Calculate cost using `calculate_cost()`
    /// 5. Log request details (CRITICAL for debugging)
    /// 6. Return (result, usage)
    ///
    /// # Example
    ///
    /// ```no_run
    /// # use percolate_rocks::agents::LlmClient;
    /// # use serde_json::json;
    /// # async fn example() -> Result<(), Box<dyn std::error::Error>> {
    /// # let client = LlmClient::new("claude-haiku-4-5", "key".to_string());
    /// let (result, usage) = client.request(
    ///     "You are a data extractor. Extract entities from text.",
    ///     "Apple Inc. was founded by Steve Jobs in Cupertino.",
    ///     &json!({
    ///         "type": "object",
    ///         "properties": {
    ///             "entities": {
    ///                 "type": "array",
    ///                 "items": {"type": "string"}
    ///             }
    ///         }
    ///     }),
    /// ).await?;
    ///
    /// assert_eq!(result["entities"].as_array().unwrap().len(), 3);
    /// println!("Cost: ${:.4}", usage.estimated_cost_usd);
    /// # Ok(())
    /// # }
    /// ```
    pub async fn request(
        &self,
        system_prompt: &str,
        content: &str,
        output_schema: &serde_json::Value,
    ) -> Result<(serde_json::Value, TokenUsage), Box<dyn std::error::Error>> {
        // TODO: Implement in Phase 1
        //
        // Steps:
        // 1. Build HTTP request body (format depends on provider)
        // 2. Add authentication headers
        // 3. POST to endpoint
        // 4. Handle HTTP errors (retry on 5xx, fail on 4xx)
        // 5. Parse response JSON
        // 6. Extract structured output (tool call or response_format)
        // 7. Extract token usage from response.usage
        // 8. Calculate cost
        // 9. Log request details:
        //    tracing::info!(
        //        model = %self.model,
        //        input_tokens = usage.input_tokens,
        //        output_tokens = usage.output_tokens,
        //        cost_usd = usage.estimated_cost_usd,
        //        "LLM request completed"
        //    );
        // 10. Return (result, usage)
        todo!("Make LLM HTTP request with token tracking")
    }

    /// Calculate cost based on model pricing
    ///
    /// Uses current pricing as of 2025. Update this when pricing changes.
    ///
    /// # Arguments
    ///
    /// * `input_tokens` - Number of input tokens
    /// * `output_tokens` - Number of output tokens
    ///
    /// # Returns
    ///
    /// Estimated cost in USD
    ///
    /// # Pricing (2025)
    ///
    /// | Model | Input (per MTok) | Output (per MTok) |
    /// |-------|------------------|-------------------|
    /// | claude-haiku-4-5 | $0.25 | $1.25 |
    /// | claude-sonnet-4-5 | $3.00 | $15.00 |
    /// | gpt-4.1 | $2.50 | $10.00 |
    ///
    /// # Example
    ///
    /// ```no_run
    /// # use percolate_rocks::agents::LlmClient;
    /// # let client = LlmClient::new("claude-haiku-4-5", "key".to_string());
    /// // 10k input tokens, 2k output tokens with claude-haiku-4-5
    /// // = (10000 * 0.25/1M) + (2000 * 1.25/1M)
    /// // = 0.0025 + 0.0025
    /// // = $0.005
    /// let cost = client.calculate_cost(10_000, 2_000);
    /// assert!((cost - 0.005).abs() < 0.0001);
    /// ```
    fn calculate_cost(&self, input_tokens: u32, output_tokens: u32) -> f64 {
        // Model-specific pricing (as of 2025)
        let (input_cost_per_mtok, output_cost_per_mtok) = match self.model.as_str() {
            // Anthropic Claude models
            "claude-haiku-4-5" => (0.25, 1.25),
            "claude-sonnet-4-5" => (3.0, 15.0),
            "claude-opus-4" => (15.0, 75.0),

            // OpenAI GPT models
            "gpt-4.1" => (2.5, 10.0),
            "gpt-4.1-turbo" => (1.0, 3.0),

            // Unknown model - return 0 cost but log warning
            _ => {
                tracing::warn!(
                    model = %self.model,
                    "Unknown model pricing - cost calculation will be 0"
                );
                (0.0, 0.0)
            }
        };

        // Calculate cost: (tokens / 1M) * price_per_mtok
        let input_cost = (input_tokens as f64 / 1_000_000.0) * input_cost_per_mtok;
        let output_cost = (output_tokens as f64 / 1_000_000.0) * output_cost_per_mtok;

        input_cost + output_cost
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_calculate_cost_haiku() {
        let client = LlmClient {
            model: "claude-haiku-4-5".to_string(),
            api_key: "test".to_string(),
            endpoint: "https://api.anthropic.com/v1/messages".to_string(),
        };

        // 10k input, 2k output = $0.005
        let cost = client.calculate_cost(10_000, 2_000);
        assert!((cost - 0.005).abs() < 0.0001);
    }

    #[test]
    fn test_calculate_cost_sonnet() {
        let client = LlmClient {
            model: "claude-sonnet-4-5".to_string(),
            api_key: "test".to_string(),
            endpoint: "https://api.anthropic.com/v1/messages".to_string(),
        };

        // 10k input, 2k output = $0.06
        let cost = client.calculate_cost(10_000, 2_000);
        assert!((cost - 0.06).abs() < 0.0001);
    }

    #[test]
    fn test_calculate_cost_unknown_model() {
        let client = LlmClient {
            model: "unknown-model".to_string(),
            api_key: "test".to_string(),
            endpoint: "https://example.com".to_string(),
        };

        // Unknown model should return 0 cost
        let cost = client.calculate_cost(10_000, 2_000);
        assert_eq!(cost, 0.0);
    }
}
