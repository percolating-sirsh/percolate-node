# MCP Tools - Schema-Aware Knowledge Base Access

## Overview

This directory contains MCP (Model Context Protocol) tool and resource definitions for **schema-aware** access to the REM knowledge base. Felix Prime uses these tools through Claude Desktop or other MCP clients to query deals, entities, market data, and documents.

## Key Innovation: Schema Discovery

Unlike traditional knowledge bases with a single search interface, Percolate exposes **multiple schemas** with different search strategies:

- **resources**: Document chunks with embeddings (semantic search)
- **entities**: Structured data with graph traversal (sponsors, deals, properties)
- **moments**: Timestamped events (deal analyses, interactions)
- **trends**: Time series data (NCREIF, CBSA, energy prices, rates)

MCP clients can **discover available schemas** and their specifications via special resources.

## MCP Tools

### 1. `search_knowledge_base`
**Purpose**: Structured search with explicit schema targeting

**Key Features**:
- `schema` parameter: Target specific data type (resources|entities|moments|trends|all)
- Schema-specific filters
- Ranked results with relevance scores

**Examples**:
```typescript
// Semantic search on documents
search_knowledge_base({
  query: "industrial warehouse Columbus Ohio",
  schema: "resources",
  limit: 5
})

// Entity lookup
search_knowledge_base({
  query: "Greenline Renewables track record",
  schema: "entities",
  filters: { entity_type: "sponsor" }
})

// Time series query
search_knowledge_base({
  query: "apartment cap rates",
  schema: "trends",
  filters: {
    category: "property_benchmark",
    sub_category: "Apartment",
    start_date: "2024-01-01",
    end_date: "2024-09-30"
  }
})
```

**When to use**: Programmatic queries, specific schema targeting, bulk operations

---

### 2. `ask`
**Purpose**: Natural language questions with intelligent routing

**Key Features**:
- Intent classification (trend_query, semantic_search, entity_lookup, relationship_query, etc.)
- Automatic routing to optimal search strategy
- Conversational answers (not just search results)
- Follow-up question suggestions

**Routing Logic**:
| Question Type | Triggers | Strategy | Example |
|--------------|----------|----------|---------|
| Trend query | "recent trends", "NCREIF", "cap rate", "population growth" | SQL on trends schema | "What are recent NCREIF apartment cap rates?" |
| Semantic search | "find documents about", "mentions of" | Vector search on resources | "Find documents about solar energy" |
| Entity lookup | "who is", "track record", "details" | Entity property search | "What is Greenline's track record?" |
| Relationship query | "colleagues of", "deals by", "connected to" | Graph traversal | "What deals has Felix analyzed?" |
| Temporal query | "recent", "last month", "this quarter" | Moments temporal index | "What deals were analyzed recently?" |
| Aggregation | "average", "compare", "trend over time" | SQL aggregation | "Compare apartment vs office cap rates" |

**Examples**:
```typescript
// Trend query
ask({
  question: "What are the latest NCREIF apartment cap rates?"
})
// → Routes to SQL on trends, returns: "Latest apartment cap rates: 5.35% (2024-Q3)..."

// Semantic search
ask({
  question: "Find all documents mentioning solar energy in California"
})
// → Routes to vector search on resources

// Relationship traversal
ask({
  question: "What deals has Felix Prime analyzed?"
})
// → Routes to graph traversal on entities

// Population growth
ask({
  question: "What's the population growth in Austin over the last year?"
})
// → Routes to SQL on trends with CBSA filter
```

**When to use**: Exploratory questions, analyst workflows, conversational interfaces

---

## MCP Resources (Schema Discovery)

### `schema://list`
Returns list of all available schemas with metadata.

**Response**:
```json
{
  "schemas": [
    {
      "name": "resources",
      "description": "Document chunks with embeddings",
      "count": 0,
      "supports_search": true,
      "supports_embedding": true
    },
    {
      "name": "entities",
      "description": "Structured entities (sponsors, properties, deals)",
      "count": 70,
      "entity_types": ["deal", "sponsor", "property", "market_sector", "lender", "analyst"]
    },
    {
      "name": "trends",
      "description": "Time series data (NCREIF, CBSA, energy, rates)",
      "count": 437,
      "categories": ["property_benchmark", "market_metric", "energy_price", "interest_rate"]
    }
  ]
}
```

**Use case**: "What data is available in this knowledge base?"

---

### `schema://spec/<name>`
Returns full specification for a specific schema.

**Examples**:

#### `schema://spec/trends`
```json
{
  "schema_name": "trends",
  "key_structure": "trend:{tenant_id}:{sub_category}:{key}:{date}",
  "unique_constraint": "sub_category + key + date",
  "categories": {
    "property_benchmark": {
      "sub_categories": ["Apartment", "Industrial-Warehouse", "Office"],
      "keys": ["total_return_pct", "cap_rate_pct", "occupancy_pct"],
      "source": "NCREIF"
    },
    "market_metric": {
      "sub_categories": ["CBSA-19740", "CBSA-12060", "CBSA-36740"],
      "keys": ["population_growth_yoy_pct", "employment_growth_yoy_pct"],
      "source": "US Census Bureau"
    }
  },
  "ingestion_command": "percolate ingest --file data.csv --schema trends --category {category}"
}
```

**Use case**: "What categories and keys are available in the trends schema?"

---

#### `schema://spec/entities`
```json
{
  "schema_name": "entities",
  "entity_types": {
    "deal": {
      "id_pattern": "deal:XXX-NNN",
      "required_properties": ["deal_name", "asset_class"],
      "example": "deal:GLV-001"
    },
    "sponsor": {
      "id_pattern": "sponsor:XXX-NNN",
      "required_properties": ["name", "track_record"],
      "example": "sponsor:GRN-001"
    }
  },
  "edge_types": ["SPONSORS", "ASSET", "ANALYZED_BY"]
}
```

**Use case**: "What entity types can I search for?"

---

## Usage Workflow

### 1. Schema Discovery
```typescript
// Step 1: Discover available schemas
GET schema://list
// → Returns: resources, entities, moments, trends

// Step 2: Get specification for trends
GET schema://spec/trends
// → Returns: categories, keys, ingestion commands

// Step 3: Search specific schema
search_knowledge_base({
  query: "apartment cap rates",
  schema: "trends",
  filters: { category: "property_benchmark" }
})
```

### 2. Natural Language Queries
```typescript
// One-shot natural language query
ask({ question: "What are recent NCREIF apartment trends?" })
// → System discovers schema, routes query, returns answer

// No need for manual schema discovery in conversational mode
```

### 3. Programmatic Queries
```typescript
// Explicit schema targeting for programmatic use
search_knowledge_base({
  query: "population growth Austin",
  schema: "trends",
  filters: {
    sub_category: "CBSA-12420",
    key: "population_growth_yoy_pct",
    start_date: "2024-01-01"
  },
  limit: 10
})
```

## Comparison: `search_knowledge_base` vs `ask`

| Feature | `search_knowledge_base` | `ask` |
|---------|------------------------|-------|
| Schema targeting | Explicit via `schema` param | Automatic via intent classification |
| Input format | Structured (query + filters) | Natural language question |
| Output format | Ranked results | Conversational answer |
| Routing | Manual | Automatic |
| Follow-ups | No | Yes (suggested questions) |
| Best for | Programmatic, bulk ops | Exploratory, conversational |

**Rule of thumb**:
- Use `search_knowledge_base` when you **know the schema** and want structured results
- Use `ask` when you have a **natural question** and want the system to figure out routing

## Testing

### Test Ingestion Pipeline
```bash
cd market-data
python3 test_ingest_embeddings.py
```

**Results**:
- ✅ 1,235 trend data points ingested
- ✅ Idempotent upserts (deterministic keys)
- ✅ Temporal queries (date range filtering)
- ✅ Cross-sectional queries (compare across categories)

### Test Query Interface
```bash
cd market-data
python3 test_query_trends.py
```

**Results**:
- ✅ Latest cap rates by property type
- ✅ Population growth across markets
- ✅ Wind PPA rate comparisons
- ✅ SOFR rate trends
- ✅ Time series aggregation

## Implementation Notes

### Schema Registration
Custom schemas can be registered and will automatically appear in `schema://list`:

```python
from percolate.memory import REMDatabase

db = REMDatabase()
db.register_schema(
    name="custom_metrics",
    description="Custom financial metrics",
    key_pattern="custom:{tenant_id}:{metric}:{date}",
    supports_embedding=False,
    search_strategy="temporal"
)
```

### Search Strategies by Schema

| Schema | Primary Index | Search Strategy | Supports Embedding |
|--------|--------------|-----------------|-------------------|
| resources | Vector (HNSW) | Semantic similarity | ✅ Yes |
| entities | Property + Graph | Fuzzy match + traversal | ❌ No |
| moments | Temporal | Date range + type filter | ❌ No |
| trends | Temporal + Category | SQL aggregation | ❌ No* |

*Trends CAN use embeddings for metadata/descriptions, but structured queries are more efficient for time series.

### Performance Optimization

1. **Schema-specific indexes**: Each schema uses optimized indexes (vector, temporal, property, graph)
2. **Query routing**: Intent classification routes to most efficient strategy
3. **Result caching**: Schema specs can be cached by MCP clients
4. **Federated search**: `schema: "all"` uses score fusion across schemas

## Files in This Directory

- **search_knowledge_base.json**: Structured search tool with schema targeting
- **ask.json**: Natural language query tool with intelligent routing
- **schema-resources.json**: MCP resources for schema discovery
- **README.md**: This file

## Related Documentation

- `../market-data/schema-trends.md`: Full trends schema specification
- `../entities.yaml`: Entity ground truth with NCREIF/NAICS/CBSA codes
- `../about.md`: Complete case study profile
- `../README.md`: Quick start guide

## Next Steps

1. Implement MCP server with these tool definitions
2. Test with Claude Desktop MCP client
3. Add custom schemas for deal-specific metrics
4. Implement federated search for `schema: "all"`
5. Add schema versioning for evolution
