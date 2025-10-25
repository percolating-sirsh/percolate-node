# REM Database Test Scripts

This directory contains test scripts and utilities for the REM database.

## Scripts

### `generate_test_data.py`

Generates realistic test data for ingestion testing.

**Output:**
- `test-data/articles.jsonl` - 100 articles about Rust, Python, and databases
- `test-data/users.jsonl` - 50 users with various roles

**Usage:**
```bash
python3 scripts/generate_test_data.py
```

**Data generated:**
- **Articles**: Technical content with categories, authors, views, ratings, tags
- **Users**: Names, emails, ages, roles, statuses, departments

### `test_queries.sh`

Comprehensive Bash test suite for all query types.

**Features:**
- Schema registration and validation
- Data generation and ingestion
- Key lookup queries (LOOKUP)
- Semantic search queries (SEARCH)
- Standard SQL queries (SELECT)
- Natural language queries (ask)
- Edge case and error handling

**Usage:**
```bash
./scripts/test_queries.sh
```

**Output:** Colorized test results with pass/fail counts

### `test_queries.py`

Python test suite with detailed validation and output capture.

**Features:**
- All features from Bash version
- Detailed validation functions
- Better error messages
- Machine-readable output

**Usage:**
```bash
./scripts/test_queries.py
```

**Environment Variables:**
- `P8_DEFAULT_EMBEDDING` - Embedding provider (e.g., `local:all-MiniLM-L6-v2`)
- `OPENAI_API_KEY` - For OpenAI embeddings and LLM queries
- `ANTHROPIC_API_KEY` - For Anthropic Claude queries

## Test Phases

Both test scripts execute these phases:

### Phase 1: Schema Registration
- Register articles schema from `test-data/articles_schema.json`
- List schemas to verify registration

### Phase 2: Data Generation & Ingestion
- Generate test data (articles and users)
- Ingest JSONL files
- Verify entity counts

### Phase 3: Key Lookup Queries (LOOKUP)
Tests from `docs/sql-dialect.md` section 1:
```sql
LOOKUP 'Rust Tutorial 1'
LOOKUP 'Rust Tutorial 1', 'Python Tutorial 5'
LOOKUP 'Rust Tutorial 1' SELECT name, category
```

### Phase 4: Semantic Search (SEARCH)
Tests from `docs/sql-dialect.md` section 3:
```sql
SEARCH 'memory safety' IN articles --top-k 5
SEARCH 'async programming' IN articles WHERE category = 'rust'
SEARCH 'machine learning' IN articles ORDER BY rating DESC
```

**Note:** Requires embedding provider configured

### Phase 5: Standard SQL Queries
Tests from `docs/sql-dialect.md` section 4:
```sql
SELECT * FROM articles LIMIT 5
SELECT name, author FROM articles WHERE category = 'rust'
SELECT name FROM articles WHERE views >= 5000
SELECT name, rating FROM articles ORDER BY rating DESC
```

### Phase 6: Natural Language Queries (ask)
Tests natural language to SQL conversion:
```bash
rem ask "Find articles about Rust performance"
rem ask "Show me Python tutorials by Alice" --plan
rem ask "What are the highest rated database articles?"
```

**Note:** Requires LLM API key (OpenAI or Anthropic)

### Phase 7: Edge Cases & Error Handling
- Non-existent schemas
- Invalid SQL syntax
- Empty queries
- Missing required parameters

## Running Tests

### Minimal Setup (No Embeddings/LLM)

Tests SQL queries and key lookups only:

```bash
# Build binary
cargo build --bin rem --release

# Run tests
./scripts/test_queries.sh
```

**Expected:** ~25 tests pass, search/ask tests skipped

### With Local Embeddings

Tests SQL queries, key lookups, and semantic search:

```bash
# Set embedding provider
export P8_DEFAULT_EMBEDDING="local:all-MiniLM-L6-v2"

# Build and test
cargo build --bin rem --release
./scripts/test_queries.py
```

**Expected:** ~35 tests pass, ask tests skipped

### With OpenAI (Full Testing)

Tests all features including natural language queries:

```bash
# Set API keys
export P8_DEFAULT_EMBEDDING="openai:text-embedding-3-small"
export OPENAI_API_KEY="sk-..."

# Build and test
cargo build --bin rem --release
./scripts/test_queries.py
```

**Expected:** All ~45 tests pass

## Test Data Schema

### Articles Schema (`test-data/articles_schema.json`)

```json
{
  "title": "Article",
  "short_name": "articles",
  "properties": {
    "name": {"type": "string", "description": "Article title"},
    "content": {"type": "string", "description": "Article content"},
    "category": {"type": "string", "description": "Content category"},
    "author": {"type": "string", "description": "Article author"},
    "views": {"type": "integer", "description": "View count"},
    "rating": {"type": "number", "description": "Rating 1-5"},
    "created_at": {"type": "string", "format": "date-time"},
    "tags": {"type": "array", "items": {"type": "string"}}
  },
  "json_schema_extra": {
    "embedding_fields": ["content"],
    "embedding_provider": "default",
    "indexed_fields": ["category", "author"],
    "key_field": "name"
  }
}
```

### Generated Content Distribution

**Articles (100 total):**
- ~33 Rust articles (ownership, async, performance, CLI tools)
- ~33 Python articles (data science, web frameworks, ML)
- ~34 Database articles (RocksDB, vector DBs, SQL vs NoSQL, graph DBs)

**Metadata:**
- Authors: alice, bob, charlie, diana
- Views: 10 - 10,000 (random)
- Ratings: 1.0 - 5.0 (random, 1 decimal)
- Tags: tutorial, beginner, advanced, performance, best-practices
- Created dates: Last 365 days

## Debugging Failed Tests

If tests fail, check:

1. **Binary exists:** `ls -lh target/release/rem`
2. **Database path:** `ls -la test-db/`
3. **Test data:** `ls -lh test-data/*.jsonl`
4. **Schema registered:** `./target/release/rem schema list`
5. **Environment:** `env | grep -E '(P8_|OPENAI|ANTHROPIC)'`

View detailed error output:
```bash
# Run individual command
./target/release/rem query "SELECT * FROM articles LIMIT 5"

# Check schema
./target/release/rem schema list

# Count entities
./target/release/rem count articles
```

## Adding New Tests

To add tests, edit test_queries.py:

```python
suite.run(
    "Your test name",
    [str(REM_BIN), "query", "YOUR SQL HERE"],
    validate_fn=lambda out: "expected" in out
)
```

Validation functions can check:
- String presence: `"text" in output`
- Regex patterns: `re.search(r'pattern', output)`
- Entity counts: `int(re.search(r'\d+', output).group()) == 100`
- JSON structure: `json.loads(output)`

## Performance Expectations

| Operation | Expected Time | Notes |
|-----------|---------------|-------|
| Schema registration | < 100ms | JSON validation only |
| Ingest 100 items (no embeddings) | < 1s | RocksDB writes |
| Ingest 100 items (with embeddings) | 5-30s | Network bound (OpenAI) or CPU bound (local) |
| Key lookup | < 1ms | Direct RocksDB get |
| SQL query (indexed) | < 10ms | Column family scan |
| Semantic search (100 docs) | < 100ms | Build + search HNSW |
| Semantic search (10k docs) | < 500ms | Larger HNSW index |
| Natural language query | 1-3s | LLM API call |

## Continuous Integration

To run tests in CI:

```yaml
# .github/workflows/test.yml
- name: Build REM
  run: cargo build --bin rem --release

- name: Run test suite
  run: ./scripts/test_queries.sh
  env:
    P8_DEFAULT_EMBEDDING: "local:all-MiniLM-L6-v2"
```

Skip LLM tests in CI (rate limits, cost) unless needed.
