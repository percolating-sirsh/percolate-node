//! Natural language to SQL/SEARCH query builder.

use crate::types::Result;
use crate::llm::planner::{QueryPlan, QueryResult};

/// LLM-powered query builder.
pub struct LlmQueryBuilder {
    api_key: String,
    model: String,
}

impl LlmQueryBuilder {
    /// Create new query builder.
    ///
    /// # Arguments
    ///
    /// * `api_key` - OpenAI API key
    /// * `model` - LLM model name (e.g., "gpt-4.1")
    ///
    /// # Returns
    ///
    /// New `LlmQueryBuilder`
    pub fn new(api_key: String, model: String) -> Self {
        todo!("Implement LlmQueryBuilder::new")
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
        todo!("Implement LlmQueryBuilder::build_query")
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
        todo!("Implement LlmQueryBuilder::plan_query")
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
        question: &str,
        schema_context: &str,
        max_stages: usize,
    ) -> Result<QueryResult> {
        todo!("Implement LlmQueryBuilder::execute_with_stages")
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
        todo!("Implement LlmQueryBuilder::is_entity_lookup")
    }
}
