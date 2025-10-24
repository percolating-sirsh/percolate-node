# Implementation Plan - REM Database (Clean Implementation)

**Date:** 2025-10-24
**Version:** 0.1.0
**Status:** Planning Phase

## Overview

This document outlines the implementation plan, design decisions, and open questions for the REM Database clean implementation - a high-performance embedded database combining Rust core with Python ergonomics.

## Design Questions

### 1. Dependency Choices

**Question:** Should we use `hnsw` crate or `hnswlib-rs` for vector indexing?

**Options:**
- `hnsw` (0.11): Pure Rust, smaller dependency tree
- `hnswlib-rs`: Bindings to C++ hnswlib (faster, more mature)

**Recommendation:** Start with `hnsw` for pure Rust benefits. Benchmark against hnswlib if performance targets not met.

**Related NB:** Performance target is < 5ms for 1M docs (200x speedup over naive scan)

---

**Question:** For SQL parsing, should we use `sqlparser` or write a custom parser?

**Options:**
- `sqlparser` crate: Full-featured, handles complex SQL
- Custom parser: Only parse subset we need (SELECT, WHERE, ORDER BY, LIMIT)

**Recommendation:** Use `sqlparser` crate. Complexity is minimal and future-proofs for advanced features.

---

**Question:** Should we support both local embeddings (fastembed) and OpenAI from day 1?

**Options:**
- Local only initially (simpler, offline-capable)
- Both from start (more flexible, matches README examples)

**Recommendation:** Implement both. Provider pattern makes this straightforward and README shows both use cases.

**Related NB:** Always batch embeddings - never individual requests (README line 344)

---

### 2. Storage Architecture

**Question:** How should we handle tenant isolation in RocksDB?

**Options:**
1. **Separate databases per tenant** - One RocksDB instance per tenant
2. **Tenant prefix in keys** - Single DB, keys prefixed with `{tenant_id}:`
3. **Hybrid** - Column family per tenant (limited by CF count)

**Recommendation:** Tenant prefix in keys (Option 2)
- Simpler operations (single DB to manage)
- No CF limit issues
- Easy cross-tenant operations if needed later
- All keys already include tenant_id in encoding

**Trade-off:** Slightly larger keys (~20 bytes overhead) vs operational simplicity

---

**Question:** Should we use MessagePack, Bincode, or JSON for entity serialization?

**Options:**
- JSON: Human-readable, debuggable, slower
- Bincode: Fast, compact, not human-readable
- MessagePack: Compact, language-agnostic

**Recommendation:**
- **Entities CF:** JSON (debuggability during development, acceptable perf)
- **Embeddings CF:** Raw binary `[f32]` (3x compression, zero-copy)
- **WAL CF:** Bincode (speed critical for replication)

---

**Question:** How should we implement the key index for global lookups?

**Options:**
1. **Column Family** - Separate `key_index` CF (README approach)
2. **Multi-Get** - Store key->id mapping in entity properties, multi-get all schemas
3. **Bloom Filter + Scan** - Bloom filter to skip schemas, then scan

**Recommendation:** Column Family (Option 1) as per README
- O(log n) lookup vs O(schemas) multi-get
- Follows architecture from README/CLAUDE.md
- Small storage overhead (~10%) acceptable

**Related NB:** Precedence for deterministic UUID is uri -> key_field -> key -> name (README line 276)

---

### 3. Embedding Strategy

**Question:** When should embeddings be generated - at insert time or lazily?

**Options:**
- **Eager** (insert time): Consistent UX, higher insert latency
- **Lazy** (first search): Lower insert latency, search requires generation
- **Background** (async worker): Complex, eventual consistency

**Recommendation:** Eager at insert time
- Simpler model (no background workers)
- Batching makes latency acceptable (< 50ms for network call)
- Search always fast (no generation needed)

**Related NB:** Always use batch embeddings API (README line 344)

---

**Question:** Should we cache embedding models (local) or reload per operation?

**Options:**
- Cache in memory (fast, uses RAM)
- Reload per batch (slower, no memory overhead)
- LRU cache (balanced)

**Recommendation:** Cache in memory (singleton pattern)
- Local models are ~100MB (acceptable)
- Reload would add 500ms+ latency per operation
- Use lazy_static or OnceCell for initialization

---

### 4. HNSW Index Management

**Question:** When should HNSW index be built - at startup or on-demand?

**Options:**
1. **Lazy build** - Build when first search happens
2. **Startup build** - Load/rebuild at database open
3. **Incremental** - Update index on each insert

**Recommendation:** Incremental updates (Option 3)
- Add to index immediately on insert with embedding
- Persist index to disk on flush/close
- Load from disk on startup (if exists)

**Trade-off:** Slightly slower inserts (~1ms) vs always-ready search

---

**Question:** Should we support multiple HNSW indexes (one per schema with embeddings)?

**Options:**
- Single global index (all embeddings together)
- One index per schema with `embedding_fields`

**Recommendation:** One index per schema
- Natural isolation (schema -> index mapping)
- Smaller indexes = faster search for single schema
- Matches `--schema` parameter in search CLI

**Implementation:** Store indexes in `{db_path}/indexes/{schema_name}.hnsw`

---

### 5. Schema Validation

**Question:** Should we validate entities at Python or Rust layer?

**Options:**
- **Python** (Pydantic): Validates before Rust, type-safe
- **Rust** (jsonschema crate): Validates in Rust, single source of truth
- **Both**: Double validation (safest, slowest)

**Recommendation:** Rust only (Option 2)
- Single source of truth (schema stored in Rust DB)
- Prevents Python bypass (if someone calls Rust directly)
- Pydantic used for schema *generation* only

**Related NB:** Rust drives things with Pydantic-aware JSON Schema semantics (README line 272)

---

**Question:** How should we handle schema evolution and versioning?

**Options:**
1. **No versioning** - Schema changes break existing data
2. **Version in json_schema_extra** - Track version, no migration
3. **Migration support** - Full schema migration framework

**Recommendation:** Version tracking (Option 2) for v0.1
- Store version in `json_schema_extra` (already in examples)
- Validate version matches on operations
- Migration support deferred to v0.2

---

### 6. Replication Protocol

**Question:** Should WAL use gRPC streaming or pull-based sync?

**Options:**
- **gRPC streaming** (README approach): Real-time, low latency
- **Pull-based**: Simpler, works through firewalls
- **Hybrid**: Stream + pull fallback

**Recommendation:** gRPC streaming (per README)
- Low latency (< 10ms lag target)
- Bi-directional (server can push to replicas)
- Use `tonic` for async Rust gRPC

---

**Question:** Should replicas be read-only or support writes with conflict resolution?

**Options:**
- Read-only replicas (simpler)
- Multi-master with CRDT (complex)

**Recommendation:** Read-only replicas for v0.1 (per README examples)
- Simpler implementation
- No conflict resolution needed
- Matches primary/replica mode from README

---

### 7. CLI Design

**Question:** Should CLI spawn server process or use embedded database?

**Options:**
- Embedded (direct DB access)
- Client-server (spawn background process)

**Recommendation:** Embedded for v0.1
- Simpler UX (no server management)
- Matches SQLite model
- Server mode only for replication (`rem serve`)

---

**Question:** How should `rem ask --plan` work without executing?

**Implementation:**
- Call LLM to generate query plan
- Return plan JSON without calling query executor
- `--plan` flag controls whether to execute query from plan

---

### 8. Performance Targets

**Question:** Are the performance targets realistic for v0.1?

**Targets from README:**
- Insert (no embedding): < 1ms
- Insert (with embedding): < 50ms (network-bound)
- Get by ID: < 0.1ms
- Vector search (1M docs): < 5ms (200x speedup)
- SQL query (indexed): < 10ms
- Graph traversal (3 hops): < 5ms
- Batch insert (1000 docs): < 500ms
- Parquet export (100k rows): < 2s

**Recommendation:** Target all for v0.1 except:
- Defer 1M vector search to v0.2 (start with 100k)
- Defer Parquet export optimization (start with baseline impl)

**Rationale:** Focus on correctness first, then optimize hot paths

---

## Implementation Order

### Phase 1: Core Foundation (Week 1)
1. Storage layer (RocksDB wrapper, column families, key encoding)
2. **Background worker** (task queue, async operations) - **CRITICAL FOR PERFORMANCE**
3. Entity CRUD operations (insert, get, update, delete)
4. Basic tests (test_crud.rs, test_worker.rs)

**Validation:** Can insert and retrieve entities, worker processes tasks

**Why worker in Phase 1:**
- Enables non-blocking index saves (critical for insert performance)
- Required for async HNSW loading (fast database startup)
- Foundation for future async embedding generation
- Python spike shows ~3-5x insert speedup with background saves

### Phase 2: Indexing (Week 2)
4. Field indexer (SQL predicates)
5. Key index (global lookups)
6. Basic query execution (SELECT with WHERE)
7. Tests (test_query.rs)

**Validation:** Can run SQL queries on indexed fields

### Phase 3: Vector Search (Week 3)
8. Embedding provider trait
9. Local embeddings (fastembed)
10. OpenAI embeddings
11. **HNSW index integration** (with async loading/saving)
12. **Batch embedder** (with async generation support)
13. Search API
14. Tests (test_search.rs)

**Validation:** Can search by semantic similarity, async index operations work

**Key features:**
- HNSW index loads asynchronously on startup (fast DB open)
- Index saves happen in background worker (non-blocking inserts)
- Embedding generation can be async (future optimization)

### Phase 4: Schema & Python Bindings (Week 4)
14. Schema registry with categories (System/Agents/Public/User)
15. Built-in schemas auto-registration (schemas, documents, resources)
16. Pydantic parser with agent-let support (tools/resources extraction)
17. Schema validator with field description checks
18. PyO3 bindings (Database wrapper)
19. Python package (cli.py, models.py)
20. Tests (test_schema.rs - 40 tests, test_api.py, test_cli.py)

**Validation:** Python API works end-to-end, built-in schemas registered, agent-lets load correctly

### Phase 5: Graph Operations (Week 5)
19. Edge manager (bidirectional edges)
20. Graph traversal (BFS/DFS)
21. Tests (test_graph.rs)

**Validation:** Can traverse graph relationships

### Phase 6: Export & Ingest (Week 6)
22. Document chunking
23. PDF parsing
24. Parquet export
25. CSV/JSONL export
26. Tests (test_export.rs)

**Validation:** Can ingest documents and export data

### Phase 7: Replication (Week 7)
27. Write-ahead log (WAL) - Use AtomicU64 for sequences, bincode serialization
28. Create proto/replication.proto and add tonic-build to Cargo.toml
29. Primary node with tokio broadcast channel (fan-out to replicas)
30. Replica node with auto-reconnect and idempotent apply
31. Sync state machine (Disconnected/Connecting/Syncing/Streaming/Error)
32. Tests (test_replication.rs)

**Validation:** Can replicate data between nodes, lag < 10ms, auto-reconnect works

**Note:** See docs/replication.md for WAL structure (WalEntry needs entity_id, entity_type, data fields)

### Phase 8: LLM & Polish (Week 8)
32. LLM query builder (OpenAI integration)
33. Query planner
34. Async API wrappers
35. Performance benchmarks
36. Documentation

**Validation:** All tests pass, performance targets met

---

## Open Questions

### Critical (Must Resolve Before Implementation)

1. **gRPC Proto Definitions**: Where should `proto/replication.proto` live? In src/ or separate directory?
   - **Recommendation:** `proto/` directory at root, generated code in `src/replication/protocol.rs`

2. **Error Handling Strategy**: Should we use `anyhow` for internal errors or always use `DatabaseError`?
   - **Recommendation:** `DatabaseError` throughout (already defined), `anyhow` only in examples/tests

3. **Async Runtime**: Should PyO3 async use `tokio` or `async-std`?
   - **Recommendation:** `tokio` (more popular, better ecosystem, already in Cargo.toml)

### Important (Can Defer)

4. **Compression**: Should we compress entity JSON in storage?
   - **Initial:** No compression (simpler, debuggable)
   - **Future:** LZ4 compression for entities (configurable)

5. **Caching**: Should we cache frequently accessed entities in memory?
   - **Initial:** No caching (RocksDB block cache sufficient)
   - **Future:** LRU cache for hot entities (optional optimization)

6. **Observability**: How should we expose metrics and tracing?
   - **Initial:** Basic logging with `tracing` crate
   - **Future:** Prometheus metrics export

### Nice to Have

7. **Multi-tenancy**: Should we support JWT-based auth for tenant isolation?
   - **Deferred to v0.2:** Focus on embedded use case first

8. **Backup/Restore**: Should we implement snapshot functionality?
   - **Deferred to v0.2:** RocksDB backup API integration

9. **Query Optimizer**: Should we build a cost-based query optimizer?
   - **Deferred to v0.2:** Start with rule-based planning

---

## Key Implementation Notes (NBs from README)

### NB 1: Field Configuration (Line 260)
"While we support adding metadata in config. Fields can also take properties like key-field and embedding_provider as json schema extra and is preferred."

**Implementation:**
- Support both `model_config.json_schema_extra` AND field-level `json_schema_extra`
- Field-level takes precedence
- Example:
  ```python
  uri: str = Field(json_schema_extra={"key_field": True})
  ```

---

### NB 2: Pydantic-Driven Schema (Line 272)
"Rust can also define schema in equivalent mode classes or schema but we drive things with pydantic aware semantics of the json schema format."

**Implementation:**
- Rust never defines schemas - only validates against JSON Schema
- All schemas originate from Pydantic models
- `PydanticSchemaParser` extracts metadata from `json_schema_extra`

---

### NB 3: UUID Precedence (Line 276)
"Precedence; uri -> key -> name unless specified in config."

**Implementation:**
- Check fields in order: `uri`, `json_schema_extra.key_field`, `key`, `name`
- Use first non-null value for deterministic UUID
- If none present, generate random UUID v4

**Code location:** `src/storage/keys.rs::deterministic_uuid()`

---

### NB 4: Batch Operations (Line 344)
"WE generally work in batches; batch upserts and batch embeddings. NEVER make individual requests when batches are possible."

**Implementation:**
- `insert_batch()` required in all APIs
- Embedding providers must support `embed_batch()`
- Single OpenAI API call for entire batch
- Batch size configurable (default: 100 from env `P8_EMBEDDING_BATCH_SIZE`)

**Code location:** `src/embeddings/batch.rs::BatchEmbedder`

---

## Critical Path

The critical path for achieving a working v0.1:

1. **Storage + CRUD** (Week 1) - Foundation for everything
2. **Schema + Validation** (Part of Week 4) - Required for entity operations
3. **Embeddings + Search** (Week 3) - Core value proposition
4. **Python Bindings** (Week 4) - User-facing API
5. **CLI** (Part of Week 4) - Primary UX

Everything else (graph, replication, export, LLM) can be deferred if needed.

---

## Risk Assessment

### High Risk
- **HNSW Performance**: May not hit 5ms target for 1M docs
  - **Mitigation:** Start with 100k docs, optimize incrementally

- **PyO3 Async**: Complex to get tokio<->asyncio working correctly
  - **Mitigation:** Use `pyo3-asyncio` crate, follow examples

### Medium Risk
- **gRPC Replication**: Networking and state machine complexity
  - **Mitigation:** Follow tonic examples closely, extensive testing

- **Schema Evolution**: May need migrations sooner than expected
  - **Mitigation:** Design for forward compatibility from start

### Low Risk
- **SQL Parsing**: `sqlparser` crate handles this
- **Export Formats**: Well-established crates (parquet, csv)

---

## Success Criteria

### Minimum Viable (v0.1)
- [ ] Insert entities with automatic embeddings
- [ ] Search by semantic similarity (100k docs)
- [ ] SQL queries with indexed fields
- [ ] Python API and CLI work
- [ ] Pass all integration tests

### Target (v0.1)
- All minimum viable criteria plus:
- [ ] Graph traversal operations
- [ ] Document ingestion with chunking
- [ ] Export to Parquet/CSV
- [ ] Performance targets met (except 1M docs)

### Stretch (v0.1)
- All target criteria plus:
- [ ] Peer replication working
- [ ] LLM query builder (`rem ask`)
- [ ] 1M doc vector search in < 5ms

---

## Updates from Iterated Retrieval Document

### Critical Additions to Implementation

After reviewing `/docs/iterated-retrieval.md`, the following features must be added:

#### 1. Multi-Stage Query Execution

**Requirement:** LLM query builder must support staged retrieval (not just single-shot)

**Implementation Changes:**
- Add `max_stages` parameter to `LlmQueryBuilder`
- Track stage results and retry with broader queries
- Return metadata showing which stage succeeded

**Code Location:** `src/llm/query_builder.rs`

```rust
pub struct QueryResult {
    pub results: Vec<Entity>,
    pub query: String,
    pub query_type: QueryType,
    pub confidence: f64,
    pub stages: usize,
    pub stage_results: Vec<usize>,
    pub total_time_ms: u64,
}
```

---

#### 2. Confidence Scoring System

**Requirement:** All LLM queries return confidence scores with explanation if < 0.6

**Confidence Levels:**
- `1.0` - Exact ID lookup
- `0.8-0.95` - Clear field-based query
- `0.6-0.8` - Semantic/vector search
- `< 0.6` - Ambiguous (explanation required)

**Implementation Changes:**
- Add `confidence` field to `QueryPlan` struct (already in stub)
- Enforce explanation when confidence < 0.6
- Add `is_confident()` and `needs_confirmation()` helpers (already stubbed)

**Code Location:** `src/llm/planner.rs` (already has confidence field)

---

#### 3. Entity Lookup Query Type

**New Query Type:** Schema-agnostic key lookup using `key_index` CF

**Implementation:**
```rust
pub enum QueryType {
    EntityLookup,  // NEW - global key lookup
    Sql,           // Existing
    Vector,        // Existing
    Hybrid,        // Existing
}
```

**Detection Pattern:** `^\w+[-_]?\w+$` (identifier-like queries)

**Examples:**
- `rem ask "111213"` → Entity lookup across all schemas
- `rem ask "ABS-234"` → Entity lookup
- `rem ask "bob"` → Entity lookup

**Code Location:**
- `src/llm/planner.rs` - Add EntityLookup variant
- `src/index/keys.rs` - Already has `lookup()` method stubbed

---

#### 4. Batch Key Lookup

**Requirement:** Efficient batch lookup for multiple keys (performance-critical)

**Implementation:**
```rust
// src/index/keys.rs
pub fn lookup_batch(&self, keys: &[String]) -> Result<Vec<(String, String, Uuid)>> {
    // Returns: (tenant_id, entity_type, entity_id) for each match
    // Uses parallel prefix scans for each key
}
```

**Performance Target:** ~1ms for 10 keys (parallel lookups)

**Code Location:** `src/index/keys.rs::KeyIndex::lookup_batch()`

---

#### 5. Schema Embedding for Discovery

**Requirement:** Embed schema descriptions for semantic schema search when >10 schemas registered

**Why:** With 100+ schemas, can't brute force search all of them

**Implementation:**
1. When schema registered, extract description field
2. Generate embedding for description
3. Store in separate HNSW index: `{db_path}/indexes/_schemas.hnsw`
4. When query is ambiguous, search schema embeddings first
5. Execute query against top 3-5 most relevant schemas

**Configuration:**
```bash
export P8_SCHEMA_BRUTE_FORCE_LIMIT=10  # Use brute force if ≤10 schemas
export P8_SCHEMA_SEARCH_TOP_K=3        # Search top 3 schemas
```

**Code Location:**
- `src/schema/registry.rs` - Add schema embedding on registration
- `src/llm/query_builder.rs` - Add schema discovery logic

---

#### 6. Query Response Metadata

**Requirement:** All query responses include execution metadata

**Response Format:**
```json
{
  "results": [...],
  "query": "SELECT * FROM articles WHERE category = 'tutorial'",
  "query_type": "sql",
  "confidence": 0.85,
  "stages": 2,
  "stage_results": [0, 15],
  "total_time_ms": 1250,
  "explanation": null  // Only if confidence < 0.6
}
```

**Code Location:**
- `src/llm/planner.rs::QueryPlan` - Already has most fields
- Add `stage_results`, `total_time_ms` fields

---

#### 7. CLI Parameter Updates

**New Parameters:**
```bash
rem ask "query" --max-stages 3      # Multi-stage retrieval
rem ask "query" --schema employees  # Schema hint for faster lookup
rem ask "query" --model gpt-3.5     # Model override
```

**Code Location:** `python/rem_db/cli.py::ask()` command

---

### Updated Implementation Order

**Phase 8 (LLM & Polish) now becomes more complex:**

**Week 8a: Core LLM (3 days)**
1. Basic query builder (single-stage)
2. Confidence scoring
3. Query plan generation

**Week 8b: Advanced LLM (4 days)**
4. Multi-stage execution
5. Entity lookup detection
6. Schema discovery (brute force + semantic)
7. Response metadata

**Phase 8 is now blocking** for full `rem ask` functionality

---

### New Design Questions

**Question:** Should schema embeddings use same provider as entity embeddings?

**Options:**
- Same provider (simpler)
- Separate provider (flexibility)

**Recommendation:** Same provider for v0.1
- Simpler configuration
- Schemas are small (~10-100), embedding cost negligible
- Can split later if needed

---

**Question:** Should we implement fuzzy key lookup in v0.1?

**Options from iterated-retrieval.md:**
1. Trigram indexing (PostgreSQL style)
2. BK-Tree (Levenshtein distance)
3. Tantivy sidecar (full-text search)
4. Use vector search as workaround

**Recommendation:** Use vector search workaround (Option 4) for v0.1
- Already have HNSW index
- Just embed name fields
- Defer proper fuzzy search to v0.2
- Document limitation in README

**Rationale:** Fuzzy search is complex and not critical path. Vector search provides "good enough" typo tolerance for initial release.

---

**Question:** What should `P8_SCHEMA_BRUTE_FORCE_LIMIT` default be?

**Options:**
- 5 schemas (conservative)
- 10 schemas (balanced, from doc)
- 20 schemas (aggressive)

**Recommendation:** 10 schemas (per iterated-retrieval.md)
- Reasonable for most use cases
- ~1ms total for 10 parallel lookups
- Configurable via environment variable

---

### Updated Risk Assessment

**New High Risk:**
- **Multi-stage LLM execution** - Complex state management across stages
  - **Mitigation:** Start with 2-stage (primary + fallback), expand later

- **Schema semantic search** - Requires HNSW index for schemas
  - **Mitigation:** Defer to v0.2 if time constrained, use brute force only

**New Medium Risk:**
- **Entity lookup detection** - Regex pattern may be too simple
  - **Mitigation:** Start with simple pattern, refine based on user feedback

---

### Updated Success Criteria

**Minimum Viable (v0.1) - UPDATED:**
- All previous criteria plus:
- [ ] Background worker for async operations
- [ ] Async HNSW index loading (fast startup)
- [ ] Non-blocking index saves (fast inserts)
- [ ] `rem ask` with confidence scoring
- [ ] Entity lookup query type (global key search)
- [ ] Schema hint support (`--schema` flag)

**Target (v0.1) - UPDATED:**
- All minimum viable criteria plus:
- [ ] Multi-stage query execution (2 stages)
- [ ] Query response metadata
- [ ] Brute force schema discovery (≤10 schemas)

**Stretch (v0.1) - UPDATED:**
- All target criteria plus:
- [ ] Semantic schema search (>10 schemas)
- [ ] 3+ stage execution
- [ ] Fuzzy key lookup (proper implementation)

---

## Background Worker Implementation (CRITICAL)

### Overview

Background worker added to Phase 1 as **critical performance component**.

### Architecture

```rust
pub struct BackgroundWorker {
    tx: mpsc::UnboundedSender<(Task, Option<TaskCallback>)>,
    status: Arc<RwLock<WorkerStatus>>,
    semaphore: Arc<Semaphore>,
    handle: Option<JoinHandle<()>>,
}

pub enum Task {
    SaveIndex { schema: String, index_path: PathBuf },
    LoadIndex { schema: String, index_path: PathBuf },
    GenerateEmbeddings { entity_ids: Vec<Uuid>, texts: Vec<String>, schema: String },
    FlushWal,
    CompactCF { cf_name: String },
    Shutdown,
}
```

### Integration Points

**1. HNSW Index (src/index/hnsw.rs)**
- Async loading: `load_async(path, &worker)` - loads index in background on startup
- Async saving: `save_async(&worker)` - saves index after upserts without blocking
- State tracking: `IndexState` enum (NotLoaded, Loading, Ready, Error)
- Wait for ready: `wait_ready(timeout)` - blocks search until index loaded

**2. Batch Embedder (src/embeddings/batch.rs)**
- Async generation: `embed_async(entity_ids, texts, &worker)` - generates embeddings in background
- Pending cache: `HashMap<Uuid, Vec<f32>>` - tracks in-flight embeddings
- Non-blocking inserts: Entity created immediately, embedding added later
- Future optimization: Currently sync, infrastructure ready for async

**3. Storage (src/storage/mod.rs)**
- Exports worker types: `BackgroundWorker`, `Task`, `TaskResult`, `WorkerStatus`
- Worker lifecycle managed by database instance
- Graceful shutdown on database close

### Performance Impact

**Without worker (blocking saves):**
- Insert with embedding: ~100-150ms (50ms embed + 50-100ms index save)
- Database startup: ~5-10s (load all indexes)
- User experience: Laggy inserts, slow startup

**With worker (async saves):**
- Insert with embedding: ~50-60ms (50ms embed, save in background)
- Database startup: < 100ms (indexes load in background)
- User experience: Fast inserts, instant startup

**Speedup: 2-3x for inserts, 50-100x for startup**

### Implementation Timeline

**Week 1 (Phase 1):**
- Day 1-2: Storage layer basics
- Day 3-4: **Background worker** (task queue, execution loop)
- Day 5-6: Entity CRUD with worker integration
- Day 7: Testing (test_worker.rs)

**Week 3 (Phase 3):**
- Integrate worker with HNSW index
- Integrate worker with batch embedder
- Test async loading/saving

### Testing Strategy

**Worker tests (test_worker.rs):**
- Lifecycle (start, submit, shutdown)
- Task execution (all task types)
- Wait idle (timeout handling)
- Error handling (task failures)
- Callbacks (completion notification)
- Concurrency (thread-safe submission)

**Integration tests:**
- test_search.rs: Async index loading
- test_crud.rs: Non-blocking index saves
- test_end_to_end.py: Full workflow with worker

---

## Next Steps

1. **Resolve critical questions** (gRPC proto location, async runtime)
2. **Set up build toolchain** (cargo build, maturin develop)
3. **Start Phase 1** (storage layer + **background worker**)
4. **Create proto files** (if using gRPC)
5. **Set up CI** (GitHub Actions for testing)
6. **Review iterated-retrieval.md impact** ✓ DONE
7. **Review python-reflection.md impact** ✓ DONE - **Worker added to Phase 1**

---

## Notes for Review

This plan assumes:
- 8 week timeline for v0.1 (may need +1 week for LLM complexity)
- Single developer (can parallelize some tasks)
- Focus on correctness over optimization
- Iterative approach (get working, then optimize)

**Questions for team review:**
1. Is 8-9 week timeline realistic (updated for LLM complexity)?
2. Should we cut any features from v0.1?
3. Are performance targets too aggressive?
4. Should we support Windows (currently UNIX-focused)?
5. **NEW:** Should schema semantic search be v0.1 or v0.2?
6. **NEW:** Is fuzzy key lookup critical for v0.1?
