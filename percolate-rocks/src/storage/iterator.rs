//! Prefix iterator for scanning RocksDB keys.
//!
//! Efficiently iterates over keys with a common prefix.

use rocksdb::DB;

/// Iterator for scanning keys with prefix.
///
/// Stops iteration when prefix no longer matches.
pub struct PrefixIterator<'a> {
    iter: rocksdb::DBIterator<'a>,
    prefix: Vec<u8>,
}

impl<'a> PrefixIterator<'a> {
    /// Create new prefix iterator.
    ///
    /// # Arguments
    ///
    /// * `db` - Database handle
    /// * `cf_name` - Column family name
    /// * `prefix` - Key prefix to match
    ///
    /// # Returns
    ///
    /// New `PrefixIterator`
    pub fn new(db: &'a DB, cf_name: &str, prefix: Vec<u8>) -> Self {
        todo!("Implement PrefixIterator::new")
    }

    /// Get next key-value pair matching prefix.
    ///
    /// # Returns
    ///
    /// `Some((key, value))` if match found, `None` if iteration complete
    pub fn next(&mut self) -> Option<(Vec<u8>, Vec<u8>)> {
        todo!("Implement PrefixIterator::next")
    }

    /// Collect all matching key-value pairs.
    ///
    /// # Returns
    ///
    /// Vector of `(key, value)` tuples
    pub fn collect_all(mut self) -> Vec<(Vec<u8>, Vec<u8>)> {
        todo!("Implement PrefixIterator::collect_all")
    }
}
