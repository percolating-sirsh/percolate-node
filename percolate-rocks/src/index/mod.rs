//! Indexing layer for fast lookups.
//!
//! Provides:
//! - **HNSW** vector index for semantic search (multi-layer graph, fast build)
//! - **DiskANN** vector index for billion-scale search (memory-mapped, disk-optimized)
//! - **BM25** keyword search for full-text retrieval (best-match ranking)
//! - **Fuzzy key lookup** with BM25 fallback (exact → prefix → fuzzy)
//! - Field indexes for SQL predicates
//! - Reverse key index for global lookups

pub mod hnsw;
pub mod diskann;
pub mod tiered;
pub mod bm25;
pub mod fields;
pub mod keys;
pub mod keys_fuzzy;

pub use hnsw::HnswIndex;
pub use diskann::DiskANNIndex;
pub use tiered::{TieredIndex, TieredSearchConfig};
pub use bm25::BM25Index;
pub use fields::FieldIndexer;
pub use keys::KeyIndex;
pub use keys_fuzzy::{FuzzyKeyIndex, LookupResult, MatchType};
