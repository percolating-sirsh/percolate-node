# Paginated Agentic Requests - Implementation Status

## Overview

Planning phase for implementing paginated agentic requests in percolate-rocks (Rust) for background indexing. This allows the database to make LLM requests directly without the Python layer.

## Design Principles

**Lightweight and minimal:**
- ✅ Use `reqwest` HTTP client only (no full agent framework)
- ✅ Token-aware chunking with `tiktoken-rs`
- ✅ Parallel execution with `tokio`
- ✅ Critical token usage tracking for cost control

**Comparison to Python:**

| Aspect | Python (percolate) | Rust (percolate-rocks) |
|--------|-------------------|----------------------|
| Framework | Pydantic AI (full) | reqwest HTTP client |
| Tools | MCP + custom | None |
| Context | AgentContext | Just schema |
| Use case | Interactive API | Background indexing |
| Size | ~800 lines | ~380 lines target |

## Module Structure

```
percolate-rocks/src/agents/
├── mod.rs           # Module exports
├── client.rs        # Minimal LLM HTTP client (~80 lines)
├── chunking.rs      # Token-aware chunking (~100 lines)
├── pagination.rs    # Pagination engine (~150 lines)
└── schema.rs        # RocksDB schema storage (~50 lines)
```

## Implementation Status

### Phase 0: Planning ✅ COMPLETE

**Completed:**
- ✅ Design document created (`paginated-agentic-requests.md`)
- ✅ Module stubs created in `src/agents/`
- ✅ Token usage tracking design completed
- ✅ Module integrated into `lib.rs`
- ✅ Dependency added: `tiktoken-rs = "0.5"`

**Files created:**
- `docs/dreaming/paginated-agentic-requests.md` (587 lines)
- `docs/dreaming/README.md` (93 lines)
- `src/agents/mod.rs` (33 lines)
- `src/agents/client.rs` (74 lines stub)
- `src/agents/chunking.rs` (56 lines stub)
- `src/agents/pagination.rs` (114 lines stub)
- `src/agents/schema.rs` (46 lines stub)

### Phase 1: HTTP Client (Week 1) ⏳ PLANNED

**Tasks:**
- [ ] Implement `LlmClient::new()` with reqwest
- [ ] Support Anthropic API format
- [ ] Support OpenAI API format
- [ ] Token usage extraction from response
- [ ] Cost calculation per model
- [ ] Request/response logging
- [ ] Error handling and retries

**Key features:**
```rust
pub async fn request(
    &self,
    system_prompt: &str,
    content: &str,
    output_schema: &serde_json::Value,
) -> Result<(serde_json::Value, TokenUsage)>
```

**Token tracking (CRITICAL):**
- Extract `input_tokens` and `output_tokens` from API response
- Calculate cost using model-specific pricing
- Log every request with token counts and cost
- Return `TokenUsage` struct with full details

### Phase 2: Chunking (Week 2) ⏳ PLANNED

**Tasks:**
- [ ] Integrate `tiktoken-rs` for token counting
- [ ] Implement `chunk_text()` with sentence boundaries
- [ ] Implement `chunk_records()` for JSON arrays
- [ ] Token estimation with fallback
- [ ] Unit tests for chunking logic

### Phase 3: Pagination (Week 3) ⏳ PLANNED

**Tasks:**
- [ ] Implement parallel execution with tokio
- [ ] Implement sequential execution
- [ ] Implement merge strategies (concat, merge, first, last)
- [ ] Aggregate token usage across chunks
- [ ] Error handling for partial failures
- [ ] Integration tests

**Token aggregation:**
```rust
pub struct AggregatedTokenUsage {
    pub total_input_tokens: u32,
    pub total_output_tokens: u32,
    pub total_cost_usd: f64,
    pub chunks_processed: usize,
    pub per_chunk_usage: Vec<TokenUsage>,
}
```

### Phase 4: Schema Storage (Week 4) ⏳ PLANNED

**Tasks:**
- [ ] Define agent schema format
- [ ] Implement RocksDB storage/retrieval
- [ ] Version management
- [ ] Schema validation

**Storage key format:**
```
agent:{tenant_id}:{agent_name}
```

### Phase 5: Dreaming Integration (Week 5) ⏳ PLANNED

**Tasks:**
- [ ] Create AgentRuntime in dreaming module
- [ ] Hook into background indexing pipeline
- [ ] Configuration for agent triggers
- [ ] Monitoring and metrics
- [ ] Token usage persistence

### Phase 6: Production Hardening (Week 6) ⏳ PLANNED

**Tasks:**
- [ ] Rate limiting for LLM APIs
- [ ] Retry logic with exponential backoff
- [ ] Timeout handling
- [ ] **Token usage auditing (CRITICAL)**
- [ ] Logging and observability
- [ ] Graceful degradation

## Token Usage Tracking (Critical Feature)

### Why This Matters

- Background dreaming can process thousands of documents
- LLM costs scale linearly with tokens
- Without tracking, costs can spiral unexpectedly
- Need visibility for debugging, budgeting, optimization

### Implementation Requirements

**Per-request tracking:**
- Extract tokens from API response
- Calculate cost using current pricing
- Log every request with structured logging
- Return usage data to caller

**Aggregation:**
- Sum tokens across all chunks in paginated request
- Store historical usage in RocksDB
- CLI commands to query usage statistics
- Cost breakdown by model, operation, time period

**Storage pattern:**
```
token_usage:{tenant_id}:{timestamp}:{dreaming_run_id}
```

**Model pricing (2025):**
- `claude-haiku-4-5`: $0.25 / $1.25 per MTok (input/output)
- `claude-sonnet-4-5`: $3.00 / $15.00 per MTok
- `gpt-4.1`: $2.50 / $10.00 per MTok (approximate)

## Reference Implementation

**Python implementation:** `percolate/src/percolate/agents/pagination.py`

**Key learnings to port:**
- Chunking logic (token-based, record-based)
- Merge strategies (concat, merge, first, last)
- Parallel execution pattern
- Configuration structure

**What to simplify:**
- No AgentContext (use tenant_id string)
- No full agent framework (just HTTP client)
- No complex model selection (fixed per schema)
- No tool calling (agents are pure prompt→response)

## Dependencies

**Already in Cargo.toml:**
- `reqwest` - HTTP client
- `tokio` - Async runtime
- `serde_json` - JSON parsing
- `serde` - Serialization

**Added:**
- `tiktoken-rs = "0.5"` - Token counting

## Next Steps

1. **Complete Phase 0 build verification** - Ensure module stubs compile
2. **Begin Phase 1** - Implement HTTP client with token tracking
3. **Add integration tests** - Test with real LLM APIs
4. **Document API** - Full Rust documentation with examples

## Open Questions

1. **API keys** - Store in env vars or RocksDB encrypted? → **Env vars for now**
2. **Cost tracking** - Per-tenant or global? → **Per-tenant**
3. **Schema versioning** - How to handle breaking changes? → **Semantic versioning**
4. **Failure modes** - What if LLM is down during indexing? → **Skip with warning, retry later**
5. **Priority** - Which documents to process first? → **Queue-based, configurable**

## Timeline

- **Week 1**: HTTP client with token tracking
- **Week 2**: Chunking implementation
- **Week 3**: Pagination engine
- **Week 4**: Schema storage
- **Week 5**: Dreaming integration
- **Week 6**: Production hardening

**Total estimated time:** 6 weeks for full implementation

## Success Metrics

- ✅ All module stubs compile without errors
- ✅ Token tracking integrated from day 1
- ⏳ Phase 1: HTTP client working with Anthropic/OpenAI
- ⏳ Phase 2: Chunking preserves boundaries correctly
- ⏳ Phase 3: Pagination handles large documents (>100k tokens)
- ⏳ Phase 4: Schemas stored and retrieved from RocksDB
- ⏳ Phase 5: Background indexing processes documents automatically
- ⏳ Phase 6: Token usage visible in CLI, costs controlled
