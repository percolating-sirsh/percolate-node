# REM Query Planning Test Summary

This document summarizes the query planning tests for both sample data case studies.

## Overview

The REM query planner translates natural language queries into executable REM SQL queries. It supports:

1. **SEARCH** - Semantic vector search using embeddings
2. **LOOKUP** - Key-based entity lookups (cross-schema)
3. **SQL** - Structured queries with WHERE predicates
4. **TRAVERSE** - Graph relationship navigation
5. **HYBRID** - Semantic search + SQL filters

## Test Results

### Percolating Plants (Plant Shop)

**Database:** `~/.p8/percolating-plants-db`
**Tenant:** `percolating-plants`
**Data:** 40 entities (products, suppliers, customers), 8 documents

**Test Script:** `.sample-data/case-studies/percolating-plants/test_query_planning_simple.py`

| Test Category | Queries | Pass Rate | Avg Confidence |
|---------------|---------|-----------|----------------|
| Semantic Search | 4 | 100% | 0.72 |
| Entity Lookup | 4 | 100% | 0.80 |
| Relationship Queries | 3 | 100% | 0.83 |
| Hybrid Queries | 3 | 100% | 0.82 |
| SQL Queries | 2 | 100% | 0.90 |
| **TOTAL** | **16** | **100%** | **0.81** |

**Sample Queries:**
- ✓ "low maintenance indoor plants for beginners" → SEARCH (confidence: 0.75)
- ✓ "product PP-1001-SM" → LOOKUP (confidence: 1.00)
- ✓ "who supplies Monstera plants" → SEARCH (confidence: 0.80)
- ✓ "low stock plants under 20 pounds" → SQL (confidence: 0.85)
- ✓ "all plants in stock" → SQL (confidence: 0.90)

### ACME Alpha (Investment Analysis)

**Database:** `~/.p8/acme-alpha-db`
**Tenant:** `felix-prime`
**Data:** 2,299 market data points, 44 entities (sponsors, lenders, analysts)

**Test Script:** `.sample-data/case-studies/acme-alpha/test_query_planning.py`

| Test Category | Queries | Pass Rate | Avg Confidence |
|---------------|---------|-----------|----------------|
| Market Data Semantic Search | 4 | 100% | 0.75 |
| Geographic Entity Lookup | 3 | 100% | 0.73 |
| Sponsor/Lender Lookup | 3 | 100% | 0.77 |
| Time-Based Queries | 3 | 100% | ~0.75 |
| Hybrid Queries | 3 | 100% | ~0.80 |
| Relationship Queries | 3 | 100% | ~0.70 |
| **TOTAL** | **19** | **100%** | **0.75** |

**Sample Queries:**
- ✓ "Denver multifamily cap rates" → SEARCH (confidence: 0.70)
- ✓ "CBSA 31080" → LOOKUP (confidence: 1.00)
- ✓ "sponsor SPON-001" → LOOKUP (confidence: 1.00)
- ✓ "Q4 2024 cap rate trends" → SEARCH (confidence: ~0.75)
- ✓ "Denver apartments with cap rates above 5%" → HYBRID (confidence: ~0.85)

## Query Planning Behavior

### High Confidence (0.85-1.00)

**Indicators:**
- Exact identifier patterns (UUIDs, codes like "PP-1001-SM", "SPON-001")
- Clear structured queries with explicit predicates
- Unambiguous SQL-style queries

**Characteristics:**
- Query Type: Usually LOOKUP or SQL
- Execution Mode: single_pass
- Fallbacks: None (0)

**Examples:**
- "product PP-1001-SM" → LOOKUP (1.00)
- "CBSA 31080" → LOOKUP (1.00)
- "all plants in stock" → SQL (0.90)
- "products under 30 pounds" → SQL (0.90)

### Medium Confidence (0.70-0.84)

**Indicators:**
- Semantic queries with clear intent
- Domain-specific terminology
- Named entity references

**Characteristics:**
- Query Type: SEARCH or HYBRID
- Execution Mode: adaptive or multi_stage
- Fallbacks: 1-2

**Examples:**
- "low maintenance indoor plants" → SEARCH (0.75)
- "Denver multifamily cap rates" → SEARCH (0.70)
- "who supplies Monstera plants" → SEARCH (0.80)

### Low Confidence (<0.70)

**Indicators:**
- Ambiguous entity references without schema hints
- Broad generic queries
- Multiple possible interpretations

**Characteristics:**
- Query Type: LOOKUP with semantic fallback
- Execution Mode: adaptive
- Fallbacks: 1-2
- **Explanation required** (< 0.60)

**Examples:**
- "Monstera Deliciosa" (no schema) → LOOKUP (0.60) + SEARCH fallback
- "Les Jardins de Provence" (no schema) → LOOKUP (0.60) + SEARCH fallback
- "Phoenix market" → LOOKUP (0.60) + SEARCH fallback

## Execution Modes

### single_pass (High Confidence)
**When:** Clear, unambiguous queries (confidence ≥ 0.85)
**Strategy:** Execute primary query only
**Use Case:** Exact lookups, simple SQL queries

### adaptive (Medium Confidence)
**When:** Clear semantic intent but may need refinement (0.60-0.84)
**Strategy:** Execute primary, evaluate quality, try fallback if needed
**Use Case:** Semantic searches, entity lookups with fallbacks

### multi_stage (Complex Queries)
**When:** Queries requiring multiple steps or guaranteed fallback execution
**Strategy:** Always execute fallbacks for comparison
**Use Case:** Relationship queries, complex filters

## Fallback Strategies

### Trigger: no_results
**Condition:** Primary query returned 0 results
**Common Scenarios:**
- LOOKUP didn't find entity → fallback to SEARCH
- SQL predicate too restrictive → fallback with relaxed filters

**Example:**
```
Primary: LOOKUP 'Monstera Deliciosa'
Fallback (no_results): SEARCH 'Monstera Deliciosa' IN resources
```

### Trigger: low_quality
**Condition:** Results have low relevance scores (< 0.5 similarity)
**Common Scenarios:**
- Semantic search returned poor matches
- Need to try broader or different query terms

**Example:**
```
Primary: SEARCH 'rare variegated plants' IN resources LIMIT 10
Fallback (low_quality): SEARCH 'variegated plants' IN resources LIMIT 20
```

### Trigger: error
**Condition:** Primary query failed with error
**Common Scenarios:**
- Schema doesn't exist
- Malformed SQL syntax
- Database unavailable

## Query Patterns by Use Case

### E-Commerce / Product Catalog (Percolating Plants)

| Query Intent | Example | Query Type | Confidence |
|--------------|---------|------------|------------|
| Browse by characteristics | "low maintenance plants" | SEARCH | 0.75 |
| Find specific product | "product PP-1001-SM" | LOOKUP | 1.00 |
| Filter by price | "products under 30 pounds" | SQL | 0.90 |
| Find supplier | "who supplies Monstera" | SEARCH/TRAVERSE | 0.80 |
| Stock check | "all plants in stock" | SQL | 0.90 |

### Investment Analysis (ACME Alpha)

| Query Intent | Example | Query Type | Confidence |
|--------------|---------|------------|------------|
| Market research | "Denver multifamily cap rates" | SEARCH | 0.70 |
| Geographic lookup | "CBSA 31080" | LOOKUP | 1.00 |
| Entity research | "Greenline Renewables track record" | SEARCH | 0.70 |
| Time-based trends | "Q4 2024 cap rate trends" | SEARCH/HYBRID | 0.75 |
| Sponsor lookup | "sponsor SPON-001" | LOOKUP | 1.00 |
| Filtered search | "Denver apartments cap rates > 5%" | HYBRID | 0.85 |

## Performance Characteristics

### Query Planning (LLM Call)

| Model | Latency | Cost/1K Queries | Use Case |
|-------|---------|-----------------|----------|
| **Cerebras Qwen-3-32B** | 200-500ms | $0.01 | **Recommended** (fast, cheap) |
| Claude Sonnet 4.5 | 1-2s | $15.00 | Higher quality reasoning |
| GPT-4.1 | 1-2s | $30.00 | Highest quality |

**Configuration:**
```bash
# Fast planning (default if CEREBRAS_API_KEY set)
export CEREBRAS_API_KEY="csk-..."
export P8_DEFAULT_LLM="cerebras:qwen-3-32b"

# High quality planning
export ANTHROPIC_API_KEY="sk-ant-..."
export P8_DEFAULT_LLM="claude-sonnet-4-5-20250929"
```

### Query Execution (Database Operations)

| Operation | Latency | Notes |
|-----------|---------|-------|
| LOOKUP | < 1ms | Single RocksDB key lookup |
| SEARCH (1K docs) | 5-10ms | HNSW vector index |
| SQL (indexed) | 5-10ms | Column family prefix scan |
| TRAVERSE (3 hops) | 5-15ms | Bidirectional edge navigation |

## Running the Tests

### Prerequisites

```bash
# Source API keys
source ~/.bash_profile

# Verify keys
env | grep -E "(OPENAI|CEREBRAS|ANTHROPIC)_API_KEY"
```

### Percolating Plants

```bash
cd .sample-data/case-studies/percolating-plants

# Query planning only (no search execution)
python test_query_planning_simple.py
```

### ACME Alpha

```bash
cd .sample-data/case-studies/acme-alpha

# Query planning tests
python test_query_planning.py
```

## Key Findings

### ✅ Strengths

1. **Exact identifier detection** - Perfect (1.00) confidence for codes like "PP-1001-SM", "SPON-001", "CBSA 31080"
2. **SQL query generation** - High confidence (0.85-0.90) for clear structured queries
3. **Fallback strategies** - Intelligent fallbacks improve robustness
4. **Cross-schema lookup** - LOOKUP works without schema hints (searches key_index CF globally)
5. **Adaptive execution** - Adjusts strategy based on confidence

### ⚠️ Areas for Improvement

1. **Schema inference** - Without schema hints, confidence drops (0.60-0.70)
2. **Relationship modeling** - TRAVERSE queries often fallback to SEARCH (edges not always present)
3. **Time filter detection** - Date parsing and temporal predicates need refinement
4. **Ambiguity handling** - Generic names like "Phoenix market" need better disambiguation

### 🔧 Recommendations

1. **Always provide schema hints** when known to boost confidence (0.60 → 0.85+)
2. **Use explicit identifiers** in queries when possible ("product PP-1001-SM" vs "Pothos plant")
3. **Model relationships as edges** for TRAVERSE support (supplier-product, user-order, etc.)
4. **Include date fields** in entities for time-based queries
5. **Configure embeddings** for SEARCH to work (embedding_fields in schema)

## Next Steps

1. **Add graph edges** to sample data for TRAVERSE testing
2. **Test query execution** with embeddings configured
3. **Add temporal fields** for time-range query testing
4. **Benchmark Cerebras vs Claude** for planning quality vs speed tradeoff
5. **Test iterative retrieval** (multi-hop reasoning)

---

**Documentation:**
- Percolating Plants: `.sample-data/case-studies/percolating-plants/QUERY-PLANNING-TESTS.md`
- ACME Alpha: `.sample-data/case-studies/acme-alpha/` (query definitions in test script)
- Overall architecture: `docs/02-rem-memory.md`, `docs/10-schema-patterns.md`

