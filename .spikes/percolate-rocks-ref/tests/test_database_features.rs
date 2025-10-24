//! Integration tests for core database features.

use percolate_rocks::Database;
use serde_json::json;
use tempfile::tempdir;

#[test]
fn test_database_creation() {
    let dir = tempdir().unwrap();
    let db = Database::open(dir.path(), "test-tenant");
    assert!(db.is_ok());
}

#[test]
fn test_schema_registration() {
    let dir = tempdir().unwrap();
    let db = Database::open(dir.path(), "test-tenant").unwrap();

    // Register a simple schema
    let schema = json!({
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "description": {"type": "string"}
        },
        "required": ["name"]
    });

    let result = db.register_schema(
        "resources".to_string(),
        schema,
        vec!["name".to_string()],
        vec!["description".to_string()],
    );

    assert!(result.is_ok());

    // Verify schema exists
    let retrieved = db.get_schema("resources");
    assert!(retrieved.is_ok());
}

#[test]
fn test_entity_insert_and_retrieve() {
    let dir = tempdir().unwrap();
    let db = Database::open(dir.path(), "test-tenant").unwrap();

    // Register schema
    let schema = json!({
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "content": {"type": "string"}
        },
        "required": ["name"]
    });

    db.register_schema(
        "resources".to_string(),
        schema,
        vec![],
        vec![],
    ).unwrap();

    // Insert entity
    let data = json!({
        "name": "Test Resource",
        "content": "This is a test resource"
    });

    let entity_id = db.insert_entity("resources", data).unwrap();

    // Retrieve entity
    let entity = db.get_entity(entity_id).unwrap();
    assert!(entity.is_some());

    let entity = entity.unwrap();
    assert_eq!(entity.entity_type, "resources");
    assert_eq!(entity.properties["name"], "Test Resource");
}

#[test]
fn test_entity_scan_by_type() {
    let dir = tempdir().unwrap();
    let db = Database::open(dir.path(), "test-tenant").unwrap();

    // Register schema
    let schema = json!({
        "type": "object",
        "properties": {
            "name": {"type": "string"}
        }
    });

    db.register_schema("resources".to_string(), schema, vec![], vec![]).unwrap();

    // Insert multiple entities
    for i in 1..=3 {
        db.insert_entity("resources", json!({"name": format!("Resource {}", i)})).unwrap();
    }

    // Scan by type
    let entities = db.scan_entities_by_type("resources").unwrap();
    assert_eq!(entities.len(), 3);
}

#[test]
fn test_schema_validation() {
    let dir = tempdir().unwrap();
    let db = Database::open(dir.path(), "test-tenant").unwrap();

    // Register schema with required field
    let schema = json!({
        "type": "object",
        "properties": {
            "name": {"type": "string"}
        },
        "required": ["name"]
    });

    db.register_schema("resources".to_string(), schema, vec![], vec![]).unwrap();

    // Try to insert invalid data (missing required field)
    let invalid_data = json!({"description": "Missing name field"});
    let result = db.insert_entity("resources", invalid_data);

    assert!(result.is_err());
}
