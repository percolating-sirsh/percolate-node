//! SQL query parsing and execution.
//!
//! Provides native SQL execution 5-10x faster than Python.
//!
//! Supports extended syntax:
//! - `LOOKUP 'key1', 'key2'` - Key-based entity lookup
//! - `TRAVERSE FROM 'uuid' DEPTH n DIRECTION dir` - Graph traversal
//! - `SEARCH 'query' IN table` - Semantic search

pub mod parser;
pub mod executor;
pub mod predicates;
pub mod planner;
pub mod extended;

pub use extended::{
    parse_extended_query, ExtendedQuery, KeyLookupQuery, TraverseQuery, SearchQuery, TraverseDirection
};
