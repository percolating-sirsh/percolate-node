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
    /// * `config` - Provider config (e.g., "local:all-MiniLM-L6-v2", "openai:text-embedding-3-small")
    ///
    /// # Returns
    ///
    /// Box of embedding provider
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::ConfigError` if config is invalid
    pub fn create(config: &str) -> Result<Box<dyn EmbeddingProvider>> {
        todo!("Implement ProviderFactory::create")
    }
}
