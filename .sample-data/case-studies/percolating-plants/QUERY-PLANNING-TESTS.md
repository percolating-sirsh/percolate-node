# REM Query Planning Tests - Percolating Plants

This document describes natural language queries for testing the REM query planning system with the Percolating Plants knowledge base.

## Test Setup

```bash
# Source API keys
source ~/.bash_profile

# Verify keys are set
echo $OPENAI_API_KEY  # Required for embeddings
echo $CEREBRAS_API_KEY  # Optional, for fast query planning

# Run query planning tests (plan generation only)
python test_query_planning_simple.py
```

## Test Coverage

The tests cover all REM query types:
1. **Semantic Search** (SEARCH) - Find content by meaning
2. **Entity Lookup** (LOOKUP) - Find specific entities by ID/key
3. **Relationship Queries** (TRAVERSE) - Navigate graph relationships
4. **Hybrid Queries** (HYBRID) - Semantic + SQL filters
5. **SQL Queries** (SQL) - Structured queries with predicates

---

## Test Queries

### 1. Semantic Search

These queries use vector embeddings to find semantically similar content.

#### Query 1.1: Plant characteristics
```
Natural Language: "low maintenance indoor plants for beginners"
Expected Type: SEARCH
Expected Parameters:
  - query_text: "low maintenance indoor plants for beginners"
  - schema: "resources"
  - top_k: 10
Expected SQL: SEARCH 'low maintenance indoor plants for beginners' IN resources LIMIT 10
```

**Expected Results:**
- Pothos (Devil's Ivy) - Care Level: Easy
- Snake Plant (Sansevieria) - Care Level: Easy
- ZZ Plant - Care Level: Easy

**Query Plan Details:**
- Confidence: 0.75
- Execution Mode: adaptive
- Fallbacks: 1 (broader search if low quality)

#### Query 1.2: Light requirements
```
Natural Language: "plants that need bright indirect light"
Expected Type: SEARCH
Expected Parameters:
  - query_text: "plants that need bright indirect light"
  - schema: "resources"
  - top_k: 10
Expected SQL: SEARCH 'plants that need bright indirect light' IN resources LIMIT 10
```

**Expected Results:**
- Monstera Deliciosa - Light: Bright indirect light
- Fiddle Leaf Fig - Light: Bright indirect light
- Bird of Paradise - Light: Bright indirect light

#### Query 1.3: Rarity search
```
Natural Language: "rare variegated plants"
Expected Type: SEARCH
Expected Parameters:
  - query_text: "rare variegated plants"
  - schema: "resources"
  - top_k: 10
Expected SQL: SEARCH 'rare variegated plants' IN resources LIMIT 10
```

**Expected Results:**
- Pink Princess Philodendron (rare, high demand)
- Variegated Monstera (if in stock)

#### Query 1.4: Size/use context
```
Natural Language: "large statement plants for living room"
Expected Type: SEARCH
Expected Parameters:
  - query_text: "large statement plants for living room"
  - schema: "resources"
  - top_k: 10
Expected SQL: SEARCH 'large statement plants for living room' IN resources LIMIT 10
```

**Expected Results:**
- Monstera Deliciosa (Large: 60-90cm)
- Fiddle Leaf Fig (Large size)
- Bird of Paradise (Large tropical)

---

### 2. Entity Lookup

These queries use key-based lookup for exact matches.

#### Query 2.1: Product code lookup
```
Natural Language: "product PP-1001-SM"
Expected Type: LOOKUP
Expected Parameters:
  - keys: ["PP-1001-SM"]
Expected SQL: LOOKUP 'PP-1001-SM'
```

**Expected Results:**
- Pothos (Devil's Ivy) - Small
- Direct match by product_code

**Query Plan Details:**
- Confidence: 1.00 (exact identifier)
- Execution Mode: single_pass
- No fallbacks needed

#### Query 2.2: Product name lookup
```
Natural Language: "Monstera Deliciosa"
Expected Type: LOOKUP
Expected Parameters:
  - keys: ["Monstera Deliciosa"]
Expected SQL: LOOKUP 'Monstera Deliciosa'
```

**Expected Results:**
- Monstera Deliciosa product entity

**Query Plan Details:**
- Confidence: 0.60 (ambiguous without schema)
- Execution Mode: adaptive
- Fallbacks: 1 (semantic search if no results)

#### Query 2.3: Supplier ID lookup
```
Natural Language: "supplier SUP-001"
Expected Type: LOOKUP
Expected Parameters:
  - keys: ["SUP-001"]
Expected SQL: LOOKUP 'SUP-001'
```

**Expected Results:**
- Les Jardins de Provence supplier entity

**Query Plan Details:**
- Confidence: 1.00 (exact identifier pattern)
- Execution Mode: single_pass

#### Query 2.4: Supplier name lookup
```
Natural Language: "Les Jardins de Provence"
Expected Type: LOOKUP
Expected Parameters:
  - keys: ["Les Jardins de Provence"]
Expected SQL: LOOKUP 'Les Jardins de Provence'
```

**Expected Results:**
- Supplier entity with SUP-001

**Query Plan Details:**
- Confidence: 0.60 (could be name in any schema)
- Execution Mode: adaptive
- Fallbacks: 1 (semantic search)

---

### 3. Relationship Queries

These queries navigate graph relationships using TRAVERSE.

#### Query 3.1: Find supplier for product
```
Natural Language: "who supplies Monstera plants"
Expected Type: SEARCH or TRAVERSE
Expected Parameters (if TRAVERSE):
  - start_key: "Monstera"
  - depth: 1
  - direction: "in"
  - edge_type: "supplies"
Expected SQL: LOOKUP 'Monstera' → TRAVERSE FROM <uuid> DEPTH 1 DIRECTION in TYPE 'supplies'
```

**Expected Results:**
- Les Jardins de Provence (SUP-001)
- Other suppliers of Monstera

**Note:** Current implementation may use SEARCH instead of TRAVERSE if relationships aren't explicitly modeled as edges.

#### Query 3.2: Find products from supplier
```
Natural Language: "all products from Les Jardins de Provence"
Expected Type: SQL or TRAVERSE
Expected Parameters:
  - schema: "resources"
  - where: {"supplier": "Les Jardins de Provence"}
Expected SQL: SELECT * FROM resources WHERE supplier = 'Les Jardins de Provence'
```

**Expected Results:**
- All products supplied by Les Jardins de Provence
- French-origin plants

#### Query 3.3: Customer-product relationships
```
Natural Language: "customers who bought Pink Princess"
Expected Type: SEARCH or TRAVERSE
```

**Expected Results:**
- Customer entities with purchase history
- Order records mentioning Pink Princess

**Note:** May return customer service emails or order documents mentioning Pink Princess.

---

### 4. Hybrid Queries (Semantic + Filters)

These combine semantic search with SQL predicates.

#### Query 4.1: Semantic + time filter
```
Natural Language: "customer emails about plant care from last month"
Expected Type: SQL or HYBRID
Expected Parameters:
  - schema: "resources"
  - where: {date filter + topic filter}
Expected SQL: SELECT * FROM resources WHERE topic = 'plant care' AND date >= '...'
```

**Expected Results:**
- Email documents about plant care
- Customer service correspondence

**Query Plan Details:**
- Confidence: 0.85 (clear structured query)
- Execution Mode: adaptive
- May use time-based filters if date fields exist

#### Query 4.2: Semantic + attribute filter
```
Natural Language: "low stock plants under 20 pounds"
Expected Type: SQL or HYBRID
Expected Parameters:
  - schema: "resources"
  - where: {"stock_level": "<20", "price_gbp": "<20"}
Expected SQL: SELECT * FROM resources WHERE type = 'plant' AND stock < 20 AND price < 20
```

**Expected Results:**
- Products with low stock AND price under £20
- Pink Princess Philodendron (£18, 5 units)

**Query Plan Details:**
- Confidence: 0.85
- Execution Mode: multi_stage
- Fallback: Remove price constraint if no results

#### Query 4.3: Semantic + recency
```
Natural Language: "recent blog posts about Monstera care"
Expected Type: SEARCH or HYBRID
Expected Parameters:
  - query_text: "Monstera care blog posts"
  - schema: "resources"
  - filters: {recency or date filter}
Expected SQL: SEARCH 'recent blog posts about Monstera care' IN resources LIMIT 10
```

**Expected Results:**
- Blog post about Monstera care
- Care guides mentioning Monstera

---

### 5. SQL Queries

These are structured queries with explicit predicates.

#### Query 5.1: Filter by type
```
Natural Language: "all plants in stock"
Expected Type: SQL
Expected Parameters:
  - schema: "resources"
  - where: {"type": "plant"}
Expected SQL: SELECT * FROM resources WHERE type = 'plant'
```

**Expected Results:**
- All plant products (not accessories)
- ~10 plant entities

**Query Plan Details:**
- Confidence: 0.90 (clear structured query)
- Execution Mode: single_pass

#### Query 5.2: Price filter
```
Natural Language: "products under 30 pounds"
Expected Type: SQL
Expected Parameters:
  - schema: "resources"
  - where: {"price_gbp": "< 30"}
Expected SQL: SELECT * FROM resources WHERE price_gbp < 30
```

**Expected Results:**
- Most plants (except large specimens)
- Accessories

**Query Plan Details:**
- Confidence: 0.90
- Execution Mode: single_pass

---

## Running the Tests

### Plan-Only Tests (No API Keys Needed for Execution)
```bash
# Test query planning (generates plans only)
python test_query_planning_simple.py
```

**Output:**
- Query type for each query
- Confidence scores
- Executable SQL for each plan
- Fallback strategies

### Full Execution Tests (Requires Embeddings)
```bash
# Ensure API keys are set
source ~/.bash_profile

# Run execution tests (searches database)
python test_query_execution.py
```

**Note:** Execution tests require:
1. `OPENAI_API_KEY` for embedding generation
2. Database populated with embeddings enabled
3. No database locks (close other connections)

---

## Test Results Summary

All 16 query planning tests should pass with these characteristics:

| Query Type | Count | Expected Confidence | Fallbacks |
|------------|-------|---------------------|-----------|
| SEARCH | 7 | 0.70-0.80 | 1-2 |
| LOOKUP | 4 | 0.60-1.00 | 0-1 |
| SQL | 3 | 0.85-0.90 | 0 |
| TRAVERSE | 0-2 | 0.70-0.80 | 1 |
| HYBRID | 0-2 | 0.75-0.85 | 1 |

**Note:** TRAVERSE queries may be interpreted as SEARCH if relationships aren't explicitly modeled as graph edges.

---

## Known Issues

1. **Embeddings Required:** Search queries require embeddings. Data must be inserted with `embedding_fields` configured in schema.

2. **Database Locks:** Can't have multiple Database instances accessing same DB simultaneously. Use single connection or close others.

3. **Relationship Modeling:** Current implementation may not have explicit graph edges for supplier-product relationships, so TRAVERSE queries may fallback to SEARCH.

4. **Time Filters:** Date filtering requires date fields in entities. Current sample data may not have consistent date fields.

---

## Next Steps

1. **Re-populate with embeddings:** Update populate script to configure embeddings
2. **Add graph edges:** Model supplier-product relationships as explicit edges
3. **Add timestamps:** Include created_at, modified_at fields for time-based queries
4. **Test execution:** Run full execution tests once embeddings are configured

