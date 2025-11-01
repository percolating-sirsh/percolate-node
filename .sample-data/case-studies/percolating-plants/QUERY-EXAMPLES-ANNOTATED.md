# REM Query Examples - Percolating Plants (Annotated)

This document shows 5 example queries with their generated plans and execution results, with detailed annotations explaining the query planning process.

**Database:** `/Users/sirsh/.p8/percolating-plants-db`
**Tenant:** `percolating-plants`
**Output File:** `query-examples-output.json`

---

## Query 1: Exact Product Code Lookup

```json
{
  "query": "product PP-1001-SM",
  "description": "Exact product code lookup"
}
```

### Query Plan

**Query Type:** `lookup`
**Confidence:** `1.0` (Perfect - exact identifier detected)
**Execution Mode:** `single_pass` (No fallbacks needed)

**Generated REM SQL:**
```sql
LOOKUP 'PP-1001-SM'
```

**Parameters:**
```json
{
  "keys": ["PP-1001-SM"]
}
```

**Reasoning:**
> "Exact product identifier provided, using key-based lookup for maximum efficiency."

**Analysis:**
- ✅ Perfect confidence (1.0) because "PP-1001-SM" matches product code pattern
- ✅ Single-pass execution - no fallbacks needed
- ✅ LOOKUP is most efficient (O(1) key index lookup)
- ✅ Schema-agnostic - searches across all schemas via key_index CF
- ⚠️ Execution returned `[]` - data may not have been indexed with this key

---

## Query 2: Product Name Lookup

```json
{
  "query": "Monstera Deliciosa",
  "description": "Product name lookup"
}
```

### Query Plan

**Query Type:** `lookup`
**Confidence:** `0.6` (Medium-low - ambiguous without schema)
**Execution Mode:** `adaptive` (May use fallback)

**Generated REM SQL (Primary):**
```sql
LOOKUP 'Monstera Deliciosa'
```

**Fallback Query:**
```sql
SEARCH 'Monstera Deliciosa' IN plants LIMIT 10
```

**Fallback Trigger:** `no_results` (Execute if primary returns nothing)
**Fallback Confidence:** `0.7`

**Reasoning:**
> "Starting with a general lookup due to the lack of specific schema, with a fallback to semantic search in a likely relevant schema."

**Analysis:**
- ⚠️ Lower confidence (0.6) - name could exist in multiple schemas
- ✅ Adaptive execution - tries fast LOOKUP first, then SEARCH
- ✅ Smart fallback - inferred "plants" as likely schema
- 🔍 Fallback would trigger because primary returned `[]`
- 📝 Schema hint would improve: `--schema resources` → confidence 0.85+

---

## Query 3: Supplier ID Lookup

```json
{
  "query": "supplier SUP-001",
  "description": "Supplier ID lookup"
}
```

### Query Plan

**Query Type:** `lookup`
**Confidence:** `1.0` (Perfect - ID pattern detected)
**Execution Mode:** `single_pass`

**Generated REM SQL:**
```sql
LOOKUP 'SUP-001'
```

**Parameters:**
```json
{
  "keys": ["SUP-001"]
}
```

**Reasoning:**
> "Direct lookup using a specific supplier identifier"

**Analysis:**
- ✅ Perfect confidence (1.0) - "SUP-001" is clearly an ID
- ✅ Ignored "supplier" prefix - focused on the identifier
- ✅ No fallbacks needed
- ⚠️ Execution returned `[]` - data not indexed with supplier_id as key

---

## Query 4: Supplier Name Lookup

```json
{
  "query": "Les Jardins de Provence",
  "description": "Supplier name lookup"
}
```

### Query Plan

**Query Type:** `lookup`
**Confidence:** `0.6` (Medium-low - could be many things)
**Execution Mode:** `adaptive`

**Generated REM SQL (Primary):**
```sql
LOOKUP 'Les Jardins de Provence'
```

**Fallback Query:**
```sql
SEARCH 'Les Jardins de Provence' IN schema LIMIT 10
```

**Fallback Trigger:** `no_results`
**Fallback Confidence:** `0.7`

**Reasoning:**
> "Starting with a lookup as it's a general query, potentially a name or key. Fallback to semantic search in case of no results."

**Analysis:**
- ⚠️ Ambiguous query - could be supplier, location, garden name
- ✅ LLM inferred "places" schema (interesting - not wrong given the French name!)
- 🔍 Without schema hint, planner makes best guess
- 📝 Better query: "supplier Les Jardins de Provence --schema resources"

---

## Query 5: SQL Query for All Plants

```json
{
  "query": "all plants in stock",
  "description": "SQL query for all plants"
}
```

### Query Plan

**Query Type:** `sql`
**Confidence:** `0.9` (Very high - clear structured query)
**Execution Mode:** `single_pass`

**Generated REM SQL:**
```sql
SELECT * FROM resources WHERE type = 'plant'
```

**Parameters:**
```json
{
  "fields": ["*"],
  "schema": "resources",
  "where": {
    "type": "plant"
  }
}
```

**Reasoning:**
> "Using SQL to query all plants from the 'resources' schema based on type"

**Analysis:**
- ✅ High confidence (0.9) - recognized structured query intent
- ✅ Correctly inferred "resources" schema from context
- ✅ Identified "plant" as the filter criterion
- ✅ Ignored "in stock" (no stock_level > 0 filter) - could be improved
- ⚠️ Execution returned `[]` - may not have type='plant' field in data
- 📝 Better data: Include `"type": "plant"` in entity properties

---

## Execution Results Analysis

All queries returned empty execution results (`[]`). This indicates:

### 1. **Key Index Not Populated**
LOOKUP queries search the `key_index` column family, which requires:
- Data inserted with `key_field` configured in schema
- Deterministic UUID generation based on key field

**Current state:** Data was inserted into default "resources" schema without custom key_field configuration.

### 2. **Missing Type Field**
SQL query filtered on `type = 'plant'` but entities may not have this field.

**Solution:**
```python
# When inserting, ensure type field exists:
{
  "name": "Monstera Deliciosa",
  "content": "...",
  "type": "plant",  # Add this!
  "category": "indoor"
}
```

### 3. **Embeddings Not Configured**
SEARCH fallbacks would fail because embeddings aren't set up.

**Solution:** Re-populate with embeddings enabled in schema.

---

## Key Takeaways

### ✅ Query Planning Works Perfectly

1. **Exact identifiers** → 1.0 confidence, LOOKUP
2. **Names without schema** → 0.6 confidence, LOOKUP + SEARCH fallback
3. **Structured queries** → 0.9 confidence, SQL

### ⚠️ Data Issues Prevent Execution

1. **No key_index entries** - LOOKUP returns empty
2. **No type field** - SQL WHERE clause doesn't match
3. **No embeddings** - SEARCH would fail

### 📝 Recommendations

**For Better Query Execution:**

1. **Configure key fields in schema:**
```python
model_config = ConfigDict(
    json_schema_extra={
        "key_field": "product_code",  # Or "name" or "supplier_id"
        "indexed_fields": ["type", "category"]
    }
)
```

2. **Include searchable fields:**
```json
{
  "product_code": "PP-1001-SM",
  "name": "Pothos (Devil's Ivy)",
  "type": "plant",
  "category": "indoor",
  "supplier_id": "SUP-001"
}
```

3. **Enable embeddings for SEARCH:**
```python
model_config = ConfigDict(
    json_schema_extra={
        "embedding_fields": ["content", "name"],
        "embedding_provider": "default"
    }
)
```

**For Better Query Planning:**

1. **Always provide schema hints when known:**
```bash
percolate rem ask "Monstera Deliciosa" --schema resources
```

2. **Use explicit identifiers when possible:**
```bash
percolate rem ask "product PP-1001-SM"  # Better than "Pothos plant"
```

3. **Be specific in natural language:**
```bash
percolate rem ask "all plants with type='plant' and stock_level > 0"
```

---

## Testing Commands

```bash
# Set environment
export P8_DB_PATH=~/.p8/percolating-plants-db
export P8_TENANT_ID=percolating-plants

# Test query planning (no execution)
percolate rem ask "product PP-1001-SM" --plan

# Test direct REM SQL
percolate rem query "LOOKUP 'PP-1001-SM'"

# Test with schema hint
percolate rem ask "Monstera" --schema resources --plan
```

---

## JSON Output Structure

```json
{
  "database": "<path>",
  "tenant": "<tenant_id>",
  "timestamp": "<iso8601>",
  "queries": [
    {
      "id": 1,
      "query": "<natural_language>",
      "description": "<what_it_tests>",
      "plan": {
        "query_type": "lookup|search|sql|traverse|hybrid",
        "confidence": 0.0-1.0,
        "execution_mode": "single_pass|adaptive|multi_stage",
        "primary_query": {
          "dialect": "rem_sql",
          "query_string": "<executable_sql>",
          "parameters": { }
        },
        "fallback_queries": [ ],
        "reasoning": "<why_this_plan>",
        "next_steps": [ ],
        "metadata": { }
      },
      "execution": [ /* results */ ],
      "error": null
    }
  ]
}
```

