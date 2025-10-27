# Dreaming Module - Background Indexing with Agents

## Overview

The dreaming module handles background processing tasks:
- Document indexing
- Metadata extraction
- Entity recognition
- Classification
- Embedding generation

## Paginated Agentic Requests

See [paginated-agentic-requests.md](./paginated-agentic-requests.md) for detailed design.

### Quick Summary

Allow percolate-rocks to make LLM requests directly from Rust for background processing:

```rust
// Database can process documents with agents
let db = RocksDB::new("/path/to/db")?;

// Store agent schema
db.store_agent_schema("tenant-123", AgentSchema {
    name: "entity-extractor",
    system_prompt: "Extract entities from text",
    output_schema: json!({
        "type": "object",
        "properties": {
            "entities": {"type": "array", "items": {"type": "string"}}
        }
    }),
    model: "claude-haiku-4-5",
    ..Default::default()
})?;

// Process large document with pagination
let result = db.process_with_agent(
    "tenant-123",
    "entity-extractor",
    large_document,
)?;
```

### Key Benefits

1. **Self-contained** - Database can process data without Python layer
2. **Fast** - Native Rust performance
3. **Simple** - Minimal dependencies (reqwest, tokio, tiktoken-rs)
4. **Scalable** - Parallel processing in Rust

### Reference Implementation

Python implementation: `percolate/src/percolate/agents/pagination.py`

The Python version handles interactive API requests.
The Rust version handles background indexing.

### Status

**Planning phase** - Module stubs created in `src/agents/`

Implementation phases:
1. HTTP client (Week 1)
2. Chunking (Week 2)
3. Pagination (Week 3)
4. Schema storage (Week 4)
5. Dreaming integration (Week 5)
6. Production hardening (Week 6)

### Files

- `docs/dreaming/paginated-agentic-requests.md` - Detailed design
- `src/agents/mod.rs` - Module definition
- `src/agents/client.rs` - HTTP client (stub)
- `src/agents/chunking.rs` - Token-aware chunking (stub)
- `src/agents/pagination.rs` - Pagination engine (stub)
- `src/agents/schema.rs` - Schema storage (stub)

### Next Steps

1. Review design document
2. Validate approach with team
3. Begin Phase 1 implementation (HTTP client)
4. Add to roadmap

## Related

- Background indexing: `src/dreaming/mod.rs` (when created)
- Memory layer: `src/memory/`
- Vector search: `src/embeddings/`
