//! Core storage operations using RocksDB.
//!
//! Provides low-level get/put/delete operations with column family support.

use crate::types::{DatabaseError, Result};
use rocksdb::{DB, ColumnFamily};
use std::path::Path;
use std::sync::Arc;

/// Storage wrapper around RocksDB with column family support.
///
/// Thread-safe and optimized for concurrent access.
pub struct Storage {
    db: Arc<DB>,
}

impl Storage {
    /// Open database at path with column families.
    ///
    /// Creates database and column families if they don't exist.
    ///
    /// # Arguments
    ///
    /// * `path` - Database directory path
    ///
    /// # Returns
    ///
    /// `Storage` instance
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::StorageError` if RocksDB fails to open
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// let storage = Storage::open("./data")?;
    /// ```
    pub fn open<P: AsRef<Path>>(path: P) -> Result<Self> {
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

        Ok(Self {
            db: Arc::new(db),
        })
    }

    /// Open database in memory for testing.
    ///
    /// # Returns
    ///
    /// `Storage` instance with in-memory backend
    pub fn open_temp() -> Result<Self> {
        // Use a temporary directory for testing
        let temp_dir = std::env::temp_dir().join(format!("rem-db-test-{}", uuid::Uuid::new_v4()));
        Self::open(temp_dir)
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
}
