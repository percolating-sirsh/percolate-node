//! Local embedding models using embed-anything.

use crate::types::{Result, DatabaseError};
use crate::embeddings::provider::EmbeddingProvider;
use async_trait::async_trait;
use embed_anything::embeddings::embed::{Embedder, EmbedderBuilder};
use std::sync::Arc;

/// Local embedding model provider using embed-anything.
pub struct LocalEmbedder {
    embedder: Arc<Embedder>,
    model_name: String,
    dimensions: usize,
}

impl LocalEmbedder {
    /// Create new local embedder with default model (all-MiniLM-L6-v2).
    ///
    /// # Returns
    ///
    /// New `LocalEmbedder` with 384-dimensional embeddings
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::EmbeddingError` if model loading fails
    pub fn new_default() -> Result<Self> {
        Self::new("sentence-transformers/all-MiniLM-L6-v2")
    }

    /// Create new local embedder with specified Hugging Face model.
    ///
    /// # Arguments
    ///
    /// * `model_id` - HuggingFace model ID (e.g., "sentence-transformers/all-MiniLM-L6-v2")
    ///
    /// # Returns
    ///
    /// New `LocalEmbedder`
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::EmbeddingError` if model loading fails
    ///
    /// # Supported Models
    ///
    /// - `sentence-transformers/all-MiniLM-L6-v2` (384 dims) - Default, fast
    /// - `BAAI/bge-small-en-v1.5` (384 dims) - Better quality
    /// - `BAAI/bge-base-en-v1.5` (768 dims) - Best quality, slower
    /// - `jinaai/jina-embeddings-v2-small-en` (512 dims) - Good balance
    pub fn new(model_id: &str) -> Result<Self> {
        // Determine dimensions and architecture based on model
        let (dimensions, architecture) = match model_id {
            "sentence-transformers/all-MiniLM-L6-v2" => (384, "bert"),
            "BAAI/bge-small-en-v1.5" => (384, "bert"),
            "BAAI/bge-base-en-v1.5" => (768, "bert"),
            "jinaai/jina-embeddings-v2-small-en" => (512, "jina"),
            "jinaai/jina-embeddings-v2-base-en" => (768, "jina"),
            _ => {
                // Try to infer from model name
                if model_id.contains("jina") {
                    (512, "jina")
                } else {
                    (384, "bert") // Default
                }
            }
        };

        // Build embedder
        let embedder = EmbedderBuilder::new()
            .model_architecture(architecture)
            .model_id(Some(model_id))
            .revision(None)
            .token(None)
            .from_pretrained_hf()
            .map_err(|e| DatabaseError::EmbeddingError(
                format!("Failed to load model {}: {:?}", model_id, e)
            ))?;

        Ok(Self {
            embedder: Arc::new(embedder),
            model_name: model_id.to_string(),
            dimensions,
        })
    }
}

#[async_trait]
impl EmbeddingProvider for LocalEmbedder {
    async fn embed(&self, text: &str) -> Result<Vec<f32>> {
        // embed-anything doesn't have a direct single-text method
        // Use embed_query which takes a vector
        let texts = vec![text.to_string()];
        let embedder = self.embedder.clone();

        // embed_query returns a Future, so we need to await it
        let results = embed_anything::embed_query(texts, &embedder, None)
            .await
            .map_err(|e| DatabaseError::EmbeddingError(format!("Embedding failed: {:?}", e)))?;

        // Extract first result
        results.into_iter().next()
            .ok_or_else(|| DatabaseError::EmbeddingError("No embedding returned".to_string()))
    }

    async fn embed_batch(&self, texts: &[String]) -> Result<Vec<Vec<f32>>> {
        let texts = texts.to_vec();
        let embedder = self.embedder.clone();

        // embed_query returns a Future, so we need to await it
        embed_anything::embed_query(texts, &embedder, None)
            .await
            .map_err(|e| DatabaseError::EmbeddingError(format!("Batch embedding failed: {:?}", e)))
    }

    fn dimensions(&self) -> usize {
        self.dimensions
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_local_embedder_single() {
        let embedder = LocalEmbedder::new_default().unwrap();
        let result = embedder.embed("Hello world").await.unwrap();

        assert_eq!(result.len(), 384); // all-MiniLM-L6-v2 is 384-dimensional
        assert_eq!(embedder.dimensions(), 384);
    }

    #[tokio::test]
    async fn test_local_embedder_batch() {
        let embedder = LocalEmbedder::new_default().unwrap();
        let texts = vec!["Hello".to_string(), "World".to_string()];
        let results = embedder.embed_batch(&texts).await.unwrap();

        assert_eq!(results.len(), 2);
        assert_eq!(results[0].len(), 384);
        assert_eq!(results[1].len(), 384);
    }
}
