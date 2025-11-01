# Testing Notes for Sample Data Scripts

## Environment Variables - CRITICAL

**ALWAYS read API keys from the environment, never hardcode or skip them.**

### Correct Pattern for Test Scripts

```python
#!/usr/bin/env python3
import os
import sys

# Set database-specific environment variables
os.environ["P8_DB_PATH"] = "/path/to/db"
os.environ["P8_TENANT_ID"] = "tenant-name"

# CHECK for API keys - don't override if already set
if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("P8_OPENAI_API_KEY"):
    print("ERROR: OPENAI_API_KEY not found in environment")
    print("Please set it first: export OPENAI_API_KEY='your-key'")
    sys.exit(1)

# Now run tests that require embeddings/search
```

### Why This Matters

1. **Search requires embeddings**: The `search_knowledge_base` MCP tool needs OpenAI API to generate embeddings
2. **API keys are in the user's environment**: Don't assume they need to be set manually in the script
3. **Fail early with clear message**: If the key is missing, tell the user immediately

### Common Mistakes to Avoid

❌ **Wrong**: Assuming embeddings will work without API keys
```python
# This will fail silently or with confusing errors
result = await search_knowledge_base(query="...", tenant_id="...")
```

❌ **Wrong**: Hardcoding API keys in test scripts
```python
os.environ["OPENAI_API_KEY"] = "sk-..."  # NEVER do this
```

❌ **Wrong**: Not checking if keys exist before testing
```python
# Script will run but search will return 0 results with errors in logs
```

✅ **Correct**: Check environment and fail with clear message
```python
if not os.environ.get("OPENAI_API_KEY"):
    print("ERROR: OPENAI_API_KEY not found")
    sys.exit(1)
```

## Testing Workflow

### 1. Populate Database
```bash
python populate_sample_data.py
# This doesn't need API keys - just creates database
```

### 2. Verify with Search (needs API keys)
```bash
export OPENAI_API_KEY="your-key"  # Required!
python verify_sample_data.py
```

### 3. Test MCP Server
```bash
export OPENAI_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"
export CEREBRAS_API_KEY="your-key"  # For query builder testing
uv run percolate mcp
# MCP server will read these from environment
```

## API Key Resolution Order

Percolate checks these environment variables in order:

1. `OPENAI_API_KEY` (standard)
2. `P8_OPENAI_API_KEY` (percolate-specific)
3. `PERCOLATE_OPENAI_API_KEY` (via settings)

**Best practice**: Use the standard `OPENAI_API_KEY` name.

## Claude Desktop Integration

Claude Desktop config uses `${VAR_NAME}` syntax:

```json
{
  "env": {
    "OPENAI_API_KEY": "${OPENAI_API_KEY}",
    "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}",
    "CEREBRAS_API_KEY": "${CEREBRAS_API_KEY}",
    "P8_DB_PATH": "/Users/user/.p8/db",
    "P8_TENANT_ID": "tenant-id"
  }
}
```

This reads from the **system environment** (shell profile), not from the JSON file.

## Summary

- ✅ Check for API keys before running search tests
- ✅ Read from environment, never hardcode
- ✅ Fail early with clear error messages
- ✅ Document which operations need which keys
- ❌ Never assume API keys are set
- ❌ Never hardcode keys in scripts
- ❌ Never silently fail on missing keys
