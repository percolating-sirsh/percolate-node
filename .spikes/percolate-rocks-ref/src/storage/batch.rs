//! Write batch operations.

use rocksdb::WriteBatch;

/// Atomic write batch builder.
pub struct BatchBuilder {
    inner: WriteBatch,
}

impl BatchBuilder {
    /// Create new batch.
    pub fn new() -> Self {
        Self {
            inner: WriteBatch::default(),
        }
    }

    /// Add put operation.
    pub fn put(&mut self, cf: &rocksdb::ColumnFamily, key: &[u8], value: &[u8]) {
        self.inner.put_cf(cf, key, value);
    }

    /// Add delete operation.
    pub fn delete(&mut self, cf: &rocksdb::ColumnFamily, key: &[u8]) {
        self.inner.delete_cf(cf, key);
    }

    /// Get inner batch.
    pub fn into_inner(self) -> WriteBatch {
        self.inner
    }
}

impl Default for BatchBuilder {
    fn default() -> Self {
        Self::new()
    }
}
