//! OpenAI embedding API client.

use crate::types::{Result, DatabaseError};
use crate::embeddings::provider::EmbeddingProvider;
use async_trait::async_trait;
use reqwest::Client;
use serde::{Deserialize, Serialize};

/// OpenAI API embedding request.
#[derive(Debug, Serialize)]
struct EmbeddingRequest {
    model: String,
    input: serde_json::Value,  // String or Vec<String>
}

/// OpenAI API embedding response.
#[derive(Debug, Deserialize)]
struct EmbeddingResponse {
    data: Vec<EmbeddingData>,
}

#[derive(Debug, Deserialize)]
struct EmbeddingData {
    embedding: Vec<f32>,
}

/// OpenAI embedding provider.
pub struct OpenAIEmbedder {
    api_key: String,
    model: String,
    dimensions: usize,
    client: Client,
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
        // Determine dimensions based on model
        let dimensions = match model.as_str() {
            "text-embedding-3-small" => 1536,
            "text-embedding-3-large" => 3072,
            "text-embedding-ada-002" => 1536,
            _ => 1536,  // Default to 1536
        };

        Self {
            api_key,
            model,
            dimensions,
            client: Client::new(),
        }
    }

    /// Call OpenAI embeddings API.
    async fn call_api(&self, input: serde_json::Value) -> Result<Vec<Vec<f32>>> {
        let request = EmbeddingRequest {
            model: self.model.clone(),
            input,
        };

        let response = self.client
            .post("https://api.openai.com/v1/embeddings")
            .header("Authorization", format!("Bearer {}", self.api_key))
            .header("Content-Type", "application/json")
            .json(&request)
            .send()
            .await
            .map_err(|e| DatabaseError::EmbeddingError(format!("OpenAI API request failed: {}", e)))?;

        if !response.status().is_success() {
            let status = response.status();
            let error_text = response.text().await.unwrap_or_else(|_| "Unknown error".to_string());
            return Err(DatabaseError::EmbeddingError(format!(
                "OpenAI API error ({}): {}",
                status,
                error_text
            )));
        }

        let embedding_response: EmbeddingResponse = response
            .json()
            .await
            .map_err(|e| DatabaseError::EmbeddingError(format!("Failed to parse OpenAI response: {}", e)))?;

        Ok(embedding_response.data.into_iter().map(|d| d.embedding).collect())
    }
}

#[async_trait]
impl EmbeddingProvider for OpenAIEmbedder {
    async fn embed(&self, text: &str) -> Result<Vec<f32>> {
        let embeddings = self.call_api(serde_json::json!(text)).await?;

        embeddings.into_iter().next()
            .ok_or_else(|| DatabaseError::EmbeddingError("No embedding returned from OpenAI".to_string()))
    }

    async fn embed_batch(&self, texts: &[String]) -> Result<Vec<Vec<f32>>> {
        if texts.is_empty() {
            return Ok(Vec::new());
        }

        // OpenAI supports batch embeddings (up to ~2048 texts per request)
        // For simplicity, send all at once (caller should handle chunking if needed)
        self.call_api(serde_json::json!(texts)).await
    }

    fn dimensions(&self) -> usize {
        self.dimensions
    }
}
