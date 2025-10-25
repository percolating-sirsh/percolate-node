# 2025 SOTA Review: Vector Search and Embeddings

**Document Version:** 1.0
**Date:** October 2025
**Reviewed By:** Technical Architecture Team

## Executive Summary

This document reviews the current REM database implementation against 2025 state-of-the-art (SOTA) technologies for vector search, embeddings, and hybrid retrieval. Our stack uses RocksDB + HNSW + local embeddings (all-MiniLM-L6-v2) + OpenAI API support. This review identifies newer alternatives and patterns that could improve performance, accuracy, or developer experience.

**Key Finding:** Our current architecture remains competitive for embedded/edge deployments, but several 2025 innovations could provide significant improvements for specific use cases.

## Current Architecture

### Storage Layer
- **RocksDB** (v0.22): Embedded key-value store with column families
- **Custom implementation**: Entity storage, graph edges, vector indexes
- **Strengths**: Zero external dependencies, full control, embedded
- **Weaknesses**: Custom code maintenance burden, no built-in vector optimizations

### Vector Search
- **instant-distance** (v0.6): Pure Rust HNSW implementation
- **Index type**: In-memory graph-based ANN
- **Performance target**: <5ms for 1M documents
- **Strengths**: Memory-efficient, fast queries, pure Rust
- **Weaknesses**: Memory-only, rebuild on updates, no disk-based support

### Embeddings
- **embed_anything** (v0.6): Local models (all-MiniLM-L6-v2, BGE variants)
- **OpenAI API**: text-embedding-3-small/large via reqwest
- **Dimensions**: 384 (local) to 1536 (OpenAI large)
- **Strengths**: Privacy-preserving local option, flexible provider system
- **Weaknesses**: Limited model selection, older embedding models

### Search Strategy
- **Vector search**: Cosine similarity via HNSW
- **SQL queries**: Custom parser + RocksDB prefix scans
- **Graph traversal**: Bidirectional column families
- **Hybrid search**: Not implemented

## 2025 SOTA Alternatives

### 1. Vector Databases

#### Qdrant (Recommended for Evaluation)
**What it is:** Production-grade Rust-based vector database with sophisticated filtering

**Key advantages:**
- Native Rust implementation (performance + memory safety)
- Built-in hybrid search (sparse + dense + filters)
- Disk-backed storage with memory-mapped files
- Quantization support (reduces memory 4-8x)
- Dynamic query planning and optimization
- Payload filtering without full scan
- gRPC API with strong typing

**Performance (Qdrant benchmarks):**
- 1M vectors: ~1-3ms p95 latency
- 100M vectors: ~10-20ms p95 latency (with quantization)
- Memory: ~50-200 bytes per vector (vs 1.5KB for raw f32)

**When to consider:**
- Need >10M vectors with limited memory
- Require complex metadata filtering
- Want production-ready solution without custom implementation
- Need multi-tenancy with isolation

**Trade-offs:**
- External dependency (not truly embedded)
- Can run embedded via library, but larger binary size
- Learning curve for query API

**Integration path:**
```rust
// Replace instant-distance HNSW with Qdrant
use qdrant_client::{Qdrant, CollectionConfig};

// Embedded mode (in-process)
let client = Qdrant::from_url("file://./data/qdrant").build()?;
```

**Decision factors:**
- **Keep current**: If <1M vectors, embedded priority, simple queries
- **Migrate to Qdrant**: If >10M vectors, complex filters, production scale

---

#### LanceDB
**What it is:** Columnar vector database built on Apache Arrow and Lance format

**Key advantages:**
- Columnar storage (Parquet-like) optimized for ML workloads
- Native Rust implementation with PyO3 bindings
- Disk-based with memory mapping (efficient large-scale storage)
- Built-in versioning (data + schema evolution)
- Zero-copy integration with Arrow/Polars/DuckDB
- DiskANN support (billion-scale disk-based ANN)

**Performance:**
- Storage: ~10x more compact than JSON for structured data
- Random access: 100x faster than Parquet
- Queries: Comparable to Qdrant for <100M vectors

**When to consider:**
- Heavy analytics workload (not just vector search)
- Integration with DuckDB/Polars data pipelines
- Need versioning/time-travel
- Large structured data + embeddings

**Trade-offs:**
- Columnar format is overkill for simple entity storage
- Less mature than Qdrant for pure vector search
- DiskANN implementation still evolving

**Integration path:**
```rust
use lancedb::{connect, Table};

let db = connect("./data/lance").execute().await?;
let table = db.create_table("entities", schema, data).await?;
```

**Decision factors:**
- **Keep current**: If entity-centric, graph-heavy, simple analytics
- **Migrate to LanceDB**: If heavy analytics, versioning needs, Arrow ecosystem

---

#### Redb (Not a Vector Database)
**What it is:** Pure Rust embedded key-value store (alternative to RocksDB)

**Key advantages:**
- Pure Rust (no C++ dependencies like RocksDB)
- ACID transactions with MVCC
- Copy-on-write B-trees (similar to LMDB)
- Simpler API than RocksDB
- Smaller binary size

**Performance comparison (vs RocksDB):**
- Reads: Comparable to RocksDB
- Writes: Slower for sequential, faster for random
- Memory: Lower overhead for small databases
- Compaction: Automatic (no manual tuning)

**When to consider:**
- Want pure Rust stack (no C++ dependencies)
- Smaller databases (<100GB)
- Prefer simplicity over tuning knobs

**Trade-offs:**
- Less mature than RocksDB
- Fewer production deployments
- Limited tooling ecosystem
- No vector-specific optimizations

**Decision factors:**
- **Keep RocksDB**: Production stability, large databases, tuning requirements
- **Migrate to Redb**: Pure Rust preference, simpler operations, smaller scale

---

### 2. Embedding Models (2025 SOTA)

#### Commercial Models

**Voyage AI (voyage-3-large, voyage-3-lite)**
- **Performance**: Best-in-class retrieval accuracy (MTEB leaderboard leader)
- **voyage-3-large**: 1024 dims, highest accuracy
- **voyage-3-lite**: 512 dims, cost-efficient, competitive with OpenAI large
- **Cost**: ~$0.12/1M tokens (large), $0.02/1M tokens (lite)
- **When to use**: Production RAG systems where accuracy is critical

**Google text-embedding-005**
- **Availability**: Vertex AI only (enterprise)
- **Performance**: Competitive with Voyage
- **When to use**: Already on GCP, enterprise support needs

**OpenAI text-embedding-3 (current baseline)**
- **Status**: "Ancient" by 2025 standards (released March 2023)
- **Performance**: Solid but surpassed by Voyage and newer models
- **Recommendation**: Upgrade to Voyage-3-lite for similar cost, better accuracy

---

#### Open-Source Models (Major Updates)

**Jina Embeddings v4 (jina-embeddings-v4)** ⭐ Recommended
- **Released**: Mid-2025
- **Architecture**: Task-specific adapters + Matryoshka embeddings
- **Dimensions**: Flexible (64, 128, 256, 512, 1024) - single model
- **Languages**: Multilingual (100+ languages)
- **Features**:
  - Single-vector mode (traditional embeddings)
  - Multi-vector mode (ColBERT-style late interaction)
  - Vision mode (ColPali-style document understanding)
- **Performance**: Matches or exceeds text-embedding-3-small on MTEB
- **Size**: 137M parameters (fits on CPU/edge devices)
- **License**: Apache 2.0

**Why Jina v4 matters:**
- Single model for embedding + reranking + vision retrieval
- Matryoshka: Trade precision for speed by truncating dimensions
- Can replace both embed_anything AND reranker with one model

**Integration path:**
```rust
// Add to Cargo.toml
embed_anything = { version = "0.7", features = ["jina"] }

// Provider factory
"local:jina-embeddings-v4" => {
    let embedder = JinaEmbedder::new("jina-embeddings-v4")?;
    // Support multi-vector mode
    embedder.set_output_mode(OutputMode::MultiVector)?;
    Ok(Box::new(embedder))
}
```

---

**BGE-M3 (BAAI General Embedding)** ⭐ Recommended for Hybrid
- **Architecture**: Multi-functionality (dense + sparse + multi-vector)
- **Dimensions**: 1024 (dense), variable (sparse)
- **Languages**: 100+ languages
- **Max tokens**: 8192 (2x longer than most models)
- **Features**:
  - Dense retrieval (traditional vector search)
  - Sparse retrieval (BM25-like learned sparse vectors)
  - Multi-vector retrieval (ColBERT-style)
- **Performance**: 72% RAG accuracy (vs 57% for nomic-embed-text)
- **License**: Apache 2.0

**Why BGE-M3 matters:**
- Native hybrid search without separate BM25 index
- Single forward pass produces dense + sparse vectors
- State-of-the-art for long documents (8K tokens)

**Integration path:**
```rust
// BGE-M3 produces multiple outputs
struct BgeM3Embedder {
    dense_dim: usize,    // 1024
    sparse_dim: usize,   // ~20K vocabulary
}

// Store both in separate CFs
CF_EMBEDDINGS_DENSE  // [f32; 1024]
CF_EMBEDDINGS_SPARSE // HashMap<u32, f32> (lexical features)
```

---

**Nomic Embed v2**
- **Architecture**: Mixture-of-Experts (MoE) for text embeddings (first of its kind)
- **Dimensions**: 768 (lightweight)
- **Languages**: 100+ languages
- **Performance**: Slightly lower accuracy than BGE-M3, but faster inference
- **License**: Apache 2.0
- **When to use**: Efficiency-critical applications, lower accuracy tolerance

---

**Stella (stella-base-en-v2)**
- **Released**: December 2024
- **Performance**: Strong on MTEB benchmarks
- **Dimensions**: 768
- **License**: Apache 2.0
- **Research focus**: Excellent academic work by Dun Zhang
- **When to use**: English-only, research/experimentation

---

**ModernBERT Embed**
- **Released**: January 2025
- **Architecture**: Improved BERT (Answer.AI + LightOn AI)
- **Focus**: Speed + accuracy improvements over original BERT
- **Status**: Brand new, limited production usage
- **When to use**: Experimentation, English-focused

---

#### Recommendations by Use Case

| Use Case | Recommended Model | Why |
|----------|------------------|-----|
| **Production RAG (cloud)** | Voyage-3-lite | Best accuracy/cost ratio |
| **Production RAG (self-hosted)** | Jina v4 or BGE-M3 | SOTA open-source, multifunctional |
| **Hybrid search** | BGE-M3 | Built-in dense + sparse |
| **Edge/embedded** | Jina v4 (matryoshka @ 256 dims) | Flexible dimensions, small model |
| **Long documents (8K+ tokens)** | BGE-M3 | 8192 token max length |
| **Multilingual** | Jina v4 or BGE-M3 | 100+ languages |
| **Vision + text** | Jina v4 | Multi-modal support |
| **Budget/simple** | Keep all-MiniLM-L6-v2 | Still works, proven |

---

### 3. Vector Search Algorithms

#### HNSW (Current)
- **Type**: In-memory graph-based ANN
- **Strengths**: Fast queries (1-5ms), high recall (>95%)
- **Weaknesses**: High memory (1.5KB per vector), poor update performance, no disk support

---

#### DiskANN (Microsoft)
**What it is:** Disk-based graph ANN algorithm for billion-scale datasets

**Key advantages:**
- Disk-based (SSD-optimized), not memory-bound
- Single large graph (simpler than HNSW multi-layer)
- Stable accuracy with dynamic updates (insertions/deletions)
- Scales to billions of vectors on single node

**Performance:**
- Billion vectors: ~10-50ms latency (vs HNSW requiring 100GB+ RAM)
- Memory: ~10x lower than HNSW
- Throughput: High for batch queries

**Availability:**
- Milvus, SQL Server, custom implementations
- No mature Rust implementation yet

**Trade-offs:**
- Slower than in-memory HNSW for small datasets (<10M)
- Immutable index (FreshDiskANN variant supports updates)
- Requires fast SSD for best performance

**Decision factors:**
- **Keep HNSW**: If <10M vectors, memory available, fast queries critical
- **Migrate to DiskANN**: If >100M vectors, memory constrained, SSD available

---

#### SPANN (Microsoft)
**What it is:** Disk-based ANN variant, faster than DiskANN at lower recalls

**Key advantages:**
- Faster updates than DiskANN
- Good for moderate recall requirements (80-90%)

**Trade-offs:**
- Slower than DiskANN at high recall (>95%)
- Less widely adopted

**Availability:**
- PlanetScale MySQL uses SPANN variant
- Limited Rust implementations

---

#### Vamana (Weaviate)
**What it is:** Another graph-based ANN, optimized for disk

**Key advantages:**
- Tighter connectivity than HNSW (fewer edges)
- Lower memory footprint

**Trade-offs:**
- Slower build time than HNSW
- Comparable query performance

**Decision factors:**
- **Keep HNSW**: Widely supported, proven, fast
- **Evaluate Vamana**: If using Weaviate already

---

#### Recommendation
**For current REM DB:**
- **<1M vectors**: Keep instant-distance HNSW (fast, proven)
- **1-10M vectors**: Evaluate Qdrant (optimized HNSW + quantization)
- **>10M vectors**: Evaluate DiskANN (via Milvus or custom implementation)

**Implementation priority:**
1. Add quantization to existing HNSW (4-8x memory savings)
2. If that's insufficient, migrate to Qdrant (production-ready)
3. If >100M vectors, consider DiskANN (research phase)

---

### 4. Hybrid Search and Retrieval Patterns

#### Current Status
- **Vector search**: ✅ Implemented (HNSW)
- **SQL queries**: ✅ Implemented (custom parser)
- **Graph traversal**: ✅ Implemented (bidirectional CFs)
- **Hybrid search**: ❌ Not implemented
- **Reranking**: ❌ Not implemented

---

#### BM25 + Dense Vector Fusion

**What it is:** Combine lexical (BM25) and semantic (dense embeddings) search

**Why it matters:**
- Lexical search: Good for exact matches, entities, acronyms
- Semantic search: Good for concepts, paraphrases, synonyms
- Fusion: Best of both worlds (10-30% accuracy improvement)

**Standard approach: Reciprocal Rank Fusion (RRF)**
```
RRF_score(d) = Σ 1 / (k + rank_i(d))
```
where `k=60` (standard), `rank_i` = ranking from method `i`

**Why RRF:**
- No score normalization needed (BM25 vs cosine scores are incomparable)
- Emphasizes rank consistency, not absolute scores
- Unsupervised (no training needed)
- Industry standard (Qdrant, OpenSearch 2.19+, Weaviate, Elasticsearch)

**Performance:**
- 10-30% improvement over dense-only search (BEIR benchmarks)
- Critical for domain-specific terms, abbreviations, proper nouns

**Implementation complexity:** Low
- BM25: Classic IR algorithm (well-understood)
- RRF: Simple formula, no ML
- Storage: Add inverted index CF to RocksDB

---

#### Implementation Recommendation

**Phase 1: Add BM25 + RRF (High Priority)**
```rust
// New column family
CF_INVERTED_INDEX  // term:entity_type:term_id -> [doc_ids]

// Search flow
let dense_results = hnsw_search(query_embedding, top_k=100);
let sparse_results = bm25_search(query_tokens, top_k=100);
let fused = reciprocal_rank_fusion(dense_results, sparse_results, k=60);
```

**Expected impact:**
- +15-25% accuracy on entity searches (names, IDs, codes)
- +10-15% accuracy on mixed queries (concepts + entities)
- Storage: +5-10% for inverted index

**Rust libraries:**
- `tantivy` (BM25 + inverted index, mature)
- Custom (simple to implement)

---

#### ColBERT Reranking (Late Interaction)

**What it is:** Token-level embeddings + MaxSim scoring for reranking

**How it works:**
1. Retrieve top-K candidates with dense search (e.g., K=100)
2. For each candidate, compute token-level embeddings (query + document)
3. For each query token, find max similarity with any document token
4. Sum all max similarities → final score
5. Rerank candidates by score

**Why it matters:**
- 20-40% accuracy improvement over dense-only (RAG benchmarks)
- Captures fine-grained semantic matches (term-level precision)
- Critical for long documents, technical content

**Performance:**
- Latency: +50-100ms for reranking 100 candidates
- Accuracy: SOTA for retrieval (beats cross-encoders on speed)

**Models:**
- Jina ColBERT v2 (multilingual, 89 languages, 8K tokens)
- ColBERT v2 (original, English-focused)

**Integration:**
```rust
// Two-stage retrieval
let candidates = hnsw_search(query_embedding, top_k=100);  // Fast
let reranked = colbert_rerank(query, candidates, top_k=10);  // Accurate
```

---

#### Vision-Based Retrieval (ColPali)

**What it is:** Vision-Language Models for document retrieval (no OCR)

**How it works:**
1. Render document page as image
2. VLM encodes image → multi-vector embeddings
3. Query text → embeddings
4. Late interaction (MaxSim) for matching

**Why it matters:**
- No OCR pipeline (simpler, faster)
- Preserves layout, tables, figures
- State-of-the-art for PDFs, slides, forms

**Performance:**
- Accuracy: Beats OCR+text pipelines by 10-20%
- Speed: Faster (no OCR bottleneck)
- Robustness: Handles complex layouts, non-text elements

**Models:**
- ColPali (original, 2024)
- Jina v4 (includes ColPali mode)

**When to consider:**
- Heavy PDF/document ingestion
- Complex layouts (tables, charts, forms)
- Multimodal content

**Trade-offs:**
- Larger model size (vision encoder)
- Requires GPU for real-time inference

---

#### Matryoshka Embeddings

**What it is:** Single model produces nested embeddings (64, 128, 256, 512, 1024 dims)

**How it works:**
- Train with nested loss functions (coarse-to-fine)
- Dimensions are ordered by semantic importance
- Truncate to desired size at inference

**Why it matters:**
- Trade precision for speed (10x faster with 256 dims vs 1024)
- Single model, multiple precision levels
- Adaptive to compute budget

**Performance:**
- 256 dims: ~85% accuracy of 1024 dims, 4x less storage/compute
- 512 dims: ~95% accuracy of 1024 dims, 2x less storage/compute

**Models:**
- Jina Embeddings v4 (built-in Matryoshka)
- OpenAI text-embedding-3 (supports dimension reduction)

**Use case:**
- First-stage retrieval: 256 dims (fast, 1000 candidates)
- Second-stage reranking: 1024 dims (accurate, 10 final results)

---

#### Retrieval Pattern Recommendations

| Pattern | Priority | Complexity | Impact | When to Implement |
|---------|----------|------------|--------|-------------------|
| **BM25 + RRF** | High | Low | +15-25% | Q1 2025 (next sprint) |
| **Quantization** | High | Medium | -75% memory | Q1 2025 |
| **ColBERT Reranking** | Medium | Medium | +20-40% | Q2 2025 |
| **Matryoshka** | Medium | Low | 2-4x faster | Q2 2025 (if using Jina v4) |
| **ColPali Vision** | Low | High | PDF-specific | Q3 2025 (if PDF-heavy) |

---

### 5. Storage and Performance Optimizations

#### Quantization (High Priority)

**What it is:** Compress float32 vectors to uint8/int8

**Methods:**
- **Scalar Quantization (SQ8)**: Map f32 → uint8 via min/max
- **Product Quantization (PQ)**: Cluster subvectors, store cluster IDs
- **Binary Quantization**: Single bit per dimension (extreme compression)

**Performance:**
- **SQ8**: 4x compression, ~1-3% recall drop
- **PQ**: 8-32x compression, ~5-10% recall drop
- **Binary**: 32x compression, ~10-20% recall drop

**Recommendation:**
- Start with SQ8 (best accuracy/compression trade-off)
- Qdrant has built-in SQ8 + rescoring (minimal accuracy loss)

**Implementation:**
```rust
// Store quantized + original (hybrid)
CF_EMBEDDINGS_QUANTIZED  // [u8; 384] (1/4 size)
CF_EMBEDDINGS_FULL       // [f32; 384] (for rescoring top candidates)

// Search flow
let candidates = search_quantized(query_q8, top_k=100);  // Fast
let rescored = rescore_full(query_f32, candidates, top_k=10);  // Accurate
```

**Expected impact:**
- 75% memory reduction
- 2-3x faster search (cache-friendly)
- <1% accuracy drop (with rescoring)

---

#### Memory-Mapped Embeddings

**What it is:** Store embeddings on disk, mmap into process memory

**Why it matters:**
- OS manages paging (only active embeddings in RAM)
- Scales beyond RAM limits
- Fast access for hot data

**Current stack:**
- RocksDB: Limited mmap support
- instant-distance: In-memory only

**Alternatives:**
- Qdrant: Native mmap support
- LanceDB: Built on memory-mapped Arrow

---

## Recommended Migration Path

### Phase 1: Low-Hanging Fruit (Q1 2025)
**Priority: High | Complexity: Low-Medium**

1. **Upgrade embedding model** (1 week)
   - Replace `all-MiniLM-L6-v2` with `jina-embeddings-v4`
   - Enable Matryoshka mode (256 dims for storage, 1024 for reranking)
   - Expected: +10-15% accuracy, -50% storage (256 vs 384 dims for old model)

2. **Add BM25 + RRF hybrid search** (2 weeks)
   - Integrate `tantivy` or custom BM25
   - Add inverted index column family
   - Implement RRF fusion
   - Expected: +15-25% accuracy on entity/exact searches

3. **Add scalar quantization (SQ8)** (1 week)
   - Store uint8 quantized vectors
   - Keep full precision for rescoring
   - Expected: -75% memory, <1% accuracy drop

**Total time: 4 weeks | Expected impact: +25% accuracy, -60% memory**

---

### Phase 2: Evaluate Production Alternatives (Q2 2025)
**Priority: Medium | Complexity: Medium**

1. **Benchmark Qdrant** (2 weeks)
   - Embedded mode integration
   - Compare performance, memory, accuracy vs current
   - Decision point: Migrate or keep custom implementation

2. **Add ColBERT reranking** (3 weeks)
   - Integrate Jina ColBERT v2
   - Two-stage retrieval (HNSW → ColBERT)
   - Expected: +20-30% accuracy on complex queries

3. **Evaluate BGE-M3 for hybrid** (1 week)
   - Compare BGE-M3 (native sparse+dense) vs BM25+Jina
   - Benchmark accuracy and speed
   - Decision point: Single model vs separate BM25

**Total time: 6 weeks | Expected impact: Architecture decision + reranking**

---

### Phase 3: Advanced Features (Q3 2025)
**Priority: Low | Complexity: High**

1. **Vision retrieval (if PDF-heavy)** (4 weeks)
   - Integrate ColPali via Jina v4
   - Document rendering pipeline
   - Expected: Simpler PDF pipeline, better layout understanding

2. **Evaluate DiskANN (if >100M vectors)** (4 weeks)
   - Research Rust implementations or Milvus integration
   - Benchmark vs HNSW + quantization
   - Decision point: Stay in-memory or go disk-based

**Total time: 8 weeks | Expected impact: Domain-specific improvements**

---

## Decision Matrix

### Keep Current Stack If:
- ✅ <1M vectors (HNSW is optimal)
- ✅ Embedded/edge deployment critical (no external dependencies)
- ✅ Simple queries (vector + basic filters)
- ✅ Limited development resources
- ✅ Current performance meets requirements

### Migrate to Qdrant If:
- ✅ >10M vectors (quantization + disk support)
- ✅ Complex metadata filtering
- ✅ Multi-tenancy with isolation
- ✅ Production support needs
- ✅ Want to reduce custom code maintenance

### Migrate to LanceDB If:
- ✅ Heavy analytics workload
- ✅ Arrow/Polars/DuckDB integration
- ✅ Versioning/time-travel requirements
- ✅ Columnar data model fits use case

### Upgrade Embedding Models If:
- ✅ Current accuracy insufficient
- ✅ Need multilingual support (>10 languages)
- ✅ Long documents (>512 tokens)
- ✅ Want single model for embedding + reranking + vision

### Add Hybrid Search If:
- ✅ Exact match queries common (IDs, names, codes)
- ✅ Domain-specific terminology
- ✅ Abbreviations/acronyms frequent
- ✅ Users mix semantic + keyword searches

---

## Cost-Benefit Analysis

### Minimal Upgrade Path (Recommended)
**Time: 4 weeks | Cost: Low | Impact: High**

1. Jina v4 embeddings
2. BM25 + RRF
3. SQ8 quantization

**Result:** +25% accuracy, -60% memory, minimal code changes

---

### Full Migration to Qdrant
**Time: 8-12 weeks | Cost: Medium | Impact: Medium-High**

1. Replace custom storage with Qdrant
2. Migrate schemas and data
3. Update API layer
4. Test and validate

**Result:** Reduced maintenance, production features, similar performance

---

### Hybrid Approach (Recommended for Scale)
**Time: 6-8 weeks | Cost: Medium | Impact: High**

1. Keep RocksDB for entity/graph storage
2. Use Qdrant for vector search only
3. Add Jina v4 + ColBERT reranking
4. Implement BM25 + RRF

**Result:** Best of both worlds (custom + production tools)

---

## Glossary

- **ANN**: Approximate Nearest Neighbors (vector search)
- **BM25**: Best Match 25 (lexical search algorithm, industry standard for keyword search)
- **ColBERT**: Contextualized Late Interaction over BERT (token-level embeddings)
- **ColPali**: ColBERT for vision-language models (document images)
- **HNSW**: Hierarchical Navigable Small World graphs (in-memory vector index)
- **DiskANN**: Disk-Accelerated Nearest Neighbors (disk-based vector index)
- **Matryoshka**: Nested embeddings with variable dimensions
- **MTEB**: Massive Text Embedding Benchmark (standard evaluation)
- **RRF**: Reciprocal Rank Fusion (hybrid search scoring)
- **SQ8**: Scalar Quantization to 8-bit (vector compression)

---

## References

### Research Papers
- ColBERT: [Khattab & Zaharia, 2020] "ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT"
- ColPali: [arXiv:2407.01449] "ColPali: Efficient Document Retrieval with Vision Language Models"
- Matryoshka: [arXiv:2205.13147] "Matryoshka Representation Learning"
- DiskANN: [Jayaram et al., NeurIPS 2019] "DiskANN: Fast Accurate Billion-point Nearest Neighbor Search on a Single Node"

### Industry Resources
- Qdrant Benchmarks: https://qdrant.tech/benchmarks/
- MTEB Leaderboard: https://huggingface.co/spaces/mteb/leaderboard
- Jina Embeddings v4: https://jina.ai/news/jina-embeddings-v4
- Weaviate ANN Comparison: https://weaviate.io/blog/ann-algorithms-vamana-vs-hnsw
- OpenSearch RRF: https://opensearch.org/blog/introducing-reciprocal-rank-fusion-hybrid-search/

### Rust Crates
- `qdrant-client`: https://docs.rs/qdrant-client
- `lancedb`: https://docs.rs/lancedb
- `redb`: https://docs.rs/redb
- `tantivy`: https://docs.rs/tantivy (BM25 full-text search)
- `instant-distance`: https://docs.rs/instant-distance (current HNSW)

---

## Revision History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2025-10-25 | Initial review | Technical Team |

---

## Next Steps

1. **Review this document with team** (1 week)
2. **Prioritize Phase 1 items** (1 week)
3. **Prototype Jina v4 integration** (2 weeks)
4. **Benchmark current vs Jina v4 + BM25** (1 week)
5. **Make go/no-go decision on migration** (1 week)

**Decision deadline:** 2025-11-15
**Implementation start:** 2025-12-01 (if approved)
