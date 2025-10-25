//! Tenant key pair management.
//!
//! Each tenant has an Ed25519 key pair:
//! - **Private key**: Used for encryption (never leaves device unencrypted)
//! - **Public key**: Used for sharing (stored unencrypted for discovery)
//!
//! The private key is encrypted with the master password using Argon2 KDF.

use crate::types::{DatabaseError, Result};
use chacha20poly1305::{
    aead::{Aead, KeyInit},
    ChaCha20Poly1305, Nonce,
};
use ed25519_dalek::{SigningKey, VerifyingKey};
use rand::rngs::OsRng;

/// Tenant key pair for identity and encryption.
///
/// # Example
///
/// ```
/// use percolate_rocks::crypto::TenantKeyPair;
///
/// let keypair = TenantKeyPair::generate();
/// let public_key_bytes = keypair.public_key_bytes();
///
/// // Derive encryption key for data
/// let enc_key = keypair.encryption_key();
/// ```
pub struct TenantKeyPair {
    signing_key: SigningKey,
    verifying_key: VerifyingKey,
}

impl TenantKeyPair {
    /// Generate new random key pair.
    ///
    /// # Returns
    ///
    /// New `TenantKeyPair` with random Ed25519 keys
    ///
    /// # Example
    ///
    /// ```
    /// let keypair = TenantKeyPair::generate();
    /// ```
    pub fn generate() -> Self {
        let signing_key = SigningKey::generate(&mut OsRng);
        let verifying_key = signing_key.verifying_key();

        Self {
            signing_key,
            verifying_key,
        }
    }

    /// Load key pair from raw bytes.
    ///
    /// # Arguments
    ///
    /// * `private_key_bytes` - 32-byte Ed25519 private key
    ///
    /// # Returns
    ///
    /// `TenantKeyPair` reconstructed from bytes
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::CryptoError` if bytes are invalid
    ///
    /// # Example
    ///
    /// ```
    /// let original = TenantKeyPair::generate();
    /// let bytes = original.private_key_bytes();
    ///
    /// let restored = TenantKeyPair::from_private_key_bytes(&bytes)?;
    /// ```
    pub fn from_private_key_bytes(private_key_bytes: &[u8]) -> Result<Self> {
        if private_key_bytes.len() != 32 {
            return Err(DatabaseError::CryptoError(
                "Invalid private key length (expected 32 bytes)".to_string(),
            ));
        }

        let signing_key = SigningKey::from_bytes(
            private_key_bytes
                .try_into()
                .map_err(|e| DatabaseError::CryptoError(format!("Invalid key bytes: {:?}", e)))?,
        );
        let verifying_key = signing_key.verifying_key();

        Ok(Self {
            signing_key,
            verifying_key,
        })
    }

    /// Get private key as bytes.
    ///
    /// # Returns
    ///
    /// 32-byte Ed25519 private key
    ///
    /// # Security
    ///
    /// These bytes must be encrypted before storage!
    ///
    /// # Example
    ///
    /// ```
    /// let keypair = TenantKeyPair::generate();
    /// let private_bytes = keypair.private_key_bytes();
    /// assert_eq!(private_bytes.len(), 32);
    /// ```
    pub fn private_key_bytes(&self) -> [u8; 32] {
        self.signing_key.to_bytes()
    }

    /// Get public key as bytes.
    ///
    /// # Returns
    ///
    /// 32-byte Ed25519 public key
    ///
    /// # Example
    ///
    /// ```
    /// let keypair = TenantKeyPair::generate();
    /// let public_bytes = keypair.public_key_bytes();
    /// assert_eq!(public_bytes.len(), 32);
    /// ```
    pub fn public_key_bytes(&self) -> [u8; 32] {
        self.verifying_key.to_bytes()
    }

    /// Derive ChaCha20-Poly1305 encryption key from Ed25519 private key.
    ///
    /// Uses the Ed25519 private key directly as ChaCha20 key material.
    ///
    /// # Returns
    ///
    /// 32-byte ChaCha20-Poly1305 key
    ///
    /// # Example
    ///
    /// ```
    /// let keypair = TenantKeyPair::generate();
    /// let enc_key = keypair.encryption_key();
    /// ```
    pub fn encryption_key(&self) -> [u8; 32] {
        self.signing_key.to_bytes()
    }

    /// Encrypt data with ChaCha20-Poly1305.
    ///
    /// # Arguments
    ///
    /// * `plaintext` - Data to encrypt
    ///
    /// # Returns
    ///
    /// Encrypted data (12-byte nonce + ciphertext + 16-byte tag)
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::CryptoError` if encryption fails
    ///
    /// # Example
    ///
    /// ```
    /// let keypair = TenantKeyPair::generate();
    /// let plaintext = b"secret data";
    /// let ciphertext = keypair.encrypt(plaintext)?;
    /// ```
    pub fn encrypt(&self, plaintext: &[u8]) -> Result<Vec<u8>> {
        let key = self.encryption_key();
        let cipher = ChaCha20Poly1305::new(&key.into());

        // Generate random nonce
        let nonce_bytes: [u8; 12] = rand::random();
        let nonce = Nonce::from_slice(&nonce_bytes);

        let ciphertext = cipher
            .encrypt(nonce, plaintext)
            .map_err(|e| DatabaseError::CryptoError(format!("Encryption failed: {}", e)))?;

        // Return nonce || ciphertext
        let mut result = Vec::with_capacity(12 + ciphertext.len());
        result.extend_from_slice(&nonce_bytes);
        result.extend_from_slice(&ciphertext);

        Ok(result)
    }

    /// Decrypt data with ChaCha20-Poly1305.
    ///
    /// # Arguments
    ///
    /// * `ciphertext` - Encrypted data (nonce + ciphertext + tag)
    ///
    /// # Returns
    ///
    /// Decrypted plaintext
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::CryptoError` if:
    /// - Ciphertext too short (< 28 bytes)
    /// - Authentication tag invalid
    /// - Decryption fails
    ///
    /// # Example
    ///
    /// ```
    /// let keypair = TenantKeyPair::generate();
    /// let ciphertext = keypair.encrypt(b"secret")?;
    /// let plaintext = keypair.decrypt(&ciphertext)?;
    /// assert_eq!(plaintext, b"secret");
    /// ```
    pub fn decrypt(&self, ciphertext: &[u8]) -> Result<Vec<u8>> {
        if ciphertext.len() < 28 {
            // 12 (nonce) + 0 (data) + 16 (tag)
            return Err(DatabaseError::CryptoError(
                "Ciphertext too short".to_string(),
            ));
        }

        let key = self.encryption_key();
        let cipher = ChaCha20Poly1305::new(&key.into());

        // Split nonce and ciphertext
        let (nonce_bytes, encrypted_data) = ciphertext.split_at(12);
        let nonce = Nonce::from_slice(nonce_bytes);

        let plaintext = cipher
            .decrypt(nonce, encrypted_data)
            .map_err(|e| DatabaseError::CryptoError(format!("Decryption failed: {}", e)))?;

        Ok(plaintext)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_generate_keypair() {
        let keypair = TenantKeyPair::generate();

        assert_eq!(keypair.private_key_bytes().len(), 32);
        assert_eq!(keypair.public_key_bytes().len(), 32);
    }

    #[test]
    fn test_keypair_roundtrip() {
        let original = TenantKeyPair::generate();
        let private_bytes = original.private_key_bytes();

        let restored = TenantKeyPair::from_private_key_bytes(&private_bytes).unwrap();

        assert_eq!(
            original.private_key_bytes(),
            restored.private_key_bytes()
        );
        assert_eq!(original.public_key_bytes(), restored.public_key_bytes());
    }

    #[test]
    fn test_encrypt_decrypt() {
        let keypair = TenantKeyPair::generate();
        let plaintext = b"Hello, encryption!";

        let ciphertext = keypair.encrypt(plaintext).unwrap();

        // Ciphertext should be different from plaintext
        assert_ne!(&ciphertext[12..], plaintext);

        // Decrypt
        let decrypted = keypair.decrypt(&ciphertext).unwrap();
        assert_eq!(decrypted, plaintext);
    }

    #[test]
    fn test_encrypt_different_nonces() {
        let keypair = TenantKeyPair::generate();
        let plaintext = b"Same plaintext";

        let ciphertext1 = keypair.encrypt(plaintext).unwrap();
        let ciphertext2 = keypair.encrypt(plaintext).unwrap();

        // Different nonces → different ciphertexts
        assert_ne!(ciphertext1, ciphertext2);

        // Both decrypt correctly
        assert_eq!(keypair.decrypt(&ciphertext1).unwrap(), plaintext);
        assert_eq!(keypair.decrypt(&ciphertext2).unwrap(), plaintext);
    }

    #[test]
    fn test_decrypt_invalid_ciphertext() {
        let keypair = TenantKeyPair::generate();

        // Too short
        let result = keypair.decrypt(&[0u8; 20]);
        assert!(result.is_err());

        // Wrong data
        let result = keypair.decrypt(&[0u8; 100]);
        assert!(result.is_err());
    }

    #[test]
    fn test_decrypt_with_wrong_key() {
        let keypair1 = TenantKeyPair::generate();
        let keypair2 = TenantKeyPair::generate();

        let ciphertext = keypair1.encrypt(b"secret").unwrap();

        // Decryption with different key should fail
        let result = keypair2.decrypt(&ciphertext);
        assert!(result.is_err());
    }
}
