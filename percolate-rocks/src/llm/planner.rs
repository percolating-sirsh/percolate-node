//! Query plan generation and intent detection.

use serde::{Deserialize, Serialize};

/// Query intent detected from natural language.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum QueryIntent {
    /// Entity lookup (global key search)
    EntityLookup,
    /// SQL SELECT query
    Select,
    /// Semantic vector search
    Search,
    /// Hybrid (semantic + filters)
    Hybrid,
    /// Graph traversal
    Traverse,
    /// Aggregation
    Aggregate,
}

/// Query execution plan from natural language.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QueryPlan {
    /// Detected intent
    pub intent: QueryIntent,

    /// Generated query (SQL or SEARCH syntax)
    pub query: String,

    /// Confidence score (0.0 - 1.0)
    /// - 1.0: Exact ID lookup
    /// - 0.8-0.95: Clear field-based query
    /// - 0.6-0.8: Semantic/vector search
    /// - < 0.6: Ambiguous (explanation required)
    pub confidence: f64,

    /// Reasoning explanation
    pub reasoning: String,

    /// Explanation (required if confidence < 0.6)
    pub explanation: Option<String>,

    /// Whether semantic search is required
    pub requires_search: bool,

    /// Suggested parameters
    pub parameters: serde_json::Value,

    /// Next steps for subsequent queries (terse, actionable)
    pub next_steps: Vec<String>,
}

impl QueryPlan {
    /// Check if plan is high confidence.
    ///
    /// # Returns
    ///
    /// `true` if confidence >= 0.8
    pub fn is_confident(&self) -> bool {
        self.confidence >= 0.8
    }

    /// Check if plan requires user confirmation.
    ///
    /// # Returns
    ///
    /// `true` if confidence < 0.6
    pub fn needs_confirmation(&self) -> bool {
        self.confidence < 0.6
    }

    /// Validate plan has explanation if confidence is low.
    ///
    /// # Returns
    ///
    /// `true` if valid (high confidence OR has explanation)
    pub fn is_valid(&self) -> bool {
        self.confidence >= 0.6 || self.explanation.is_some()
    }
}

/// Query execution result with metadata.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QueryResult {
    /// Matched entities
    pub results: Vec<serde_json::Value>,

    /// Executed query
    pub query: String,

    /// Query type
    pub query_type: String,

    /// Confidence score
    pub confidence: f64,

    /// Number of stages executed
    pub stages: usize,

    /// Results per stage
    pub stage_results: Vec<usize>,

    /// Total execution time (ms)
    pub total_time_ms: u64,

    /// Explanation (if confidence < 0.6)
    pub explanation: Option<String>,
}
