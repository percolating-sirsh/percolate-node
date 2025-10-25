# Tiered Memory Architecture

**Status:** Design Phase
**Created:** 2025-10-25
**Target:** v0.4.0

## Overview

Hybrid vector search architecture combining **HNSW for hot data** (recent N days) with **DiskANN for cold data** (historical). This enables sub-millisecond search on recent data while maintaining access to full history in memory-constrained environments (K8s pods).

## Problem Statement

| Requirement | HNSW Only | DiskANN Only | Hybrid |
|-------------|-----------|--------------|--------|
| Fast recent search (<1ms) | ✅ | ❌ (5ms) | ✅ |
| Low memory (256MB pod) | ❌ (1.5GB) | ✅ (251MB) | ✅ (125MB) |
| Full history access | ❌ (OOM) | ✅ | ✅ |
| Fast startup (<5s) | ❌ (30s) | ✅ (<1s) | ✅ (5s) |

**Hybrid wins on all dimensions.**

## Architecture

### Data Partitioning

```
Timeline:
├─ Hot Zone (last 30 days)  → HNSW index (in-memory)
└─ Cold Zone (older)        → DiskANN index (mmap)

Example (1M total vectors):
├─ Hot: 100k vectors × 1.5KB = 150MB RAM
└─ Cold: 900k vectors × 0.25KB = 225MB mmap (25MB resident)
Total: 175MB RAM (vs 1.5GB HNSW-only)
```

### Search Flow

```rust
pub async fn tiered_search(
    &self,
    query: &[f32],
    top_k: usize,
    config: &TieredSearchConfig,
) -> Result<Vec<(Uuid, f32)>> {
    // 1. Search hot HNSW index (fast)
    let hot_results = self.hnsw_index
        .search(query, top_k)
        .await?;

    // 2. Search cold DiskANN index (slower, but acceptable)
    let cold_results = self.diskann_index
        .search(query, top_k)
        .await?;

    // 3. Merge and re-rank by score
    let merged = merge_results(hot_results, cold_results, top_k);

    Ok(merged)
}
```

### Background Refresh

```rust
/// Background worker that rebuilds HNSW index periodically
async fn refresh_hot_index(
    storage: Arc<Storage>,
    config: TieredSearchConfig,
) -> Result<()> {
    loop {
        tokio::time::sleep(Duration::from_secs(config.refresh_interval_secs)).await;

        // 1. Query entities from last N days
        let cutoff = Utc::now() - Duration::days(config.hot_data_days as i64);
        let hot_entities = storage.query_range("created_at", cutoff, Utc::now())?;

        // 2. Rebuild HNSW index
        let mut new_index = HnswIndex::new(dimensions, hot_entities.len());
        new_index.build_from_vectors(hot_entities).await?;

        // 3. Atomic swap
        self.hnsw_index.store(Arc::new(new_index));

        log::info!("Refreshed hot index: {} vectors", hot_entities.len());
    }
}
```

## Implementation Plan

### Phase 1: Tiered Search Layer (3 hours)

**File:** `src/index/tiered.rs`

```rust
pub struct TieredIndex {
    /// Hot data index (HNSW, recent N days)
    hot: Arc<RwLock<HnswIndex>>,

    /// Cold data index (DiskANN, historical)
    cold: Arc<DiskAnnIndex>,

    /// Configuration
    config: TieredSearchConfig,

    /// Refresh task handle
    refresh_task: Option<JoinHandle<()>>,
}

impl TieredIndex {
    pub fn new(config: TieredSearchConfig) -> Self;
    pub async fn build(&mut self, vectors: Vec<(Uuid, Vec<f32>)>) -> Result<()>;
    pub async fn search(&self, query: &[f32], top_k: usize) -> Result<Vec<(Uuid, f32)>>;
    pub async fn refresh_hot_index(&mut self) -> Result<()>;
}
```

### Phase 2: Time-Range Queries (2 hours)

**File:** `src/storage/time_range.rs`

```rust
impl Storage {
    /// Query entities by time range using indexed `created_at` field
    pub fn query_time_range(
        &self,
        start: DateTime<Utc>,
        end: DateTime<Utc>,
    ) -> Result<Vec<Entity>> {
        let start_key = format!("idx:created_at:{}", start.to_rfc3339());
        let end_key = format!("idx:created_at:{}", end.to_rfc3339());

        let iter = self.range_iterator(CF_INDEXES, &start_key, &end_key);
        // ... collect entities
    }
}
```

### Phase 3: Score Fusion (1 hour)

**File:** `src/index/tiered.rs`

```rust
/// Merge results from hot and cold indexes
fn merge_results(
    hot: Vec<(Uuid, f32)>,
    cold: Vec<(Uuid, f32)>,
    top_k: usize,
) -> Vec<(Uuid, f32)> {
    use std::collections::BinaryHeap;

    let mut heap = BinaryHeap::new();

    // Add all results to heap
    for (id, score) in hot.into_iter().chain(cold.into_iter()) {
        heap.push((OrderedFloat(-score), id));  // Min heap by score
    }

    // Take top K
    heap.into_sorted_vec()
        .into_iter()
        .take(top_k)
        .map(|(score, id)| (id, -score.0))
        .collect()
}
```

### Phase 4: Database Integration (2 hours)

**File:** `src/database.rs`

```rust
impl Database {
    pub async fn search(
        &self,
        tenant_id: &str,
        table: &str,
        query: &str,
        top_k: usize,
    ) -> Result<Vec<(Entity, f32)>> {
        // Check if tiered search is enabled
        if self.config.enable_tiered_search {
            self.tiered_index.search(query_embedding, top_k).await
        } else {
            // Fallback to HNSW or DiskANN only
            self.hnsw_index.search(query_embedding, top_k).await
        }
    }
}
```

## Configuration

### Environment Variables

```bash
# Enable tiered search
P8_TIERED_SEARCH=true

# Hot data age threshold (days)
P8_HOT_DATA_DAYS=30

# Maximum hot index size (vectors)
P8_MAX_HOT_VECTORS=100000

# Auto-refresh interval (seconds)
P8_REFRESH_INTERVAL=3600
```

### TOML Configuration

```toml
[search]
tiered = true
hot_data_days = 30
max_hot_vectors = 100000
refresh_interval_secs = 3600

[search.hot]
# HNSW configuration for hot data
m = 16
ef_construction = 200
ef_search = 64

[search.cold]
# DiskANN configuration for cold data
R = 64
L = 100
alpha = 1.2
```

## Memory Analysis

### Example: 1M vectors, 384 dimensions

| Component | Vectors | Memory | Calculation |
|-----------|---------|--------|-------------|
| **Hot HNSW** | 100k | 150 MB | 100k × 1.5KB |
| **Cold DiskANN** | 900k | 225 MB (mmap) | 900k × 0.25KB |
| **Resident** | - | **175 MB** | 150MB + 25MB (10% resident) |

**Comparison:**
- HNSW-only: 1.5GB RAM ❌
- DiskANN-only: 251MB RAM ✅
- **Hybrid: 175MB RAM** ✅✅ (89% reduction vs HNSW)

## Performance Characteristics

### Search Latency

| Data Age | Index | Latency | % of Queries |
|----------|-------|---------|--------------|
| Last 30 days | HNSW | <1ms | 80% (typical workload) |
| Older | DiskANN | ~5ms | 20% |
| **Avg** | **Hybrid** | **<2ms** | **100%** |

### Startup Time

| Operation | Time | Why |
|-----------|------|-----|
| Load DiskANN (mmap) | <1s | Memory-mapped, lazy load |
| Build HNSW (100k) | 5s | In-memory construction |
| **Total** | **~5s** | Acceptable for K8s pod restart |

## K8s Deployment

### Pod Sizing

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: rem-db-pod
spec:
  containers:
  - name: rem-db
    image: rem-db:latest
    resources:
      requests:
        memory: "256Mi"  # Fits comfortably!
        cpu: "500m"
      limits:
        memory: "512Mi"
        cpu: "1000m"
    env:
    - name: P8_TIERED_SEARCH
      value: "true"
    - name: P8_HOT_DATA_DAYS
      value: "30"
```

## Testing Plan

### Unit Tests

```rust
#[tokio::test]
async fn test_tiered_search_hot_path() {
    // Recent data should hit HNSW
    let db = Database::open_temp("test").unwrap();
    db.insert("docs", json!({"content": "Recent doc", "created_at": Utc::now()})).await.unwrap();

    let results = db.search("docs", "Recent", 5).await.unwrap();
    assert!(results[0].1 < 0.001);  // Fast, accurate
}

#[tokio::test]
async fn test_tiered_search_cold_path() {
    // Old data should hit DiskANN
    let db = Database::open_temp("test").unwrap();
    let old_date = Utc::now() - Duration::days(60);
    db.insert("docs", json!({"content": "Old doc", "created_at": old_date})).await.unwrap();

    let results = db.search("docs", "Old", 5).await.unwrap();
    assert!(results[0].1 < 0.01);  // Slower, but still good
}

#[tokio::test]
async fn test_score_fusion() {
    // Both hot and cold should merge correctly
    let hot = vec![(uuid1, 0.1), (uuid2, 0.3)];
    let cold = vec![(uuid3, 0.2), (uuid4, 0.4)];

    let merged = merge_results(hot, cold, 3);
    assert_eq!(merged.len(), 3);
    assert_eq!(merged[0].0, uuid1);  // Best score
}
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_tiered_search_e2e(db):
    # Insert mix of recent and old docs
    recent_id = db.insert("docs", {"content": "Recent AI news", "created_at": datetime.now()})
    old_id = db.insert("docs", {"content": "Old AI news", "created_at": datetime.now() - timedelta(days=60)})

    # Search should find both
    results = await db.search("docs", "AI news", top_k=10)
    ids = [r[0] for r in results]
    assert recent_id in ids
    assert old_id in ids

    # Recent should score higher (recency bias)
    assert results[0][0] == recent_id
```

## Migration Strategy

### Phase 1: Implement Core (This Sprint)
- Tiered index structure
- Time-range queries
- Score fusion

### Phase 2: Background Refresh (Next Sprint)
- Background worker
- Atomic index swap
- Graceful degradation

### Phase 3: Production Hardening
- Metrics and monitoring
- Auto-tuning hot data threshold
- Adaptive K8s resource requests

## Success Metrics

- ✅ 256MB pod memory (down from 1.5GB)
- ✅ <2ms avg search latency (80% <1ms, 20% <5ms)
- ✅ <5s startup time
- ✅ 100% historical data accessible
- ✅ Zero OOM errors on small K8s pods

## Related Work

- **Qdrant**: Uses similar tiered approach with quantization
- **Weaviate**: Implements hot/cold storage for vectors
- **Milvus**: Supports data tiering with different index types

---

**Next Steps:**
1. Implement `TieredIndex` struct
2. Add time-range query support
3. Implement score fusion
4. Integration tests
5. K8s deployment validation
