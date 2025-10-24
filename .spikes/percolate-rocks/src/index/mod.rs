//! Indexing layer for fast lookups.
//!
//! Provides:
//! - HNSW vector index for semantic search (200x speedup)
//! - Field indexes for SQL predicates
//! - Reverse key index for global lookups

pub mod hnsw;
pub mod fields;
pub mod keys;

pub use hnsw::HnswIndex;
pub use fields::FieldIndexer;
pub use keys::KeyIndex;
