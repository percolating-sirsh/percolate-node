//! Graph operations for entity relationships.
//!
//! Provides bidirectional edge storage and traversal (20x faster than scan).

pub mod edges;
pub mod traversal;

pub use edges::EdgeManager;
pub use traversal::{GraphTraversal, TraversalDirection, EdgeProvider};
