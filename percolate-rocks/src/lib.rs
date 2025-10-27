//! Percolate REM Database - Rust core library
//!
//! High-performance embedded database combining:
//! - Vector search with HNSW indexing (200x faster than naive scan)
//! - Graph queries with bidirectional edges
//! - SQL predicates on indexed fields
//!
//! Can be used as:
//! - Standalone Rust library (cargo build --no-default-features)
//! - Python extension (maturin develop)
//!
//! # Encryption Architecture (TODO)
//!
//! **Encryption at Rest**:
//! - Each tenant has Ed25519 key pair (private key + public key) generated at initialization
//! - All entity data encrypted with ChaCha20-Poly1305 AEAD using tenant's private key
//! - Private keys encrypted with user's master password (PBKDF2 key derivation)
//! - Public keys stored unencrypted for sharing capabilities
//!
//! **Tenant Data Sharing**:
//! - Share data with another tenant: encrypt with recipient's public key (X25519 ECDH)
//! - Recipient decrypts with their private key
//! - End-to-end encryption - even database admin cannot read shared data
//!
//! **Device-to-Device Replication**:
//! - WAL entries encrypted before transmission over gRPC
//! - Each device in tenant has same key pair (synced securely on first device setup)
//! - Replication stream: mTLS (transport) + encrypted WAL (application layer)
//! - Defense in depth: even if TLS compromised, data remains encrypted
//!
//! **Key Management**:
//! - `Storage::new(path, master_password)` generates tenant key pair on first run
//! - Private key never leaves device unencrypted
//! - Key rotation: re-encrypt all entities with new key pair
//!
//! See `docs/encryption-architecture.md` for complete design

pub mod types;
pub mod storage;
pub mod index;
pub mod query;
pub mod embeddings;
pub mod schema;
pub mod graph;
pub mod replication;
pub mod export;
pub mod ingest;
pub mod llm;
pub mod crypto;
pub mod dreaming;
pub mod agents;  // Lightweight agent runtime for background indexing

// High-level database API
pub mod database;

// Database administration operations
pub mod admin;

#[cfg(feature = "python")]
pub mod bindings;

#[cfg(feature = "python")]
use pyo3::prelude::*;

/// PyO3 module definition for Python integration.
///
/// Exposes the Rust implementation as `rem_db._rust` Python module.
///
/// Only available when compiled with the "python" feature (default).
#[cfg(feature = "python")]
#[pymodule]
fn _rust(py: Python, m: &PyModule) -> PyResult<()> {
    bindings::register_module(py, m)?;
    Ok(())
}
