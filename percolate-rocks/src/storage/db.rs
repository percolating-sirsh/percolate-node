//! Core storage operations using RocksDB.
//!
//! Provides low-level get/put/delete operations with column family support.
//!
//! # Encryption at Rest (TODO)
//!
//! **Current**: Data stored unencrypted in RocksDB
//!
//! **Planned**:
//! - Each tenant has Ed25519 key pair generated during initialization
//! - All entity values encrypted with ChaCha20-Poly1305 before storage
//! - Keys stored in separate column family `CF_KEYS` (encrypted with master password)
//! - Transparent encryption/decryption in `get()`/`put()` methods
//!
//! **Example** (future):
//! ```rust,ignore
//! let storage = Storage::open("./data", Some(master_password))?;
//! storage.put(CF_ENTITIES, key, value)?;  // Automatically encrypts
//! let decrypted = storage.get(CF_ENTITIES, key)?;  // Automatically decrypts
//! ```

use crate::crypto::TenantKeyPair;
use crate::otel::{db_span, DbOperation};
use crate::storage::column_families::CF_KEYS;
use crate::types::{DatabaseError, Result};
use rocksdb::DB;
use std::path::Path;
use std::sync::Arc;

/// Storage wrapper around RocksDB with column family support and encryption at rest.
///
/// Thread-safe and optimized for concurrent access.
///
/// Each tenant has an Ed25519 key pair for encryption:
/// - Private key encrypted with master password (Argon2 KDF)
/// - Public key stored unencrypted for sharing
/// - All entity data encrypted with ChaCha20-Poly1305
pub struct Storage {
    db: Arc<DB>,
    keypair: Option<Arc<TenantKeyPair>>,
}

impl Storage {
    /// Open database at path with column families and optional encryption.
    ///
    /// Creates database and column families if they don't exist.
    ///
    /// If `master_password` is provided, enables encryption at rest:
    /// - Generates new tenant key pair if none exists
    /// - Loads existing key pair if found
    /// - Private key encrypted with Argon2-derived key
    /// - All entity data encrypted with ChaCha20-Poly1305
    ///
    /// # Arguments
    ///
    /// * `path` - Database directory path
    /// * `master_password` - Optional master password for encryption at rest
    ///
    /// # Returns
    ///
    /// `Storage` instance
    ///
    /// # Errors
    ///
    /// Returns error if:
    /// - RocksDB fails to open
    /// - Wrong master password (decryption fails)
    /// - Corrupted key data
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// // Without encryption
    /// let storage = Storage::open("./data", None)?;
    ///
    /// // With encryption
    /// let storage = Storage::open("./data", Some("strong_password"))?;
    /// ```
    pub fn open<P: AsRef<Path>>(path: P, master_password: Option<&str>) -> Result<Self> {
        let mut opts = rocksdb::Options::default();
        opts.create_if_missing(true);
        opts.create_missing_column_families(true);

        // Performance tuning
        opts.set_max_open_files(1000);
        opts.set_max_background_jobs(4);
        opts.set_write_buffer_size(64 * 1024 * 1024); // 64MB

        // Create column family descriptors
        let cfs = super::column_families::create_column_family_descriptors();

        // Open database with column families
        let db = DB::open_cf_descriptors(&opts, path, cfs)
            .map_err(|e| DatabaseError::StorageError(e.into()))?;

        let db = Arc::new(db);

        // Load or generate tenant key pair if password provided
        let keypair = if let Some(password) = master_password {
            Some(Arc::new(Self::load_or_generate_keypair(&db, password)?))
        } else {
            None
        };

        Ok(Self { db, keypair })
    }

    /// Load existing key pair or generate new one.
    ///
    /// # Arguments
    ///
    /// * `db` - RocksDB instance
    /// * `master_password` - Master password for key encryption
    ///
    /// # Returns
    ///
    /// `TenantKeyPair` (loaded or newly generated)
    ///
    /// # Errors
    ///
    /// Returns error if wrong password or corrupted data
    fn load_or_generate_keypair(db: &Arc<DB>, master_password: &str) -> Result<TenantKeyPair> {
        let cf = db
            .cf_handle(CF_KEYS)
            .ok_or_else(|| DatabaseError::InternalError("CF_KEYS not found".to_string()))?;

        // Try to load existing key
        if let Some(encrypted_key) = db.get_cf(&cf, b"private_key_encrypted")? {
            // Decrypt and load
            let private_key_bytes =
                crate::crypto::decrypt_private_key(&encrypted_key, master_password)?;
            return TenantKeyPair::from_private_key_bytes(&private_key_bytes);
        }

        // Generate new key pair
        let keypair = TenantKeyPair::generate();

        // Encrypt private key with master password
        let private_key_bytes = keypair.private_key_bytes();
        let encrypted = crate::crypto::encrypt_private_key(&private_key_bytes, master_password)?;

        // Store encrypted private key
        db.put_cf(&cf, b"private_key_encrypted", &encrypted)?;

        // Store public key (unencrypted for sharing)
        let public_key_bytes = keypair.public_key_bytes();
        db.put_cf(&cf, b"public_key", &public_key_bytes)?;

        Ok(keypair)
    }

    /// Open database in temporary directory for testing.
    ///
    /// # Returns
    ///
    /// `Storage` instance with temporary storage (no encryption)
    pub fn open_temp() -> Result<Self> {
        // Use a temporary directory for testing
        let temp_dir = std::env::temp_dir().join(format!("rem-db-test-{}", uuid::Uuid::new_v4()));
        Self::open(temp_dir, None)
    }

    /// Get value from column family.
    ///
    /// # Arguments
    ///
    /// * `cf_name` - Column family name
    /// * `key` - Key bytes
    ///
    /// # Returns
    ///
    /// `Some(Vec<u8>)` if key exists, `None` otherwise
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::StorageError` if RocksDB fails
    pub fn get(&self, cf_name: &str, key: &[u8]) -> Result<Option<Vec<u8>>> {
        let _span = db_span(DbOperation::Get, Some(cf_name), None).entered();

        let cf = self.cf_handle(cf_name);
        self.db
            .get_cf(&cf, key)
            .map_err(|e| DatabaseError::StorageError(e.into()))
    }

    /// Put value into column family.
    ///
    /// # Arguments
    ///
    /// * `cf_name` - Column family name
    /// * `key` - Key bytes
    /// * `value` - Value bytes
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::StorageError` if RocksDB fails
    pub fn put(&self, cf_name: &str, key: &[u8], value: &[u8]) -> Result<()> {
        let _span = db_span(DbOperation::Put, Some(cf_name), None).entered();

        let cf = self.cf_handle(cf_name);
        self.db
            .put_cf(&cf, key, value)
            .map_err(|e| DatabaseError::StorageError(e.into()))
    }

    /// Delete key from column family.
    ///
    /// # Arguments
    ///
    /// * `cf_name` - Column family name
    /// * `key` - Key bytes
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::StorageError` if RocksDB fails
    pub fn delete(&self, cf_name: &str, key: &[u8]) -> Result<()> {
        let _span = db_span(DbOperation::Delete, Some(cf_name), None).entered();

        let cf = self.cf_handle(cf_name);
        self.db
            .delete_cf(&cf, key)
            .map_err(|e| DatabaseError::StorageError(e.into()))
    }

    /// Get column family handle.
    ///
    /// # Arguments
    ///
    /// * `name` - Column family name
    ///
    /// # Returns
    ///
    /// `ColumnFamily` handle
    ///
    /// # Panics
    ///
    /// Panics if column family doesn't exist (programming error)
    pub fn cf_handle(&self, name: &str) -> Arc<rocksdb::BoundColumnFamily> {
        self.db
            .cf_handle(name)
            .unwrap_or_else(|| panic!("Column family '{}' not found", name))
    }

    /// Create an iterator that scans keys with a given prefix.
    ///
    /// # Arguments
    ///
    /// * `cf_name` - Column family name
    /// * `prefix` - Key prefix to scan
    ///
    /// # Returns
    ///
    /// Iterator over (key, value) pairs
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// for item in storage.prefix_iterator(CF_WAL, b"wal:") {
    ///     let (key, value) = item?;
    ///     // Process entry
    /// }
    /// ```
    pub fn prefix_iterator(&self, cf_name: &str, prefix: &[u8]) -> impl Iterator<Item = Result<(Box<[u8]>, Box<[u8]>)>> + '_ {
        let cf = self.cf_handle(cf_name);
        let iter = self.db.iterator_cf(&cf, rocksdb::IteratorMode::From(prefix, rocksdb::Direction::Forward));
        let prefix = prefix.to_vec();

        iter.map(move |item| {
            item.map_err(|e| DatabaseError::StorageError(e.into()))
        })
        .take_while(move |item| {
            match item {
                Ok((key, _)) => key.starts_with(&prefix),
                Err(_) => true, // Propagate errors
            }
        })
    }

    /// Create a reverse iterator over a column family.
    ///
    /// # Arguments
    ///
    /// * `cf_name` - Column family name
    ///
    /// # Returns
    ///
    /// Iterator over (key, value) pairs in reverse order
    pub fn iterator_reverse(&self, cf_name: &str) -> impl Iterator<Item = Result<(Box<[u8]>, Box<[u8]>)>> + '_ {
        let cf = self.cf_handle(cf_name);
        self.db
            .iterator_cf(&cf, rocksdb::IteratorMode::End)
            .map(|item| item.map_err(|e| DatabaseError::StorageError(e.into())))
    }

    /// Get underlying RocksDB instance.
    ///
    /// # Returns
    ///
    /// Arc reference to DB
    ///
    /// # Note
    ///
    /// Used for advanced operations like custom iterators.
    pub fn db(&self) -> &Arc<DB> {
        &self.db
    }

    /// Flush all memtables to disk.
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::StorageError` if RocksDB fails
    pub fn flush(&self) -> Result<()> {
        self.db.flush().map_err(|e| DatabaseError::StorageError(e.into()))
    }

    /// Create database snapshot for consistent reads.
    ///
    /// # Returns
    ///
    /// Snapshot handle
    pub fn snapshot(&self) -> rocksdb::Snapshot {
        self.db.snapshot()
    }

    /// Compact column family.
    ///
    /// # Arguments
    ///
    /// * `cf_name` - Column family name
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::StorageError` if RocksDB fails
    pub fn compact(&self, cf_name: &str) -> Result<()> {
        let cf = self.cf_handle(cf_name);
        self.db.compact_range_cf(&cf, None::<&[u8]>, None::<&[u8]>);
        Ok(())
    }

    /// Check if encryption is enabled.
    ///
    /// # Returns
    ///
    /// `true` if database was opened with a master password
    pub fn is_encrypted(&self) -> bool {
        self.keypair.is_some()
    }

    /// Get tenant public key for sharing.
    ///
    /// # Returns
    ///
    /// 32-byte Ed25519 public key if encryption enabled, None otherwise
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// if let Some(public_key) = storage.public_key() {
    ///     // Share public key with other tenants
    /// }
    /// ```
    pub fn public_key(&self) -> Option<[u8; 32]> {
        self.keypair.as_ref().map(|kp| kp.public_key_bytes())
    }

    /// Put value with automatic encryption.
    ///
    /// If encryption is enabled, encrypts value before storage.
    ///
    /// # Arguments
    ///
    /// * `cf_name` - Column family name
    /// * `key` - Key bytes
    /// * `value` - Value bytes (will be encrypted if encryption enabled)
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::StorageError` or `DatabaseError::CryptoError`
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// storage.put_encrypted(CF_ENTITIES, b"key", b"secret data")?;
    /// ```
    pub fn put_encrypted(&self, cf_name: &str, key: &[u8], value: &[u8]) -> Result<()> {
        if let Some(keypair) = &self.keypair {
            let encrypted = keypair.encrypt(value)?;
            self.put(cf_name, key, &encrypted)
        } else {
            self.put(cf_name, key, value)
        }
    }

    /// Get value with automatic decryption.
    ///
    /// If encryption is enabled, decrypts value after retrieval.
    ///
    /// # Arguments
    ///
    /// * `cf_name` - Column family name
    /// * `key` - Key bytes
    ///
    /// # Returns
    ///
    /// Decrypted value if found, None otherwise
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::StorageError` or `DatabaseError::CryptoError`
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// let data = storage.get_encrypted(CF_ENTITIES, b"key")?;
    /// ```
    pub fn get_encrypted(&self, cf_name: &str, key: &[u8]) -> Result<Option<Vec<u8>>> {
        let value = self.get(cf_name, key)?;

        if let Some(encrypted) = value {
            if let Some(keypair) = &self.keypair {
                let decrypted = keypair.decrypt(&encrypted)?;
                Ok(Some(decrypted))
            } else {
                Ok(Some(encrypted))
            }
        } else {
            Ok(None)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use super::super::column_families::{CF_ENTITIES, CF_KEY_INDEX, CF_EMBEDDINGS};

    #[test]
    fn test_open_temp() {
        let storage = Storage::open_temp().unwrap();

        // Verify storage was created successfully
        // Column families are verified by successful put/get operations
        storage.put(CF_ENTITIES, b"test", b"value").unwrap();
        assert_eq!(storage.get(CF_ENTITIES, b"test").unwrap(), Some(b"value".to_vec()));
    }

    #[test]
    fn test_get_put_delete() {
        let storage = Storage::open_temp().unwrap();

        let key = b"test_key";
        let value = b"test_value";

        // Initially empty
        assert_eq!(storage.get(CF_ENTITIES, key).unwrap(), None);

        // Put value
        storage.put(CF_ENTITIES, key, value).unwrap();

        // Get value
        let result = storage.get(CF_ENTITIES, key).unwrap();
        assert_eq!(result, Some(value.to_vec()));

        // Delete
        storage.delete(CF_ENTITIES, key).unwrap();

        // Verify deleted
        assert_eq!(storage.get(CF_ENTITIES, key).unwrap(), None);
    }

    #[test]
    fn test_column_families() {
        let storage = Storage::open_temp().unwrap();

        let key = b"test_key";

        // Put same key in different CFs
        storage.put(CF_ENTITIES, key, b"entities_value").unwrap();
        storage.put(CF_KEY_INDEX, key, b"index_value").unwrap();
        storage.put(CF_EMBEDDINGS, key, b"embedding_value").unwrap();

        // Values should be isolated by CF
        assert_eq!(
            storage.get(CF_ENTITIES, key).unwrap(),
            Some(b"entities_value".to_vec())
        );
        assert_eq!(
            storage.get(CF_KEY_INDEX, key).unwrap(),
            Some(b"index_value".to_vec())
        );
        assert_eq!(
            storage.get(CF_EMBEDDINGS, key).unwrap(),
            Some(b"embedding_value".to_vec())
        );
    }

    #[test]
    fn test_flush() {
        let storage = Storage::open_temp().unwrap();

        storage.put(CF_ENTITIES, b"key", b"value").unwrap();
        storage.flush().unwrap();

        // Value should still be retrievable
        assert_eq!(
            storage.get(CF_ENTITIES, b"key").unwrap(),
            Some(b"value".to_vec())
        );
    }

    #[test]
    fn test_snapshot() {
        let storage = Storage::open_temp().unwrap();

        storage.put(CF_ENTITIES, b"key", b"value1").unwrap();

        let snapshot = storage.snapshot();

        // Modify after snapshot
        storage.put(CF_ENTITIES, b"key", b"value2").unwrap();

        // Snapshot should see old value
        let cf = storage.cf_handle(CF_ENTITIES);
        let old_value = snapshot.get_cf(&cf, b"key").unwrap();
        assert_eq!(old_value, Some(b"value1".to_vec()));

        // Current DB should see new value
        let new_value = storage.get(CF_ENTITIES, b"key").unwrap();
        assert_eq!(new_value, Some(b"value2".to_vec()));
    }

    #[test]
    fn test_compact() {
        let storage = Storage::open_temp().unwrap();

        // Put and delete to create fragmentation
        for i in 0..100 {
            let key = format!("key_{}", i);
            storage.put(CF_ENTITIES, key.as_bytes(), b"value").unwrap();
        }

        for i in 0..50 {
            let key = format!("key_{}", i);
            storage.delete(CF_ENTITIES, key.as_bytes()).unwrap();
        }

        // Compact should not fail
        storage.compact(CF_ENTITIES).unwrap();

        // Verify remaining keys are still accessible
        for i in 50..100 {
            let key = format!("key_{}", i);
            let result = storage.get(CF_ENTITIES, key.as_bytes()).unwrap();
            assert_eq!(result, Some(b"value".to_vec()));
        }
    }

    #[test]
    #[should_panic(expected = "Column family 'nonexistent' not found")]
    fn test_invalid_cf() {
        let storage = Storage::open_temp().unwrap();
        storage.cf_handle("nonexistent");
    }

    #[test]
    fn test_encryption_disabled_by_default() {
        let storage = Storage::open_temp().unwrap();
        assert!(!storage.is_encrypted());
        assert!(storage.public_key().is_none());
    }

    #[test]
    fn test_encryption_enabled_with_password() {
        let temp_dir = std::env::temp_dir().join(format!("rem-db-enc-{}", uuid::Uuid::new_v4()));
        let storage = Storage::open(&temp_dir, Some("test_password")).unwrap();

        assert!(storage.is_encrypted());
        assert!(storage.public_key().is_some());

        std::fs::remove_dir_all(temp_dir).ok();
    }

    #[test]
    fn test_encrypt_decrypt_roundtrip() {
        let temp_dir = std::env::temp_dir().join(format!("rem-db-enc-{}", uuid::Uuid::new_v4()));
        let storage = Storage::open(&temp_dir, Some("test_password")).unwrap();

        let key = b"test_key";
        let value = b"secret data";

        // Put encrypted
        storage.put_encrypted(CF_ENTITIES, key, value).unwrap();

        // Get decrypted
        let result = storage.get_encrypted(CF_ENTITIES, key).unwrap();
        assert_eq!(result, Some(value.to_vec()));

        std::fs::remove_dir_all(temp_dir).ok();
    }

    #[test]
    fn test_encrypted_data_is_actually_encrypted() {
        let temp_dir = std::env::temp_dir().join(format!("rem-db-enc-{}", uuid::Uuid::new_v4()));
        let storage = Storage::open(&temp_dir, Some("test_password")).unwrap();

        let key = b"test_key";
        let value = b"secret data";

        // Put encrypted
        storage.put_encrypted(CF_ENTITIES, key, value).unwrap();

        // Raw get should return encrypted data (different from plaintext)
        let raw = storage.get(CF_ENTITIES, key).unwrap().unwrap();
        assert_ne!(raw, value);

        std::fs::remove_dir_all(temp_dir).ok();
    }

    #[test]
    fn test_key_persistence() {
        let temp_dir = std::env::temp_dir().join(format!("rem-db-enc-{}", uuid::Uuid::new_v4()));

        let public_key1;
        {
            let storage = Storage::open(&temp_dir, Some("test_password")).unwrap();
            public_key1 = storage.public_key().unwrap();

            storage.put_encrypted(CF_ENTITIES, b"key", b"value").unwrap();
        }

        // Reopen with same password
        {
            let storage = Storage::open(&temp_dir, Some("test_password")).unwrap();
            let public_key2 = storage.public_key().unwrap();

            // Same key pair should be loaded
            assert_eq!(public_key1, public_key2);

            // Data should still be accessible
            let result = storage.get_encrypted(CF_ENTITIES, b"key").unwrap();
            assert_eq!(result, Some(b"value".to_vec()));
        }

        std::fs::remove_dir_all(temp_dir).ok();
    }

    #[test]
    fn test_wrong_password_fails() {
        let temp_dir = std::env::temp_dir().join(format!("rem-db-enc-{}", uuid::Uuid::new_v4()));

        {
            let storage = Storage::open(&temp_dir, Some("correct_password")).unwrap();
            storage.put_encrypted(CF_ENTITIES, b"key", b"value").unwrap();
        }

        // Try to open with wrong password
        let result = Storage::open(&temp_dir, Some("wrong_password"));
        assert!(result.is_err());

        std::fs::remove_dir_all(temp_dir).ok();
    }

    #[test]
    fn test_encryption_without_password_stores_plaintext() {
        let temp_dir = std::env::temp_dir().join(format!("rem-db-plain-{}", uuid::Uuid::new_v4()));
        let storage = Storage::open(&temp_dir, None).unwrap();

        let key = b"test_key";
        let value = b"plaintext data";

        // Put "encrypted" (actually stores plaintext)
        storage.put_encrypted(CF_ENTITIES, key, value).unwrap();

        // Raw get should return same data
        let raw = storage.get(CF_ENTITIES, key).unwrap().unwrap();
        assert_eq!(raw, value);

        std::fs::remove_dir_all(temp_dir).ok();
    }
}
