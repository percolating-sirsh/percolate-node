# ACME Alpha - Claude Desktop Setup

This guide shows how to connect Claude Desktop to the ACME Alpha knowledge base via MCP **stdio mode**.

## Important: MCP Transport Mode

Claude Desktop requires MCP servers to run in **stdio mode** (standard input/output), NOT HTTP mode.

- ✅ **Correct**: `percolate mcp` (stdio transport)
- ❌ **Wrong**: `percolate serve` (HTTP/SSE transport)

The configuration below uses `percolate mcp` which runs FastMCP in stdio mode.

## Prerequisites

1. **Populate the database** (if not done already):
   ```bash
   cd /Users/sirsh/code/percolation/percolate
   env -u VIRTUAL_ENV uv run python ../.sample-data/populate_sample_data.py
   ```

   This creates a database at `~/.p8/acme-alpha-db` with:
   - 2,299 market data points (NCREIF, CBSA, energy, rates)
   - 44 entities (analysts, sponsors, lenders, markets, properties)

2. **Set up API keys** in your environment:
   ```bash
   export OPENAI_API_KEY="your-openai-api-key"
   export ANTHROPIC_API_KEY="your-anthropic-api-key"
   export CEREBRAS_API_KEY="your-cerebras-api-key"  # For query builder testing
   ```

## Configure Claude Desktop

### Option 1: Manual Configuration

1. Open Claude Desktop settings
2. Go to the MCP Servers configuration
3. Add the configuration from `claude-desktop-config.json` to your `~/Library/Application Support/Claude/claude_desktop_config.json`

### Option 2: Use the provided config

Copy the MCP server configuration:

```bash
# Backup existing config (if any)
cp ~/Library/Application\ Support/Claude/claude_desktop_config.json \
   ~/Library/Application\ Support/Claude/claude_desktop_config.json.backup

# Copy the ACME Alpha config
cp .sample-data/case-studies/acme-alpha/claude-desktop-config.json \
   ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

## Configuration Details

The MCP server configuration connects Claude Desktop to the acme-alpha database using **stdio transport**:

```json
{
  "mcpServers": {
    "percolate-acme-alpha": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/Users/sirsh/code/percolation/percolate",
        "percolate",
        "mcp"
      ],
      "env": {
        "P8_DB_PATH": "/Users/sirsh/.p8/acme-alpha-db",
        "P8_TENANT_ID": "felix-prime",
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

### Key Environment Variables

- **P8_DB_PATH**: Points to the acme-alpha database (`~/.p8/acme-alpha-db`)
- **P8_TENANT_ID**: Tenant scope (`felix-prime`)
- **PERCOLATE_OPENAI_API_KEY**: For embeddings (required for search)
- **PERCOLATE_ANTHROPIC_API_KEY**: For agent execution

## Available MCP Tools

Once configured, Claude Desktop will have access to these tools:

### 1. `search_knowledge_base`
Search the REM database for semantically similar content.

**Example queries:**
```
"Search for NCREIF apartment cap rates in 2024"
"Find information about Greenline Renewables track record"
"What are the latest population growth trends in Denver?"
"Show me Wyoming wind PPA rates"
```

**Parameters:**
- `query` (string): Natural language search query
- `tenant_id` (string): Tenant ID (default: "felix-prime")
- `limit` (int): Max results (default: 10)
- `schema` (string): Schema to search (default: "resources")

### 2. `lookup_entity`
Get specific entity by ID.

**Example:**
```
"Look up analyst FEL-001"
"Get details for sponsor GRN-001"
```

### 3. `parse_document`
Parse and ingest new documents into the knowledge base.

**Example:**
```
"Parse the attached PDF and add it to the knowledge base"
```

### 4. `create_agent` & `ask_agent`
Create and execute AI agents.

**Example:**
```
"Create an agent to analyze this investment opportunity"
"Ask the alpha-extraction agent to review this deal"
```

### 5. `about`
Get information about the MCP server.

## Testing the Connection

After restarting Claude Desktop, try these test queries:

1. **Search for market data:**
   ```
   Can you search the knowledge base for "NCREIF apartment cap rates 2024"?
   ```

2. **Find sponsor information:**
   ```
   Search for information about Greenline Renewables in the knowledge base
   ```

3. **Query demographics:**
   ```
   What population growth data do we have for Denver?
   ```

## Database Contents

### Market Data (2,299 data points)

1. **NCREIF Property Benchmarks** (570 points)
   - Property types: Apartment, Industrial-Warehouse, Office, Retail, Seniors Housing
   - Metrics: Total return, cap rate, occupancy, NOI growth
   - Period: Q1 2020 - Q3 2024

2. **CBSA Market Metrics** (760 points)
   - Markets: Denver, Atlanta, Orlando, Austin, Dallas-Fort Worth
   - Metrics: Population, employment, GDP growth, unemployment
   - Period: Q1 2020 - Q3 2024

3. **Energy Market PPA Rates** (570 points)
   - Markets: Wyoming wind, Texas wind, Southwest solar, California solar
   - Metrics: PPA rates, capacity factors, merchant exposure
   - Period: Q1 2020 - Q3 2024

4. **Financial Market Rates** (399 points)
   - Instruments: SOFR, US Treasury
   - Metrics: Overnight, 1M, 3M, 6M, 1Y, 2Y, 5Y, 10Y rates
   - Period: Jan 2020 - Sep 2024

### Entities (44 entities)

- **Analysts** (3): Felix Prime, Sarah Chen, Michael Torres
- **Sponsors** (10): Greenline Renewables, Horizon Industrial, Riverbend Capital, etc.
- **Markets** (8): Wyoming wind, Denver real estate, etc.
- **Lenders** (5): Various financial institutions
- **Properties** (13): Industrial, multifamily, office, energy projects
- **Deals** (5): Investment opportunities with alpha scores

## Troubleshooting

### MCP Server Not Starting

1. **Check the logs** in Claude Desktop settings (Developer → MCP Server Logs)
2. **Verify paths** are correct in the config (use absolute paths)
3. **Test manually in stdio mode**:
   ```bash
   cd /Users/sirsh/code/percolation/percolate
   export P8_DB_PATH=~/.p8/acme-alpha-db
   export P8_TENANT_ID=felix-prime
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
   ls -la ~/.p8/acme-alpha-db/
   ```

3. **Re-populate** if needed:
   ```bash
   rm -rf ~/.p8/acme-alpha-db
   uv run python .sample-data/populate_sample_data.py
   ```

### Embeddings Not Generated

The search tool requires OpenAI API key for generating embeddings:

```bash
export OPENAI_API_KEY="your-key-here"
```

Then restart Claude Desktop to pick up the new environment variable.

## Advanced Usage

### Query Planning

For faster structured queries, you can use Cerebras:

```bash
export PERCOLATE_CEREBRAS_API_KEY="your-key-here"
export PERCOLATE_QUERY_MODEL="cerebras:qwen-3-32b"
```

### Custom Schemas

You can register additional schemas for specific data types:

```python
from rem_db import Database

db = Database()
db.register_schema("deals", deal_schema_json)
```

## Resources

- **Case Study Overview**: `about.md`
- **Entity Ground Truth**: `entities.yaml`
- **Agent-let Schemas**: `agentlets/`
- **Test Documents**: `test-cases/`
- **Market Data**: `market-data/`

## Next Steps

1. Try the example queries above
2. Explore the agent-let schemas in `agentlets/`
3. Test document parsing with files from `test-cases/`
4. Create custom queries for your use case

---

**Note**: This is a demo database for the ACME Alpha case study. For production use, you would configure a persistent database path and implement proper backup/replication.
