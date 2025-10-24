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
    ]
}

/// Create column family descriptors with optimized settings.
///
/// # Returns
///
/// Vector of `ColumnFamilyDescriptor` with appropriate options for each CF
pub fn create_column_family_descriptors() -> Vec<ColumnFamilyDescriptor> {
    todo!("Implement create_column_family_descriptors")
}

/// Get options for entity storage CF.
///
/// # Returns
///
/// `Options` optimized for entity storage (compressed, bloom filter)
pub fn entity_cf_options() -> Options {
    todo!("Implement entity_cf_options")
}

/// Get options for embedding storage CF.
///
/// # Returns
///
/// `Options` optimized for binary embedding storage (no compression, large blocks)
pub fn embedding_cf_options() -> Options {
    todo!("Implement embedding_cf_options")
}

/// Get options for index CFs.
///
/// # Returns
///
/// `Options` optimized for index lookups (prefix extraction, bloom filter)
pub fn index_cf_options() -> Options {
    todo!("Implement index_cf_options")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_all_column_families() {
        // TODO: Test all CFs are listed
    }

    #[test]
    fn test_column_family_options() {
        // TODO: Test CF options creation
    }
}
