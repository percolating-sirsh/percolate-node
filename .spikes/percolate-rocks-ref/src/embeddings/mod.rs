//! Embedding generation with multiple providers.
//!
//! Supports:
//! - Local embeddings via embed_anything (all-MiniLM-L6-v2, 384 dims)
//! - OpenAI embeddings (text-embedding-ada-002, text-embedding-3-small/large)
//!
//! Configuration via environment variables:
//! - P8_DEFAULT_EMBEDDING: Model name (e.g., "text-embedding-3-small")
//! - OPENAI_API_KEY: OpenAI API key (required for OpenAI models)
//!
//! If P8_DEFAULT_EMBEDDING is not set, defaults to local model (requires download).

mod openai;

use crate::types::{DatabaseError, Result};
use embed_anything::embed_query;
use embed_anything::embeddings::embed::{Embedder, TextEmbedder};
use embed_anything::embeddings::local::bert::BertEmbedder;
use openai::OpenAIEmbeddings;
use std::path::PathBuf;
use std::sync::Arc;

/// Embedding backend (local or OpenAI).
enum EmbeddingBackend {
    Local {
        embedder: Arc<Embedder>,
        dimensions: usize,
    },
    OpenAI(OpenAIEmbeddings),
}

/// Embedding provider for generating vector embeddings.
///
/// Automatically selects provider based on P8_DEFAULT_EMBEDDING env var:
/// - If P8_DEFAULT_EMBEDDING starts with "text-embedding-" → OpenAI
/// - Otherwise → Local embed_anything model
pub struct EmbeddingProvider {
    backend: EmbeddingBackend,
    model_name: String,
}

impl EmbeddingProvider {
    /// Get model cache directory (~/.p8/models/).
    fn model_cache_dir() -> Result<PathBuf> {
        let home = std::env::var("HOME")
            .map_err(|_| DatabaseError::EmbeddingError("HOME not set".to_string()))?;
        let cache_dir = PathBuf::from(home).join(".p8").join("models");

        // Create cache directory if it doesn't exist
        std::fs::create_dir_all(&cache_dir)
            .map_err(|e| DatabaseError::EmbeddingError(format!("Failed to create cache dir: {}", e)))?;

        Ok(cache_dir)
    }

    /// Create new embedding provider using environment variables.
    ///
    /// Reads P8_DEFAULT_EMBEDDING to determine provider:
    /// - "text-embedding-3-small" → OpenAI (requires OPENAI_API_KEY)
    /// - "text-embedding-ada-002" → OpenAI (requires OPENAI_API_KEY)
    /// - Not set → Local all-MiniLM-L6-v2 (downloads model to ~/.p8/models/)
    pub fn new() -> Result<Self> {
        let model_name = std::env::var("P8_DEFAULT_EMBEDDING")
            .unwrap_or_else(|_| "sentence-transformers/all-MiniLM-L6-v2".to_string());

        Self::with_model(&model_name)
    }

    /// Create embedding provider with specific model.
    pub fn with_model(model_name: &str) -> Result<Self> {
        // Detect provider based on model name
        if model_name.starts_with("text-embedding-") {
            // OpenAI model
            let api_key = std::env::var("OPENAI_API_KEY").map_err(|_| {
                DatabaseError::EmbeddingError(
                    "OPENAI_API_KEY environment variable required for OpenAI models".to_string(),
                )
            })?;

            let backend = EmbeddingBackend::OpenAI(OpenAIEmbeddings::new(
                api_key,
                model_name.to_string(),
            )?);

            Ok(Self {
                backend,
                model_name: model_name.to_string(),
            })
        } else {
            // Local model via embed_anything
            Self::with_local_model(model_name)
        }
    }

    /// Create local embedding provider.
    fn with_local_model(model_name: &str) -> Result<Self> {
        // Default dimensions for known models
        let dimensions = if model_name.contains("all-MiniLM-L6-v2") {
            384
        } else {
            384 // Default assumption
        };

        // Set HF_HOME if not already set to use ~/.p8/models
        if std::env::var("HF_HOME").is_err() {
            if let Ok(cache_dir) = Self::model_cache_dir() {
                std::env::set_var("HF_HOME", cache_dir);
            }
        }

        // Initialize BERT model with embed_anything
        let bert_embedder = BertEmbedder::new(
            model_name.to_string(),
            None,  // Use default revision
            None   // Use model_name as model_id
        ).map_err(|e| DatabaseError::EmbeddingError(format!("Failed to load model: {}", e)))?;

        let embedder = Embedder::Text(TextEmbedder::Bert(Box::new(bert_embedder)));

        Ok(Self {
            backend: EmbeddingBackend::Local {
                embedder: Arc::new(embedder),
                dimensions,
            },
            model_name: model_name.to_string(),
        })
    }

    /// Get embedding dimensions.
    pub fn dimensions(&self) -> usize {
        match &self.backend {
            EmbeddingBackend::Local { dimensions, .. } => *dimensions,
            EmbeddingBackend::OpenAI(oai) => oai.dimensions(),
        }
    }

    /// Generate embeddings for multiple texts (batch API).
    ///
    /// This is the preferred method for efficiency.
    pub async fn embed_batch(&self, texts: Vec<String>) -> Result<Vec<Vec<f32>>> {
        match &self.backend {
            EmbeddingBackend::Local { embedder, .. } => {
                // embed_anything processes all texts at once
                let text_refs: Vec<&str> = texts.iter().map(|s| s.as_str()).collect();
                let embeddings = embed_query(&text_refs, embedder, None)
                    .await
                    .map_err(|e| DatabaseError::EmbeddingError(format!("Embedding failed: {}", e)))?;

                embeddings
                    .into_iter()
                    .map(|emb| {
                        emb.embedding
                            .to_dense()
                            .map_err(|e| DatabaseError::EmbeddingError(format!("Dense conversion failed: {}", e)))
                    })
                    .collect()
            }
            EmbeddingBackend::OpenAI(oai) => oai.embed_batch(&texts).await,
        }
    }

    /// Generate embedding for a single text.
    ///
    /// Note: For multiple texts, use embed_batch() for better performance.
    pub async fn embed(&self, text: &str) -> Result<Vec<f32>> {
        let embeddings = self.embed_batch(vec![text.to_string()]).await?;
        embeddings
            .into_iter()
            .next()
            .ok_or_else(|| DatabaseError::EmbeddingError("No embedding generated".to_string()))
    }

    /// Get model name.
    pub fn model_name(&self) -> &str {
        &self.model_name
    }
}

/// Calculate cosine similarity between two vectors.
pub fn cosine_similarity(a: &[f32], b: &[f32]) -> f32 {
    if a.len() != b.len() {
        return 0.0;
    }

    let dot: f32 = a.iter().zip(b.iter()).map(|(x, y)| x * y).sum();
    let mag_a: f32 = a.iter().map(|x| x * x).sum::<f32>().sqrt();
    let mag_b: f32 = b.iter().map(|x| x * x).sum::<f32>().sqrt();

    if mag_a == 0.0 || mag_b == 0.0 {
        return 0.0;
    }

    dot / (mag_a * mag_b)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_cosine_similarity() {
        let a = vec![1.0, 2.0, 3.0];
        let b = vec![4.0, 5.0, 6.0];
        let c = vec![-1.0, -2.0, -3.0];

        let sim_ab = cosine_similarity(&a, &b);
        let sim_ac = cosine_similarity(&a, &c);

        assert!(sim_ab > 0.9); // Similar direction
        assert!(sim_ac < -0.9); // Opposite direction

        println!("Similarity(a, b): {}", sim_ab);
        println!("Similarity(a, c): {}", sim_ac);
    }

    #[tokio::test]
    #[ignore] // Requires OPENAI_API_KEY
    async fn test_openai_provider() {
        std::env::set_var("P8_DEFAULT_EMBEDDING", "text-embedding-3-small");

        let provider = EmbeddingProvider::new().expect("Failed to create provider");
        assert_eq!(provider.dimensions(), 1536);
        assert_eq!(provider.model_name(), "text-embedding-3-small");

        let embedding = provider.embed("Hello, world!").await.expect("Failed to embed");
        assert_eq!(embedding.len(), 1536);

        println!("✓ OpenAI provider works");
    }

    #[tokio::test]
    #[ignore] // Requires OPENAI_API_KEY
    async fn test_openai_batch() {
        std::env::set_var("P8_DEFAULT_EMBEDDING", "text-embedding-3-small");

        let provider = EmbeddingProvider::new().expect("Failed to create provider");

        let texts = vec![
            "Rust is fast".to_string(),
            "Python is easy".to_string(),
            "Go is simple".to_string(),
        ];

        let embeddings = provider.embed_batch(texts).await.expect("Failed to batch embed");

        assert_eq!(embeddings.len(), 3);
        for emb in &embeddings {
            assert_eq!(emb.len(), 1536);
        }

        println!("✓ OpenAI batch embeddings work");
    }
}
