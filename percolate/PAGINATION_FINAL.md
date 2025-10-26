# Pagination - Final Minimal Implementation

## Core Concept

The agent already has its system prompt. We just:
1. Chunk the input data
2. Run agent on each chunk
3. Merge results

That's it.

## API

```python
result = await paginated_request(
    agent=agent,     # Pre-configured with system prompt
    content=data,    # Input to paginate
    config=config,   # How to chunk and merge
)
```

**No prompt parameter** - the agent already knows what to do.

## Complete Example

```python
from percolate.agents.factory import create_agent
from percolate.agents.pagination import paginated_request, PaginationConfig

# 1. Create agent (has system prompt in schema)
agent = await create_agent(
    context=AgentContext(tenant_id="user-123"),
    agent_schema_override={
        "description": "Extract entities from text",  # System prompt
        "properties": {"entities": {"type": "array", "items": {"type": "string"}}},
    },
    result_type=EntityExtractor,
)

# 2. Use pagination for large input
result = await paginated_request(
    agent=agent,
    content=large_document,  # Automatically chunked
    config=PaginationConfig(merge_strategy="merge", chunk_size=50),
)
```

## File Stats

- **pagination.py**: 218 lines (was 420 originally)
- **Tests**: 44 tests, all passing in 0.37s
- **Reduction**: 48% less code

## What It Does

1. **Detects content type** - list (records) or string (text)
2. **Chunks content** - preserves boundaries (sentence/record)
3. **Executes agent** - parallel or sequential
4. **Merges results** - concat, merge, first, last, or custom

## Merge Strategies

- `concat` - Returns list of all chunk results
- `merge` - Combines list fields, keeps first non-list values
- `first` - Returns first chunk result only
- `last` - Returns last chunk result only (default)
- `custom` - User-defined merge function

## Key Principle

**The agent knows what to do. We just paginate the data.**

No extra prompts, no confusion, no unnecessary parameters.

## Test Results

```bash
$ uv run pytest tests/unit/agents/test_pagination_unit.py tests/unit/utils/test_chunking.py -v

44 passed in 0.37s ✅
```

## Files

- `src/percolate/agents/pagination.py` - Core implementation (218 lines)
- `src/percolate/utils/chunking.py` - Chunking utilities (550 lines)
- `docs/examples/pagination_simple.py` - Usage example
- `tests/unit/agents/test_pagination_unit.py` - 13 tests
- `tests/unit/utils/test_chunking.py` - 31 tests
