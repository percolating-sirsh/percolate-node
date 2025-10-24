# Batch insert implementation

## Overview

Implemented efficient batch insert functionality with automatic embedding generation in Rust, addressing the user's feedback: *"i dont like this looping - why dont we have just batch insert and handle it in the rust side?"*

## Key features

### 1. Rust-side batch operations

**Location:** `src/memory/database.rs:152-268`

- Single batch API call for embedding generation
- Efficient processing of multiple entities at once
- No Python-side loops required

**Method signature:**
```rust
pub async fn batch_insert_with_embedding(
    &self,
    table: &str,
    entities: Vec<serde_json::Value>,
    key_field: Option<&str>,
) -> Result<Vec<Uuid>>
```

### 2. Smart key field resolution

**Precedence:** uri → key_field → name → id

- **URI mode:** For resources, generates ID from `hash(uri:chunk_ordinal)`
- **Custom key:** Hash any field to create deterministic UUIDs
- **Name fallback:** Uses `name` field if available
- **ID default:** Random UUID if no key specified

**Example:**
```json
{"uri": "doc.pdf", "chunk_ordinal": 0, "content": "..."}
```
Generates deterministic ID: `blake3("doc.pdf:0")` → UUID

### 3. Batch embedding generation

- Collects all texts from entities that need embeddings
- Single API call to embedding provider (OpenAI or local)
- Inserts embeddings back into entity properties
- Works with both:
  - **Local model:** all-MiniLM-L6-v2 (384 dims)
  - **OpenAI:** text-embedding-3-small (1536 dims)

### 4. Python API

**Location:** `src/bindings/database.rs:167-210`

```python
# Old way (user disliked)
for article in articles:
    id = await db.insert_with_embedding("articles", article)

# New way (efficient)
ids = await db.batch_insert("articles", articles, key_field="name")
```

**Benefits:**
- No loops in Python
- Single async call
- Batch embedding generation in Rust
- Returns list of UUIDs

### 5. CLI upsert command

**Usage:**
```bash
rem-db upsert -d <database> <table> --file data.jsonl [--key-field <field>]
```

**Features:**
- Reads JSONL files (line-delimited JSON)
- Auto-registers schema from first entity
- Detects embedding fields (`content` or `description`)
- Uses precedence: uri → key_field → name → id

**Example:**
```bash
# Create test data
cat > articles.jsonl <<EOF
{"name": "Rust", "content": "Systems programming language"}
{"name": "Python", "content": "High-level programming language"}
EOF

# Upsert with name as key
rem-db upsert -d mydb articles --file articles.jsonl --key-field name
```

**Output:**
```
→ Upserting data from articles.jsonl to table 'articles'
✓ Parsed 2 entities from file
→ Registering schema for table 'articles'
  ✓ Schema registered with embedding fields: ["content"]
✓ Upserted 2 entities to table 'articles'
   Key field: name
```

## Implementation details

### Key field modes

1. **URI mode** (key_field="uri"):
   - Generates ID from `hash(uri:chunk_ordinal)`
   - Perfect for chunked documents
   - Same URI + different ordinal = different ID
   - Idempotent: re-importing same URI updates existing entity

2. **Custom key** (key_field="name"):
   - Generates ID from `hash(field_value)`
   - Deterministic: same value = same ID
   - Enables upsert semantics

3. **Auto mode** (no key_field):
   - Checks for URI first
   - Falls back to name
   - Falls back to random UUID

### Embedding batch processing

**src/memory/database.rs:187-223**

```rust
// Collect texts
let mut texts_to_embed: Vec<String> = Vec::new();
let mut embed_indices: Vec<usize> = Vec::new();

for (idx, properties) in prepared_entities.iter().enumerate() {
    for field_name in &schema.embedding_fields {
        if let Some(text) = properties.get(field_name).and_then(|v| v.as_str()) {
            texts_to_embed.push(text.to_string());
            embed_indices.push(idx);
            break;  // One embedding per entity
        }
    }
}

// Batch generate (single API call)
let embeddings = provider.embed_batch(texts_to_embed).await?;

// Insert back
for (emb_idx, entity_idx) in embed_indices.iter().enumerate() {
    prepared_entities[*entity_idx]
        .as_object_mut()
        .unwrap()
        .insert("embedding".to_string(), json!(embeddings[emb_idx]));
}
```

## Testing

### Test 1: Local embeddings

```bash
# Initialize database
./target/release/rem-db init test-batch

# Create test data
cat > test.jsonl <<EOF
{"name": "Rust", "content": "Systems programming"}
{"name": "Python", "content": "High-level language"}
EOF

# Batch upsert
./target/release/rem-db upsert -d test-batch articles --file test.jsonl

# Search
./target/release/rem-db search -d test-batch "programming" --min-score 0.3
```

**Result:**
```
✓ Found 2 results:
1. Rust (score: 0.527)
   Systems programming
2. Python (score: 0.452)
   High-level language
```

### Test 2: OpenAI embeddings

```bash
export P8_DEFAULT_EMBEDDING="text-embedding-3-small"
export OPENAI_API_KEY="sk-..."

./target/release/rem-db init test-openai
./target/release/rem-db upsert -d test-openai articles --file test.jsonl
./target/release/rem-db search -d test-openai "coding languages" --min-score 0.3
```

## Performance comparison

| Method | Embeddings | API calls | Efficiency |
|--------|-----------|-----------|------------|
| Old (loop) | 100 entities | 100 calls | Slow |
| New (batch) | 100 entities | 1 call | Fast |

**OpenAI batch limit:** 2048 texts per request
**Local:** No limit (processes all at once)

## User feedback addressed

✅ "i dont like this looping" → Batch processing in Rust
✅ "batch insert AND batch generate embeddings" → Single batch API call
✅ "it should be clear what the key field is" → Precedence: uri → key → name → id
✅ "assume e.g. name or id or an id hashed from something like name" → Smart key resolution
✅ "i want the cli to have an upsert from file JSONL" → `rem-db upsert` command
✅ "uri generates the key for the file" → `hash(uri:chunk_ordinal)` for resources

## Example workflows

### Workflow 1: Import articles with name-based IDs

```bash
# articles.jsonl
{"name": "Article 1", "content": "First article about Rust"}
{"name": "Article 2", "content": "Second article about Python"}

# Import
rem-db upsert -d mydb articles --file articles.jsonl --key-field name

# Re-import (updates existing)
rem-db upsert -d mydb articles --file articles.jsonl --key-field name
```

### Workflow 2: Import document chunks with URI-based IDs

```bash
# chunks.jsonl
{"uri": "doc.pdf", "chunk_ordinal": 0, "content": "First chunk"}
{"uri": "doc.pdf", "chunk_ordinal": 1, "content": "Second chunk"}
{"uri": "doc.pdf", "chunk_ordinal": 2, "content": "Third chunk"}

# Import (uri takes precedence)
rem-db upsert -d mydb resources --file chunks.jsonl

# Each chunk gets deterministic ID: blake3("doc.pdf:0"), blake3("doc.pdf:1"), etc.
```

### Workflow 3: Python batch insert

```python
import asyncio
from percolate_rocks import REMDatabase

async def main():
    db = REMDatabase("mydb", "./db", enable_embeddings=True)

    # Register schema
    db.register_schema("articles", {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "content": {"type": "string"}
        }
    }, embedding_fields=["content"])

    # Batch insert (no loops!)
    articles = [
        {"name": "Article 1", "content": "Rust is fast"},
        {"name": "Article 2", "content": "Python is easy"},
        {"name": "Article 3", "content": "Go is simple"}
    ]

    ids = await db.batch_insert("articles", articles, key_field="name")
    print(f"Inserted {len(ids)} articles")

asyncio.run(main())
```

## Notes

- Schemas are auto-registered from first entity in JSONL file
- Embedding fields auto-detected: `content` or `description`
- Batch size unlimited for local embeddings
- OpenAI batch size: up to 2048 texts per call
- Deterministic UUIDs enable idempotent upserts
