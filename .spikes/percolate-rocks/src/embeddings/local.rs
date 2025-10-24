//! Local embedding models using fastembed.

use crate::types::Result;
use crate::embeddings::provider::EmbeddingProvider;
use async_trait::async_trait;

/// Local embedding model provider.
pub struct LocalEmbedder {
    model_name: String,
    dimensions: usize,
}

impl LocalEmbedder {
    /// Create new local embedder.
    ///
    /// # Arguments
    ///
    /// * `model_name` - Model name (e.g., "all-MiniLM-L6-v2")
    ///
    /// # Returns
    ///
    /// New `LocalEmbedder`
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::EmbeddingError` if model loading fails
    pub fn new(model_name: &str) -> Result<Self> {
        todo!("Implement LocalEmbedder::new")
    }
}

#[async_trait]
impl EmbeddingProvider for LocalEmbedder {
    async fn embed(&self, text: &str) -> Result<Vec<f32>> {
        todo!("Implement LocalEmbedder::embed")
    }

    async fn embed_batch(&self, texts: &[String]) -> Result<Vec<Vec<f32>>> {
        todo!("Implement LocalEmbedder::embed_batch")
    }

    fn dimensions(&self) -> usize {
        self.dimensions
    }
}
