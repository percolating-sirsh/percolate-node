//! Embedding provider trait and factory.

use crate::types::Result;
use async_trait::async_trait;

/// Embedding provider trait.
#[async_trait]
pub trait EmbeddingProvider: Send + Sync {
    /// Generate embedding for single text.
    ///
    /// # Arguments
    ///
    /// * `text` - Input text
    ///
    /// # Returns
    ///
    /// Embedding vector
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::EmbeddingError` if generation fails
    async fn embed(&self, text: &str) -> Result<Vec<f32>>;

    /// Generate embeddings for batch of texts.
    ///
    /// # Arguments
    ///
    /// * `texts` - Input texts
    ///
    /// # Returns
    ///
    /// Embedding vectors
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::EmbeddingError` if generation fails
    async fn embed_batch(&self, texts: &[String]) -> Result<Vec<Vec<f32>>>;

    /// Get embedding dimensionality.
    ///
    /// # Returns
    ///
    /// Vector dimension
    fn dimensions(&self) -> usize;
}

/// Factory for creating embedding providers.
pub struct ProviderFactory;

impl ProviderFactory {
    /// Create provider from config string.
    ///
    /// # Arguments
    ///
    /// * `config` - Provider config:
    ///   - "local" or "local:all-MiniLM-L6-v2" - Default local model
    ///   - "local:model-name" - Specific local model
    ///   - "openai:text-embedding-3-small" - OpenAI model (requires API key in env)
    ///
    /// # Returns
    ///
    /// Box of embedding provider
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::ConfigError` if config is invalid
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// // Default local model
    /// let provider = ProviderFactory::create("local")?;
    ///
    /// // Specific local model
    /// let provider = ProviderFactory::create("local:bge-small-en-v1.5")?;
    ///
    /// // OpenAI (requires P8_OPENAI_API_KEY env var)
    /// let provider = ProviderFactory::create("openai:text-embedding-3-small")?;
    /// ```
    pub fn create(config: &str) -> Result<Box<dyn EmbeddingProvider>> {
        use crate::embeddings::local::LocalEmbedder;
        use crate::embeddings::openai::OpenAIEmbedder;
        use crate::types::DatabaseError;

        let parts: Vec<&str> = config.split(':').collect();

        match parts[0] {
            "local" => {
                let model = if parts.len() > 1 {
                    parts[1]
                } else {
                    // NOTE: Consider upgrading default to "jina-embeddings-v4" for 2025 (see docs/2025-review.md)
                    // Benefits:
                    // - +10-15% accuracy improvement over all-MiniLM-L6-v2 (MTEB benchmarks)
                    // - Matryoshka embeddings: flexible dimensions (64-1024) from single model
                    // - Multi-vector mode support (ColBERT-style late interaction)
                    // - Multilingual: 100+ languages vs English-only
                    // - Vision mode: ColPali-style document retrieval
                    // - Apache 2.0 license
                    // References:
                    // - https://jina.ai/news/jina-embeddings-v4
                    // - https://arxiv.org/abs/2506.18902
                    // - MTEB leaderboard: https://huggingface.co/spaces/mteb/leaderboard
                    "all-MiniLM-L6-v2" // Default (proven, lightweight, 384 dims)
                };

                let embedder = LocalEmbedder::new(model)?;
                Ok(Box::new(embedder))
            }
            "openai" => {
                if parts.len() < 2 {
                    return Err(DatabaseError::ConfigError(
                        "OpenAI config requires model name: 'openai:text-embedding-3-small'".to_string()
                    ));
                }

                let api_key = std::env::var("P8_OPENAI_API_KEY")
                    .map_err(|_| DatabaseError::ConfigError(
                        "P8_OPENAI_API_KEY environment variable not set".to_string()
                    ))?;

                let model = parts[1].to_string();
                let embedder = OpenAIEmbedder::new(api_key, model);
                Ok(Box::new(embedder))
            }
            _ => Err(DatabaseError::ConfigError(
                format!("Unknown provider: '{}'. Use 'local' or 'openai'", parts[0])
            ))
        }
    }
}
