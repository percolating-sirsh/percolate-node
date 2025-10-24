//! Integration tests for automatic embedding generation.

use percolate_rocks::{Database, Direction};
use serde_json::json;
use tempfile::tempdir;

#[tokio::test]
async fn test_insert_with_automatic_embedding() {
    let dir = tempdir().unwrap();
    let db = Database::open(dir.path(), "test-tenant").unwrap();

    // Register schema with content field marked for embedding
    let schema = json!({
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "content": {"type": "string"},
            "category": {"type": "string"}
        },
        "required": ["name", "content"]
    });

    db.register_schema(
        "resource".to_string(),
        schema,
        vec!["category".to_string()],
        vec!["content".to_string()], // Mark content for embedding
    )
    .unwrap();

    // Insert entity with content - should auto-generate embedding
    let properties = json!({
        "name": "Test Resource",
        "content": "This is a test document about programming in Rust",
        "category": "tutorial"
    });

    let entity_id = db
        .insert_entity_with_embedding("resource", properties)
        .await
        .unwrap();

    // Retrieve entity and verify embedding was generated
    let entity = db.get_entity(entity_id).unwrap().unwrap();

    // Check that embedding field exists
    assert!(entity.properties.get("embedding").is_some());

    // Check that embedding is a vector of floats
    let embedding = entity.properties["embedding"].as_array().unwrap();
    assert_eq!(embedding.len(), 384); // all-MiniLM-L6-v2 has 384 dimensions

    // Verify all embedding values are valid floats
    for val in embedding {
        assert!(val.as_f64().is_some());
    }

    println!(
        "✓ Successfully generated {}-dimensional embedding",
        embedding.len()
    );
}

#[tokio::test]
async fn test_insert_without_embedding_provider() {
    let dir = tempdir().unwrap();
    let db = Database::open_with_embeddings(dir.path(), "test-tenant", false).unwrap();

    // Register schema
    let schema = json!({
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "content": {"type": "string"}
        }
    });

    db.register_schema(
        "resource".to_string(),
        schema,
        vec![],
        vec!["content".to_string()],
    )
    .unwrap();

    // Insert - should work but without embedding
    let properties = json!({
        "name": "Test",
        "content": "Content"
    });

    let entity_id = db
        .insert_entity_with_embedding("resource", properties)
        .await
        .unwrap();

    let entity = db.get_entity(entity_id).unwrap().unwrap();

    // No embedding should be generated
    assert!(entity.properties.get("embedding").is_none());
}

#[tokio::test]
async fn test_embedding_similarity() {
    let dir = tempdir().unwrap();
    let db = Database::open(dir.path(), "test-tenant").unwrap();

    // Register schema
    let schema = json!({
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "content": {"type": "string"}
        }
    });

    db.register_schema(
        "resource".to_string(),
        schema,
        vec![],
        vec!["content".to_string()],
    )
    .unwrap();

    // Insert related documents
    let doc1 = json!({
        "name": "Rust Tutorial",
        "content": "Learn Rust programming language"
    });

    let doc2 = json!({
        "name": "Rust Guide",
        "content": "Programming in Rust with examples"
    });

    let doc3 = json!({
        "name": "Python Guide",
        "content": "Learn Python for data science"
    });

    let id1 = db.insert_entity_with_embedding("resource", doc1).await.unwrap();
    let id2 = db.insert_entity_with_embedding("resource", doc2).await.unwrap();
    let id3 = db.insert_entity_with_embedding("resource", doc3).await.unwrap();

    // Get embeddings
    let entity1 = db.get_entity(id1).unwrap().unwrap();
    let entity2 = db.get_entity(id2).unwrap().unwrap();
    let entity3 = db.get_entity(id3).unwrap().unwrap();

    let emb1: Vec<f32> = entity1.properties["embedding"]
        .as_array()
        .unwrap()
        .iter()
        .map(|v| v.as_f64().unwrap() as f32)
        .collect();

    let emb2: Vec<f32> = entity2.properties["embedding"]
        .as_array()
        .unwrap()
        .iter()
        .map(|v| v.as_f64().unwrap() as f32)
        .collect();

    let emb3: Vec<f32> = entity3.properties["embedding"]
        .as_array()
        .unwrap()
        .iter()
        .map(|v| v.as_f64().unwrap() as f32)
        .collect();

    // Calculate similarities
    use percolate_rocks::embeddings::cosine_similarity;

    let sim_1_2 = cosine_similarity(&emb1, &emb2);
    let sim_1_3 = cosine_similarity(&emb1, &emb3);

    println!("Similarity (Rust vs Rust): {:.4}", sim_1_2);
    println!("Similarity (Rust vs Python): {:.4}", sim_1_3);

    // Rust documents should be more similar to each other than to Python
    assert!(
        sim_1_2 > sim_1_3,
        "Rust docs should be more similar ({}  > {})",
        sim_1_2,
        sim_1_3
    );
}
