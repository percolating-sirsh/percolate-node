# Roadmap

## Completed: v0.3.0 - Replication (Core Complete)

**Status:** Core implementation done, integration tests deferred
**Completed:** November 2024

### ✅ Completed

| Task | File | Status |
|------|------|--------|
| Replica WAL application | `src/replication/replica.rs:165-196` | ✅ Done |
| Lag calculation | `src/replication/replica.rs:230-258` | ✅ Done |
| WAL serialization fix (bincode → JSON) | `src/replication/wal.rs` | ✅ Done |
| WAL test updates (Arc<Storage>) | `src/replication/wal.rs` (7 tests passing) | ✅ Done |

**Key Changes:**
- Replica node applies WAL operations to local Database (Insert/Update/Delete)
- Lag tracking with GetStatus RPC call to primary
- Fixed WAL serialization to support `serde_json::Value` (switched from bincode to JSON)
- All 7 WAL unit tests passing

### Deferred to Later

| Task | File | Effort | Reason |
|------|------|--------|--------|
| Integration tests | `tests/rust/test_replication.rs` | 4h | Focus on vector search features |
| Track replica count | `src/replication/primary.rs:203` | 30min | Non-critical |
| Track entry count/size | `src/replication/primary.rs:116-117, 204` | 30min | Non-critical |

## Current Sprint: v0.4.0 - Vector Search & Embeddings

**Target:** December 2024
**Estimated Effort:** ~20 hours (revised from 40h - much is already implemented!)
**Status:** 60% complete (structure exists, filling TODOs)

### Current status

**Structure:** ✅ Complete (2,143 lines)
**Implementation:** 60% complete (134 TODOs remaining)

| Component | Lines | Status | TODOs | Priority |
|-----------|-------|--------|-------|----------|
| HNSW index | ~380 | 80% ✅ | 12 | High |
| DiskANN index | ~650 | 50% 🚧 | 45 | Medium |
| BM25 full-text | ~280 | 70% ✅ | 18 | Medium |
| Embedding providers | ~350 | 70% ✅ | 22 | High |
| Fuzzy key lookup | ~180 | 80% ✅ | 8 | High |
| Field indexes | ~303 | 90% ✅ | 9 | High |

### Work breakdown

**Phase 1: Complete HNSW & Embeddings** (~8 hours)
1. Fill HNSW TODOs (incremental insert, deletion) - 3h
2. Complete embedding providers (batch operations) - 2h
3. Wire up to Database insert/update - 2h
4. Integration tests - 1h

**Phase 2: Complete BM25** (~4 hours)
1. Fill BM25 inverted index TODOs - 2h
2. Wire up to Database query - 1h
3. Integration tests - 1h

**Phase 3: Fuzzy Key Lookup** (~3 hours)
1. Complete fuzzy matching logic - 1h
2. Wire up to Database lookup - 1h
3. Integration tests - 1h

**Phase 4: DiskANN (Optional - defer to v0.5.0)** (~25 hours)
- Graph building, pruning, mmap, search - complex
- Only needed for >10M vectors
- HNSW sufficient for initial release

**Deliverables:**
- ✅ `rem search "semantic query" --schema=articles --top-k=10`
- ✅ Automatic embedding generation on insert
- ✅ BM25 keyword search with ranking
- ✅ Fuzzy key lookup with confidence scores

## v0.5.0 - Graph Operations

**Target:** January 2025
**Estimated Effort:** ~12 hours (revised from 20h - structure exists!)

### Current status

**Structure:** ✅ Complete (~200 lines)
**Implementation:** 20% complete (29 TODOs)

| Component | Status | TODOs | Priority |
|-----------|--------|-------|----------|
| Edge CRUD | 20% 🚧 | 15 | High |
| Graph traversal (BFS/DFS) | 30% 🚧 | 14 | High |

### Work breakdown

**Phase 1: Edge Operations** (~6 hours)
1. Implement EdgeManager CRUD - 3h
2. Bidirectional edge storage (CF_EDGES, CF_EDGES_REVERSE) - 2h
3. Integration tests - 1h

**Phase 2: Graph Traversal** (~6 hours)
1. Implement BFS/DFS traversal - 3h
2. Edge filtering by type/properties - 1h
3. Traversal depth limits - 1h
4. Integration tests - 1h

**Deliverables:**
- ✅ `rem traverse <uuid> --depth=3 --direction=out --type=related_to`
- ✅ Bidirectional edge queries (O(1) lookups)
- ✅ Relationship filtering

## v0.6.0 - Document Ingestion

**Target:** February 2025
**Estimated Effort:** ~30 hours

### Current status

**Structure:** Partial (some PDF/chunking code exists)
**Implementation:** 10% complete

| Component | Lines | Status | Priority |
|-----------|-------|--------|----------|
| PDF parser | ~100 | 30% 🚧 | High |
| Text chunking | ~50 | 40% 🚧 | High |
| Metadata extraction | 0 | ⏸️ Todo | Medium |
| Batch ingestion | 0 | ⏸️ Todo | High |
| Excel parser | 0 | ⏸️ Todo | Low |

### Work breakdown

**Phase 1: Core Ingestion** (~15 hours)
1. Complete PDF parser (extract text, tables, images) - 5h
2. Implement smart chunking (semantic boundaries) - 4h
3. Metadata extraction (title, author, date) - 3h
4. Wire up to Database insert with embeddings - 3h

**Phase 2: Batch Processing** (~8 hours)
1. Batch file processor - 3h
2. Progress tracking and resumption - 2h
3. Error handling and validation - 2h
4. Integration tests - 1h

**Phase 3: Additional Formats** (~7 hours)
1. Excel parser (.xlsx, .xls) - 4h
2. Word document parser (.docx) - 3h

**Deliverables:**
- ✅ `rem ingest document.pdf --schema=articles --chunk-size=500`
- ✅ `rem ingest *.pdf --batch --schema=docs`
- ✅ Automatic chunking with semantic boundaries
- ✅ Metadata extraction

## v0.7.0 - Export & LLM Query Builder

**Target:** March 2025
**Estimated Effort:** ~25 hours

### Export Formats (~15 hours)

| Component | Status | Priority |
|-----------|--------|----------|
| Parquet writer | ⏸️ Todo | High |
| CSV exporter | ⏸️ Todo | Medium |
| JSONL exporter | ⏸️ Todo | Low |
| Batch export | ⏸️ Todo | High |

**Phase 1: Parquet Export** (~8 hours)
1. Schema conversion (Entity → Parquet) - 3h
2. Streaming writer for large datasets - 3h
3. Compression (ZSTD) - 1h
4. Integration tests - 1h

**Phase 2: CSV/JSONL** (~4 hours)
1. CSV writer with headers - 2h
2. JSONL streaming writer - 1h
3. Integration tests - 1h

**Phase 3: Batch Export** (~3 hours)
1. Multi-schema export - 2h
2. Export filtering (date ranges, predicates) - 1h

### LLM Query Builder (~10 hours)

| Component | Status | Priority |
|-----------|--------|----------|
| NL → SQL conversion | 30% 🚧 | High |
| Query plan generation | 40% 🚧 | Medium |
| Confidence scoring | 20% 🚧 | Medium |

**Phase 1: Query Generation** (~6 hours)
1. Complete NL → SQL converter - 3h
2. Schema-aware query generation - 2h
3. Integration tests - 1h

**Phase 2: Query Planning** (~4 hours)
1. Complete query plan generator - 2h
2. Confidence scoring - 1h
3. Integration tests - 1h

**Deliverables:**
- ✅ `rem export articles --output data.parquet --format parquet`
- ✅ `rem export --all --output ./exports/ --date-range "2024-01-01,2024-12-31"`
- ✅ `rem ask "show recent articles about Rust" --execute`
- ✅ `rem ask "count articles by category" --plan`

## v0.8.0 - Encryption at Rest

**Target:** April 2025
**Estimated Effort:** ~35 hours

### Current status

**Structure:** Documented (see `src/lib.rs`, `src/storage/db.rs`)
**Implementation:** 0% complete

| Component | Status | Priority |
|-----------|--------|----------|
| Ed25519 key management | ⏸️ Todo | High |
| ChaCha20-Poly1305 AEAD | ⏸️ Todo | High |
| Tenant key derivation | ⏸️ Todo | High |
| Encrypted column family | ⏸️ Todo | High |
| Key rotation | ⏸️ Todo | Medium |

### Work breakdown

**Phase 1: Key Management** (~10 hours)
1. Ed25519 key pair generation - 2h
2. Argon2 password-based KDF - 2h
3. Encrypted key storage (~/.p8/keys/) - 2h
4. Key loading and validation - 2h
5. Integration tests - 2h

**Phase 2: Data Encryption** (~15 hours)
1. ChaCha20-Poly1305 AEAD implementation - 4h
2. Encrypted column family (CF_KEYS) - 4h
3. Transparent encrypt/decrypt on put/get - 4h
4. Tenant key derivation (HKDF) - 2h
5. Integration tests - 1h

**Phase 3: Key Rotation** (~10 hours)
1. Key rotation mechanism - 4h
2. Re-encryption background worker - 4h
3. Progress tracking - 1h
4. Integration tests - 1h

**Deliverables:**
- ✅ `rem key-gen --password "strong_password"`
- ✅ `rem init --password "strong_password"` (encryption at rest)
- ✅ Transparent encryption/decryption
- ✅ Per-tenant key isolation

## v0.9.0 - Admin & Observability

**Target:** May 2025
**Estimated Effort:** ~25 hours

### Current status

**Structure:** Partial (some admin modules exist)
**Implementation:** 30% complete

| Module | Status | TODOs |
|--------|--------|-------|
| Statistics | 40% 🚧 | 15 |
| Compaction | 40% 🚧 | 12 |
| Backup/Restore | 40% 🚧 | 18 |
| Indexing admin | 40% 🚧 | 14 |
| Vacuum | 40% 🚧 | 10 |
| Verification | 40% 🚧 | 13 |

### Work breakdown

**Phase 1: Statistics & Monitoring** (~8 hours)
1. Complete database statistics - 3h
2. Schema statistics - 2h
3. Performance metrics - 2h
4. Integration tests - 1h

**Phase 2: Maintenance** (~10 hours)
1. Complete compaction triggers - 3h
2. Complete vacuum (soft delete cleanup) - 3h
3. Complete verification checks - 2h
4. Integration tests - 2h

**Phase 3: Backup/Restore** (~7 hours)
1. Complete backup to S3/local - 3h
2. Complete restore with verification - 3h
3. Integration tests - 1h

**Deliverables:**
- ✅ `rem stats` - Database statistics
- ✅ `rem compact` - Manual compaction
- ✅ `rem vacuum --dry-run` - Cleanup soft-deleted entities
- ✅ `rem verify` - Integrity checks
- ✅ `rem backup --output s3://bucket/path` - Backup to S3
- ✅ `rem restore --input backup.tar.gz` - Restore from backup

## v1.0.0 - Production Ready

**Target:** June 2025
**Estimated Effort:** ~50 hours

### Focus areas

**Stability & Performance** (~20 hours)
- Comprehensive error handling
- Memory leak detection and fixes
- Performance profiling and optimization
- Load testing (1M+ entities, concurrent users)

**Test Coverage** (~15 hours)
- Rust: 40% → 90% coverage
- Python: 0% → 90% coverage
- Integration tests for all features
- Property-based testing (proptest)

**Documentation** (~10 hours)
- API documentation (rustdoc)
- User guide
- Architecture diagrams
- Performance tuning guide

**Production Hardening** (~5 hours)
- Rate limiting
- Circuit breakers
- Graceful degradation
- Connection pooling

### Success criteria

- ✅ 90% test coverage (Rust + Python)
- ✅ <1% error rate under load
- ✅ <100ms p99 latency for reads
- ✅ <500ms p99 latency for writes
- ✅ Zero memory leaks
- ✅ Comprehensive documentation
- ✅ Production deployment guide

## Beyond v1.0.0 - Future Considerations

### Distributed Features (v1.1.0+)

- Multi-region replication
- Automatic failover
- Distributed transactions
- Consensus protocol (Raft)

### Advanced Query (v1.2.0+)

- JOINs (INNER, LEFT, RIGHT)
- Subqueries
- Window functions
- Query optimization (cost-based planner)

### ML Integration (v1.3.0+)

- Model inference (ONNX)
- Feature stores
- A/B testing framework
- Real-time predictions

### Scale (v2.0.0+)

- Sharding (horizontal scaling)
- Read replicas with load balancing
- Caching layer (Redis)
- CDN integration for static assets

## Summary: Total Remaining Effort

| Version | Focus | Effort | Target |
|---------|-------|--------|--------|
| **v0.3.0** | Replication | 8h | Nov 2024 |
| **v0.4.0** | Vector Search | 20h | Dec 2024 |
| **v0.5.0** | Graph Operations | 12h | Jan 2025 |
| **v0.6.0** | Document Ingestion | 30h | Feb 2025 |
| **v0.7.0** | Export & LLM | 25h | Mar 2025 |
| **v0.8.0** | Encryption | 35h | Apr 2025 |
| **v0.9.0** | Admin & Observability | 25h | May 2025 |
| **v1.0.0** | Production Ready | 50h | Jun 2025 |

**Total:** ~205 hours (~5 weeks full-time)

**Reality Check:** With ~60% of vector search and graph already implemented, we're ahead of initial estimates. The structure is solid, just need to fill in the TODOs.

---

Last updated: 2025-10-25
