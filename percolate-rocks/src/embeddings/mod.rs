//! Embedding providers for vector generation.
//!
//! Supports local and OpenAI embedding models.

pub mod provider;
pub mod local;
pub mod openai;
pub mod batch;

pub use provider::{EmbeddingProvider, ProviderFactory};
pub use local::LocalEmbedder;
pub use openai::OpenAIEmbedder;
pub use batch::BatchEmbedder;
