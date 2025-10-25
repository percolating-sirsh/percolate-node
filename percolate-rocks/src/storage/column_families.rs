//! Column family constants and setup for RocksDB.
//!
//! Defines column families for logical data separation and performance optimization.

use rocksdb::{ColumnFamilyDescriptor, Options};

/// Main entity storage
pub const CF_ENTITIES: &str = "entities";

/// Reverse key lookup index (global search)
pub const CF_KEY_INDEX: &str = "key_index";

/// Forward graph edges
pub const CF_EDGES: &str = "edges";

/// Reverse graph edges (bidirectional traversal)
pub const CF_EDGES_REVERSE: &str = "edges_reverse";

/// Vector embeddings (binary format)
pub const CF_EMBEDDINGS: &str = "embeddings";

/// Indexed field lookups
pub const CF_INDEXES: &str = "indexes";

/// Write-ahead log for replication
pub const CF_WAL: &str = "wal";

/// Tenant encryption keys (encrypted private keys, public keys)
pub const CF_KEYS: &str = "keys";

/// BM25 keyword search index for fuzzy key lookups
pub const CF_BM25_INDEX: &str = "bm25_index";

/// Get all column family names.
///
/// # Returns
///
/// Vector of column family names used by the database
pub fn all_column_families() -> Vec<&'static str> {
    vec![
        CF_ENTITIES,
        CF_KEY_INDEX,
        CF_EDGES,
        CF_EDGES_REVERSE,
        CF_EMBEDDINGS,
        CF_INDEXES,
        CF_WAL,
        CF_KEYS,
        CF_BM25_INDEX,
    ]
}

/// Create column family descriptors with optimized settings.
///
/// # Returns
///
/// Vector of `ColumnFamilyDescriptor` with appropriate options for each CF
pub fn create_column_family_descriptors() -> Vec<ColumnFamilyDescriptor> {
    vec![
        ColumnFamilyDescriptor::new(CF_ENTITIES, entity_cf_options()),
        ColumnFamilyDescriptor::new(CF_KEY_INDEX, index_cf_options()),
        ColumnFamilyDescriptor::new(CF_EDGES, entity_cf_options()),
        ColumnFamilyDescriptor::new(CF_EDGES_REVERSE, entity_cf_options()),
        ColumnFamilyDescriptor::new(CF_EMBEDDINGS, embedding_cf_options()),
        ColumnFamilyDescriptor::new(CF_INDEXES, index_cf_options()),
        ColumnFamilyDescriptor::new(CF_WAL, entity_cf_options()),
        ColumnFamilyDescriptor::new(CF_KEYS, entity_cf_options()),
        ColumnFamilyDescriptor::new(CF_BM25_INDEX, index_cf_options()),
    ]
}

/// Get options for entity storage CF.
///
/// # Returns
///
/// `Options` optimized for entity storage (compressed, bloom filter)
pub fn entity_cf_options() -> Options {
    let mut opts = Options::default();

    // Compression for space savings (JSON data compresses well)
    opts.set_compression_type(rocksdb::DBCompressionType::Lz4);

    // Block-based table with bloom filter
    let mut block_opts = rocksdb::BlockBasedOptions::default();
    block_opts.set_block_size(4 * 1024); // 4KB blocks
    block_opts.set_bloom_filter(10.0, false); // 10 bits per key
    opts.set_block_based_table_factory(&block_opts);

    // Enable prefix bloom filter for range queries
    opts.set_prefix_extractor(rocksdb::SliceTransform::create_fixed_prefix(10));

    opts
}

/// Get options for embedding storage CF.
///
/// # Returns
///
/// `Options` optimized for binary embedding storage (no compression, large blocks)
pub fn embedding_cf_options() -> Options {
    let mut opts = Options::default();

    // No compression - binary data doesn't compress well
    opts.set_compression_type(rocksdb::DBCompressionType::None);

    // Block-based table with larger blocks
    let mut block_opts = rocksdb::BlockBasedOptions::default();
    block_opts.set_block_size(32 * 1024); // 32KB blocks for sequential reads
    block_opts.set_bloom_filter(10.0, false);
    opts.set_block_based_table_factory(&block_opts);

    opts
}

/// Get options for index CFs.
///
/// # Returns
///
/// `Options` optimized for index lookups (prefix extraction, bloom filter)
pub fn index_cf_options() -> Options {
    let mut opts = Options::default();

    // Light compression (index keys compress well)
    opts.set_compression_type(rocksdb::DBCompressionType::Lz4);

    // Block-based table optimized for indexes
    let mut block_opts = rocksdb::BlockBasedOptions::default();
    block_opts.set_block_size(2 * 1024); // 2KB blocks
    block_opts.set_bloom_filter(10.0, false); // Critical for index lookups
    opts.set_block_based_table_factory(&block_opts);

    // Prefix extraction for range scans
    opts.set_prefix_extractor(rocksdb::SliceTransform::create_fixed_prefix(15));

    opts
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_all_column_families() {
        let cfs = all_column_families();

        assert_eq!(cfs.len(), 8);
        assert!(cfs.contains(&CF_ENTITIES));
        assert!(cfs.contains(&CF_KEY_INDEX));
        assert!(cfs.contains(&CF_EDGES));
        assert!(cfs.contains(&CF_EDGES_REVERSE));
        assert!(cfs.contains(&CF_EMBEDDINGS));
        assert!(cfs.contains(&CF_INDEXES));
        assert!(cfs.contains(&CF_WAL));
        assert!(cfs.contains(&CF_KEYS));
    }

    #[test]
    fn test_column_family_descriptors() {
        let descriptors = create_column_family_descriptors();

        assert_eq!(descriptors.len(), 8);

        // Verify all CFs have descriptors
        let names: Vec<_> = descriptors.iter().map(|d| d.name()).collect();
        assert!(names.contains(&CF_ENTITIES));
        assert!(names.contains(&CF_KEY_INDEX));
        assert!(names.contains(&CF_EDGES));
        assert!(names.contains(&CF_EDGES_REVERSE));
        assert!(names.contains(&CF_EMBEDDINGS));
        assert!(names.contains(&CF_INDEXES));
        assert!(names.contains(&CF_WAL));
        assert!(names.contains(&CF_KEYS));
    }

    #[test]
    fn test_entity_cf_options() {
        let opts = entity_cf_options();
        // Options are created successfully
        // Can't easily test internal settings, but we verify no panic
        drop(opts);
    }

    #[test]
    fn test_embedding_cf_options() {
        let opts = embedding_cf_options();
        // Options are created successfully
        drop(opts);
    }

    #[test]
    fn test_index_cf_options() {
        let opts = index_cf_options();
        // Options are created successfully
        drop(opts);
    }
}
