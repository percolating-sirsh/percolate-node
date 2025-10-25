//! Key derivation functions for password-based encryption.
//!
//! Uses Argon2 to derive encryption keys from master passwords.

use crate::types::{DatabaseError, Result};
use argon2::{
    password_hash::{PasswordHasher, SaltString},
    Argon2, PasswordHash, PasswordVerifier,
};
use chacha20poly1305::{
    aead::{Aead, KeyInit},
    ChaCha20Poly1305, Key, Nonce,
};
use rand::rngs::OsRng;

/// Derive 32-byte key from password using Argon2.
///
/// # Arguments
///
/// * `password` - Master password
/// * `salt` - 16-byte salt (must be unique per tenant)
///
/// # Returns
///
/// 32-byte derived key suitable for ChaCha20-Poly1305
///
/// # Example
///
/// ```
/// let salt = b"unique_tenant_id";
/// let key = derive_key("my_password", salt)?;
/// assert_eq!(key.len(), 32);
/// ```
pub fn derive_key(password: &str, salt: &[u8]) -> Result<[u8; 32]> {
    if salt.len() < 16 {
        return Err(DatabaseError::CryptoError(
            "Salt too short (minimum 16 bytes)".to_string(),
        ));
    }

    let argon2 = Argon2::default();

    // Create salt string from bytes
    let salt_str = SaltString::encode_b64(salt)
        .map_err(|e| DatabaseError::CryptoError(format!("Invalid salt: {}", e)))?;

    // Hash password
    let hash = argon2
        .hash_password(password.as_bytes(), &salt_str)
        .map_err(|e| DatabaseError::CryptoError(format!("Key derivation failed: {}", e)))?;

    // Extract hash bytes
    let hash_bytes = hash
        .hash
        .ok_or_else(|| DatabaseError::CryptoError("No hash output".to_string()))?;

    let mut key = [0u8; 32];
    key.copy_from_slice(&hash_bytes.as_bytes()[..32]);

    Ok(key)
}

/// Encrypt private key with password-derived key.
///
/// # Arguments
///
/// * `private_key` - 32-byte Ed25519 private key
/// * `password` - Master password
///
/// # Returns
///
/// Encrypted private key (16-byte salt + 12-byte nonce + ciphertext + 16-byte tag)
///
/// # Example
///
/// ```
/// let private_key = [42u8; 32];
/// let encrypted = encrypt_private_key(&private_key, "my_password")?;
/// ```
pub fn encrypt_private_key(private_key: &[u8; 32], password: &str) -> Result<Vec<u8>> {
    // Generate random salt
    let salt: [u8; 16] = rand::random();

    // Derive encryption key
    let key = derive_key(password, &salt)?;
    let cipher = ChaCha20Poly1305::new(Key::from_slice(&key));

    // Generate random nonce
    let nonce_bytes: [u8; 12] = rand::random();
    let nonce = Nonce::from_slice(&nonce_bytes);

    // Encrypt
    let ciphertext = cipher
        .encrypt(nonce, private_key.as_ref())
        .map_err(|e| DatabaseError::CryptoError(format!("Encryption failed: {}", e)))?;

    // Return salt || nonce || ciphertext
    let mut result = Vec::with_capacity(16 + 12 + ciphertext.len());
    result.extend_from_slice(&salt);
    result.extend_from_slice(&nonce_bytes);
    result.extend_from_slice(&ciphertext);

    Ok(result)
}

/// Decrypt private key with password-derived key.
///
/// # Arguments
///
/// * `encrypted` - Encrypted private key (salt + nonce + ciphertext)
/// * `password` - Master password
///
/// # Returns
///
/// 32-byte Ed25519 private key
///
/// # Errors
///
/// Returns `DatabaseError::CryptoError` if:
/// - Encrypted data too short
/// - Wrong password
/// - Corrupted data
///
/// # Example
///
/// ```
/// let private_key = [42u8; 32];
/// let encrypted = encrypt_private_key(&private_key, "password")?;
/// let decrypted = decrypt_private_key(&encrypted, "password")?;
/// assert_eq!(decrypted, private_key);
/// ```
pub fn decrypt_private_key(encrypted: &[u8], password: &str) -> Result<[u8; 32]> {
    if encrypted.len() < 60 {
        // 16 (salt) + 12 (nonce) + 32 (key) + 16 (tag) = 76 minimum
        return Err(DatabaseError::CryptoError(
            "Encrypted data too short".to_string(),
        ));
    }

    // Split components
    let (salt, rest) = encrypted.split_at(16);
    let (nonce_bytes, ciphertext) = rest.split_at(12);

    // Derive decryption key
    let key = derive_key(password, salt)?;
    let cipher = ChaCha20Poly1305::new(Key::from_slice(&key));

    let nonce = Nonce::from_slice(nonce_bytes);

    // Decrypt
    let plaintext = cipher
        .decrypt(nonce, ciphertext)
        .map_err(|e| DatabaseError::CryptoError(format!("Decryption failed: {}", e)))?;

    if plaintext.len() != 32 {
        return Err(DatabaseError::CryptoError(
            "Invalid private key length after decryption".to_string(),
        ));
    }

    let mut private_key = [0u8; 32];
    private_key.copy_from_slice(&plaintext);

    Ok(private_key)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_derive_key() {
        let salt = b"test_tenant_1234";
        let key = derive_key("my_password", salt).unwrap();

        assert_eq!(key.len(), 32);

        // Same password + salt → same key
        let key2 = derive_key("my_password", salt).unwrap();
        assert_eq!(key, key2);

        // Different password → different key
        let key3 = derive_key("other_password", salt).unwrap();
        assert_ne!(key, key3);

        // Different salt → different key
        let salt2 = b"other_tenant_123";
        let key4 = derive_key("my_password", salt2).unwrap();
        assert_ne!(key, key4);
    }

    #[test]
    fn test_derive_key_short_salt() {
        let result = derive_key("password", b"short");
        assert!(result.is_err());
    }

    #[test]
    fn test_encrypt_decrypt_private_key() {
        let private_key = [42u8; 32];
        let password = "strong_password";

        let encrypted = encrypt_private_key(&private_key, password).unwrap();

        // Encrypted should be longer (salt + nonce + ciphertext + tag)
        assert!(encrypted.len() > 32);

        // Decrypt
        let decrypted = decrypt_private_key(&encrypted, password).unwrap();
        assert_eq!(decrypted, private_key);
    }

    #[test]
    fn test_decrypt_with_wrong_password() {
        let private_key = [42u8; 32];
        let encrypted = encrypt_private_key(&private_key, "correct").unwrap();

        // Wrong password should fail
        let result = decrypt_private_key(&encrypted, "wrong");
        assert!(result.is_err());
    }

    #[test]
    fn test_decrypt_corrupted_data() {
        let private_key = [42u8; 32];
        let mut encrypted = encrypt_private_key(&private_key, "password").unwrap();

        // Corrupt the ciphertext
        encrypted[50] ^= 0xFF;

        let result = decrypt_private_key(&encrypted, "password");
        assert!(result.is_err());
    }

    #[test]
    fn test_encrypt_different_salts() {
        let private_key = [42u8; 32];
        let password = "password";

        let encrypted1 = encrypt_private_key(&private_key, password).unwrap();
        let encrypted2 = encrypt_private_key(&private_key, password).unwrap();

        // Different salts → different ciphertexts
        assert_ne!(encrypted1, encrypted2);

        // Both decrypt correctly
        assert_eq!(
            decrypt_private_key(&encrypted1, password).unwrap(),
            private_key
        );
        assert_eq!(
            decrypt_private_key(&encrypted2, password).unwrap(),
            private_key
        );
    }
}
