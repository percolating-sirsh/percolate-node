// Agent runtime for background processing (dreaming module)
//
// Minimal implementation for paginated LLM requests from RocksDB.
// Reference: percolate/src/percolate/agents/pagination.py

pub mod chunking;
pub mod client;
pub mod pagination;
pub mod schema;

pub use chunking::Chunker;
pub use client::{LlmClient, TokenUsage};
pub use pagination::{AggregatedTokenUsage, MergeStrategy, PaginatedRequest};
pub use schema::AgentSchema;

/// Agent runtime for making paginated LLM requests
///
/// Example:
/// ```no_run
/// use percolate_rocks::agents::{AgentRuntime, MergeStrategy};
///
/// let runtime = AgentRuntime::new(db);
/// let result = runtime.process_with_agent(
///     "tenant-123",
///     "entity-extractor",
///     large_document,
///     MergeStrategy::Merge,
/// ).await?;
/// ```
pub struct AgentRuntime {
    // Will be implemented in phases
}
