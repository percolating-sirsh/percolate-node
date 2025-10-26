# Agent-lets: Trainable AI Skills for Percolate

Agent-lets are **JSON schema-defined AI skills** that provide structured, repeatable AI capabilities in Percolate. They combine:

1. **System prompts** (instructions for the LLM)
2. **Structured output schemas** (Pydantic models)
3. **MCP tool references** (external capabilities)
4. **Version metadata** (for evolution tracking)

Think of agent-lets as **reusable AI functions** that can be shared, versioned, and evolved over time.

## Core Concepts

### Agent-let = Schema + Prompt + Tools

An agent-let has three essential components:

```
┌─────────────────────────────────────┐
│         Agent-let Schema            │
├─────────────────────────────────────┤
│  description (system prompt)        │
│  properties (output structure)      │
│  tools[] (MCP tool references)      │
│  metadata (name, version)           │
└─────────────────────────────────────┘
                 ↓
         Pydantic AI Factory
                 ↓
       Executable AI Agent
```

### Two Definition Formats

Agent-lets can be defined in two ways:

**1. JSON Schema (Portable)**
```json
{
  "title": "TestAgent",
  "description": "System prompt goes here...",
  "properties": {
    "answer": {"type": "string"},
    "confidence": {"type": "number", "minimum": 0, "maximum": 1}
  },
  "required": ["answer", "confidence"]
}
```

**2. Pydantic Model (Type-Safe)**
```python
class TestAgent(BaseModel):
    """System prompt goes here as docstring."""

    model_config = ConfigDict(
        json_schema_extra={
            "tools": [{"mcp_server": "percolate", "tool_name": "search_memory"}]
        }
    )

    answer: str
    confidence: float = Field(ge=0.0, le=1.0)
```

Both formats are equivalent and can be used interchangeably. The JSON format is portable (can be stored in REM, shared across systems), while the Pydantic format provides IDE support and type safety.

## Factory Pattern

The **agent factory** is the core of Percolate's agent-let system. It converts schemas to executable agents:

```python
from percolate.agents.factory import create_agent
from percolate.agents.context import AgentContext

# Load schema (JSON or Pydantic)
schema = load_agentlet_schema("test-agent")

# Create context
context = AgentContext(
    tenant_id="tenant-123",
    default_model="claude-3-5-sonnet-20241022"
)

# Create executable agent
agent = await create_agent(
    context=context,
    agent_schema_override=schema
)

# Run agent
result = await agent.run("What is 2+2?")
print(result.output)  # {"answer": "4", "confidence": 1.0, ...}
```

### Factory Features

The factory handles:

1. **Schema Dumper**: Strips model description from LLM schema to avoid duplication with system prompt
2. **Dynamic Model Creation**: Converts JSON schemas to Pydantic models on-the-fly
3. **MCP Tool Loading**: Dynamically attaches tools from schema metadata
4. **OpenTelemetry**: Optional tracing (disabled by default)

**Key Insight**: The model's docstring **IS** the system prompt. We strip the description from the JSON schema sent to the LLM to avoid redundancy:

```python
# LLM sees:
# System Prompt: "You are a test agent..."
# Output Schema: {properties: {answer: "string", ...}}
#
# NOT:
# System Prompt: "You are a test agent..."
# Output Schema: {description: "You are a test agent...", properties: {...}}
```

## MCP Tool Integration

Agent-lets can reference MCP tools for external capabilities:

### Tool Reference Format

```json
{
  "json_schema_extra": {
    "tools": [
      {
        "mcp_server": "percolate",
        "tool_name": "search_memory",
        "usage": "Search REM memory for relevant information"
      }
    ]
  }
}
```

### Tool Wrapper Pattern

The **tool_wrapper** module bridges FastMCP tools (with `ctx` parameter) to Pydantic AI tools (without `ctx`):

```python
from percolate.agents.tool_wrapper import create_pydantic_tool

# MCP tool with ctx parameter
async def search_memory(ctx, query: str, limit: int = 5):
    """Search REM memory."""
    return await search_impl(query, limit)

# Convert to Pydantic AI tool
tool = create_pydantic_tool(search_memory)

# Use with agent
agent = Agent(model="claude-3-5-sonnet-20241022", tools=[tool])
```

The wrapper:
- Extracts parameter schema (excluding `ctx`)
- Creates wrapper function that calls tool with `ctx=None`
- Uses `Tool.from_schema()` with `takes_ctx=False`

## Agent Evaluation

### Via CLI

```bash
# Basic evaluation
percolate agent-eval test-agent "What is 2+2?"

# With model override
percolate agent-eval test-agent "Explain percolate" --model claude-opus-4

# JSON output for scripting
percolate agent-eval test-agent "Test query" --json
```

Output:
```
✓ Agent: test-agent
Model: claude-3-5-sonnet-20241022

Response:
 answer      2 + 2 = 4
 confidence  1.0
 tags        math, arithmetic

Tokens: 614 in / 90 out
```

### Via MCP Tool

```python
from percolate.mcp.tools.agent import ask_agent

result = await ask_agent(
    ctx=None,
    agent_uri="test-agent",
    tenant_id="tenant-123",
    prompt="What is percolate?",
    model="claude-3-5-sonnet-20241022",
)

print(result["response"])  # Structured output dict
print(result["usage"])     # Token usage metrics
```

### Via Python API

```python
from percolate.agents.factory import create_agent
from percolate.agents.registry import load_agentlet_schema
from percolate.agents.context import AgentContext

# Load and create
schema = load_agentlet_schema("test-agent")
context = AgentContext(tenant_id="test")
agent = await create_agent(context, agent_schema_override=schema)

# Execute
result = await agent.run("Your prompt here")
print(result.output)
print(result.usage())
```

## Creating Agent-lets

### System Agent-lets

System agents are built-in and stored in `src/percolate/schema/agentlets/`:

**JSON Format** (`percolate-test-agent.json`):
```json
{
  "title": "TestAgent",
  "description": "System prompt...",
  "version": "1.0.0",
  "short_name": "test_agent",
  "fully_qualified_name": "percolate.agents.test_agent.TestAgent",
  "json_schema_extra": {
    "tools": []
  },
  "properties": {
    "answer": {"type": "string", "description": "Answer"},
    "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0}
  },
  "required": ["answer", "confidence"]
}
```

**Pydantic Format** (`test_agent.py`):
```python
from pydantic import BaseModel, Field, ConfigDict

class TestAgent(BaseModel):
    """System prompt goes here as docstring.

    Use markdown formatting for clarity.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "fully_qualified_name": "percolate.agents.test_agent.TestAgent",
            "short_name": "test_agent",
            "version": "1.0.0",
            "tools": []
        }
    )

    answer: str = Field(description="The answer")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence 0-1")
    tags: list[str] = Field(default_factory=list, description="Tags")
```

### User Agent-lets

User agents are **not yet implemented** but will be stored in tenant-scoped REM storage:

```
user/{tenant_id}/{agent_name}.json
```

Access control: users can only access their own tenant's agents.

## Best Practices

### 1. System Prompt Design

- **Be specific**: Clear instructions produce better results
- **Use examples**: Show the LLM what good output looks like
- **Structure with markdown**: Use headers, lists, and code blocks
- **Include constraints**: Specify what NOT to do

### 2. Output Schema Design

- **Required fields first**: Ensure critical data is always present
- **Use descriptions**: Help the LLM understand field semantics
- **Constrain types**: Use `minimum`, `maximum`, `enum` for validation
- **Default values**: Provide sensible defaults for optional fields

### 3. Tool Selection

- **Minimize tools**: Only attach tools the agent actually needs
- **Clear tool docs**: Tool docstrings are sent to the LLM
- **Handle failures**: Tools can fail, design prompts to handle this

### 4. Testing and Iteration

- **Start simple**: Begin with basic prompts and schemas
- **Use CLI**: `percolate agent-eval` for rapid testing
- **Check confidence**: Low confidence = unclear instructions or ambiguous prompt
- **Version agents**: Increment version when making breaking changes

## Configuration

### Environment Variables

```bash
# Required for agent execution
PERCOLATE_ANTHROPIC_API_KEY=your-key-here

# Optional: override model
PERCOLATE_DEFAULT_MODEL=claude-3-5-sonnet-20241022

# Optional: enable tracing
PERCOLATE_OTEL_ENABLED=true
PERCOLATE_OTEL_ENDPOINT=http://localhost:4318
```

### Model Selection Priority

1. **Override**: Explicit model in `create_agent(model_override=...)`
2. **Context**: Model from `AgentContext.default_model`
3. **Settings**: Global `settings.default_model`

### OpenTelemetry (Optional)

Tracing is **disabled by default** to minimize dependencies:

```python
# Enable in settings.py
settings.otel_enabled = True
settings.otel_endpoint = "http://localhost:4318"  # Phoenix/Jaeger endpoint
```

When enabled:
- Pydantic AI instrumentation tracks agent runs
- Spans include tenant_id, user_id, session_id
- Integrates with Phoenix for visualization

## Advanced Patterns

### Chaining Agent-lets

```python
# Agent 1: Extract entities
entities_result = await entities_agent.run(text)

# Agent 2: Classify entities using output from Agent 1
classification = await classifier_agent.run(
    f"Classify these entities: {entities_result.output}"
)
```

### Conditional Tool Access

```python
# Different tools for different contexts
if user_has_admin_role:
    tools_config = [
        {"mcp_server": "percolate", "tool_name": "search_memory"},
        {"mcp_server": "percolate", "tool_name": "admin_tool"}
    ]
else:
    tools_config = [
        {"mcp_server": "percolate", "tool_name": "search_memory"}
    ]

schema["json_schema_extra"]["tools"] = tools_config
```

### Dynamic Schema Generation

```python
from pydantic import create_model, Field

# Create schema at runtime
properties = {
    field_name: (str, Field(description=field_desc))
    for field_name, field_desc in user_defined_fields.items()
}

DynamicAgent = create_model("DynamicAgent", **properties)

# Use with factory
agent = await create_agent(context, result_type=DynamicAgent)
```

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────┐
│                     User/Application                     │
└──────────────────────┬──────────────────────────────────┘
                       │
          ┌────────────┼────────────┐
          │            │            │
      CLI Tool     MCP Tool     Python API
          │            │            │
          └────────────┼────────────┘
                       ↓
              ┌────────────────┐
              │ ask_agent()    │
              └────────┬───────┘
                       ↓
              ┌────────────────┐
              │   Registry     │  Load schema
              │ (load_schema)  │
              └────────┬───────┘
                       ↓
              ┌────────────────┐
              │     Factory    │  Create agent
              │ (create_agent) │
              └────────┬───────┘
                       │
          ┌────────────┼────────────┐
          │            │            │
    Schema Dumper  Tool Wrapper  OTEL Setup
          │            │            │
          └────────────┼────────────┘
                       ↓
              ┌────────────────┐
              │  Pydantic AI   │
              │     Agent      │
              └────────┬───────┘
                       ↓
                  LLM Provider
             (Anthropic, OpenAI, ...)
```

### Data Flow

1. **Schema Loading**: Registry loads JSON or Pydantic schema
2. **Model Creation**: Factory creates dynamic Pydantic model (if needed)
3. **Tool Attachment**: Tool wrapper bridges MCP tools to Pydantic AI
4. **Agent Creation**: Pydantic AI Agent instantiated with config
5. **Execution**: Agent runs with prompt, returns structured output
6. **Response Formatting**: Output converted to dict/JSON for API

## Troubleshooting

### "System agent not found"

- Check agent URI matches filename (without `.json`)
- Verify file in `src/percolate/schema/agentlets/`
- Try: `percolate agent-eval percolate-test-agent "test"`

### "ANTHROPIC_API_KEY not set"

- Add to `.env`: `PERCOLATE_ANTHROPIC_API_KEY=your-key`
- Settings automatically sync to `ANTHROPIC_API_KEY` environment variable

### "Unknown keyword arguments: result_type"

- Use `output_type` parameter in Pydantic AI Agent constructor
- Fixed in factory.py

### Low confidence scores

- Unclear system prompt
- Ambiguous user query
- Insufficient context
- Missing relevant tools

### Schema validation errors

- Check `required` fields match `properties`
- Verify type names (`string`, `number`, `boolean`, `array`)
- Use Field constraints (`ge`, `le`, `enum`)

## Next Steps

1. **Create custom agent**: Copy `percolate-test-agent.json`, modify prompt/schema
2. **Add MCP tools**: Implement tools in `percolate/mcp/tools/`, reference in schema
3. **Test thoroughly**: Use `percolate agent-eval` with diverse prompts
4. **Deploy**: System agents are immediately available to all tenants
5. **Iterate**: Version your agents, track performance, refine prompts

## References

- [Pydantic AI Documentation](https://ai.pydantic.dev)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/)
