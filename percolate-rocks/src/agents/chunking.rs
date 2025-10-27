//! Token-aware content chunking
//!
//! Splits large content into chunks that fit within model context windows.
//! Uses tiktoken-rs for accurate token counting.
//!
//! # Design Philosophy
//!
//! - **Accurate token counting**: Use tiktoken-rs (same as OpenAI/Anthropic)
//! - **Boundary preservation**: Never split mid-sentence or mid-record
//! - **Optimal chunk size**: Calculate based on model context window
//! - **Two modes**: Text chunking (sentences) and record chunking (JSON arrays)
//!
//! # Reference
//!
//! Python implementation: `percolate/src/percolate/utils/chunking.py`
//! This Rust version should match the Python behavior exactly.

/// Token-aware chunker
///
/// Splits content into chunks that fit within a model's context window,
/// preserving natural boundaries (sentences for text, records for JSON).
///
/// # Design Notes
///
/// **Why token-based chunking?**
/// - Character-based chunking is inaccurate (1 char ≠ 1 token)
/// - Word-based chunking ignores tokenization (1 word can be multiple tokens)
/// - Token-based chunking ensures chunks actually fit in context window
///
/// **Context window calculation:**
/// ```text
/// usable_tokens = context_window - overhead - response_buffer
///
/// where:
///   context_window = model's max tokens (e.g., 200k for claude-haiku-4-5)
///   overhead = system prompt + schema (typically ~2k tokens)
///   response_buffer = space for LLM response (20% of window)
/// ```
///
/// **Example for claude-haiku-4-5:**
/// ```text
/// context_window = 200,000
/// overhead = 2,000
/// response_buffer = 40,000 (20%)
/// usable_tokens = 200,000 - 2,000 - 40,000 = 158,000 tokens per chunk
/// ```
///
/// # Example
///
/// ```no_run
/// # use percolate_rocks::agents::Chunker;
/// let chunker = Chunker::new("claude-haiku-4-5", Some(50_000));
/// let large_text = "Very long document...".repeat(1000);
/// let chunks = chunker.chunk_text(&large_text);
///
/// println!("Split into {} chunks", chunks.len());
/// for (i, chunk) in chunks.iter().enumerate() {
///     println!("Chunk {}: {} chars", i, chunk.len());
/// }
/// ```
pub struct Chunker {
    /// Model name for token counting
    ///
    /// Different models use different tokenizers:
    /// - claude-*: cl100k_base (Anthropic uses same as OpenAI)
    /// - gpt-*: cl100k_base (GPT-4) or o200k_base (GPT-4.1)
    pub(crate) model: String,

    /// Maximum tokens per chunk
    ///
    /// If None, calculated automatically based on model context window.
    /// Can be overridden for testing (e.g., force small chunks).
    pub(crate) max_tokens: usize,
}

impl Chunker {
    /// Create a new chunker
    ///
    /// # Arguments
    ///
    /// * `model` - Model name (e.g., "claude-haiku-4-5")
    /// * `max_tokens` - Optional max tokens per chunk (None = auto-calculate)
    ///
    /// # Returns
    ///
    /// Configured chunker ready to split content
    ///
    /// # Implementation Notes (Phase 2)
    ///
    /// **Auto-calculate max_tokens if not provided:**
    /// ```text
    /// 1. Get model context window:
    ///    - claude-haiku-4-5: 200k
    ///    - claude-sonnet-4-5: 200k
    ///    - gpt-4.1: 128k
    ///
    /// 2. Calculate usable tokens:
    ///    overhead = 2000  // System prompt + schema
    ///    response_buffer = context_window * 0.2  // 20% for response
    ///    usable = context_window - overhead - response_buffer
    ///
    /// 3. Set max_tokens = usable
    /// ```
    ///
    /// # Example
    ///
    /// ```no_run
    /// # use percolate_rocks::agents::Chunker;
    /// // Auto-calculate based on model
    /// let chunker1 = Chunker::new("claude-haiku-4-5", None);
    ///
    /// // Override for testing (force small chunks)
    /// let chunker2 = Chunker::new("claude-haiku-4-5", Some(1000));
    /// ```
    pub fn new(model: &str, max_tokens: Option<usize>) -> Self {
        // TODO: Implement in Phase 2
        //
        // Steps:
        // 1. If max_tokens is Some, use it directly
        // 2. If max_tokens is None, calculate from model:
        //    a. Get context window size
        //    b. Subtract overhead (2000 tokens)
        //    c. Subtract response buffer (20%)
        //    d. Use result as max_tokens
        // 3. Store model and max_tokens
        todo!("Create chunker")
    }

    /// Chunk text with sentence boundary preservation
    ///
    /// Splits text into chunks under max_tokens, never breaking mid-sentence.
    ///
    /// # Arguments
    ///
    /// * `content` - Text to chunk
    ///
    /// # Returns
    ///
    /// Vector of text chunks, each under max_tokens
    ///
    /// # Algorithm
    ///
    /// ```text
    /// 1. Estimate total tokens in content
    /// 2. If under max_tokens, return single chunk
    /// 3. Split text into sentences (. ! ? with space after)
    /// 4. Group sentences into chunks:
    ///    - Add sentences to current chunk while under max_tokens
    ///    - When adding next sentence would exceed max_tokens, start new chunk
    /// 5. Return chunks
    /// ```
    ///
    /// # Boundary Preservation
    ///
    /// **Never split mid-sentence:**
    /// ```text
    /// Good:
    ///   Chunk 1: "The cat sat on the mat. The dog ran away."
    ///   Chunk 2: "The bird flew high. The fish swam deep."
    ///
    /// Bad:
    ///   Chunk 1: "The cat sat on the mat. The dog ran aw"
    ///   Chunk 2: "ay. The bird flew high. The fish swam deep."
    /// ```
    ///
    /// # Implementation Notes (Phase 2)
    ///
    /// **Sentence detection (simple approach):**
    /// ```rust
    /// let sentences: Vec<&str> = content
    ///     .split_inclusive(&['.', '!', '?'])
    ///     .filter(|s| !s.trim().is_empty())
    ///     .collect();
    /// ```
    ///
    /// **Token estimation per sentence:**
    /// ```rust
    /// use tiktoken_rs::tokenize;
    ///
    /// for sentence in sentences {
    ///     let tokens = tokenize(&self.model, sentence);
    ///     if current_chunk_tokens + tokens.len() > self.max_tokens {
    ///         // Start new chunk
    ///     } else {
    ///         // Add to current chunk
    ///     }
    /// }
    /// ```
    ///
    /// # Example
    ///
    /// ```no_run
    /// # use percolate_rocks::agents::Chunker;
    /// let chunker = Chunker::new("claude-haiku-4-5", Some(100));
    /// let text = "First sentence. Second sentence. Third sentence. Fourth sentence.";
    /// let chunks = chunker.chunk_text(text);
    ///
    /// // With max_tokens=100, might get 2 chunks:
    /// // chunks[0] = "First sentence. Second sentence."
    /// // chunks[1] = "Third sentence. Fourth sentence."
    /// ```
    pub fn chunk_text(&self, content: &str) -> Vec<String> {
        // TODO: Implement in Phase 2
        //
        // Steps:
        // 1. Estimate total tokens
        // 2. If under max_tokens, return vec![content.to_string()]
        // 3. Split into sentences
        // 4. Group sentences into chunks:
        //    let mut chunks = Vec::new();
        //    let mut current_chunk = String::new();
        //    let mut current_tokens = 0;
        //
        //    for sentence in sentences {
        //        let sentence_tokens = estimate_tokens(sentence);
        //        if current_tokens + sentence_tokens > self.max_tokens {
        //            chunks.push(current_chunk);
        //            current_chunk = sentence.to_string();
        //            current_tokens = sentence_tokens;
        //        } else {
        //            current_chunk.push_str(sentence);
        //            current_tokens += sentence_tokens;
        //        }
        //    }
        //    if !current_chunk.is_empty() {
        //        chunks.push(current_chunk);
        //    }
        // 5. Return chunks
        todo!("Chunk text by tokens with sentence boundaries")
    }

    /// Chunk JSON records preserving record boundaries
    ///
    /// Splits array of JSON objects into chunks, never breaking mid-record.
    ///
    /// # Arguments
    ///
    /// * `records` - Array of JSON objects to chunk
    ///
    /// # Returns
    ///
    /// Vector of record chunks, each under max_tokens
    ///
    /// # Algorithm
    ///
    /// ```text
    /// 1. Sample first 10 records to estimate avg tokens per record
    /// 2. Calculate records_per_chunk = max_tokens / avg_tokens_per_record
    /// 3. Split records into chunks of size records_per_chunk
    /// 4. Return chunks
    /// ```
    ///
    /// # Boundary Preservation
    ///
    /// **Never split mid-record:**
    /// ```text
    /// Good:
    ///   Chunk 1: [{"id": 1}, {"id": 2}]
    ///   Chunk 2: [{"id": 3}, {"id": 4}]
    ///
    /// Bad:
    ///   Chunk 1: [{"id": 1}, {"id": 2}, {"id":]
    ///   Chunk 2: [3}, {"id": 4}]
    /// ```
    ///
    /// # Implementation Notes (Phase 2)
    ///
    /// **Estimate tokens per record:**
    /// ```rust
    /// // Sample first 10 records
    /// let sample_size = records.len().min(10);
    /// let mut total_tokens = 0;
    ///
    /// for record in &records[..sample_size] {
    ///     let json_str = serde_json::to_string(record)?;
    ///     total_tokens += estimate_tokens(&json_str);
    /// }
    ///
    /// let avg_tokens_per_record = total_tokens / sample_size;
    /// let records_per_chunk = self.max_tokens / avg_tokens_per_record;
    /// ```
    ///
    /// **Chunk records:**
    /// ```rust
    /// let chunks: Vec<Vec<serde_json::Value>> = records
    ///     .chunks(records_per_chunk)
    ///     .map(|chunk| chunk.to_vec())
    ///     .collect();
    /// ```
    ///
    /// # Example
    ///
    /// ```no_run
    /// # use percolate_rocks::agents::Chunker;
    /// # use serde_json::json;
    /// let chunker = Chunker::new("claude-haiku-4-5", Some(1000));
    /// let records = vec![
    ///     json!({"id": 1, "name": "Alice"}),
    ///     json!({"id": 2, "name": "Bob"}),
    ///     json!({"id": 3, "name": "Charlie"}),
    /// ];
    /// let chunks = chunker.chunk_records(&records);
    ///
    /// // Might get 2 chunks depending on token size:
    /// // chunks[0] = [{"id": 1, ...}, {"id": 2, ...}]
    /// // chunks[1] = [{"id": 3, ...}]
    /// ```
    pub fn chunk_records(&self, records: &[serde_json::Value]) -> Vec<Vec<serde_json::Value>> {
        // TODO: Implement in Phase 2
        //
        // Steps:
        // 1. If records is empty, return empty vec
        // 2. Sample first 10 records (or fewer if less than 10)
        // 3. Estimate avg tokens per record:
        //    let mut total_tokens = 0;
        //    for record in sample {
        //        let json_str = serde_json::to_string(record)?;
        //        total_tokens += estimate_tokens(&json_str);
        //    }
        //    let avg = total_tokens / sample.len();
        // 4. Calculate records per chunk:
        //    let records_per_chunk = (self.max_tokens / avg).max(1);
        // 5. Split records into chunks:
        //    records.chunks(records_per_chunk)
        //        .map(|chunk| chunk.to_vec())
        //        .collect()
        todo!("Chunk records preserving boundaries")
    }

    /// Estimate token count for content
    ///
    /// Uses tiktoken-rs for accurate counting. Falls back to char count / 4
    /// if tiktoken fails.
    ///
    /// # Arguments
    ///
    /// * `content` - Text to estimate tokens for
    ///
    /// # Returns
    ///
    /// Estimated number of tokens
    ///
    /// # Implementation Notes (Phase 2)
    ///
    /// **Token counting with tiktoken-rs:**
    /// ```rust
    /// use tiktoken_rs::{get_bpe_from_model, tokenize};
    ///
    /// // Get tokenizer for model
    /// let bpe = get_bpe_from_model(&self.model)?;
    ///
    /// // Tokenize content
    /// let tokens = bpe.encode_with_special_tokens(content);
    ///
    /// // Return token count
    /// tokens.len()
    /// ```
    ///
    /// **Fallback if tiktoken unavailable:**
    /// ```rust
    /// // Rough estimate: 1 token ≈ 4 characters
    /// (content.chars().count() / 4).max(1)
    /// ```
    ///
    /// # Accuracy
    ///
    /// **tiktoken-rs is highly accurate** (same tokenizer as OpenAI/Anthropic):
    /// ```text
    /// "Hello world" = 2 tokens
    /// "The quick brown fox" = 4 tokens
    /// "anthropic" = 1 token
    /// "tokenization" = 3 tokens
    /// ```
    ///
    /// **Fallback is approximate** but safe (overestimates):
    /// ```text
    /// "Hello world" (11 chars) → 11/4 = 2 tokens ✓
    /// "The quick brown fox" (19 chars) → 19/4 = 4 tokens ✓
    /// "anthropic" (9 chars) → 9/4 = 2 tokens (actual: 1) ✗
    /// ```
    ///
    /// # Example
    ///
    /// ```no_run
    /// # use percolate_rocks::agents::Chunker;
    /// let chunker = Chunker::new("claude-haiku-4-5", None);
    ///
    /// let short_text = "Hello world";
    /// let tokens = chunker.estimate_tokens(short_text);
    /// assert_eq!(tokens, 2);  // With tiktoken
    ///
    /// let long_text = "word ".repeat(1000);
    /// let tokens = chunker.estimate_tokens(&long_text);
    /// assert!(tokens > 900 && tokens < 1100);  // ~1000 tokens
    /// ```
    pub fn estimate_tokens(&self, content: &str) -> usize {
        // TODO: Implement in Phase 2
        //
        // Steps:
        // 1. Try tiktoken-rs:
        //    use tiktoken_rs::get_bpe_from_model;
        //    if let Ok(bpe) = get_bpe_from_model(&self.model) {
        //        let tokens = bpe.encode_with_special_tokens(content);
        //        return tokens.len();
        //    }
        // 2. Fallback to char count / 4:
        //    (content.chars().count() / 4).max(1)
        todo!("Estimate tokens using tiktoken-rs")
    }

    /// Get model context window size in tokens
    ///
    /// Returns the maximum context window for the model.
    ///
    /// # Returns
    ///
    /// Context window size in tokens
    ///
    /// # Context Windows (2025)
    ///
    /// | Model | Context Window |
    /// |-------|---------------|
    /// | claude-haiku-4-5 | 200,000 |
    /// | claude-sonnet-4-5 | 200,000 |
    /// | claude-opus-4 | 200,000 |
    /// | gpt-4.1 | 128,000 |
    /// | gpt-4.1-turbo | 128,000 |
    ///
    /// # Example
    ///
    /// ```no_run
    /// # use percolate_rocks::agents::Chunker;
    /// let chunker = Chunker::new("claude-haiku-4-5", None);
    /// let window = chunker.get_context_window();
    /// assert_eq!(window, 200_000);
    /// ```
    fn get_context_window(&self) -> usize {
        match self.model.as_str() {
            // Anthropic Claude models
            "claude-haiku-4-5" | "claude-sonnet-4-5" | "claude-opus-4" => 200_000,

            // OpenAI GPT models
            "gpt-4.1" | "gpt-4.1-turbo" => 128_000,

            // Unknown model - conservative default
            _ => {
                tracing::warn!(
                    model = %self.model,
                    "Unknown model context window - using 100k default"
                );
                100_000
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_get_context_window() {
        let chunker = Chunker {
            model: "claude-haiku-4-5".to_string(),
            max_tokens: 50_000,
        };
        assert_eq!(chunker.get_context_window(), 200_000);

        let chunker = Chunker {
            model: "gpt-4.1".to_string(),
            max_tokens: 50_000,
        };
        assert_eq!(chunker.get_context_window(), 128_000);

        let chunker = Chunker {
            model: "unknown-model".to_string(),
            max_tokens: 50_000,
        };
        assert_eq!(chunker.get_context_window(), 100_000);
    }

    // TODO: Add more tests in Phase 2
    // - test_chunk_text_single_chunk
    // - test_chunk_text_multiple_chunks
    // - test_chunk_text_preserves_sentences
    // - test_chunk_records_single_chunk
    // - test_chunk_records_multiple_chunks
    // - test_estimate_tokens_fallback
}
