//! Key encoding and decoding functions for RocksDB.
//!
//! Provides deterministic key generation and parsing for all column families.

use crate::types::{DatabaseError, Result};
use uuid::Uuid;

/// Encode entity key.
///
/// Format: `entity:{tenant_id}:{uuid}`
///
/// # Arguments
///
/// * `tenant_id` - Tenant scope
/// * `entity_id` - Entity UUID
///
/// # Returns
///
/// Encoded key as bytes
pub fn encode_entity_key(tenant_id: &str, entity_id: Uuid) -> Vec<u8> {
    format!("entity:{}:{}", tenant_id, entity_id).into_bytes()
}

/// Decode entity key.
///
/// # Arguments
///
/// * `key` - Encoded key bytes
///
/// # Returns
///
/// `(tenant_id, entity_id)` tuple
///
/// # Errors
///
/// Returns `DatabaseError::InvalidKey` if key format is invalid
pub fn decode_entity_key(key: &[u8]) -> Result<(String, Uuid)> {
    let key_str = std::str::from_utf8(key)
        .map_err(|e| DatabaseError::InvalidKey(format!("Invalid UTF-8: {}", e)))?;

    let parts: Vec<&str> = key_str.split(':').collect();
    if parts.len() != 3 || parts[0] != "entity" {
        return Err(DatabaseError::InvalidKey(format!("Invalid entity key format: {}", key_str)));
    }

    let tenant_id = parts[1].to_string();
    let entity_id = Uuid::parse_str(parts[2])
        .map_err(|e| DatabaseError::InvalidKey(format!("Invalid UUID: {}", e)))?;

    Ok((tenant_id, entity_id))
}

/// Encode key index entry.
///
/// Format: `key:{tenant_id}:{key_value}:{uuid}`
///
/// # Arguments
///
/// * `tenant_id` - Tenant scope
/// * `key_value` - Key field value (from uri, key, or name)
/// * `entity_id` - Entity UUID
///
/// # Returns
///
/// Encoded key as bytes
pub fn encode_key_index(tenant_id: &str, key_value: &str, entity_id: Uuid) -> Vec<u8> {
    format!("key:{}:{}:{}", tenant_id, key_value, entity_id).into_bytes()
}

/// Encode forward edge key.
///
/// Format: `src:{src_uuid}:dst:{dst_uuid}:type:{rel_type}`
///
/// # Arguments
///
/// * `src` - Source entity UUID
/// * `dst` - Destination entity UUID
/// * `rel_type` - Relationship type
///
/// # Returns
///
/// Encoded key as bytes
pub fn encode_edge_key(src: Uuid, dst: Uuid, rel_type: &str) -> Vec<u8> {
    format!("src:{}:dst:{}:type:{}", src, dst, rel_type).into_bytes()
}

/// Encode reverse edge key.
///
/// Format: `dst:{dst_uuid}:src:{src_uuid}:type:{rel_type}`
///
/// # Arguments
///
/// * `dst` - Destination entity UUID
/// * `src` - Source entity UUID
/// * `rel_type` - Relationship type
///
/// # Returns
///
/// Encoded key as bytes
pub fn encode_reverse_edge_key(dst: Uuid, src: Uuid, rel_type: &str) -> Vec<u8> {
    format!("dst:{}:src:{}:type:{}", dst, src, rel_type).into_bytes()
}

/// Encode embedding key.
///
/// Format: `emb:{tenant_id}:{uuid}`
///
/// # Arguments
///
/// * `tenant_id` - Tenant scope
/// * `entity_id` - Entity UUID
///
/// # Returns
///
/// Encoded key as bytes
pub fn encode_embedding_key(tenant_id: &str, entity_id: Uuid) -> Vec<u8> {
    format!("emb:{}:{}", tenant_id, entity_id).into_bytes()
}

/// Encode index key for field value.
///
/// Format: `idx:{tenant_id}:{field_name}:{field_value}:{uuid}`
///
/// # Arguments
///
/// * `tenant_id` - Tenant scope
/// * `field_name` - Field name being indexed
/// * `field_value` - Field value
/// * `entity_id` - Entity UUID
///
/// # Returns
///
/// Encoded key as bytes
pub fn encode_index_key(
    tenant_id: &str,
    field_name: &str,
    field_value: &str,
    entity_id: Uuid,
) -> Vec<u8> {
    format!("idx:{}:{}:{}:{}", tenant_id, field_name, field_value, entity_id).into_bytes()
}

/// Encode WAL key.
///
/// Format: `wal:{sequence_number}`
///
/// # Arguments
///
/// * `seq` - WAL sequence number
///
/// # Returns
///
/// Encoded key as bytes
pub fn encode_wal_key(seq: u64) -> Vec<u8> {
    format!("wal:{:020}", seq).into_bytes()  // Zero-padded for lexicographic ordering
}

/// Generate deterministic UUID from key value.
///
/// Uses BLAKE3 hash of `tenant_id:entity_type:key_value` to generate UUID.
///
/// # Arguments
///
/// * `tenant_id` - Tenant scope
/// * `entity_type` - Schema/table name
/// * `key_value` - Key field value
///
/// # Returns
///
/// Deterministic UUID
pub fn deterministic_uuid(tenant_id: &str, entity_type: &str, key_value: &str) -> Uuid {
    let input = format!("{}:{}:{}", tenant_id, entity_type, key_value);
    let hash = blake3::hash(input.as_bytes());
    let bytes = hash.as_bytes()[..16].try_into().unwrap();
    Uuid::from_bytes(bytes)
}

/// Generate deterministic UUID for resource with chunk ordinal.
///
/// Uses BLAKE3 hash of `tenant_id:entity_type:uri:chunk_ordinal`.
///
/// # Arguments
///
/// * `tenant_id` - Tenant scope
/// * `entity_type` - Schema/table name
/// * `uri` - Resource URI
/// * `chunk_ordinal` - Chunk number (0 for single resources)
///
/// # Returns
///
/// Deterministic UUID
pub fn resource_uuid(tenant_id: &str, entity_type: &str, uri: &str, chunk_ordinal: u32) -> Uuid {
    let input = format!("{}:{}:{}:{}", tenant_id, entity_type, uri, chunk_ordinal);
    let hash = blake3::hash(input.as_bytes());
    let bytes = hash.as_bytes()[..16].try_into().unwrap();
    Uuid::from_bytes(bytes)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_encode_entity_key() {
        let id = Uuid::new_v4();
        let key = encode_entity_key("tenant1", id);
        let key_str = String::from_utf8(key.clone()).unwrap();

        assert!(key_str.starts_with("entity:tenant1:"));
        assert!(key_str.contains(&id.to_string()));
    }

    #[test]
    fn test_decode_entity_key() {
        let id = Uuid::new_v4();
        let key = encode_entity_key("tenant1", id);

        let (tenant_id, entity_id) = decode_entity_key(&key).unwrap();

        assert_eq!(tenant_id, "tenant1");
        assert_eq!(entity_id, id);
    }

    #[test]
    fn test_decode_invalid_entity_key() {
        let result = decode_entity_key(b"invalid:key");
        assert!(result.is_err());

        let result = decode_entity_key(b"entity:tenant1:not-a-uuid");
        assert!(result.is_err());
    }

    #[test]
    fn test_encode_key_index() {
        let id = Uuid::new_v4();
        let key = encode_key_index("tenant1", "alice@example.com", id);
        let key_str = String::from_utf8(key).unwrap();

        assert_eq!(key_str, format!("key:tenant1:alice@example.com:{}", id));
    }

    #[test]
    fn test_encode_edge_keys() {
        let src = Uuid::new_v4();
        let dst = Uuid::new_v4();

        let forward = encode_edge_key(src, dst, "authored");
        let forward_str = String::from_utf8(forward).unwrap();
        assert_eq!(forward_str, format!("src:{}:dst:{}:type:authored", src, dst));

        let reverse = encode_reverse_edge_key(dst, src, "authored");
        let reverse_str = String::from_utf8(reverse).unwrap();
        assert_eq!(reverse_str, format!("dst:{}:src:{}:type:authored", dst, src));
    }

    #[test]
    fn test_encode_embedding_key() {
        let id = Uuid::new_v4();
        let key = encode_embedding_key("tenant1", id);
        let key_str = String::from_utf8(key).unwrap();

        assert_eq!(key_str, format!("emb:tenant1:{}", id));
    }

    #[test]
    fn test_encode_index_key() {
        let id = Uuid::new_v4();
        let key = encode_index_key("tenant1", "category", "tutorial", id);
        let key_str = String::from_utf8(key).unwrap();

        assert_eq!(key_str, format!("idx:tenant1:category:tutorial:{}", id));
    }

    #[test]
    fn test_encode_wal_key() {
        let key1 = encode_wal_key(0);
        let key2 = encode_wal_key(1);
        let key3 = encode_wal_key(999999);

        let key1_str = String::from_utf8(key1.clone()).unwrap();
        let key2_str = String::from_utf8(key2.clone()).unwrap();
        let key3_str = String::from_utf8(key3.clone()).unwrap();

        assert_eq!(key1_str, "wal:00000000000000000000");
        assert_eq!(key2_str, "wal:00000000000000000001");
        assert_eq!(key3_str, "wal:00000000000000999999");

        // Verify lexicographic ordering
        assert!(key1 < key2);
        assert!(key2 < key3);
    }

    #[test]
    fn test_deterministic_uuid() {
        let uuid1 = deterministic_uuid("tenant1", "articles", "alice@example.com");
        let uuid2 = deterministic_uuid("tenant1", "articles", "alice@example.com");
        let uuid3 = deterministic_uuid("tenant1", "articles", "bob@example.com");

        // Same input produces same UUID
        assert_eq!(uuid1, uuid2);

        // Different input produces different UUID
        assert_ne!(uuid1, uuid3);
    }

    #[test]
    fn test_deterministic_uuid_tenant_isolation() {
        let uuid1 = deterministic_uuid("tenant1", "articles", "test");
        let uuid2 = deterministic_uuid("tenant2", "articles", "test");

        // Different tenants produce different UUIDs
        assert_ne!(uuid1, uuid2);
    }

    #[test]
    fn test_resource_uuid_with_chunks() {
        let uuid0 = resource_uuid("tenant1", "resources", "https://example.com/doc.pdf", 0);
        let uuid1 = resource_uuid("tenant1", "resources", "https://example.com/doc.pdf", 1);
        let uuid2 = resource_uuid("tenant1", "resources", "https://example.com/doc.pdf", 2);

        // Different chunks produce different UUIDs
        assert_ne!(uuid0, uuid1);
        assert_ne!(uuid1, uuid2);

        // Same chunk ordinal produces same UUID
        let uuid0_again = resource_uuid("tenant1", "resources", "https://example.com/doc.pdf", 0);
        assert_eq!(uuid0, uuid0_again);
    }

    #[test]
    fn test_resource_uuid_different_uris() {
        let uuid1 = resource_uuid("tenant1", "resources", "https://example.com/doc1.pdf", 0);
        let uuid2 = resource_uuid("tenant1", "resources", "https://example.com/doc2.pdf", 0);

        // Different URIs produce different UUIDs
        assert_ne!(uuid1, uuid2);
    }
}
