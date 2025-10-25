//! Cryptographic primitives
//!
//! This module provides:
//! - Ed25519 signature verification
//! - ChaCha20-Poly1305 encryption
//! - HKDF key derivation

use ed25519_dalek::{PublicKey, Signature, Verifier};
use pyo3::prelude::*;

/// Verify Ed25519 signature
///
/// # Arguments
///
/// * `message` - Message bytes
/// * `signature` - Signature bytes (64 bytes)
/// * `public_key` - Public key bytes (32 bytes)
///
/// # Returns
///
/// `true` if signature is valid, `false` otherwise
///
/// # Example
///
/// ```python
/// from percolate_core import verify_ed25519_signature
///
/// is_valid = verify_ed25519_signature(message, signature, public_key)
/// ```
#[pyfunction]
pub fn verify_ed25519_signature(message: &[u8], signature: &[u8], public_key: &[u8]) -> PyResult<bool> {
    let public_key = PublicKey::from_bytes(public_key)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid public key: {}", e)))?;

    let signature = Signature::from_bytes(signature)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid signature: {}", e)))?;

    Ok(public_key.verify(message, &signature).is_ok())
}
