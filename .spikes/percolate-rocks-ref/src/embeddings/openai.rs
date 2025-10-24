//! OpenAI embedding provider with batch support.

use crate::types::{DatabaseError, Result};
use reqwest::Client;
use serde::{Deserialize, Serialize};

/// OpenAI API base URL
const OPENAI_API_BASE: &str = "https://api.openai.com/v1";

/// OpenAI embedding request
#[derive(Debug, Serialize)]
struct EmbeddingRequest {
    input: Vec<String>,
    model: String,
}

/// OpenAI embedding response
#[derive(Debug, Deserialize)]
struct EmbeddingResponse {
    data: Vec<EmbeddingData>,
}

#[derive(Debug, Deserialize)]
struct EmbeddingData {
    embedding: Vec<f32>,
    index: usize,
}

/// OpenAI embedding provider with batch support.
pub struct OpenAIEmbeddings {
    client: Client,
    api_key: String,
    model: String,
    dimensions: usize,
}

impl OpenAIEmbeddings {
    /// Create new OpenAI embedding provider.
    ///
    /// # Arguments
    /// * `api_key` - OpenAI API key (from OPENAI_API_KEY env var)
    /// * `model` - Model name (e.g., "text-embedding-ada-002", "text-embedding-3-small")
    ///
    /// # Dimensions
    /// - text-embedding-ada-002: 1536
    /// - text-embedding-3-small: 1536
    /// - text-embedding-3-large: 3072
    pub fn new(api_key: String, model: String) -> Result<Self> {
        let dimensions = match model.as_str() {
            "text-embedding-ada-002" => 1536,
            "text-embedding-3-small" => 1536,
            "text-embedding-3-large" => 3072,
            _ => {
                return Err(DatabaseError::EmbeddingError(format!(
                    "Unknown OpenAI model: {}. Supported: text-embedding-ada-002, text-embedding-3-small, text-embedding-3-large",
                    model
                )))
            }
        };

        Ok(Self {
            client: Client::new(),
            api_key,
            model,
            dimensions,
        })
    }

    /// Get embedding dimensions for this model.
    pub fn dimensions(&self) -> usize {
        self.dimensions
    }

    /// Generate embeddings for multiple texts (batch API).
    ///
    /// OpenAI supports up to 2048 inputs per request.
    /// This automatically batches larger requests.
    pub async fn embed_batch(&self, texts: &[String]) -> Result<Vec<Vec<f32>>> {
        if texts.is_empty() {
            return Ok(vec![]);
        }

        // OpenAI limit: 2048 texts per request
        const BATCH_SIZE: usize = 2048;

        let mut all_embeddings = Vec::with_capacity(texts.len());

        for chunk in texts.chunks(BATCH_SIZE) {
            let embeddings = self.embed_chunk(chunk).await?;
            all_embeddings.extend(embeddings);
        }

        Ok(all_embeddings)
    }

    /// Embed a single chunk (up to 2048 texts).
    async fn embed_chunk(&self, texts: &[String]) -> Result<Vec<Vec<f32>>> {
        let request = EmbeddingRequest {
            input: texts.to_vec(),
            model: self.model.clone(),
        };

        let response = self
            .client
            .post(format!("{}/embeddings", OPENAI_API_BASE))
            .header("Authorization", format!("Bearer {}", self.api_key))
            .header("Content-Type", "application/json")
            .json(&request)
            .send()
            .await
            .map_err(|e| DatabaseError::EmbeddingError(format!("OpenAI request failed: {}", e)))?;

        if !response.status().is_success() {
            let status = response.status();
            let error_text = response
                .text()
                .await
                .unwrap_or_else(|_| "Unknown error".to_string());
            return Err(DatabaseError::EmbeddingError(format!(
                "OpenAI API error {}: {}",
                status, error_text
            )));
        }

        let embedding_response: EmbeddingResponse = response
            .json()
            .await
            .map_err(|e| DatabaseError::EmbeddingError(format!("Failed to parse response: {}", e)))?;

        // Sort by index to maintain order
        let mut data = embedding_response.data;
        data.sort_by_key(|d| d.index);

        Ok(data.into_iter().map(|d| d.embedding).collect())
    }

    /// Generate embedding for a single text (convenience method).
    pub async fn embed(&self, text: &str) -> Result<Vec<f32>> {
        let embeddings = self.embed_batch(&[text.to_string()]).await?;
        embeddings
            .into_iter()
            .next()
            .ok_or_else(|| DatabaseError::EmbeddingError("No embedding returned".to_string()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    #[ignore] // Requires OPENAI_API_KEY
    async fn test_openai_embed_single() {
        let api_key = std::env::var("OPENAI_API_KEY").expect("OPENAI_API_KEY not set");
        let embedder = OpenAIEmbeddings::new(api_key, "text-embedding-3-small".to_string())
            .expect("Failed to create embedder");

        let embedding = embedder.embed("Hello, world!").await.expect("Failed to embed");

        assert_eq!(embedding.len(), 1536);
        println!("✓ Single embedding: {} dimensions", embedding.len());
    }

    #[tokio::test]
    #[ignore] // Requires OPENAI_API_KEY
    async fn test_openai_embed_batch() {
        let api_key = std::env::var("OPENAI_API_KEY").expect("OPENAI_API_KEY not set");
        let embedder = OpenAIEmbeddings::new(api_key, "text-embedding-3-small".to_string())
            .expect("Failed to create embedder");

        let texts = vec![
            "Rust is a systems programming language".to_string(),
            "Python is great for data science".to_string(),
            "JavaScript runs in the browser".to_string(),
        ];

        let embeddings = embedder
            .embed_batch(&texts)
            .await
            .expect("Failed to embed batch");

        assert_eq!(embeddings.len(), 3);
        for (i, emb) in embeddings.iter().enumerate() {
            assert_eq!(emb.len(), 1536);
            println!("✓ Embedding {}: {} dimensions", i + 1, emb.len());
        }
    }
}
