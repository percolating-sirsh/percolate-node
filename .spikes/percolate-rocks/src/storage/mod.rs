//! Storage layer operations using RocksDB.
//!
//! Provides low-level storage primitives with column family support for:
//! - Entity storage
//! - Key indexing
//! - Graph edges (forward and reverse)
//! - Embeddings (binary format)
//! - Field indexes
//! - Write-ahead log (WAL)
//!
//! Also includes background worker for async operations.

pub mod db;
pub mod keys;
pub mod batch;
pub mod iterator;
pub mod column_families;
pub mod worker;

pub use db::Storage;
pub use keys::*;
pub use batch::BatchWriter;
pub use iterator::PrefixIterator;
pub use column_families::*;
pub use worker::{BackgroundWorker, Task, TaskResult, WorkerStatus};
