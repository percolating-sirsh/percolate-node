# Paginated Agentic Requests in percolate-rocks

## Concept

Allow the database to make paginated LLM requests directly from Rust during background indexing, without needing the full Percolate Python orchestration layer.

**Use case:** Background indexing needs to process large documents/datasets with LLMs to extract metadata, classify content, generate embeddings, etc.

## Why in the Database?

Background indexing runs continuously:
- New documents ingested → need classification
- Large text chunks → need entity extraction
- Batch operations → need parallel processing

Current approach: Python layer orchestrates everything
**Problem:** Database can't do agentic work independently

Proposed: Database can make LLM calls directly
**Benefit:** Self-contained background processing

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    percolate-rocks                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │         Background Indexing (dreaming)         │    │
│  │                                                 │    │
│  │  1. Detect large document needs processing     │    │
│  │  2. Load agent schema from KV store            │    │
│  │  3. Chunk content (token-aware)                │    │
│  │  4. Make parallel LLM requests                 │    │
│  │  5. Merge results                              │    │
│  │  6. Store metadata back to RocksDB             │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │          Minimal Agent Runtime                  │    │
│  │                                                 │    │
│  │  - Schema loading (JSON from KV)               │    │
│  │  - HTTP client for LLM APIs                    │    │
│  │  - Token counting (tiktoken-rs)                │    │
│  │  - Chunk/merge logic                           │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Token Usage Tracking (Critical)

**Why This Matters:**
- Background dreaming can process thousands of documents
- LLM costs scale linearly with tokens (input + output)
- Without tracking, costs can spiral unexpectedly
- Need visibility for debugging, budgeting, and optimization

**Implementation Pattern:**

```rust
pub struct TokenUsage {
    pub input_tokens: u32,
    pub output_tokens: u32,
    pub estimated_cost_usd: f64,
    pub model: String,
}

impl LlmClient {
    pub async fn request(
        &self,
        system_prompt: &str,
        content: &str,
        output_schema: &serde_json::Value,
    ) -> Result<(serde_json::Value, TokenUsage)> {
        // Make request
        let response = self.http_client.post(&self.endpoint)
            .json(&request_body)
            .send()
            .await?;

        let body: serde_json::Value = response.json().await?;

        // Extract token usage from response
        let usage = TokenUsage {
            input_tokens: body["usage"]["input_tokens"].as_u64().unwrap_or(0) as u32,
            output_tokens: body["usage"]["output_tokens"].as_u64().unwrap_or(0) as u32,
            estimated_cost_usd: self.calculate_cost(&body),
            model: self.model.clone(),
        };

        // CRITICAL: Log token usage
        tracing::info!(
            "LLM request completed: {} input tokens, {} output tokens, ${:.4}",
            usage.input_tokens,
            usage.output_tokens,
            usage.estimated_cost_usd
        );

        Ok((body["content"], usage))
    }

    fn calculate_cost(&self, response: &serde_json::Value) -> f64 {
        // Model-specific pricing (as of 2025)
        let (input_cost, output_cost) = match self.model.as_str() {
            "claude-haiku-4-5" => (0.25 / 1_000_000.0, 1.25 / 1_000_000.0),  // $0.25 / $1.25 per MTok
            "claude-sonnet-4-5" => (3.0 / 1_000_000.0, 15.0 / 1_000_000.0),   // $3 / $15 per MTok
            "gpt-4.1" => (2.5 / 1_000_000.0, 10.0 / 1_000_000.0),             // Approximate
            _ => (0.0, 0.0),  // Unknown model
        };

        let input_tokens = response["usage"]["input_tokens"].as_f64().unwrap_or(0.0);
        let output_tokens = response["usage"]["output_tokens"].as_f64().unwrap_or(0.0);

        (input_tokens * input_cost) + (output_tokens * output_cost)
    }
}

pub struct DreamingStats {
    pub moments_created: usize,
    pub edges_created: usize,
    pub summaries_created: usize,
    pub duration_seconds: f64,
    pub total_tokens_used: u32,           // NEW: Track total tokens
    pub estimated_cost_usd: f64,          // NEW: Track estimated cost
    pub cost_breakdown: Vec<TokenUsage>,  // NEW: Per-request breakdown
}
```

**Storage Pattern:**

```rust
// Store token usage for historical analysis
// Key: token_usage:{tenant_id}:{timestamp}:{dreaming_run_id}
#[derive(Serialize, Deserialize)]
pub struct TokenUsageRecord {
    pub timestamp: String,
    pub dreaming_run_id: String,
    pub model: String,
    pub input_tokens: u32,
    pub output_tokens: u32,
    pub cost_usd: f64,
    pub operation: String,  // "entity_extraction", "summarization", etc.
}

// Store in RocksDB for analysis
impl Database {
    pub fn log_token_usage(&self, tenant_id: &str, usage: &TokenUsageRecord) -> Result<()> {
        let key = format!("token_usage:{}:{}:{}",
            tenant_id,
            usage.timestamp,
            usage.dreaming_run_id
        );
        let value = serde_json::to_vec(usage)?;
        self.storage.put(&key, &value)?;
        Ok(())
    }

    pub fn get_token_usage_stats(&self, tenant_id: &str, days: u32) -> Result<TokenStats> {
        // Scan prefix for token usage records
        // Aggregate by model, operation, time period
        // Return summary stats
    }
}
```

**CLI Commands:**

```bash
# Show token usage for last 7 days
rem dreaming token-usage --days 7

# Output:
# Token Usage (last 7 days):
#   claude-haiku-4-5: 1.2M tokens ($0.45)
#   claude-sonnet-4-5: 450K tokens ($6.75)
#   Total cost: $7.20
#
# By operation:
#   entity_extraction: 800K tokens ($2.40)
#   summarization: 600K tokens ($3.60)
#   classification: 250K tokens ($1.20)
```

## Components Needed

### 1. Agent Schema Storage

Store agent definitions in RocksDB:

```rust
// Key: agent:{tenant_id}:{agent_name}
// Value: JSON schema
{
  "name": "entity-extractor",
  "version": "1.0.0",
  "system_prompt": "Extract entities from the text",
  "output_schema": {
    "type": "object",
    "properties": {
      "entities": {"type": "array", "items": {"type": "string"}},
      "count": {"type": "integer"}
    }
  },
  "model": "claude-haiku-4-5",
  "api_endpoint": "https://api.anthropic.com/v1/messages",
  "api_key_env": "ANTHROPIC_API_KEY"
}
```

### 2. Minimal HTTP Client

Lightweight LLM API client (no full Pydantic AI):

```rust
pub struct LlmClient {
    http_client: reqwest::Client,
    api_key: String,
    endpoint: String,
    model: String,
}

impl LlmClient {
    pub async fn request(
        &self,
        system_prompt: &str,
        content: &str,
        output_schema: &JsonSchema,
    ) -> Result<serde_json::Value, Error> {
        // Simple HTTP POST to LLM API
        // Returns structured JSON matching schema
    }
}
```

### 3. Token-Aware Chunking

Port our Python chunking to Rust:

```rust
pub struct Chunker {
    model_name: String,
    max_tokens: usize,
}

impl Chunker {
    pub fn chunk_text(&self, content: &str) -> Vec<String> {
        // Token-based chunking
        // Preserve sentence boundaries
    }

    pub fn chunk_records(&self, content: &[serde_json::Value]) -> Vec<Vec<serde_json::Value>> {
        // Record-based chunking
        // Never split mid-record
    }

    pub fn estimate_tokens(&self, content: &str) -> usize {
        // Use tiktoken-rs crate
    }
}
```

### 4. Pagination Engine

Similar to our Python implementation but in Rust:

```rust
pub struct PaginatedRequest {
    agent_schema: AgentSchema,
    llm_client: LlmClient,
    chunker: Chunker,
}

impl PaginatedRequest {
    pub async fn execute(
        &self,
        content: &str,
        merge_strategy: MergeStrategy,
        parallel: bool,
    ) -> Result<serde_json::Value, Error> {
        // 1. Chunk content
        let chunks = self.chunker.chunk_text(content);

        // 2. Execute requests (parallel or sequential)
        let results = if parallel {
            self.execute_parallel(&chunks).await?
        } else {
            self.execute_sequential(&chunks).await?
        };

        // 3. Merge results
        self.merge_results(results, merge_strategy)
    }

    async fn execute_parallel(&self, chunks: &[String]) -> Result<Vec<serde_json::Value>, Error> {
        use futures::future::join_all;

        let futures = chunks.iter().map(|chunk| {
            self.llm_client.request(
                &self.agent_schema.system_prompt,
                chunk,
                &self.agent_schema.output_schema,
            )
        });

        join_all(futures).await.into_iter().collect()
    }

    fn merge_results(
        &self,
        results: Vec<serde_json::Value>,
        strategy: MergeStrategy,
    ) -> Result<serde_json::Value, Error> {
        // Same merge logic as Python:
        // - concat: return Vec
        // - merge: combine list fields
        // - first/last: return specific result
    }
}
```

### 5. Background Indexing Integration

Hook into dreaming module:

```rust
// In percolate-rocks/src/dreaming/mod.rs

pub struct DreamingEngine {
    db: Arc<RocksDB>,
    agent_runtime: AgentRuntime,
}

impl DreamingEngine {
    pub async fn process_document(&self, doc_id: &str) -> Result<(), Error> {
        // 1. Load document from RocksDB
        let content = self.db.get_resource(doc_id)?;

        // 2. Check if content is large (needs pagination)
        let needs_pagination = content.len() > 50_000; // ~50k chars

        if needs_pagination {
            // 3. Load agent schema
            let agent_schema = self.agent_runtime.load_schema("entity-extractor")?;

            // 4. Execute paginated request
            let result = self.agent_runtime
                .paginated_request(
                    &agent_schema,
                    &content,
                    MergeStrategy::Merge,
                    true, // parallel
                )
                .await?;

            // 5. Store extracted metadata
            self.db.put_metadata(doc_id, &result)?;
        }

        Ok(())
    }
}
```

## Setup Steps

### Phase 1: Minimal HTTP Client (Week 1)

```bash
# Add dependencies to Cargo.toml
[dependencies]
reqwest = { version = "0.11", features = ["json"] }
tokio = { version = "1", features = ["full"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
tiktoken-rs = "0.5"
```

**Tasks:**
- [ ] Create `src/agents/mod.rs` module
- [ ] Implement `LlmClient` struct
- [ ] Support Anthropic API (claude models)
- [ ] Support OpenAI API (gpt models)
- [ ] Basic error handling and retries

**Test:**
```rust
#[tokio::test]
async fn test_llm_request() {
    let client = LlmClient::new("claude-haiku-4-5");
    let result = client.request(
        "Extract entities",
        "Apple and Google are tech companies",
        &entity_schema(),
    ).await.unwrap();

    assert!(result["entities"].as_array().unwrap().len() >= 2);
}
```

### Phase 2: Token Chunking (Week 2)

```rust
// src/agents/chunking.rs

use tiktoken_rs::tokenize;

pub struct Chunker {
    model: String,
    max_tokens: usize,
}

impl Chunker {
    pub fn chunk_text(&self, text: &str) -> Vec<String> {
        let tokens = tokenize(&self.model, text);

        // Split into chunks at sentence boundaries
        let mut chunks = Vec::new();
        let mut current_chunk = Vec::new();

        for token in tokens {
            current_chunk.push(token);

            if current_chunk.len() >= self.max_tokens {
                chunks.push(self.detokenize(&current_chunk));
                current_chunk.clear();
            }
        }

        if !current_chunk.is_empty() {
            chunks.push(self.detokenize(&current_chunk));
        }

        chunks
    }
}
```

**Tasks:**
- [ ] Integrate `tiktoken-rs` crate
- [ ] Implement token counting
- [ ] Implement text chunking with boundary preservation
- [ ] Implement record chunking (JSON array splitting)
- [ ] Unit tests for chunking logic

**Test:**
```rust
#[test]
fn test_chunk_preserves_boundaries() {
    let chunker = Chunker::new("claude-haiku-4-5", 100);
    let chunks = chunker.chunk_text("Sentence one. Sentence two.");

    // Each chunk should end with period
    for chunk in &chunks[..chunks.len()-1] {
        assert!(chunk.trim().ends_with('.'));
    }
}
```

### Phase 3: Pagination Engine (Week 3)

```rust
// src/agents/pagination.rs

pub enum MergeStrategy {
    Concat,
    Merge,
    First,
    Last,
}

pub struct PaginatedRequest {
    client: LlmClient,
    chunker: Chunker,
}

impl PaginatedRequest {
    pub async fn execute(
        &self,
        system_prompt: &str,
        content: &str,
        output_schema: &JsonSchema,
        strategy: MergeStrategy,
    ) -> Result<serde_json::Value, Error> {
        // Implementation
    }
}
```

**Tasks:**
- [ ] Create pagination module
- [ ] Implement parallel execution with tokio
- [ ] Implement merge strategies
- [ ] Error handling for partial failures
- [ ] Integration tests with mock LLM

**Test:**
```rust
#[tokio::test]
async fn test_pagination_merge() {
    let paginator = PaginatedRequest::new(...);
    let large_text = "content".repeat(10000);

    let result = paginator.execute(
        "Extract entities",
        &large_text,
        &entity_schema(),
        MergeStrategy::Merge,
    ).await.unwrap();

    // Should have merged entities from all chunks
    assert!(result["entities"].as_array().unwrap().len() > 0);
}
```

### Phase 4: Agent Schema Storage (Week 4)

```rust
// src/agents/schema.rs

#[derive(Deserialize, Serialize)]
pub struct AgentSchema {
    pub name: String,
    pub version: String,
    pub system_prompt: String,
    pub output_schema: JsonSchema,
    pub model: String,
    pub api_endpoint: String,
}

impl AgentSchema {
    pub fn from_db(db: &RocksDB, tenant_id: &str, name: &str) -> Result<Self, Error> {
        let key = format!("agent:{}:{}", tenant_id, name);
        let json = db.get(&key)?;
        serde_json::from_slice(&json)
    }

    pub fn to_db(&self, db: &RocksDB, tenant_id: &str) -> Result<(), Error> {
        let key = format!("agent:{}:{}", tenant_id, self.name);
        let json = serde_json::to_vec(self)?;
        db.put(&key, &json)
    }
}
```

**Tasks:**
- [ ] Define agent schema format
- [ ] Implement storage/retrieval from RocksDB
- [ ] Version management
- [ ] Schema validation

### Phase 5: Dreaming Integration (Week 5)

```rust
// src/dreaming/agents.rs

pub struct AgentRuntime {
    db: Arc<RocksDB>,
    http_client: LlmClient,
}

impl AgentRuntime {
    pub async fn process_with_agent(
        &self,
        tenant_id: &str,
        agent_name: &str,
        content: &str,
    ) -> Result<serde_json::Value, Error> {
        // 1. Load schema
        let schema = AgentSchema::from_db(&self.db, tenant_id, agent_name)?;

        // 2. Create chunker based on model
        let chunker = Chunker::new(&schema.model, None);

        // 3. Execute paginated request
        let paginator = PaginatedRequest::new(self.http_client.clone(), chunker);

        paginator.execute(
            &schema.system_prompt,
            content,
            &schema.output_schema,
            MergeStrategy::Merge,
        ).await
    }
}
```

**Tasks:**
- [ ] Create AgentRuntime in dreaming module
- [ ] Hook into background indexing pipeline
- [ ] Add configuration for which agents to run
- [ ] Monitoring and metrics

### Phase 6: Production Hardening (Week 6)

**Tasks:**
- [ ] Rate limiting for LLM APIs
- [ ] Retry logic with exponential backoff
- [ ] Timeout handling
- [ ] **Token usage auditing (CRITICAL for cost control)**
- [ ] Logging and observability
- [ ] Graceful degradation (skip if LLM unavailable)

**Token Usage Auditing (Required):**
- Track tokens per request (input + output)
- Aggregate tokens per dreaming run
- Store token usage in database for historical analysis
- Calculate estimated cost based on model pricing
- Log warnings if token usage exceeds thresholds
- Provide cost breakdown in dreaming stats

## Configuration

Store in RocksDB config:

```json
{
  "dreaming": {
    "agents_enabled": true,
    "default_agents": [
      {
        "name": "entity-extractor",
        "trigger": "document_size > 10000",
        "priority": "low"
      },
      {
        "name": "classifier",
        "trigger": "document_type == 'unknown'",
        "priority": "high"
      }
    ],
    "llm_config": {
      "max_parallel_requests": 10,
      "timeout_seconds": 30,
      "retry_attempts": 3
    }
  }
}
```

## Example Usage from Python

Once implemented, Python layer can still use it:

```python
# Python calls into Rust
from percolate_rocks import RocksDB

db = RocksDB("/path/to/db")

# Store agent schema
db.store_agent_schema(
    tenant_id="user-123",
    schema={
        "name": "entity-extractor",
        "system_prompt": "Extract entities",
        "output_schema": {...},
        "model": "claude-haiku-4-5",
    }
)

# Process document with agent (Rust handles pagination)
result = db.process_with_agent(
    tenant_id="user-123",
    agent_name="entity-extractor",
    content=large_document,
)

print(result["entities"])
```

## Benefits

1. **Self-contained** - Database can process data independently
2. **Efficient** - No Python/Rust boundary crossing for chunks
3. **Fast** - Native Rust performance
4. **Simple** - Minimal dependencies (reqwest, tokio, serde)
5. **Scalable** - Parallel processing in Rust

## Comparison to Python Implementation

| Feature | Python (Percolate) | Rust (percolate-rocks) |
|---------|-------------------|----------------------|
| Agent framework | Pydantic AI (full) | Minimal HTTP client |
| Schema storage | Python objects | RocksDB KV store |
| Chunking | Python | Rust (tiktoken-rs) |
| Parallelism | asyncio | tokio |
| Use case | Interactive API | Background indexing |
| Dependencies | Many | Few (reqwest, tokio) |

## Learning from Python Implementation

Reference: `percolate/src/percolate/agents/pagination.py`

**What to port:**
- Chunking logic (token-based, record-based)
- Merge strategies (concat, merge, first, last)
- Parallel execution pattern
- Configuration structure

**What to simplify:**
- No AgentContext (use tenant_id string)
- No full agent framework (just HTTP client)
- No complex model selection (fixed per schema)
- No tool calling (agents are pure prompt→response)

## Next Steps

1. **Prototype** - Implement Phase 1-2 (HTTP client + chunking)
2. **Validate** - Test with real LLM APIs
3. **Integrate** - Hook into dreaming module
4. **Iterate** - Add features based on usage

## Open Questions

1. **API keys** - Store in env vars or RocksDB encrypted?
2. **Cost tracking** - Per-tenant or global?
3. **Schema versioning** - How to handle breaking changes?
4. **Failure modes** - What if LLM is down during indexing?
5. **Priority** - Which documents to process first?

## References

- Python implementation: `percolate/src/percolate/agents/pagination.py`
- Chunking utils: `percolate/src/percolate/utils/chunking.py`
- tiktoken-rs: https://github.com/zurawiki/tiktoken-rs
- reqwest: https://github.com/seanmonstar/reqwest
