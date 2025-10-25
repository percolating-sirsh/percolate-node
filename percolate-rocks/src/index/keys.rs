//! Reverse key index for global lookups.
//!
//! Enables `rem lookup "key_value"` to find entities by key field.

use crate::types::Result;
use crate::storage::Storage;
use uuid::Uuid;

/// Reverse key index for global entity lookups.
pub struct KeyIndex {
    storage: Storage,
}

impl KeyIndex {
    /// Create new key index.
    ///
    /// # Arguments
    ///
    /// * `storage` - Storage instance
    ///
    /// # Returns
    ///
    /// New `KeyIndex`
    pub fn new(storage: Storage) -> Self {
        todo!("Implement KeyIndex::new")
    }

    /// Index key value for entity.
    ///
    /// # Arguments
    ///
    /// * `tenant_id` - Tenant scope
    /// * `key_value` - Key field value (uri, key, or name)
    /// * `entity_id` - Entity UUID
    /// * `entity_type` - Schema/table name
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::StorageError` if indexing fails
    pub fn index_key(
        &self,
        tenant_id: &str,
        key_value: &str,
        entity_id: Uuid,
        entity_type: &str,
    ) -> Result<()> {
        todo!("Implement KeyIndex::index_key")
    }

    /// Lookup entity by key value (global search).
    ///
    /// # Arguments
    ///
    /// * `key_value` - Key field value to search
    ///
    /// # Returns
    ///
    /// Vector of `(tenant_id, entity_type, entity_id)` tuples
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::StorageError` if lookup fails
    pub fn lookup(&self, key_value: &str) -> Result<Vec<(String, String, Uuid)>> {
        todo!("Implement KeyIndex::lookup")
    }

    /// Batch lookup multiple keys efficiently.
    ///
    /// # Arguments
    ///
    /// * `keys` - Key field values to search
    ///
    /// # Returns
    ///
    /// Vector of `(key_value, tenant_id, entity_type, entity_id)` tuples
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::StorageError` if lookup fails
    ///
    /// # Performance
    ///
    /// Target: ~1ms for 10 keys (parallel prefix scans)
    pub fn lookup_batch(&self, keys: &[String]) -> Result<Vec<(String, String, String, Uuid)>> {
        todo!("Implement KeyIndex::lookup_batch")
    }

    /// Remove key index for entity.
    ///
    /// # Arguments
    ///
    /// * `tenant_id` - Tenant scope
    /// * `key_value` - Key field value
    /// * `entity_id` - Entity UUID
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::StorageError` if removal fails
    pub fn remove_key(&self, tenant_id: &str, key_value: &str, entity_id: Uuid) -> Result<()> {
        todo!("Implement KeyIndex::remove_key")
    }
}
