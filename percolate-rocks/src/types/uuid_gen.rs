//! Deterministic UUID generation for idempotent inserts.
//!
//! Uses BLAKE3 hashing to generate deterministic UUIDs from entity keys.

use uuid::Uuid;
use blake3;

/// Generate deterministic UUID from entity data.
///
/// # Precedence
///
/// 1. `uri` + `chunk_ordinal` → `blake3(entity_type:uri:chunk_ordinal)`
/// 2. `key_field` (from schema) → `blake3(entity_type:field_value)`
/// 3. `key` field → `blake3(entity_type:key)`
/// 4. `name` field → `blake3(entity_type:name)`
/// 5. Fallback → `UUID::v4()` (random)
///
/// # Arguments
///
/// * `entity_type` - Schema/table name
/// * `data` - Entity data
/// * `key_field` - Optional key field from schema configuration
///
/// # Returns
///
/// Deterministic UUID if key found, random UUID otherwise
///
/// # Example
///
/// ```rust,ignore
/// let data = json!({"uri": "https://docs.python.org", "chunk_ordinal": 0});
/// let id = generate_uuid("resources", &data, None);
/// // Same data → same UUID (idempotent)
/// ```
pub fn generate_uuid(
    entity_type: &str,
    data: &serde_json::Value,
    key_field: Option<&str>,
) -> Uuid {
    // Priority 1: uri + chunk_ordinal (for resources/chunked documents)
    if let Some(uri) = data.get("uri").and_then(|v| v.as_str()) {
        let chunk_ordinal = data.get("chunk_ordinal")
            .and_then(|v| v.as_u64())
            .unwrap_or(0);

        let key = format!("{}:{}:{}", entity_type, uri, chunk_ordinal);
        return hash_to_uuid(&key);
    }

    // Priority 2: Custom key_field from schema
    if let Some(field_name) = key_field {
        if let Some(value) = data.get(field_name) {
            let key = format!("{}:{}", entity_type, value_to_string(value));
            return hash_to_uuid(&key);
        }
    }

    // Priority 3: Generic "key" field
    if let Some(key_value) = data.get("key") {
        let key = format!("{}:{}", entity_type, value_to_string(key_value));
        return hash_to_uuid(&key);
    }

    // Priority 4: "name" field
    if let Some(name) = data.get("name").and_then(|v| v.as_str()) {
        let key = format!("{}:{}", entity_type, name);
        return hash_to_uuid(&key);
    }

    // Priority 5: Random UUID (fallback)
    Uuid::new_v4()
}

/// Hash string to UUID using BLAKE3.
///
/// # Arguments
///
/// * `input` - String to hash
///
/// # Returns
///
/// Deterministic UUID (v5-like with BLAKE3)
fn hash_to_uuid(input: &str) -> Uuid {
    let hash = blake3::hash(input.as_bytes());
    let bytes = hash.as_bytes();

    // Use first 16 bytes of hash for UUID
    let mut uuid_bytes = [0u8; 16];
    uuid_bytes.copy_from_slice(&bytes[..16]);

    // Set version and variant bits for UUID v5 compatibility
    uuid_bytes[6] = (uuid_bytes[6] & 0x0f) | 0x50; // Version 5
    uuid_bytes[8] = (uuid_bytes[8] & 0x3f) | 0x80; // Variant 10

    Uuid::from_bytes(uuid_bytes)
}

/// Convert JSON value to string for hashing.
///
/// # Arguments
///
/// * `value` - JSON value
///
/// # Returns
///
/// String representation for hashing
fn value_to_string(value: &serde_json::Value) -> String {
    match value {
        serde_json::Value::String(s) => s.clone(),
        serde_json::Value::Number(n) => n.to_string(),
        serde_json::Value::Bool(b) => b.to_string(),
        _ => value.to_string(), // Fallback to JSON string
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_deterministic_uri() {
        let data1 = json!({"uri": "https://example.com", "chunk_ordinal": 0});
        let data2 = json!({"uri": "https://example.com", "chunk_ordinal": 0});

        let id1 = generate_uuid("resources", &data1, None);
        let id2 = generate_uuid("resources", &data2, None);

        assert_eq!(id1, id2); // Same data → same UUID
    }

    #[test]
    fn test_deterministic_key_field() {
        let data1 = json!({"email": "alice@example.com", "name": "Alice"});
        let data2 = json!({"email": "alice@example.com", "name": "Alice"});

        let id1 = generate_uuid("users", &data1, Some("email"));
        let id2 = generate_uuid("users", &data2, Some("email"));

        assert_eq!(id1, id2); // Same key → same UUID
    }

    #[test]
    fn test_deterministic_name() {
        let data1 = json!({"name": "Project Alpha"});
        let data2 = json!({"name": "Project Alpha"});

        let id1 = generate_uuid("projects", &data1, None);
        let id2 = generate_uuid("projects", &data2, None);

        assert_eq!(id1, id2); // Same name → same UUID
    }

    #[test]
    fn test_different_keys_different_uuids() {
        let data1 = json!({"name": "Alice"});
        let data2 = json!({"name": "Bob"});

        let id1 = generate_uuid("users", &data1, None);
        let id2 = generate_uuid("users", &data2, None);

        assert_ne!(id1, id2); // Different names → different UUIDs
    }

    #[test]
    fn test_random_fallback() {
        let data1 = json!({"description": "No key field"});
        let data2 = json!({"description": "No key field"});

        let id1 = generate_uuid("items", &data1, None);
        let id2 = generate_uuid("items", &data2, None);

        // No key field → random UUIDs
        assert_ne!(id1, id2);
    }

    #[test]
    fn test_chunk_ordinal_difference() {
        let data1 = json!({"uri": "https://example.com", "chunk_ordinal": 0});
        let data2 = json!({"uri": "https://example.com", "chunk_ordinal": 1});

        let id1 = generate_uuid("resources", &data1, None);
        let id2 = generate_uuid("resources", &data2, None);

        assert_ne!(id1, id2); // Different chunk ordinals → different UUIDs
    }

    #[test]
    fn test_priority_order() {
        // uri takes precedence over name
        let data = json!({
            "uri": "https://example.com",
            "name": "Example",
            "key": "some-key"
        });

        let id_with_uri = generate_uuid("test", &data, None);

        let data_no_uri = json!({
            "name": "Example",
            "key": "some-key"
        });

        let id_with_key = generate_uuid("test", &data_no_uri, Some("key"));

        // Different precedence → different UUIDs
        assert_ne!(id_with_uri, id_with_key);
    }
}
