# Agent Pagination: Processing Large Inputs with Structured Output Merging

## Overview

Agent pagination enables processing of large data inputs that exceed model context windows by:

1. **Splitting** input into context-appropriate chunks
2. **Invoking** the agent N times with each chunk
3. **Merging** structured outputs using configurable strategies

This allows agents to process arbitrarily large inputs while maintaining structured output guarantees and staying within token limits.

## Problem Statement

### Context Window Limitations

Modern LLMs have context window limits:

| Model | Context Window | Usable Space (with overhead) |
|-------|---------------|------------------------------|
| Claude Sonnet 4.5 | 200k tokens | ~160k tokens |
| Claude Opus 4 | 200k tokens | ~160k tokens |
| GPT-4.1 | 128k tokens | ~100k tokens |
| GPT-4o | 128k tokens | ~100k tokens |

**Overhead sources:**
- System prompt: ~500-2000 tokens
- Output schema: ~200-1000 tokens
- Response buffer: 20% of available space
- JSON formatting: ~5 tokens per record

### Use Cases Requiring Pagination

1. **Long documents** - PDFs, transcripts, meeting notes (>100k tokens)
2. **Large datasets** - CSV files, API responses with hundreds of records
3. **Batch analysis** - Processing multiple items with aggregated results
4. **Incremental summarization** - Building summaries from sequential chunks

## Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────┐
│                   AgentPaginationProxy                  │
├─────────────────────────────────────────────────────────┤
│  Input: Large content + Agent schema + Merge strategy  │
│                                                         │
│  1. Content Analysis                                    │
│     ├─ Detect content type (list vs string)            │
│     ├─ Estimate total tokens                           │
│     └─ Calculate optimal chunk size                    │
│                                                         │
│  2. Smart Chunking                                      │
│     ├─ List → Record-based chunking                    │
│     ├─ String → Token-based chunking                   │
│     └─ Preserve data integrity (no mid-record splits)  │
│                                                         │
│  3. Parallel Agent Execution                            │
│     ├─ Create agent per chunk                          │
│     ├─ Execute with context: "Part X/N"                │
│     └─ Collect structured outputs                      │
│                                                         │
│  4. Result Merging                                      │
│     ├─ Strategy: "first" → Take first chunk result     │
│     ├─ Strategy: "last" → Take last chunk result       │
│     ├─ Strategy: "merge" → Combine list fields         │
│     └─ Strategy: "custom" → User-defined function      │
│                                                         │
│  Output: Single structured response (merged)           │
└─────────────────────────────────────────────────────────┘
```

### Data Flow

```
Input (100k tokens)
       ↓
┌──────────────────┐
│ Content Analysis │ → Detect type, estimate tokens
└────────┬─────────┘
         ↓
┌──────────────────┐
│ Smart Chunking   │ → Split into 3 chunks (35k each)
└────────┬─────────┘
         ↓
    ┌────┴────┐
    ↓    ↓    ↓
 Chunk1 Chunk2 Chunk3 (parallel processing)
    ↓    ↓    ↓
 Agent1 Agent2 Agent3 → Each returns structured output
    ↓    ↓    ↓
Result1 Result2 Result3
    └────┬────┘
         ↓
┌──────────────────┐
│ Merge Strategy   │ → Combine into single output
└────────┬─────────┘
         ↓
   Final Result
```

## Implementation Plan

### Phase 1: Chunking Utilities

**Module:** `percolate/utils/chunking.py`

#### Token-Based Chunking

```python
from typing import Optional

def get_optimal_chunk_size(
    model_name: str,
    overhead_tokens: int = 1500,
    response_buffer_ratio: float = 0.2
) -> int:
    """Calculate optimal chunk size for a model.

    Args:
        model_name: LLM model identifier
        overhead_tokens: System prompt + schema overhead
        response_buffer_ratio: Reserve % for response (default: 20%)

    Returns:
        Maximum tokens per chunk

    Example:
        >>> get_optimal_chunk_size("claude-sonnet-4-5")
        158400  # 200k - 1500 - (200k * 0.2)
    """
    pass

def chunk_by_tokens(
    content: str,
    model_name: str,
    max_chunk_tokens: Optional[int] = None
) -> list[str]:
    """Split content by token boundaries.

    Uses tiktoken for accurate token counting.
    Falls back to character-based (~4 chars/token) if unavailable.

    Args:
        content: Text to chunk
        model_name: Model for token counting
        max_chunk_tokens: Override optimal chunk size

    Returns:
        List of text chunks

    Example:
        >>> chunks = chunk_by_tokens(long_text, "claude-sonnet-4-5")
        >>> len(chunks)
        3
    """
    pass

def estimate_tokens(content: str, model_name: str) -> int:
    """Estimate token count for content.

    Args:
        content: Text to estimate
        model_name: Model for counting

    Returns:
        Estimated token count
    """
    pass
```

#### Record-Based Chunking

```python
def is_list_content(content: str | list) -> bool:
    """Detect if content is a list structure.

    Returns:
        True if content is array of dicts/objects
    """
    pass

def chunk_by_records(
    content: list[dict],
    model_name: str,
    max_records_per_chunk: Optional[int] = None
) -> list[str]:
    """Chunk list by record boundaries (never splits records).

    Calculates optimal record count based on:
    - Average tokens per record (sample first 10)
    - 5 tokens overhead per record (JSON syntax)
    - Model context window

    Args:
        content: List of records (dicts)
        model_name: Model for token estimation
        max_records_per_chunk: Override calculated optimal

    Returns:
        List of JSON string chunks (complete records only)

    Example:
        >>> records = [{"id": 1}, {"id": 2}, {"id": 3}]
        >>> chunks = chunk_by_records(records, "claude-sonnet-4-5")
        >>> len(chunks)
        1  # All fit in one chunk
    """
    pass

def estimate_record_count(
    content: list[dict],
    model_name: str
) -> dict:
    """Provide chunking statistics for records.

    Returns:
        {
            "total_records": int,
            "total_tokens": int,
            "optimal_records_per_chunk": int,
            "estimated_chunks": int
        }
    """
    pass
```

### Phase 2: Pagination Proxy

**Module:** `percolate/agents/pagination.py`

```python
from typing import Any, Callable, Literal
from pydantic import BaseModel
from percolate.agents.context import AgentContext
from percolate.agents.factory import create_agent

MergeStrategy = Literal["first", "last", "merge", "custom"]

class PaginationConfig(BaseModel):
    """Configuration for agent pagination."""

    chunk_size: int | None = None
    """Override optimal chunk size (tokens or records)"""

    merge_strategy: MergeStrategy = "last"
    """How to combine paginated results"""

    custom_merge_fn: Callable[[list[Any]], Any] | None = None
    """Custom merge function (required if strategy="custom")"""

    use_token_chunking: bool = True
    """Use token-aware chunking (vs simple character splitting)"""

    parallel: bool = True
    """Execute chunks in parallel (vs sequential)"""

    include_chunk_metadata: bool = True
    """Add "part X/N" to chunk prompts"""

class AgentPaginationProxy:
    """Proxy that wraps agent calls with automatic pagination.

    Handles:
    - Content type detection (list vs string)
    - Smart chunking (record-based or token-based)
    - Parallel agent execution
    - Structured output merging

    Example:
        >>> proxy = AgentPaginationProxy(
        ...     context=AgentContext(tenant_id="test"),
        ...     config=PaginationConfig(merge_strategy="merge")
        ... )
        >>> result = await proxy.run(
        ...     prompt="Extract goals from this transcript",
        ...     content=large_transcript,  # 100k tokens
        ... )
        >>> isinstance(result, GoalExtractor)
        True
    """

    def __init__(
        self,
        context: AgentContext,
        config: PaginationConfig = PaginationConfig()
    ):
        """Initialize pagination proxy.

        Args:
            context: Agent execution context
            config: Pagination configuration
        """
        self.context = context
        self.config = config

    async def run(
        self,
        prompt: str,
        content: str | list,
    ) -> Any:
        """Execute agent with automatic pagination.

        Process:
        1. Detect content type and estimate tokens
        2. Chunk content if needed (or use as-is if small)
        3. Execute agent for each chunk
        4. Merge results using configured strategy
        5. Return single structured output

        Args:
            prompt: User prompt (prepended to each chunk)
            content: Large input (string or list)

        Returns:
            Merged structured output matching agent schema

        Raises:
            ValueError: If custom merge strategy but no merge function
            TokenLimitError: If single record exceeds context window
        """
        pass

    async def _execute_chunk(
        self,
        chunk: str,
        chunk_index: int,
        total_chunks: int,
        prompt: str
    ) -> Any:
        """Execute agent on single chunk.

        Args:
            chunk: Chunk content
            chunk_index: 0-based index
            total_chunks: Total number of chunks
            prompt: Original user prompt

        Returns:
            Structured output for this chunk
        """
        pass

    def _merge_results(
        self,
        results: list[Any],
        strategy: MergeStrategy
    ) -> Any:
        """Merge paginated results.

        Args:
            results: List of structured outputs (one per chunk)
            strategy: Merge strategy

        Returns:
            Single merged output

        Strategies:
            - "first": Return results[0]
            - "last": Return results[-1]
            - "merge": Combine list fields, keep first non-list values
            - "custom": Call config.custom_merge_fn(results)
        """
        pass
```

### Phase 3: Merge Strategies

#### Built-in Strategies

**Strategy: "first"** - Take first chunk's result
- **Use case:** When first chunk has definitive answer
- **Example:** Extracting metadata from document header

**Strategy: "last"** - Take last chunk's result (default)
- **Use case:** Final summaries, conclusions
- **Example:** Overall document sentiment

**Strategy: "merge"** - Intelligent combining
- **Use case:** Aggregating lists from all chunks
- **Example:** Extracting entities, goals, tasks across long document
- **Behavior:**
  - List fields: Extend (combine all items)
  - Non-list fields: Keep first occurrence
  - Nested objects: Recursive merge

**Strategy: "custom"** - User-defined function
- **Use case:** Complex domain-specific merging
- **Example:** Weighted averaging of scores, deduplication

#### Merge Strategy Examples

```python
# Example 1: Extract goals from long transcript
class GoalExtractor(BaseModel):
    goals: list[dict]  # List field → will be extended
    summary: str       # Non-list → keep first

# Chunk 1 result:
{"goals": [{"name": "Q4 Revenue"}], "summary": "Part 1 summary"}

# Chunk 2 result:
{"goals": [{"name": "Hiring"}, {"name": "Product Launch"}], "summary": "Part 2 summary"}

# Merged (strategy="merge"):
{
    "goals": [
        {"name": "Q4 Revenue"},
        {"name": "Hiring"},
        {"name": "Product Launch"}
    ],
    "summary": "Part 1 summary"  # First occurrence
}
```

```python
# Example 2: Custom merge with deduplication
def dedupe_merge(results: list[GoalExtractor]) -> GoalExtractor:
    """Merge and deduplicate goals by name."""
    seen = set()
    merged_goals = []

    for result in results:
        for goal in result.goals:
            if goal["name"] not in seen:
                seen.add(goal["name"])
                merged_goals.append(goal)

    return GoalExtractor(
        goals=merged_goals,
        summary=results[-1].summary  # Use last summary
    )

proxy = AgentPaginationProxy(
    context=ctx,
    config=PaginationConfig(
        merge_strategy="custom",
        custom_merge_fn=dedupe_merge
    )
)
```

### Phase 4: Integration with Agent Factory

**Update:** `percolate/agents/factory.py`

Add optional pagination wrapper to `create_agent`:

```python
async def create_agent(
    context: AgentContext,
    agent_schema_override: dict | None = None,
    model_override: str | None = None,
    pagination_config: PaginationConfig | None = None
) -> Agent:
    """Create agent with optional pagination support.

    Args:
        context: Execution context
        agent_schema_override: Override loaded schema
        model_override: Override model from context
        pagination_config: Enable pagination wrapper

    Returns:
        Agent instance (wrapped if pagination_config provided)

    Example:
        # Standard agent
        agent = await create_agent(context)

        # With pagination
        agent = await create_agent(
            context,
            pagination_config=PaginationConfig(merge_strategy="merge")
        )
    """
    pass
```

### Phase 5: CLI Support

**Add command:** `percolate agent-eval` with pagination flags

```bash
# Standard execution
percolate agent-eval goal-extractor "Extract goals" --input transcript.txt

# With pagination (auto-detect if needed)
percolate agent-eval goal-extractor "Extract goals" \
  --input large-transcript.txt \
  --paginate \
  --merge-strategy merge

# Custom chunk size
percolate agent-eval goal-extractor "Extract goals" \
  --input large-transcript.txt \
  --paginate \
  --chunk-size 50000 \
  --merge-strategy merge
```

## Usage Examples

### Example 1: Long Document Analysis

```python
from percolate.agents.pagination import AgentPaginationProxy, PaginationConfig
from percolate.agents.context import AgentContext
from percolate.agents.registry import load_agentlet_schema

# Load document (100k tokens)
with open("long_transcript.txt") as f:
    content = f.read()

# Create pagination proxy
context = AgentContext(
    tenant_id="user-123",
    default_model="claude-sonnet-4-5"
)

config = PaginationConfig(
    merge_strategy="merge",  # Combine list fields
    parallel=True            # Process chunks in parallel
)

proxy = AgentPaginationProxy(context, config)

# Execute with automatic pagination
result = await proxy.run(
    prompt="Extract all action items and decisions from this meeting",
    content=content
)

# Result is merged from all chunks
print(f"Found {len(result.action_items)} action items")
print(f"Found {len(result.decisions)} decisions")
```

### Example 2: CSV/List Processing

```python
import json

# Load large dataset (1000 records)
with open("customer_feedback.json") as f:
    feedback_records = json.load(f)  # List of dicts

# Classify sentiment across all records
config = PaginationConfig(
    merge_strategy="merge",
    use_token_chunking=True  # Record-based chunking
)

proxy = AgentPaginationProxy(context, config)

result = await proxy.run(
    prompt="Classify sentiment for each feedback item",
    content=feedback_records
)

# Result combines classifications from all chunks
print(f"Positive: {result.positive_count}")
print(f"Negative: {result.negative_count}")
print(f"Neutral: {result.neutral_count}")
```

### Example 3: Custom Merge Strategy

```python
from statistics import mean

class SentimentAnalysis(BaseModel):
    sentiment_score: float  # -1.0 to 1.0
    key_themes: list[str]
    sample_quotes: list[str]

def weighted_sentiment_merge(results: list[SentimentAnalysis]) -> SentimentAnalysis:
    """Merge with weighted averaging of sentiment scores."""
    return SentimentAnalysis(
        sentiment_score=mean(r.sentiment_score for r in results),
        key_themes=list(set(theme for r in results for theme in r.key_themes)),
        sample_quotes=[q for r in results for q in r.sample_quotes[:2]]  # Top 2 per chunk
    )

config = PaginationConfig(
    merge_strategy="custom",
    custom_merge_fn=weighted_sentiment_merge
)

proxy = AgentPaginationProxy(context, config)
result = await proxy.run(prompt="Analyze sentiment", content=long_reviews)
```

## Configuration Reference

### Model Context Windows

```python
MODEL_CONTEXT_WINDOWS = {
    # Anthropic
    "claude-sonnet-4-5": 200_000,
    "claude-opus-4": 200_000,
    "claude-haiku-4-5": 200_000,

    # OpenAI
    "gpt-4.1": 128_000,
    "gpt-5": 128_000,
    "gpt-4o": 128_000,

    # Google
    "gemini-3-ultra": 1_000_000,  # 1M context
    "gemini-3-pro": 1_000_000,
}
```

### Default Overhead Estimates

```python
OVERHEAD_ESTIMATES = {
    "system_prompt": 1500,        # Typical system prompt size
    "output_schema": 500,          # JSON schema sent to LLM
    "response_buffer_ratio": 0.2,  # 20% reserved for response
    "json_record_overhead": 5,     # Tokens per record (brackets, commas)
}
```

## Performance Considerations

### Parallel vs Sequential Execution

**Parallel (default):**
- ✅ Faster for large inputs (3-10x speedup)
- ✅ Better API rate limit utilization
- ⚠️ Higher memory usage (N concurrent requests)
- ⚠️ May hit rate limits with many chunks

**Sequential:**
- ✅ Lower memory footprint
- ✅ Safer for rate limits
- ❌ Slower (linear execution)

**Recommendation:** Use parallel unless hitting rate limits or memory constraints.

### Cost Optimization

Pagination may increase costs due to:
- Repeated system prompts (once per chunk)
- Redundant schema overhead (once per chunk)
- Additional completion tokens (merge results)

**Mitigation strategies:**
1. **Maximize chunk size** - Use 60-80% of context window
2. **Minimize overhead** - Concise system prompts
3. **Smart merging** - "first"/"last" strategies avoid redundant processing
4. **Batch API** - For non-urgent processing (50% cost savings)

### Token Efficiency Example

```
Input: 300k tokens
Model: Claude Sonnet 4.5 (200k context)

Without pagination:
- ❌ Fails (exceeds context window)

With pagination (naive: 100k chunks):
- 3 chunks × 1500 overhead = 4500 extra tokens
- 3 separate API calls
- Cost: ~3.5x single call

With pagination (optimized: 160k chunks):
- 2 chunks × 1500 overhead = 3000 extra tokens
- 2 API calls
- Cost: ~2.3x single call (35% better than naive)
```

## Testing Strategy

### Unit Tests

```python
# tests/unit/agents/test_chunking.py
def test_optimal_chunk_size():
    """Test chunk size calculation."""
    size = get_optimal_chunk_size("claude-sonnet-4-5")
    assert size == 158_400  # 200k - 1500 - 40k

def test_token_chunking():
    """Test token-based splitting."""
    content = "word " * 100_000  # ~100k tokens
    chunks = chunk_by_tokens(content, "claude-sonnet-4-5")
    assert all(estimate_tokens(c, "claude-sonnet-4-5") < 160_000 for c in chunks)

def test_record_chunking_preserves_integrity():
    """Test record boundaries are never split."""
    records = [{"id": i, "data": "x" * 1000} for i in range(100)]
    chunks = chunk_by_records(records, "claude-sonnet-4-5")

    # Each chunk should be valid JSON with complete records
    for chunk in chunks:
        parsed = json.loads(chunk)
        assert isinstance(parsed, list)
        assert all("id" in r and "data" in r for r in parsed)
```

### Integration Tests

```python
# tests/integration/agents/test_pagination.py
@pytest.mark.asyncio
async def test_pagination_merge_strategy():
    """Test merge strategy combines list fields."""
    proxy = AgentPaginationProxy(
        context=AgentContext(tenant_id="test"),
        config=PaginationConfig(merge_strategy="merge")
    )

    # Simulate large input that will be chunked
    large_content = generate_test_content(tokens=300_000)

    result = await proxy.run(
        prompt="Extract entities",
        content=large_content
    )

    # Verify merging worked
    assert isinstance(result.entities, list)
    assert len(result.entities) > 0
```

## Migration Path

### Phase 1: Foundation (Week 1-2)
- [ ] Implement chunking utilities (`utils/chunking.py`)
- [ ] Add model context window registry
- [ ] Unit tests for chunking logic

### Phase 2: Core Proxy (Week 3-4)
- [ ] Implement `AgentPaginationProxy`
- [ ] Add built-in merge strategies (first, last, merge)
- [ ] Integration tests with test agents

### Phase 3: Factory Integration (Week 5)
- [ ] Update `create_agent` with pagination support
- [ ] Add pagination config to agent schemas
- [ ] Update documentation

### Phase 4: CLI Support (Week 6)
- [ ] Add `--paginate` flag to `agent-eval`
- [ ] Add `--merge-strategy` option
- [ ] CLI integration tests

### Phase 5: Production Hardening (Week 7-8)
- [ ] Error handling for partial failures
- [ ] Progress tracking for long operations
- [ ] Logging and observability
- [ ] Performance benchmarks

## Open Questions

1. **Retry strategy**: How to handle failures in individual chunks?
   - Retry failed chunks only?
   - Fail entire operation?
   - Configurable retry policy?

2. **Progress tracking**: How to expose progress for long operations?
   - Callback function?
   - AsyncIterator yielding chunk results?
   - WebSocket for real-time updates?

3. **Partial results**: Should we support returning partial results if some chunks fail?
   - Return `PartialResult` wrapper with successful chunks + errors?
   - Strict mode (all or nothing)?

4. **Schema evolution**: How to handle schema changes across pagination iterations?
   - Lock schema version at start?
   - Allow schema updates between chunks?

5. **State management**: Should chunks share state?
   - Stateless (each chunk independent)?
   - Stateful (pass cumulative context between chunks)?

## References

- **P8FS Implementation**: `/Users/sirsh/code/p8fs-modules/p8fs/src/p8fs/services/llm/memory_proxy.py`
- **Token Chunking**: `/Users/sirsh/code/p8fs-modules/p8fs/src/p8fs/utils/token_chunking.py`
- **Record Chunking**: `/Users/sirsh/code/p8fs-modules/p8fs/src/p8fs/utils/list_chunking.py`
- **Batch Processing**: `/Users/sirsh/code/p8fs-modules/p8fs/src/p8fs/services/llm/batch.py`
- [Tiktoken Documentation](https://github.com/openai/tiktoken)
- [Anthropic Context Windows](https://docs.anthropic.com/en/docs/models-overview)
- [OpenAI Context Windows](https://platform.openai.com/docs/models)
