# Percolating Plants - Claude Desktop Setup

This guide shows how to connect Claude Desktop to the Percolating Plants knowledge base via MCP **stdio mode**.

## Important: MCP Transport Mode

Claude Desktop requires MCP servers to run in **stdio mode** (standard input/output), NOT HTTP mode.

- ✅ **Correct**: `percolate mcp` (stdio transport)
- ❌ **Wrong**: `percolate serve` (HTTP/SSE transport)

The configuration below uses `percolate mcp` which runs FastMCP in stdio mode.

## Prerequisites

1. **Populate the database** (if not done already):
   ```bash
   cd /Users/sirsh/code/percolation/.sample-data/case-studies/percolating-plants
   env -u VIRTUAL_ENV uv run --directory /Users/sirsh/code/percolation/percolate python populate_plants_data.py
   ```

   This creates a database at `~/.p8/percolating-plants-db` with:
   - Products (plants, accessories)
   - Suppliers, customers, employees
   - Documents (product descriptions, emails, blog posts)

2. **Set up API keys** in your environment:
   ```bash
   export OPENAI_API_KEY="your-openai-api-key"
   export ANTHROPIC_API_KEY="your-anthropic-api-key"
   export CEREBRAS_API_KEY="your-cerebras-api-key"  # For query builder testing
   ```

## Configure Claude Desktop

### Option 1: Use the provided config

Copy the MCP server configuration:

```bash
# Backup existing config (if any)
cp ~/Library/Application\ Support/Claude/claude_desktop_config.json \
   ~/Library/Application\ Support/Claude/claude_desktop_config.json.backup

# Copy the Percolating Plants config
cp claude-desktop-config.json \
   ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

### Option 2: Add to existing config

If you already have other MCP servers, add this entry to your existing `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "percolate-plants": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/Users/sirsh/code/percolation/percolate",
        "percolate",
        "mcp"
      ],
      "env": {
        "P8_DB_PATH": "/Users/sirsh/.p8/percolating-plants-db",
        "P8_TENANT_ID": "percolating-plants",
        "PERCOLATE_OPENAI_API_KEY": "${OPENAI_API_KEY}",
        "PERCOLATE_ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}",
        "OPENAI_API_KEY": "${OPENAI_API_KEY}",
        "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}"
      }
    }
  }
}
```

**Key Points:**
- Uses `percolate mcp` command (not `percolate serve`)
- Runs in stdio mode (standard input/output)
- Environment variables are passed through the `env` section
- API keys use `${VAR_NAME}` syntax to reference system environment variables

## Available MCP Tools

Once configured, Claude Desktop will have access to these tools:

### 1. `search_knowledge_base`
Search the REM database for semantically similar content.

**Example queries:**
```
"Search for low maintenance indoor plants"
"Find products from supplier SUP-001"
"What plants are suitable for bright indirect light?"
"Show me email about Pink Princess order"
```

### 2. `lookup_entity`
Get specific entity by ID.

**Example:**
```
"Look up product PP-1001-SM"
"Get details for supplier SUP-003"
```

### 3. `parse_document`
Parse and ingest new documents into the knowledge base.

### 4. `create_agent` & `ask_agent`
Create and execute AI agents.

**Example:**
```
"Create an agent to handle customer inquiries about plant care"
```

### 5. `about`
Get information about the MCP server.

## Testing the Connection

After restarting Claude Desktop, try these test queries:

1. **Search for products:**
   ```
   Can you search the knowledge base for "low maintenance plants for apartments"?
   ```

2. **Find specific product:**
   ```
   Search for information about Monstera Deliciosa in the knowledge base
   ```

3. **Query suppliers:**
   ```
   What suppliers do we have in the knowledge base?
   ```

## Database Contents

### Products (~10 items)
- Indoor plants (Monstera, Fiddle Leaf Fig, Snake Plant, etc.)
- Outdoor plants (Lavender, Japanese Maple)
- Accessories (Plant food, pots)

### Suppliers (~9 items)
- French and European plant suppliers

### Customers (~5 items)
- Retail and commercial customers

### Documents (~8 items)
- Product descriptions
- Customer service emails
- Supplier correspondence
- Blog posts and articles

## Troubleshooting

### MCP Server Not Starting

1. **Check the logs** in Claude Desktop settings (Developer → MCP Server Logs)
2. **Verify paths** are correct in the config (use absolute paths)
3. **Test manually in stdio mode**:
   ```bash
   cd /Users/sirsh/code/percolation/percolate
   export P8_DB_PATH=~/.p8/percolating-plants-db
   export P8_TENANT_ID=percolating-plants
   export OPENAI_API_KEY="your-key"
   export ANTHROPIC_API_KEY="your-key"

   # Test stdio mode (this is what Claude Desktop uses)
   uv run percolate mcp
   ```

   If the server starts correctly, you should see MCP initialization output.
   Press Ctrl+C to stop.

### Search Returns No Results

1. **Check API keys** are set:
   ```bash
   echo $OPENAI_API_KEY
   ```

2. **Verify database** exists:
   ```bash
   ls -la ~/.p8/percolating-plants-db/
   ```

3. **Re-populate** if needed:
   ```bash
   cd /Users/sirsh/code/percolation/.sample-data/case-studies/percolating-plants
   rm -rf ~/.p8/percolating-plants-db
   env -u VIRTUAL_ENV uv run --directory /Users/sirsh/code/percolation/percolate python populate_plants_data.py
   ```

### Environment Variables Not Working

Claude Desktop uses `${VAR_NAME}` syntax to reference system environment variables.
Set them in your shell profile:

```bash
# Add to ~/.zshrc or ~/.bash_profile
export OPENAI_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"
```

Then restart your terminal AND Claude Desktop.

## Resources

- **Case Study Overview**: `about.md`
- **Entity Ground Truth**: `entities.yaml`
- **Sample Documents**: `documents/`
- **Test Scripts**: `.testing/`

## Next Steps

1. Populate the database (see Prerequisites)
2. Copy config to Claude Desktop
3. Restart Claude Desktop
4. Try the example queries above
5. Test with your own queries about plants, suppliers, and orders

---

**Note**: This is a demo database for the Percolating Plants case study. The shop is fictional but represents a realistic small business use case.
