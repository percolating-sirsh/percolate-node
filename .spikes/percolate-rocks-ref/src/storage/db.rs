//! RocksDB wrapper.

use crate::types::{DatabaseError, Result};
use rocksdb::{ColumnFamilyDescriptor, Options, DB};
use std::path::Path;
use std::sync::Arc;

use super::batch::BatchBuilder;
use super::iterator::PrefixIterator;

/// Column family names
pub const CF_ENTITIES: &str = "entities";
pub const CF_EDGES: &str = "edges";
pub const CF_EMBEDDINGS: &str = "embeddings";
pub const CF_INDEXES: &str = "indexes";
pub const CF_WAL: &str = "wal";

/// RocksDB storage wrapper.
#[derive(Clone)]
pub struct Storage {
    db: Arc<DB>,
}

impl Storage {
    /// Open database at path.
    pub fn open<P: AsRef<Path>>(path: P) -> Result<Self> {
        let mut opts = Options::default();
        opts.create_if_missing(true);
        opts.create_missing_column_families(true);

        // Optimize for read-heavy workload
        opts.set_level_compaction_dynamic_level_bytes(true);
        opts.set_max_background_jobs(4);
        opts.set_bytes_per_sync(1048576);

        // Column family descriptors
        let cf_descriptors = vec![
            ColumnFamilyDescriptor::new(CF_ENTITIES, Options::default()),
            ColumnFamilyDescriptor::new(CF_EDGES, Options::default()),
            ColumnFamilyDescriptor::new(CF_EMBEDDINGS, Options::default()),
            ColumnFamilyDescriptor::new(CF_INDEXES, Options::default()),
            ColumnFamilyDescriptor::new(CF_WAL, Options::default()),
        ];

        let db = DB::open_cf_descriptors(&opts, path, cf_descriptors)?;

        Ok(Self { db: Arc::new(db) })
    }

    /// Get column family handle.
    fn cf_handle(&self, cf_name: &str) -> Result<&rocksdb::ColumnFamily> {
        self.db
            .cf_handle(cf_name)
            .ok_or_else(|| DatabaseError::InternalError(format!("CF not found: {}", cf_name)))
    }

    /// Get value from column family.
    pub fn get(&self, cf_name: &str, key: &[u8]) -> Result<Option<Vec<u8>>> {
        let cf = self.cf_handle(cf_name)?;
        Ok(self.db.get_cf(cf, key)?)
    }

    /// Put value into column family.
    pub fn put(&self, cf_name: &str, key: &[u8], value: &[u8]) -> Result<()> {
        let cf = self.cf_handle(cf_name)?;
        Ok(self.db.put_cf(cf, key, value)?)
    }

    /// Delete key from column family.
    pub fn delete(&self, cf_name: &str, key: &[u8]) -> Result<()> {
        let cf = self.cf_handle(cf_name)?;
        Ok(self.db.delete_cf(cf, key)?)
    }

    /// Create write batch.
    pub fn batch(&self) -> BatchBuilder {
        BatchBuilder::new()
    }

    /// Write batch atomically.
    pub fn write_batch(&self, batch: BatchBuilder) -> Result<()> {
        Ok(self.db.write(batch.into_inner())?)
    }

    /// Iterate over keys with prefix.
    pub fn iter_prefix(&self, cf_name: &str, prefix: &[u8]) -> Result<PrefixIterator> {
        let cf = self.cf_handle(cf_name)?;
        let iter = self.db.raw_iterator_cf(cf);
        Ok(PrefixIterator::new(iter, prefix.to_vec()))
    }

    /// Get inner DB reference.
    pub fn inner(&self) -> &Arc<DB> {
        &self.db
    }
}
