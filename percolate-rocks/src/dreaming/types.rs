//! Data types for REM Dreaming

use serde::{Deserialize, Serialize};
use chrono::{DateTime, Utc};
use uuid::Uuid;

/// Input data for dreaming process
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DreamingInput {
    pub resources: Vec<serde_json::Value>,
    pub sessions: Vec<serde_json::Value>,
    pub messages: Vec<serde_json::Value>,
    pub time_range_start: DateTime<Utc>,
    pub time_range_end: DateTime<Utc>,
}

/// Output from moment generator agent
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DreamingOutput {
    pub moments: Vec<Moment>,
    pub graph_edges: Vec<GraphEdge>,
    pub summary_resource: Option<Resource>,
    pub analysis_metadata: AnalysisMetadata,
}

/// Moment structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Moment {
    pub name: String,
    pub summary: String,
    pub start_time: DateTime<Utc>,
    pub end_time: DateTime<Utc>,
    pub moment_type: MomentType,
    pub tags: Vec<String>,
    pub emotion_tags: Vec<String>,
    pub people: Vec<String>,
    pub resource_ids: Vec<Uuid>,
    pub session_ids: Vec<Uuid>,
    pub metadata: serde_json::Value,
}

/// Moment type enum
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MomentType {
    WorkSession,
    Learning,
    Planning,
    Communication,
    Reflection,
    Creation,
    Other,
}

/// Graph edge between entities
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GraphEdge {
    pub source_id: Uuid,
    pub target_id: Uuid,
    pub edge_type: EdgeType,
    pub metadata: serde_json::Value,
}

/// Edge type enum
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EdgeType {
    RelatedTo,
    DerivedFrom,
    MentionedIn,
    Follows,
    Precedes,
    SimilarTo,
}

/// Summary resource
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Resource {
    pub name: String,
    pub content: String,
    pub tags: Vec<String>,
    pub metadata: serde_json::Value,
}

/// Analysis metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnalysisMetadata {
    pub total_resources: usize,
    pub total_sessions: usize,
    pub total_messages: usize,
    pub time_range_start: DateTime<Utc>,
    pub time_range_end: DateTime<Utc>,
    pub confidence_score: Option<f64>,
    pub llm_tokens_used: Option<usize>,
    pub estimated_cost: Option<f64>,
}

/// Statistics from dreaming run
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DreamingStats {
    pub moments_created: usize,
    pub edges_created: usize,
    pub summaries_created: usize,
    pub duration_seconds: f64,
    pub llm_tokens_used: usize,
    pub estimated_cost: f64,
}
