//! Query plan generation and intent detection.

use serde::{Deserialize, Serialize};
use serde_json::Value as JsonValue;

/// Query type classification.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum QueryType {
    /// LOOKUP 'key1', 'key2' - Key-based lookup (key_index CF)
    Lookup,
    /// SEARCH 'text' IN schema - Semantic vector search
    Search,
    /// TRAVERSE FROM uuid - Graph traversal
    Traverse,
    /// SELECT ... FROM schema - SQL query (no joins)
    Sql,
    /// SEARCH + SQL WHERE - Hybrid semantic + filters
    Hybrid,
}

/// Execution mode for query staging.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum ExecutionMode {
    /// Single pass execution (high confidence)
    SinglePass,
    /// Multi-stage with fallbacks (moderate confidence)
    MultiStage,
    /// Adaptive execution (low confidence, needs clarification)
    Adaptive,
}

/// Fallback trigger condition.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum FallbackTrigger {
    /// No results from primary query
    NoResults,
    /// Query execution error
    Error,
    /// Results below quality threshold
    LowQuality,
}

/// Query dialect.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum QueryDialect {
    /// REM extended SQL
    RemSql,
    /// Standard SQL
    StandardSql,
}

/// Single query with parameters.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Query {
    /// Query dialect
    pub dialect: QueryDialect,

    /// Query string
    pub query_string: String,

    /// Structured parameters (WHAT to query)
    pub parameters: JsonValue,
}

/// Fallback query with trigger.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FallbackQuery {
    /// Fallback query
    pub query: Query,

    /// Trigger condition
    pub trigger: FallbackTrigger,

    /// Confidence of fallback
    pub confidence: f64,

    /// Reasoning for fallback
    pub reasoning: String,
}

/// Query metadata.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QueryMetadata {
    /// Estimated result count
    pub estimated_rows: Option<u64>,

    /// Estimated latency (ms)
    pub estimated_latency_ms: Option<u64>,

    /// Whether result should be cached
    pub cacheable: bool,
}

impl Default for QueryMetadata {
    fn default() -> Self {
        Self {
            estimated_rows: None,
            estimated_latency_ms: None,
            cacheable: true,
        }
    }
}

/// Query execution plan from natural language.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QueryPlan {
    /// Query type
    pub query_type: QueryType,

    /// Confidence score (0.0 - 1.0)
    pub confidence: f64,

    /// Primary query to execute first
    pub primary_query: Query,

    /// Fallback queries (ordered by priority)
    #[serde(default)]
    pub fallback_queries: Vec<FallbackQuery>,

    /// Execution mode
    pub execution_mode: ExecutionMode,

    /// Schema hints provided by user
    #[serde(default)]
    pub schema_hints: Vec<String>,

    /// Reasoning explanation
    pub reasoning: String,

    /// Explanation (required if confidence < 0.75)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub explanation: Option<String>,

    /// Next steps for subsequent queries
    #[serde(default)]
    pub next_steps: Vec<String>,

    /// Query metadata
    #[serde(default)]
    pub metadata: QueryMetadata,
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
