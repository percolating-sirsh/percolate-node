//! Integration tests for fuzzy key lookup with BM25 fallback.

use percolate_rocks::index::keys_fuzzy::{FuzzyKeyIndex, MatchType};
use percolate_rocks::storage::Storage;
use tempfile::TempDir;
use uuid::Uuid;

/// Helper to create temp storage for testing
fn create_test_storage() -> (Storage, TempDir) {
    let temp_dir = TempDir::new().unwrap();
    let storage = Storage::open(temp_dir.path().to_str().unwrap()).unwrap();
    (storage, temp_dir)
}

#[test]
fn test_exact_match_lookup() {
    let (storage, _temp) = create_test_storage();
    let index = FuzzyKeyIndex::new(storage);

    // Index some keys
    let entity_id = Uuid::new_v4();
    index
        .index_key("tenant1", "person", entity_id, "alice@company.com")
        .unwrap();

    // Exact lookup
    let results = index.lookup("alice@company.com", 10).unwrap();

    assert_eq!(results.len(), 1);
    assert_eq!(results[0].match_type, MatchType::Exact);
    assert_eq!(results[0].score, 1.0);
    assert_eq!(results[0].entity_id, entity_id);
    assert_eq!(results[0].tenant_id, "tenant1");
    assert_eq!(results[0].entity_type, "person");
}

#[test]
fn test_prefix_match_lookup() {
    let (storage, _temp) = create_test_storage();
    let index = FuzzyKeyIndex::new(storage);

    // Index multiple keys with same prefix
    let id1 = Uuid::new_v4();
    let id2 = Uuid::new_v4();
    let id3 = Uuid::new_v4();

    index
        .index_key("tenant1", "person", id1, "alice@company.com")
        .unwrap();
    index
        .index_key("tenant1", "person", id2, "alice@example.com")
        .unwrap();
    index
        .index_key("tenant1", "person", id3, "bob@company.com")
        .unwrap();

    // Prefix lookup
    let results = index.lookup("alice@", 10).unwrap();

    assert_eq!(results.len(), 2);
    assert_eq!(results[0].match_type, MatchType::Prefix);
    assert_eq!(results[0].score, 0.8);

    // Verify both alice emails returned
    let ids: Vec<Uuid> = results.iter().map(|r| r.entity_id).collect();
    assert!(ids.contains(&id1));
    assert!(ids.contains(&id2));
    assert!(!ids.contains(&id3));
}

#[test]
fn test_fuzzy_match_lookup() {
    let (storage, _temp) = create_test_storage();
    let index = FuzzyKeyIndex::new(storage);

    // Index keys with common words
    let id1 = Uuid::new_v4();
    let id2 = Uuid::new_v4();
    let id3 = Uuid::new_v4();

    index
        .index_key("tenant1", "person", id1, "alice@example.com")
        .unwrap();
    index
        .index_key("tenant1", "person", id2, "alice.smith@example.com")
        .unwrap();
    index
        .index_key("tenant1", "person", id3, "bob.jones@company.com")
        .unwrap();

    // Fuzzy lookup (keywords that don't match exact or prefix)
    let results = index.lookup("alice example", 10).unwrap();

    assert!(!results.is_empty());
    assert_eq!(results[0].match_type, MatchType::Fuzzy);

    // alice@example.com should rank highest (has both keywords)
    assert_eq!(results[0].entity_id, id1);
    assert!(results[0].score > 0.0);
}

#[test]
fn test_cascading_fallback() {
    let (storage, _temp) = create_test_storage();
    let index = FuzzyKeyIndex::new(storage);

    let id = Uuid::new_v4();
    index
        .index_key("tenant1", "resource", id, "https://docs.rust-lang.org/tokio")
        .unwrap();

    // Exact match
    let exact = index.lookup("https://docs.rust-lang.org/tokio", 10).unwrap();
    assert_eq!(exact[0].match_type, MatchType::Exact);

    // Prefix match
    let prefix = index.lookup("https://docs.rust", 10).unwrap();
    assert_eq!(prefix[0].match_type, MatchType::Prefix);

    // Fuzzy match
    let fuzzy = index.lookup("rust tokio docs", 10).unwrap();
    assert_eq!(fuzzy[0].match_type, MatchType::Fuzzy);
}

#[test]
fn test_typo_tolerance() {
    let (storage, _temp) = create_test_storage();
    let index = FuzzyKeyIndex::new(storage);

    let id = Uuid::new_v4();
    index
        .index_key("tenant1", "person", id, "alice@company.com")
        .unwrap();

    // Typo: "alise" instead of "alice"
    // Fuzzy match should still find it (both have "company")
    let results = index.lookup("alise company", 10).unwrap();

    assert!(!results.is_empty());
    assert_eq!(results[0].match_type, MatchType::Fuzzy);
}

#[test]
fn test_automatic_index_maintenance_insert() {
    let (storage, _temp) = create_test_storage();
    let index = FuzzyKeyIndex::new(storage);

    // Insert first key
    let id1 = Uuid::new_v4();
    index
        .index_key("tenant1", "person", id1, "alice@company.com")
        .unwrap();

    let results = index.lookup("alice company", 10).unwrap();
    assert_eq!(results.len(), 1);

    // Insert second key
    let id2 = Uuid::new_v4();
    index
        .index_key("tenant1", "person", id2, "bob@company.com")
        .unwrap();

    // Should now find both
    let results = index.lookup("company", 10).unwrap();
    assert_eq!(results.len(), 2);
}

#[test]
fn test_automatic_index_maintenance_delete() {
    let (storage, _temp) = create_test_storage();
    let index = FuzzyKeyIndex::new(storage);

    let id = Uuid::new_v4();
    index
        .index_key("tenant1", "person", id, "alice@company.com")
        .unwrap();

    // Verify indexed
    let results = index.lookup("alice company", 10).unwrap();
    assert_eq!(results.len(), 1);

    // Remove from index
    index
        .remove_key("tenant1", "person", id, "alice@company.com")
        .unwrap();

    // Should no longer be found
    let results = index.lookup("alice company", 10).unwrap();
    assert_eq!(results.len(), 0);
}

#[test]
fn test_automatic_index_maintenance_update() {
    let (storage, _temp) = create_test_storage();
    let index = FuzzyKeyIndex::new(storage);

    let id = Uuid::new_v4();

    // Initial key
    index
        .index_key("tenant1", "person", id, "alice@oldcompany.com")
        .unwrap();

    // Verify old key found
    let results = index.lookup("oldcompany", 10).unwrap();
    assert_eq!(results.len(), 1);

    // Update: Remove old, add new
    index
        .remove_key("tenant1", "person", id, "alice@oldcompany.com")
        .unwrap();
    index
        .index_key("tenant1", "person", id, "alice@newcompany.com")
        .unwrap();

    // Old key not found
    let old_results = index.lookup("oldcompany", 10).unwrap();
    assert_eq!(old_results.len(), 0);

    // New key found
    let new_results = index.lookup("newcompany", 10).unwrap();
    assert_eq!(new_results.len(), 1);
}

#[test]
fn test_multi_tenant_isolation() {
    let (storage, _temp) = create_test_storage();
    let index = FuzzyKeyIndex::new(storage);

    let id1 = Uuid::new_v4();
    let id2 = Uuid::new_v4();

    index
        .index_key("tenant1", "person", id1, "alice@company.com")
        .unwrap();
    index
        .index_key("tenant2", "person", id2, "alice@company.com")
        .unwrap();

    // Fuzzy lookup returns both tenants
    let results = index.lookup("alice company", 10).unwrap();
    assert_eq!(results.len(), 2);

    // Verify different tenants
    let tenants: Vec<&str> = results.iter().map(|r| r.tenant_id.as_str()).collect();
    assert!(tenants.contains(&"tenant1"));
    assert!(tenants.contains(&"tenant2"));
}

#[test]
fn test_bm25_ranking_quality() {
    let (storage, _temp) = create_test_storage();
    let index = FuzzyKeyIndex::new(storage);

    let id1 = Uuid::new_v4();
    let id2 = Uuid::new_v4();
    let id3 = Uuid::new_v4();

    // Document with all query terms
    index
        .index_key("tenant1", "resource", id1, "rust async tokio tutorial")
        .unwrap();

    // Document with some query terms
    index
        .index_key("tenant1", "resource", id2, "rust programming guide")
        .unwrap();

    // Document with one query term
    index
        .index_key("tenant1", "resource", id3, "python async programming")
        .unwrap();

    // Query: "rust async tokio"
    let results = index.lookup("rust async tokio", 10).unwrap();

    // id1 should rank highest (has all 3 terms)
    assert_eq!(results[0].entity_id, id1);

    // Scores should be descending
    assert!(results[0].score > results[1].score);
    assert!(results[1].score > results[2].score);
}

#[test]
fn test_max_results_limit() {
    let (storage, _temp) = create_test_storage();
    let index = FuzzyKeyIndex::new(storage);

    // Index 10 keys with common term
    for i in 0..10 {
        let id = Uuid::new_v4();
        index
            .index_key(
                "tenant1",
                "person",
                id,
                &format!("user{}@company.com", i),
            )
            .unwrap();
    }

    // Request only top 5
    let results = index.lookup("company", 5).unwrap();

    assert_eq!(results.len(), 5);
}

#[test]
fn test_empty_query() {
    let (storage, _temp) = create_test_storage();
    let index = FuzzyKeyIndex::new(storage);

    let results = index.lookup("", 10).unwrap();
    assert_eq!(results.len(), 0);
}

#[test]
fn test_no_match() {
    let (storage, _temp) = create_test_storage();
    let index = FuzzyKeyIndex::new(storage);

    let id = Uuid::new_v4();
    index
        .index_key("tenant1", "person", id, "alice@company.com")
        .unwrap();

    let results = index.lookup("nonexistent", 10).unwrap();
    assert_eq!(results.len(), 0);
}
