# Agent-lets: Trainable AI Skills

## Overview

**Agent-lets** are trainable AI skills defined as JSON schemas (not code). They represent portable, versionable, evaluable units of intelligence that can be:
- Shared across users
- Evaluated against test suites
- Continuously improved through feedback
- Composed with other agent-lets

## Philosophy

### Agents Are Data, Not Code

Traditional approach:
```python
# Hardcoded agent - difficult to version, share, evaluate
class MyAgent:
    def run(self, input: str) -> str:
        # Business logic mixed with execution
        ...
```

Agent-let approach:
```json
{
  "fully_qualified_name": "percolate-agents-researcher",
  "version": "1.0.0",
  "system_prompt": "You are a research assistant...",
  "output_schema": { "type": "object", ... },
  "tools": [...]
}
```

**Benefits:**
- **Versioning**: Semantic versioning for agent capabilities
- **Sharing**: JSON files can be distributed, imported
- **Evaluation**: Test suites validate behavior objectively
- **Iteration**: Modify prompts/tools without code changes
- **Composition**: Agents can call other agents via MCP

## Agent-let Schema

### Core Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `fully_qualified_name` | string | Yes | Unique identifier (e.g., `percolate-agents-researcher`) |
| `short_name` | string | Yes | Human-friendly name (e.g., `researcher`) |
| `version` | string | Yes | Semantic version (e.g., `1.0.0`) |
| `description` | string | Yes | What the agent does |
| `system_prompt` | string | Yes | Instructions for LLM |
| `output_schema` | object | Yes | JSON schema for structured outputs |
| `tools` | array | No | MCP tools the agent can call |
| `metadata` | object | No | Additional metadata (author, tags, etc.) |

### Example: Research Agent

```json
{
  "fully_qualified_name": "percolate-agents-researcher",
  "short_name": "researcher",
  "version": "1.0.0",
  "description": "Research agent that searches REM memory and synthesizes findings",
  "system_prompt": "You are a research assistant with access to the user's personal knowledge base. When asked a question:\n1. Search REM memory for relevant information\n2. Follow entity relationships to discover related context\n3. Synthesize findings into a clear, well-cited answer\n4. Include source references for all claims",
  "output_schema": {
    "type": "object",
    "properties": {
      "answer": {
        "type": "string",
        "description": "Synthesized answer to the user's question"
      },
      "sources": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "resource_id": {"type": "string"},
            "excerpt": {"type": "string"},
            "relevance_score": {"type": "number"}
          }
        },
        "description": "Sources used to construct the answer"
      },
      "confidence": {
        "type": "number",
        "minimum": 0,
        "maximum": 1,
        "description": "Confidence in the answer (0-1)"
      },
      "related_entities": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Entity IDs discovered during research"
      }
    },
    "required": ["answer", "sources", "confidence"]
  },
  "tools": [
    {
      "mcp_server": "percolate",
      "tool_name": "search_knowledge_base",
      "usage": "Search REM memory for relevant resources and entities"
    },
    {
      "mcp_server": "percolate",
      "tool_name": "lookup_entity",
      "usage": "Get details about a specific entity and its relationships"
    }
  ],
  "metadata": {
    "author": "percolate-team",
    "tags": ["research", "knowledge-base", "synthesis"],
    "license": "MIT",
    "created_at": "2025-01-15T00:00:00Z"
  }
}
```

## Factory Pattern

### Agent Creation

Python factory creates Pydantic AI agents from JSON schemas:

```python
from pydantic_ai import Agent
from percolate.agents.factory import create_agent_from_schema

# Load schema
with open("schema/agentlets/researcher.json") as f:
    schema = json.load(f)

# Create agent
agent = create_agent_from_schema(schema, context={"tenant_id": "user-123"})

# Run agent
result = await agent.run("What did we discuss about pricing?")
print(result.data.answer)
print(result.data.sources)
```

### Factory Implementation

```python
async def create_agent_from_schema(
    schema: AgentletSchema,
    context: dict,
    model: str = "claude-sonnet-4.5"
) -> Agent:
    """Create Pydantic AI agent from JSON schema."""

    # Extract components
    system_prompt = schema["system_prompt"]
    output_schema = schema["output_schema"]
    tools = schema.get("tools", [])

    # Create Pydantic model from JSON schema
    OutputModel = create_pydantic_model(output_schema)

    # Initialize agent
    agent = Agent(
        model=model,
        system_prompt=system_prompt,
        result_type=OutputModel
    )

    # Attach MCP tools
    for tool_config in tools:
        tool = await get_mcp_tool(
            server=tool_config["mcp_server"],
            tool_name=tool_config["tool_name"]
        )
        agent.tool(tool)

    # Add OTEL instrumentation
    instrument_agent(agent, schema["fully_qualified_name"])

    return agent
```

## MCP Tool Integration

### Tool Configuration

Agent-lets reference MCP tools by server + tool name:

```json
{
  "tools": [
    {
      "mcp_server": "percolate",
      "tool_name": "search_knowledge_base",
      "usage": "Search REM memory for information"
    }
  ]
}
```

### Tool Resolution

At runtime, factory resolves tools from environment:

```bash
# Environment variables define MCP servers
export MCP_SERVER_PERCOLATE="http://localhost:8000/mcp"
export MCP_SERVER_GITHUB="stdio://mcp-github"
```

Factory connects to MCP servers and attaches tools to agent.

### Dynamic Tool Discovery

Agent-lets can discover available tools at runtime:

```python
# List available tools
tools = await mcp_client.list_tools(server="percolate")

# Agent selects appropriate tools based on task
relevant_tools = filter_tools_by_task(tools, task="research")
```

## Evaluation Framework

### Test Suites

Agent-lets are evaluated against test suites:

```json
{
  "agentlet": "percolate-agents-researcher",
  "version": "1.0.0",
  "test_cases": [
    {
      "id": "test-001",
      "difficulty": "easy",
      "input": "What was our Q4 revenue?",
      "ground_truth": {
        "answer": "$4.2M",
        "sources": ["earnings-report.pdf"]
      },
      "evaluation_criteria": {
        "answer_correctness": 1.0,
        "source_accuracy": 1.0,
        "relevance": 1.0
      }
    }
  ]
}
```

### Evaluation Metrics

| Metric | Description | Calculation |
|--------|-------------|-------------|
| **Answer Correctness** | Semantic similarity to ground truth | LLM-based scoring (0-1) |
| **Source Accuracy** | Are cited sources relevant? | Precision@k of sources |
| **Efficiency** | Cost per query | Token count × cost per token |
| **Latency** | Response time | p50, p95, p99 latencies |
| **Tool Usage** | Are tools used appropriately? | Precision/recall of tool calls |

### Evaluation Run

```python
from percolate.agents.eval import run_evaluation

# Run evaluation suite
results = await run_evaluation(
    agentlet="percolate-agents-researcher",
    test_suite="research-eval-v1",
    model="claude-sonnet-4.5"
)

# Results
print(f"Answer Correctness: {results.answer_correctness:.2f}")
print(f"Source Accuracy: {results.source_accuracy:.2f}")
print(f"Avg Cost: ${results.avg_cost:.4f}")
print(f"P95 Latency: {results.p95_latency:.0f}ms")
```

## Feedback Loop

### User Feedback

Users provide feedback on agent responses:

```python
from percolate.mcp.tools.feedback import submit_feedback

# User provides feedback
await submit_feedback(
    agent="percolate-agents-researcher",
    run_id="run-abc123",
    rating=4,  # 1-5 stars
    comment="Good answer, but missed one source",
    corrections={
        "missing_sources": ["strategy-doc.pdf"]
    }
)
```

### Feedback Analysis

Feedback collected via OpenTelemetry and analyzed:

- Low-rated responses flagged for review
- Common failure patterns identified
- Test suite updated with new cases
- Agent prompts refined based on patterns

### Continuous Improvement

```
User feedback → OTEL traces → Phoenix analysis
  → Identify failure patterns
    → Generate new test cases
      → Update agent prompt/tools
        → Re-run evaluation suite
          → Deploy improved agent
```

## Agent Registry

### Local Registry

Agent-lets stored in `schema/agentlets/`:

```
schema/
└── agentlets/
    ├── researcher.json
    ├── summarizer.json
    ├── task-planner.json
    └── code-reviewer.json
```

### Discovery

```python
from percolate.agents.registry import list_agents, load_agent

# List available agents
agents = list_agents()
for agent in agents:
    print(f"{agent.short_name} v{agent.version} - {agent.description}")

# Load specific agent
schema = load_agent("researcher", version="1.0.0")
```

### Versioning

Agent-lets use semantic versioning:
- **Major**: Breaking changes to output schema or behavior
- **Minor**: New capabilities (e.g., new tools)
- **Patch**: Bug fixes, prompt refinements

## Composition Patterns

### Agent Calling Agent

Agent-let A can call agent-let B via MCP:

```json
{
  "fully_qualified_name": "percolate-agents-meta-researcher",
  "tools": [
    {
      "mcp_server": "percolate",
      "tool_name": "run_agent",
      "usage": "Run another agent-let for specialized tasks"
    }
  ]
}
```

Example flow:
```
Meta-Researcher receives complex query
  → Breaks into sub-questions
    → Calls Researcher agent for each sub-question
      → Synthesizes sub-answers into final answer
```

### Pipeline Pattern

Sequential agent execution:

```
Document Ingestion
  → Parser Agent (extract structure)
    → Entity Extractor Agent (identify entities)
      → Relationship Mapper Agent (create edges)
        → Store in REM
```

### Hierarchical Pattern

Manager agent delegates to specialist agents:

```
Task Planner (manager)
  ├── Research Agent (specialist)
  ├── Code Generator Agent (specialist)
  └── Reviewer Agent (specialist)
```

## Deployment

### Loading Agent-lets

```bash
# Load agent-let from file
percolate agent load schema/agentlets/researcher.json

# Load from URL
percolate agent load https://percolate.dev/agents/researcher-v1.json

# List loaded agents
percolate agent list
```

### Running Agent-lets

```bash
# Run via CLI
percolate agent run researcher "What was our Q4 revenue?"

# Run via API
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "percolate-agents-researcher",
    "messages": [{"role": "user", "content": "What was our Q4 revenue?"}]
  }'

# Run via MCP
# MCP clients can discover and call agents as tools
```

## Best Practices

### System Prompts

- **Specific**: Clearly define role and capabilities
- **Structured**: Use numbered steps for procedures
- **Examples**: Include few-shot examples when helpful
- **Constraints**: Specify what the agent should NOT do
- **Citations**: Always require source references

### Output Schemas

- **Explicit**: Define all expected fields
- **Typed**: Use appropriate JSON schema types
- **Descriptions**: Document each field's purpose
- **Required**: Mark required vs. optional fields
- **Validated**: Pydantic validates structure at runtime

### Tool Usage

- **Minimal**: Only include tools the agent needs
- **Documented**: Provide clear usage instructions
- **Fallback**: Handle tool failures gracefully
- **Efficient**: Batch tool calls when possible

### Evaluation

- **Comprehensive**: Cover happy path and edge cases
- **Realistic**: Use real-world examples
- **Difficulty levels**: Easy, medium, hard, adversarial
- **Automated**: Run on every agent update
- **Tracked**: Store results for comparison over time

## Future Enhancements

### Phase 1 (Current)
- JSON schema definition
- Pydantic AI factory
- Basic evaluation framework
- MCP tool integration

### Phase 2
- Agent marketplace (share/discover agents)
- Automatic prompt optimization (DSPy-style)
- Multi-modal agents (text + image + audio)
- Agent composition UI

### Phase 3
- Federated agents (run across multiple nodes)
- Differential privacy for shared agents
- Automatic test case generation
- Agent monitoring dashboard

### Phase 4
- Self-improving agents (reinforcement learning)
- Agent collaboration protocols
- Cross-platform agent execution
- Agent capability certificates (verified skills)

## References

- Pydantic AI: https://ai.pydantic.dev
- JSON Schema: https://json-schema.org
- Model Context Protocol: https://modelcontextprotocol.io
- DSPy: https://github.com/stanfordnlp/dspy
- Phoenix Arize: https://docs.arize.com/phoenix
