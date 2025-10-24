//! Key encoding/decoding for RocksDB.

use uuid::Uuid;

/// Encode entity key: entity:{tenant}:{uuid}
pub fn encode_entity_key(tenant_id: &str, entity_id: Uuid) -> Vec<u8> {
    format!("entity:{}:{}", tenant_id, entity_id).into_bytes()
}

/// Decode entity key
pub fn decode_entity_key(key: &[u8]) -> Option<(String, Uuid)> {
    let s = std::str::from_utf8(key).ok()?;
    let parts: Vec<&str> = s.split(':').collect();

    if parts.len() != 3 || parts[0] != "entity" {
        return None;
    }

    let tenant_id = parts[1].to_string();
    let entity_id = Uuid::parse_str(parts[2]).ok()?;

    Some((tenant_id, entity_id))
}

/// Encode edge key: edge:{tenant}:{src}:{dst}:{type}
pub fn encode_edge_key(tenant_id: &str, src_id: Uuid, dst_id: Uuid, edge_type: &str) -> Vec<u8> {
    format!("edge:{}:{}:{}:{}", tenant_id, src_id, dst_id, edge_type).into_bytes()
}

/// Encode entity prefix for iteration: entity:{tenant}:
pub fn encode_entity_prefix(tenant_id: &str) -> Vec<u8> {
    format!("entity:{}:", tenant_id).into_bytes()
}

/// Encode index key: index:{field}:{tenant}:{value}:{entity_id}
pub fn encode_index_key(field: &str, tenant_id: &str, value: &str, entity_id: Uuid) -> Vec<u8> {
    format!("index:{}:{}:{}:{}", field, tenant_id, value, entity_id).into_bytes()
}

/// Encode index prefix: index:{field}:{tenant}:{value}:
pub fn encode_index_prefix(field: &str, tenant_id: &str, value: &str) -> Vec<u8> {
    format!("index:{}:{}:{}:", field, tenant_id, value).into_bytes()
}

/// Encode WAL sequence key: wal:{tenant}:seq
pub fn encode_wal_seq_key(tenant_id: &str) -> Vec<u8> {
    format!("wal:{}:seq", tenant_id).into_bytes()
}

/// Encode WAL entry key: wal:{tenant}:entry:{seq}
pub fn encode_wal_entry_key(tenant_id: &str, seq: u64) -> Vec<u8> {
    format!("wal:{}:entry:{:020}", tenant_id, seq).into_bytes()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_entity_key_roundtrip() {
        let tenant = "test-tenant";
        let id = Uuid::new_v4();

        let key = encode_entity_key(tenant, id);
        let (decoded_tenant, decoded_id) = decode_entity_key(&key).unwrap();

        assert_eq!(decoded_tenant, tenant);
        assert_eq!(decoded_id, id);
    }

    #[test]
    fn test_entity_prefix() {
        let tenant = "test-tenant";
        let prefix = encode_entity_prefix(tenant);

        let key = encode_entity_key(tenant, Uuid::new_v4());

        assert!(key.starts_with(&prefix));
    }
}
