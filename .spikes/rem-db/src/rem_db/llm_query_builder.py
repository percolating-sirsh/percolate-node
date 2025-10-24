"""LLM-powered natural language query builder.

## Overview

Converts user questions in natural language to executable database queries.
Intelligently chooses between query types and provides confidence scoring.

## Features

### Multi-stage retrieval
Automatic fallback if primary query returns no results:
1. Try specific query (e.g., exact field match)
2. If no results, broaden search (e.g., semantic similarity)
3. Up to max_stages attempts
4. Returns results + metadata showing stages used

### Query type detection
Chooses optimal query strategy:
- **entity_lookup**: Global search when table unknown (e.g., "what is 12345?")
- **sql**: Field-based filtering when structure known
- **vector**: Semantic similarity for conceptual queries
- **hybrid**: Combination (e.g., semantic + temporal filters)
- **graph**: Relationship traversal (future)

### Confidence scoring
- 1.0: Exact ID lookup
- 0.8-0.95: Clear field-based query
- 0.6-0.8: Semantic/vector search
- < 0.6: Ambiguous (explanation provided)

Low confidence triggers explanation field for transparency.

### Schema awareness
Query builder loads entity schemas to understand:
- Available fields and types
- Field descriptions (semantic matching)
- Indexed fields (efficient queries)

This prevents hallucination and enables accurate field-based queries.

## Usage

```python
from rem_db import REMDatabase

db = REMDatabase(tenant_id="default", path="./db")

# Simple query
result = db.query_natural_language(
    "find resources about Python programming",
    table="resources"
)

print(f"Query: {result['query']}")
print(f"Type: {result['query_type']}")
print(f"Confidence: {result['confidence']:.2f}")
print(f"Results: {len(result['results'])}")

# Multi-stage retrieval
result = db.query_natural_language(
    "resources about machine learning with TensorFlow",
    table="resources",
    max_stages=3
)

if result['stages'] > 1:
    print(f"Used {result['stages']} retrieval stages")
```

## CLI command

```bash
# Basic query
rem-db ask "find tutorials about programming"

# Specify table
rem-db ask "agents with Python skills" --table agents

# Show metadata
rem-db ask "resources about web dev" --metadata

# Adjust retrieval stages
rem-db ask "specific technical query" --max-stages 5
```

## Query strategies

### Entity lookup (global search)
When table/schema unknown and user provides identifier:

```bash
rem-db ask "what is 12345?"
rem-db ask "find TAP-1234"
rem-db ask "tell me about DHL"
```

Searches all entities by ID/name/alias across all tables.

### SQL queries (structured)
When table known and field-based filtering clear:

```bash
rem-db ask "resources with category tutorial"
rem-db ask "agents created in the last 7 days"
rem-db ask "resources where status is active or published"
```

Generates SQL with WHERE predicates.

### Vector search (semantic)
For conceptual/paraphrase queries:

```bash
rem-db ask "find resources about authentication and security"
rem-db ask "tutorials for beginners learning to code"
```

Uses embedding similarity (cosine or inner_product).

### Hybrid queries
Combination of semantic + filters:

```bash
rem-db ask "Python resources from the last month"
rem-db ask "active agents about coding"
```

Vector search + temporal/categorical filters.

## Architecture

```
User Query
    ↓
QueryBuilder
  - Load schema
  - Build prompt
  - Call LLM (GPT-4)
  - Parse JSON
    ↓
REMDatabase
  - Execute SQL/vector
  - Check result count
  - Fallback if needed
  - Return results
    ↓
Results + Metadata
```

## Response structure

```python
{
    "results": [
        {
            "id": "550e8400-...",
            "name": "Python Tutorial",
            "content": "Learn Python...",
            "_score": 0.87  # If vector search
        }
    ],
    "query": "SELECT * FROM resources WHERE embedding.cosine('Python') LIMIT 10",
    "query_type": "vector",
    "confidence": 0.85,
    "explanation": None,  # Only if confidence < 0.8
    "follow_up_question": None,  # For iterative retrieval
    "fallback_query": "SELECT * FROM resources LIMIT 10",
    "stages": 1  # Number of retrieval stages used
}
```

## Configuration

Requires OpenAI API key:
```bash
export OPENAI_API_KEY='your-key-here'
```

Default model: gpt-4-turbo-preview

Override in code:
```python
from rem_db.llm_query_builder import QueryBuilder

builder = QueryBuilder(
    api_key="key",
    model="gpt-3.5-turbo",  # Faster, cheaper
)
```

## Performance

- **LLM call**: 500-2000ms (depends on model, load)
- **Query execution**: 1-100ms (depends on type)
- **Total**: ~1-3 seconds typical

Optimization strategies:
1. Use SQL directly for known queries (bypass LLM)
2. Cache common patterns
3. Batch requests
4. Choose faster models (gpt-3.5-turbo vs gpt-4)

## Costs

- GPT-4-turbo: ~$0.01 per query (input + output)
- GPT-3.5-turbo: ~$0.001 per query
- Local models: $0 (future)

## Limitations

Current:
- Single table only (no JOINs)
- No aggregations (COUNT, SUM, AVG)
- Limited temporal filtering
- Requires API key
- Cost per query

Future enhancements:
- Graph traversal queries
- Aggregation support
- Multi-table JOINs
- Query caching
- Alternative LLM providers (Claude, Llama, local)
- Query plan explanation
"""

import os
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field


class QueryResult(BaseModel):
    """Structured output from LLM query builder."""

    query_type: str = Field(description="Type of query: 'key_value', 'sql', or 'vector'")
    query: str = Field(description="Generated query string")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in query correctness (0-1)")
    explanation: Optional[str] = Field(
        None, description="Explanation of query (only if confidence < 0.8)"
    )
    follow_up_question: Optional[str] = Field(
        None, description="Optional follow-up question for staged retrieval"
    )
    fallback_query: Optional[str] = Field(
        None, description="Fallback query if primary returns no results"
    )


class QueryBuilder:
    """Natural language to SQL/vector query builder using LLM.

    Features:
    - Loads entity schemas for semantic understanding
    - Generates structured queries with confidence scores
    - Supports multi-stage retrieval with fallbacks
    - Chooses appropriate query type (key-value, SQL, vector)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4-turbo-preview",
        base_url: str = "https://api.openai.com/v1",
    ):
        """Initialize query builder.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Model name (default: gpt-4-turbo-preview)
            base_url: API base URL
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key required (set OPENAI_API_KEY env var)")

        self.model = model
        self.base_url = base_url
        self.client = httpx.Client(timeout=30.0)

    def build_query(
        self,
        natural_language: str,
        schema: dict[str, Any],
        table: str,
        max_stages: int = 3,
    ) -> QueryResult:
        """Build query from natural language.

        Args:
            natural_language: User's natural language query
            schema: Entity schema (JSON Schema format)
            table: Target table name
            max_stages: Maximum retrieval stages for fallbacks

        Returns:
            QueryResult with generated query and metadata
        """
        prompt = self._build_prompt(natural_language, schema, table, max_stages)
        response = self._call_llm(prompt)
        return self._parse_response(response)

    def _build_prompt(
        self, natural_language: str, schema: dict[str, Any], table: str, max_stages: int
    ) -> str:
        """Build prompt for LLM.

        Args:
            natural_language: User's query
            schema: Entity schema
            table: Table name
            max_stages: Max retrieval stages

        Returns:
            Formatted prompt string
        """
        schema_fields = schema.get("properties", {})
        field_descriptions = "\n".join(
            f"  - {name}: {props.get('type', 'unknown')} - {props.get('description', 'No description')}"
            for name, props in schema_fields.items()
        )

        return f"""You are a query builder for the REM database system.

USER QUERY: "{natural_language}"

TARGET TABLE: {table}

SCHEMA:
{field_descriptions}

QUERY TYPES:
1. **key_value**: Direct lookup by primary key (id field)
   - Use when user provides exact ID or unique identifier
   - Example: "get resource abc-123" → SELECT * FROM resources WHERE id = 'abc-123'

2. **sql**: SQL SELECT with predicates
   - Use for field-based filtering (equality, comparisons, IN)
   - Example: "resources with name Python" → SELECT * FROM resources WHERE name = 'Python'

3. **vector**: Semantic similarity search using embeddings
   - Use for conceptual or meaning-based queries
   - Syntax: WHERE embedding.cosine("query text") or embedding.inner_product("query text")
   - Example: "resources about programming" → SELECT * FROM resources WHERE embedding.cosine("programming") LIMIT 10

DISTANCE METRICS:
- Use cosine for sentence-transformers models (default)
- Use inner_product for normalized embeddings (OpenAI models)

QUERY STRATEGY:
1. Prefer simplest query type that will work (key_value > sql > vector)
2. If confidence < 0.8, provide explanation
3. Suggest fallback query if primary might return no results
4. Maximum {max_stages} retrieval stages allowed

OUTPUT FORMAT (JSON):
{{
  "query_type": "key_value" | "sql" | "vector",
  "query": "SELECT ...",
  "confidence": 0.0-1.0,
  "explanation": "Optional explanation if confidence < 0.8",
  "follow_up_question": "Optional follow-up for staged retrieval",
  "fallback_query": "Optional fallback if no results"
}}

Generate the query now:"""

    def _call_llm(self, prompt: str) -> dict[str, Any]:
        """Call OpenAI API with structured output.

        Args:
            prompt: Formatted prompt

        Returns:
            LLM response dict
        """
        response = self.client.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def _parse_response(self, response: str) -> QueryResult:
        """Parse LLM JSON response.

        Args:
            response: JSON string from LLM

        Returns:
            Parsed QueryResult
        """
        import json

        data = json.loads(response)
        return QueryResult(**data)

    def close(self) -> None:
        """Close HTTP client."""
        self.client.close()
