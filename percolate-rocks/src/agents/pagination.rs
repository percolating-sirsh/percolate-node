//! Paginated agent requests
//!
//! Executes agent on large content by:
//! 1. Chunking content into pieces that fit in context window
//! 2. Running agent on each chunk (parallel or sequential)
//! 3. Merging results according to strategy
//!
//! # Design Philosophy
//!
//! - **Agent already has system prompt**: We just paginate the data
//! - **Token usage tracking**: Aggregate usage across all chunks for cost control
//! - **Parallel execution**: Use tokio for concurrent requests
//! - **Flexible merging**: concat, merge, first, last strategies
//!
//! # Reference
//!
//! Python implementation: `percolate/src/percolate/agents/pagination.py`
//! This Rust version should match the Python behavior.

use super::{Chunker, LlmClient, TokenUsage};

/// Merge strategy for combining paginated results
///
/// Different strategies for different use cases:
/// - **Concat**: Batch processing, keep all results separate
/// - **Merge**: Entity extraction, combine list fields
/// - **First**: Classification, only need first chunk
/// - **Last**: Summarization, only need final summary
#[derive(Debug, Clone, Copy)]
pub enum MergeStrategy {
    /// Return list of all chunk results
    ///
    /// Use case: Batch processing where each chunk result is independent
    ///
    /// # Example
    ///
    /// Input: [result1, result2, result3]
    /// Output: [result1, result2, result3]
    Concat,

    /// Combine list fields, keep first non-list values
    ///
    /// Use case: Entity extraction where entities should be combined
    ///
    /// # Example
    ///
    /// Input: [
    ///   {"entities": ["A", "B"], "count": 2},
    ///   {"entities": ["C"], "count": 1}
    /// ]
    /// Output: {"entities": ["A", "B", "C"], "count": 2}
    Merge,

    /// Return first chunk result only
    ///
    /// Use case: Classification where first chunk is sufficient
    ///
    /// # Example
    ///
    /// Input: [result1, result2, result3]
    /// Output: result1
    First,

    /// Return last chunk result only
    ///
    /// Use case: Summarization where final summary contains all info
    ///
    /// # Example
    ///
    /// Input: [result1, result2, result3]
    /// Output: result3
    Last,
}

/// Aggregated token usage across all chunks
///
/// Tracks total token usage and cost for entire paginated request.
/// This is CRITICAL for cost control in background processing.
///
/// # Example
///
/// ```no_run
/// # use percolate_rocks::agents::AggregatedTokenUsage;
/// let usage = AggregatedTokenUsage {
///     total_input_tokens: 150_000,
///     total_output_tokens: 30_000,
///     total_cost_usd: 0.075,
///     chunks_processed: 5,
///     per_chunk_usage: vec![/* ... */],
/// };
///
/// println!("Processed {} chunks", usage.chunks_processed);
/// println!("Total cost: ${:.4}", usage.total_cost_usd);
/// println!("Avg tokens per chunk: {}",
///     usage.total_input_tokens / usage.chunks_processed as u32);
/// ```
#[derive(Debug, Clone)]
pub struct AggregatedTokenUsage {
    /// Total input tokens across all chunks
    pub total_input_tokens: u32,

    /// Total output tokens across all chunks
    pub total_output_tokens: u32,

    /// Total estimated cost in USD
    pub total_cost_usd: f64,

    /// Number of chunks processed
    pub chunks_processed: usize,

    /// Per-chunk usage breakdown (for debugging/analysis)
    pub per_chunk_usage: Vec<TokenUsage>,
}

/// Paginated request executor
///
/// Handles large content that exceeds model context window by:
/// 1. Chunking content (preserving boundaries)
/// 2. Executing agent on each chunk (parallel or sequential)
/// 3. Merging results according to strategy
/// 4. Aggregating token usage for cost tracking
///
/// # Example
///
/// ```no_run
/// # use percolate_rocks::agents::{PaginatedRequest, LlmClient, Chunker, MergeStrategy};
/// # use serde_json::json;
/// # async fn example() -> Result<(), Box<dyn std::error::Error>> {
/// let client = LlmClient::new("claude-haiku-4-5", "api-key".to_string());
/// let chunker = Chunker::new("claude-haiku-4-5", Some(50_000));
/// let paginator = PaginatedRequest::new(client, chunker);
///
/// let large_document = "document content...".repeat(10000);
/// let output_schema = json!({
///     "type": "object",
///     "properties": {
///         "entities": {"type": "array", "items": {"type": "string"}}
///     }
/// });
///
/// let (result, usage) = paginator.execute(
///     "Extract entities from text",
///     &large_document,
///     &output_schema,
///     MergeStrategy::Merge,
///     true, // parallel
/// ).await?;
///
/// println!("Entities: {:?}", result["entities"]);
/// println!("Processed {} chunks at ${:.4}",
///     usage.chunks_processed, usage.total_cost_usd);
/// # Ok(())
/// # }
/// ```
pub struct PaginatedRequest {
    /// LLM client for making requests
    pub(crate) client: LlmClient,

    /// Chunker for splitting content
    pub(crate) chunker: Chunker,
}

impl PaginatedRequest {
    /// Create new paginated request executor
    ///
    /// # Arguments
    ///
    /// * `client` - Configured LLM client
    /// * `chunker` - Configured chunker with appropriate max_tokens
    ///
    /// # Returns
    ///
    /// Executor ready to process paginated requests
    ///
    /// # Example
    ///
    /// ```no_run
    /// # use percolate_rocks::agents::{PaginatedRequest, LlmClient, Chunker};
    /// let client = LlmClient::new("claude-haiku-4-5", "api-key".to_string());
    /// let chunker = Chunker::new("claude-haiku-4-5", None); // Auto-calculate
    /// let paginator = PaginatedRequest::new(client, chunker);
    /// ```
    pub fn new(client: LlmClient, chunker: Chunker) -> Self {
        Self { client, chunker }
    }

    /// Execute agent with automatic pagination
    ///
    /// Agent already has system prompt. This just chunks input data,
    /// runs agent on each chunk, and merges results.
    ///
    /// # Arguments
    ///
    /// * `system_prompt` - Agent's system prompt (from schema)
    /// * `content` - Large input data to process
    /// * `output_schema` - JSON schema for structured output
    /// * `strategy` - How to merge chunk results
    /// * `parallel` - Whether to execute chunks in parallel
    ///
    /// # Returns
    ///
    /// Tuple of `(merged_result, aggregated_usage)`:
    /// - `merged_result`: Combined result according to strategy
    /// - `aggregated_usage`: Total token usage and cost
    ///
    /// # Errors
    ///
    /// Returns error if:
    /// - Chunking fails
    /// - Any LLM request fails (in sequential mode)
    /// - Merging fails
    ///
    /// # Implementation Notes (Phase 3)
    ///
    /// **Execution flow:**
    /// ```text
    /// 1. Chunk content using chunker
    /// 2. If single chunk, execute directly (no pagination)
    /// 3. If multiple chunks:
    ///    a. Execute parallel or sequential
    ///    b. Collect results and usage
    ///    c. Merge results according to strategy
    ///    d. Aggregate token usage
    ///    e. Log total cost (CRITICAL)
    /// 4. Return (result, usage)
    /// ```
    ///
    /// **Parallel execution (recommended):**
    /// ```rust
    /// use futures::future::join_all;
    ///
    /// let futures: Vec<_> = chunks
    ///     .iter()
    ///     .map(|chunk| self.client.request(system_prompt, chunk, output_schema))
    ///     .collect();
    ///
    /// let results = join_all(futures).await;
    /// ```
    ///
    /// **Sequential execution:**
    /// ```rust
    /// let mut results = Vec::new();
    /// for chunk in chunks {
    ///     let (result, usage) = self.client.request(
    ///         system_prompt,
    ///         chunk,
    ///         output_schema
    ///     ).await?;
    ///     results.push((result, usage));
    /// }
    /// ```
    ///
    /// **Token aggregation:**
    /// ```rust
    /// let total_input = results.iter().map(|(_, u)| u.input_tokens).sum();
    /// let total_output = results.iter().map(|(_, u)| u.output_tokens).sum();
    /// let total_cost = results.iter().map(|(_, u)| u.estimated_cost_usd).sum();
    ///
    /// tracing::info!(
    ///     chunks = chunks.len(),
    ///     total_input_tokens = total_input,
    ///     total_output_tokens = total_output,
    ///     total_cost_usd = total_cost,
    ///     "Paginated request completed"
    /// );
    /// ```
    ///
    /// # Example
    ///
    /// ```no_run
    /// # use percolate_rocks::agents::{PaginatedRequest, LlmClient, Chunker, MergeStrategy};
    /// # use serde_json::json;
    /// # async fn example() -> Result<(), Box<dyn std::error::Error>> {
    /// # let client = LlmClient::new("claude-haiku-4-5", "key".to_string());
    /// # let chunker = Chunker::new("claude-haiku-4-5", Some(1000));
    /// # let paginator = PaginatedRequest::new(client, chunker);
    /// let (result, usage) = paginator.execute(
    ///     "Extract entities from the text",
    ///     "very long document...",
    ///     &json!({"type": "object", "properties": {"entities": {"type": "array"}}}),
    ///     MergeStrategy::Merge,
    ///     true,
    /// ).await?;
    ///
    /// println!("Total cost: ${:.4}", usage.total_cost_usd);
    /// # Ok(())
    /// # }
    /// ```
    pub async fn execute(
        &self,
        system_prompt: &str,
        content: &str,
        output_schema: &serde_json::Value,
        strategy: MergeStrategy,
        parallel: bool,
    ) -> Result<(serde_json::Value, AggregatedTokenUsage), Box<dyn std::error::Error>> {
        // TODO: Implement in Phase 3
        //
        // Steps:
        // 1. Chunk content
        //    let chunks = self.chunker.chunk_text(content);
        //
        // 2. Single chunk optimization
        //    if chunks.len() == 1 {
        //        let (result, usage) = self.client.request(...).await?;
        //        return Ok((result, AggregatedTokenUsage {
        //            total_input_tokens: usage.input_tokens,
        //            total_output_tokens: usage.output_tokens,
        //            total_cost_usd: usage.estimated_cost_usd,
        //            chunks_processed: 1,
        //            per_chunk_usage: vec![usage],
        //        }));
        //    }
        //
        // 3. Execute parallel or sequential
        //    let results_with_usage = if parallel {
        //        self.execute_parallel(...).await?
        //    } else {
        //        self.execute_sequential(...).await?
        //    };
        //
        // 4. Merge results
        //    let merged = self.merge_results(
        //        results_with_usage.iter().map(|(r, _)| r).collect(),
        //        strategy
        //    )?;
        //
        // 5. Aggregate usage
        //    let aggregated = self.aggregate_usage(results_with_usage);
        //
        // 6. Log total cost
        //    tracing::info!(
        //        chunks = aggregated.chunks_processed,
        //        total_cost_usd = aggregated.total_cost_usd,
        //        "Paginated request completed"
        //    );
        //
        // 7. Return
        //    Ok((merged, aggregated))
        todo!("Execute paginated request with token tracking")
    }

    /// Execute chunks in parallel using tokio
    ///
    /// Sends all chunk requests concurrently, collects results.
    ///
    /// # Arguments
    ///
    /// * `system_prompt` - Agent's system prompt
    /// * `chunks` - Content chunks to process
    /// * `output_schema` - JSON schema for output
    ///
    /// # Returns
    ///
    /// Vector of (result, usage) tuples in chunk order
    ///
    /// # Errors
    ///
    /// Returns error if any request fails
    ///
    /// # Implementation Notes (Phase 3)
    ///
    /// **Using futures::join_all:**
    /// ```rust
    /// use futures::future::join_all;
    ///
    /// let futures: Vec<_> = chunks
    ///     .iter()
    ///     .enumerate()
    ///     .map(|(i, chunk)| async move {
    ///         tracing::debug!(chunk_index = i, "Processing chunk");
    ///         self.client.request(system_prompt, chunk, output_schema).await
    ///     })
    ///     .collect();
    ///
    /// let results = join_all(futures).await;
    /// ```
    ///
    /// **Error handling:**
    /// - Collect all results
    /// - Check for errors
    /// - If any error, return first error
    /// - Otherwise return all results
    async fn execute_parallel(
        &self,
        system_prompt: &str,
        chunks: &[String],
        output_schema: &serde_json::Value,
    ) -> Result<Vec<(serde_json::Value, TokenUsage)>, Box<dyn std::error::Error>> {
        // TODO: Implement in Phase 3
        //
        // Steps:
        // 1. Create futures for all chunks
        // 2. Use tokio::spawn or futures::join_all
        // 3. Await all results
        // 4. Check for errors
        // 5. Return results
        todo!("Execute chunks in parallel")
    }

    /// Execute chunks sequentially
    ///
    /// Sends chunk requests one at a time, in order.
    ///
    /// # Arguments
    ///
    /// * `system_prompt` - Agent's system prompt
    /// * `chunks` - Content chunks to process
    /// * `output_schema` - JSON schema for output
    ///
    /// # Returns
    ///
    /// Vector of (result, usage) tuples in chunk order
    ///
    /// # Errors
    ///
    /// Returns error on first failed request (stops processing)
    ///
    /// # Implementation Notes (Phase 3)
    ///
    /// **Sequential execution:**
    /// ```rust
    /// let mut results = Vec::new();
    ///
    /// for (i, chunk) in chunks.iter().enumerate() {
    ///     tracing::debug!(chunk_index = i, "Processing chunk");
    ///
    ///     let (result, usage) = self.client.request(
    ///         system_prompt,
    ///         chunk,
    ///         output_schema
    ///     ).await?;
    ///
    ///     results.push((result, usage));
    /// }
    ///
    /// Ok(results)
    /// ```
    ///
    /// # When to use sequential
    ///
    /// - Rate limiting concerns
    /// - Memory constraints (large results)
    /// - Debugging (easier to trace)
    async fn execute_sequential(
        &self,
        system_prompt: &str,
        chunks: &[String],
        output_schema: &serde_json::Value,
    ) -> Result<Vec<(serde_json::Value, TokenUsage)>, Box<dyn std::error::Error>> {
        // TODO: Implement in Phase 3
        //
        // Steps:
        // 1. Create empty results vec
        // 2. For each chunk:
        //    a. Make request
        //    b. Push result to vec
        //    c. Continue or return error
        // 3. Return results
        todo!("Execute chunks sequentially")
    }

    /// Merge results according to strategy
    ///
    /// Combines chunk results using the specified merge strategy.
    ///
    /// # Arguments
    ///
    /// * `results` - Vector of chunk results
    /// * `strategy` - Merge strategy to use
    ///
    /// # Returns
    ///
    /// Merged result
    ///
    /// # Errors
    ///
    /// Returns error if merging fails (e.g., incompatible types)
    ///
    /// # Implementation Notes (Phase 3)
    ///
    /// **Strategy implementation:**
    /// ```rust
    /// match strategy {
    ///     MergeStrategy::Concat => {
    ///         // Return array of all results
    ///         Ok(serde_json::Value::Array(results))
    ///     }
    ///     MergeStrategy::First => {
    ///         // Return first result
    ///         Ok(results[0].clone())
    ///     }
    ///     MergeStrategy::Last => {
    ///         // Return last result
    ///         Ok(results[results.len() - 1].clone())
    ///     }
    ///     MergeStrategy::Merge => {
    ///         // Recursive merge (see below)
    ///         self.merge_recursive(results)
    ///     }
    /// }
    /// ```
    ///
    /// **Recursive merge logic:**
    /// ```text
    /// For each key in merged result:
    ///   - If all values are arrays: extend (concatenate)
    ///   - If all values are objects: recursive merge
    ///   - If primitive: keep first value
    /// ```
    fn merge_results(
        &self,
        results: Vec<serde_json::Value>,
        strategy: MergeStrategy,
    ) -> Result<serde_json::Value, Box<dyn std::error::Error>> {
        // TODO: Implement in Phase 3
        //
        // Same logic as Python implementation:
        // - Concat: return Vec
        // - Merge: combine list fields recursively
        // - First/Last: return specific result
        todo!("Merge results")
    }

    /// Merge JSON objects recursively
    ///
    /// Rules (same as Python):
    /// - List fields: extend all items
    /// - Object fields: recursive merge
    /// - Primitive fields: keep first value
    ///
    /// # Example
    ///
    /// Input:
    /// ```json
    /// [
    ///   {"entities": ["A", "B"], "count": 2},
    ///   {"entities": ["C"], "count": 1}
    /// ]
    /// ```
    ///
    /// Output:
    /// ```json
    /// {"entities": ["A", "B", "C"], "count": 2}
    /// ```
    fn merge_recursive(
        &self,
        results: Vec<serde_json::Value>,
    ) -> Result<serde_json::Value, Box<dyn std::error::Error>> {
        // TODO: Implement in Phase 3
        //
        // Steps:
        // 1. Get all keys from all results
        // 2. For each key:
        //    a. Collect values from all results
        //    b. If all are arrays: extend
        //    c. If all are objects: recursive merge
        //    d. Otherwise: take first value
        // 3. Return merged object
        todo!("Recursive merge")
    }

    /// Aggregate token usage across chunks
    ///
    /// Sums up tokens and costs from all chunks.
    ///
    /// # Arguments
    ///
    /// * `results_with_usage` - Vector of (result, usage) tuples
    ///
    /// # Returns
    ///
    /// Aggregated usage stats
    fn aggregate_usage(
        &self,
        results_with_usage: Vec<(serde_json::Value, TokenUsage)>,
    ) -> AggregatedTokenUsage {
        let total_input_tokens = results_with_usage
            .iter()
            .map(|(_, u)| u.input_tokens)
            .sum();

        let total_output_tokens = results_with_usage
            .iter()
            .map(|(_, u)| u.output_tokens)
            .sum();

        let total_cost_usd = results_with_usage
            .iter()
            .map(|(_, u)| u.estimated_cost_usd)
            .sum();

        let per_chunk_usage: Vec<TokenUsage> = results_with_usage
            .into_iter()
            .map(|(_, u)| u)
            .collect();

        AggregatedTokenUsage {
            total_input_tokens,
            total_output_tokens,
            total_cost_usd,
            chunks_processed: per_chunk_usage.len(),
            per_chunk_usage,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_aggregate_usage() {
        let paginator = PaginatedRequest {
            client: LlmClient {
                model: "claude-haiku-4-5".to_string(),
                api_key: "test".to_string(),
                endpoint: "https://api.anthropic.com/v1/messages".to_string(),
            },
            chunker: Chunker {
                model: "claude-haiku-4-5".to_string(),
                max_tokens: 50_000,
            },
        };

        let results_with_usage = vec![
            (
                serde_json::json!({"result": 1}),
                TokenUsage {
                    input_tokens: 1000,
                    output_tokens: 200,
                    estimated_cost_usd: 0.001,
                    model: "claude-haiku-4-5".to_string(),
                },
            ),
            (
                serde_json::json!({"result": 2}),
                TokenUsage {
                    input_tokens: 1500,
                    output_tokens: 300,
                    estimated_cost_usd: 0.0015,
                    model: "claude-haiku-4-5".to_string(),
                },
            ),
        ];

        let aggregated = paginator.aggregate_usage(results_with_usage);

        assert_eq!(aggregated.total_input_tokens, 2500);
        assert_eq!(aggregated.total_output_tokens, 500);
        assert!((aggregated.total_cost_usd - 0.0025).abs() < 0.0001);
        assert_eq!(aggregated.chunks_processed, 2);
    }

    // TODO: Add more tests in Phase 3
    // - test_execute_single_chunk
    // - test_execute_multiple_chunks_parallel
    // - test_execute_multiple_chunks_sequential
    // - test_merge_concat
    // - test_merge_first_last
    // - test_merge_recursive
}
