# OpenAI Embeddings Support

## Overview

percolate-rocks now supports **multiple embedding providers**:

1. **Local embeddings** (default) - `embed_anything` with all-MiniLM-L6-v2 (384 dims)
2. **OpenAI embeddings** - text-embedding-3-small/large, text-embedding-ada-002

Configuration is automatic via environment variables - no code changes needed!

## Quick Start

### Option 1: OpenAI Embeddings (No Model Download)

```bash
# Set environment variables
export P8_DEFAULT_EMBEDDING="text-embedding-3-small"
export OPENAI_API_KEY="sk-..."
```

```python
from percolate_rocks import REMDatabase

# Automatically uses OpenAI based on P8_DEFAULT_EMBEDDING
db = REMDatabase("tenant", "./db", enable_embeddings=True)

# Embeddings generated via OpenAI API (1536 dimensions)
await db.insert_with_embedding("table", {"content": "..."})
```

### Option 2: Local Embeddings (Default)

```python
from percolate_rocks import REMDatabase

# P8_DEFAULT_EMBEDDING not set → uses local model
# Downloads all-MiniLM-L6-v2 (~100MB) to ~/.p8/models/ on first use
db = REMDatabase("tenant", "./db", enable_embeddings=True)

# Embeddings generated locally (384 dimensions)
await db.insert_with_embedding("table", {"content": "..."})
```

### Option 3: No Embeddings

```python
from percolate_rocks import REMDatabase

# Fastest - no downloads, no API calls
db = REMDatabase("tenant", "./db", enable_embeddings=False)

# Handle embeddings externally if needed
```

## Environment Variables

### P8_DEFAULT_EMBEDDING

Determines which embedding provider to use:

| Value | Provider | Dimensions | Requires |
|-------|----------|------------|----------|
| `text-embedding-3-small` | OpenAI | 1536 | OPENAI_API_KEY |
| `text-embedding-3-large` | OpenAI | 3072 | OPENAI_API_KEY |
| `text-embedding-ada-002` | OpenAI | 1536 | OPENAI_API_KEY |
| Not set | Local (embed_anything) | 384 | Model download (~100MB) |
| `sentence-transformers/all-MiniLM-L6-v2` | Local | 384 | Model download |

### OPENAI_API_KEY

Required when using OpenAI models. Get your key from https://platform.openai.com/api-keys

```bash
export OPENAI_API_KEY="sk-proj-..."
```

### HF_HOME

Controls where local models are cached (default: `~/.p8/models/`):

```bash
export HF_HOME="/custom/path/to/models"
```

## Usage Examples

### Example 1: OpenAI with Batch Embeddings

```python
import asyncio
import os
from percolate_rocks import REMDatabase

async def main():
    # Configure OpenAI
    os.environ["P8_DEFAULT_EMBEDDING"] = "text-embedding-3-small"
    os.environ["OPENAI_API_KEY"] = "sk-..."

    db = REMDatabase("demo", "./db", enable_embeddings=True)

    # Register schema
    db.register_schema(
        "articles",
        {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"}
            }
        },
        embedding_fields=["content"]
    )

    # Insert multiple articles (batched automatically)
    articles = [
        {"title": "Rust Guide", "content": "Rust is a systems language..."},
        {"title": "Python Tutorial", "content": "Python is easy to learn..."},
        {"title": "Database Design", "content": "Normalization is key..."}
    ]

    for article in articles:
        await db.insert_with_embedding("articles", article)

    print("✓ All embeddings generated via OpenAI")

asyncio.run(main())
```

### Example 2: Switching Between Providers

```python
import os
from percolate_rocks import REMDatabase

# Start with OpenAI
os.environ["P8_DEFAULT_EMBEDDING"] = "text-embedding-3-small"
db1 = REMDatabase("tenant1", "./db1", enable_embeddings=True)
print(f"DB1 using: {os.environ['P8_DEFAULT_EMBEDDING']}")

# Switch to local for different database
del os.environ["P8_DEFAULT_EMBEDDING"]
db2 = REMDatabase("tenant2", "./db2", enable_embeddings=True)
print("DB2 using: local model (all-MiniLM-L6-v2)")
```

### Example 3: No Embeddings with External Service

```python
from percolate_rocks import REMDatabase
from openai import OpenAI  # Separate OpenAI client

db = REMDatabase("tenant", "./db", enable_embeddings=False)
client = OpenAI()

# Manually generate embeddings
embedding = client.embeddings.create(
    input="My text",
    model="text-embedding-3-large"
).data[0].embedding

# Store with manual embedding
db.insert("articles", {
    "content": "My text",
    "embedding": embedding  # Store manually
})
```

## API Details

### Batch Embedding Performance

Both providers support batch embeddings for efficiency:

**OpenAI:**
- Batches up to 2048 texts per request
- Automatic chunking for larger batches
- Parallel requests for different batches

**Local (embed_anything):**
- Processes all texts in single batch
- GPU acceleration if available
- CPU-based inference by default

### Cost Comparison

**OpenAI text-embedding-3-small:**
- $0.00002 per 1K tokens
- 1536 dimensions
- No local compute needed

**Local all-MiniLM-L6-v2:**
- Free (after model download)
- 384 dimensions
- Requires local compute

### Embedding Dimensions

| Model | Dimensions | Use Case |
|-------|------------|----------|
| text-embedding-3-large | 3072 | Highest quality, slower |
| text-embedding-3-small | 1536 | Good quality, fast |
| text-embedding-ada-002 | 1536 | Legacy OpenAI model |
| all-MiniLM-L6-v2 | 384 | Fast local inference |

## Error Handling

```python
from percolate_rocks import REMDatabase
import os

try:
    os.environ["P8_DEFAULT_EMBEDDING"] = "text-embedding-3-small"
    # Missing OPENAI_API_KEY will raise error
    db = REMDatabase("tenant", "./db", enable_embeddings=True)
except RuntimeError as e:
    if "OPENAI_API_KEY" in str(e):
        print("Please set OPENAI_API_KEY environment variable")
    else:
        raise
```

## Migration Guide

### From Local to OpenAI

```python
# Before (local embeddings)
db = REMDatabase("tenant", "./db", enable_embeddings=True)

# After (OpenAI embeddings)
import os
os.environ["P8_DEFAULT_EMBEDDING"] = "text-embedding-3-small"
os.environ["OPENAI_API_KEY"] = "sk-..."
db = REMDatabase("tenant", "./db", enable_embeddings=True)
```

### From External to Built-in

```python
# Before (manual OpenAI client)
from openai import OpenAI
client = OpenAI()
db = REMDatabase("tenant", "./db", enable_embeddings=False)
embedding = client.embeddings.create(...)

# After (automatic)
os.environ["P8_DEFAULT_EMBEDDING"] = "text-embedding-3-small"
db = REMDatabase("tenant", "./db", enable_embeddings=True)
await db.insert_with_embedding("table", {"content": "..."})
```

## Testing

Run the test suite:

```bash
# Test with OpenAI (requires API key)
export OPENAI_API_KEY="sk-..."
export P8_DEFAULT_EMBEDDING="text-embedding-3-small"
python3 test_openai.py

# Test with local model
unset P8_DEFAULT_EMBEDDING
python3 test_local.py

# Test without embeddings
python3 test_no_embeddings.py
```

## FAQ

### Q: Can I use both providers in the same application?

**A:** Yes, but each database instance uses the provider determined by `P8_DEFAULT_EMBEDDING` at creation time. Create separate databases for different providers.

### Q: What happens if I change P8_DEFAULT_EMBEDDING after creating a database?

**A:** The database continues using the provider it was initialized with. Environment variables are read at initialization time only.

### Q: Can I use custom OpenAI-compatible endpoints?

**A:** Not yet. Currently only supports https://api.openai.com/v1. Custom endpoints coming soon.

### Q: Which model should I choose?

- **text-embedding-3-small**: Best balance of quality and cost
- **text-embedding-3-large**: Maximum quality, higher cost
- **all-MiniLM-L6-v2**: Offline/local deployments, privacy-sensitive data

## Next Steps

- [ ] Add support for Cohere embeddings
- [ ] Add support for custom OpenAI-compatible endpoints
- [ ] Add embedding model switching for existing databases
- [ ] Add embedding dimension reduction (OpenAI supports this)
