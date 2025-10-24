//! OpenAI embedding API client.

use crate::types::Result;
use crate::embeddings::provider::EmbeddingProvider;
use async_trait::async_trait;

/// OpenAI embedding provider.
pub struct OpenAIEmbedder {
    api_key: String,
    model: String,
    dimensions: usize,
}

impl OpenAIEmbedder {
    /// Create new OpenAI embedder.
    ///
    /// # Arguments
    ///
    /// * `api_key` - OpenAI API key
    /// * `model` - Model name (e.g., "text-embedding-3-small")
    ///
    /// # Returns
    ///
    /// New `OpenAIEmbedder`
    pub fn new(api_key: String, model: String) -> Self {
        todo!("Implement OpenAIEmbedder::new")
    }
}

#[async_trait]
impl EmbeddingProvider for OpenAIEmbedder {
    async fn embed(&self, text: &str) -> Result<Vec<f32>> {
        todo!("Implement OpenAIEmbedder::embed")
    }

    async fn embed_batch(&self, texts: &[String]) -> Result<Vec<Vec<f32>>> {
        todo!("Implement OpenAIEmbedder::embed_batch")
    }

    fn dimensions(&self) -> usize {
        self.dimensions
    }
}
