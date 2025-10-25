//! Cryptographic primitives for tenant isolation and data encryption.
//!
//! This module provides encryption at rest for tenant data using:
//! - Ed25519 for tenant identity and signing
//! - X25519 for key exchange (ECDH)
//! - ChaCha20-Poly1305 for AEAD encryption
//! - Argon2 for password-based key derivation

pub mod keypair;
pub mod kdf;

pub use keypair::TenantKeyPair;
pub use kdf::{derive_key, encrypt_private_key, decrypt_private_key};
