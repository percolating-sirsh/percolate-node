# Testing

## Table of Contents

- [Test Organization](#test-organization)
- [Unit Tests](#unit-tests)
- [Integration Tests](#integration-tests)
- [Running Tests](#running-tests)
- [Best Practices](#best-practices)

## Test Organization

All tests must be in the `tests/` directory with proper organization.

### Python Tests (pytest)

```
percolate/tests/
├── fixtures/             # Shared test fixtures and data
│   ├── agentlets/        # Sample agent schemas
│   └── documents/        # Test documents
├── unit/                 # Unit tests - no external services
│   ├── agents/           # Agent factory, context tests
│   ├── mcp/              # MCP tool logic tests
│   │   └── test_tools.py
│   ├── auth/             # Auth model and crypto tests
│   ├── test_imports.py   # Dependency verification
│   └── __init__.py
└── integration/          # Integration tests - real connections
    ├── agents/           # Full agent execution tests
    │   └── test_agent_eval.py
    ├── mcp/              # MCP server protocol tests
    │   │   └── test_mcp_server.py
    ├── auth/             # OAuth flow tests
    └── __init__.py
```

### Rust Tests (cargo test)

```
percolate-core/
├── src/
│   └── memory/
│       ├── mod.rs
│       └── tests.rs   # Unit tests alongside implementation
└── tests/
    └── integration/   # Integration tests
        └── memory_test.rs
```

## Unit Tests

**Definition**: Tests with no external services (no HTTP, no database).

**Characteristics:**
- Fast execution (< 1s per test)
- Mock external dependencies minimally
- Test pure logic and data transformations
- No network calls
- No database connections

**Examples:**

```python
# tests/unit/agents/test_factory.py
import pytest
from percolate.agents.factory import create_agent_from_schema

def test_create_agent_validates_schema():
    """Factory validates agent schema structure"""
    invalid_schema = {"foo": "bar"}

    with pytest.raises(ValueError, match="Missing required field"):
        create_agent_from_schema(invalid_schema)

def test_create_agent_extracts_tools():
    """Factory extracts tool references from schema"""
    schema = {
        "fully_qualified_name": "test-agent",
        "version": "1.0.0",
        "tools": [{"mcp_server": "percolate", "tool_name": "search"}]
    }

    agent = create_agent_from_schema(schema)

    assert len(agent.tools) == 1
    assert agent.tools[0].name == "search"
```

## Integration Tests

**Definition**: Tests with real external connections (HTTP server, database).

**Characteristics:**
- May be slower (acceptable up to 10s per test)
- Require services to be running
- Test end-to-end workflows
- Real network calls
- Real database connections

**Examples:**

```python
# tests/integration/agents/test_agent_eval.py
import pytest
from percolate.agents.factory import create_pydantic_ai_agent
from percolate.agents.context import ExecutionContext

@pytest.mark.asyncio
async def test_agent_executes_with_real_llm():
    """Agent executes with real LLM API calls"""
    context = ExecutionContext(
        tenant_id="test",
        session_id="test-session"
    )

    agent = await create_pydantic_ai_agent(
        context=context,
        result_type=MyAgent
    )

    result = await agent.run("Test prompt")

    assert result.output is not None
    assert result.trace_id is not None
```

## Running Tests

### Unit Tests Only (Fast)

```bash
# No server needed
uv run pytest tests/unit/
```

### Integration Tests

```bash
# Start server first
uv run percolate serve &

# Run integration tests
uv run pytest tests/integration/

# Stop server
killall percolate
```

### All Tests

```bash
uv run pytest
```

### With Coverage

```bash
uv run pytest --cov=percolate --cov-report=html
```

### Watch Mode

```bash
uv run pytest-watch tests/unit/
```

## Best Practices

### Test Organization Rules

1. **Never put test files in project root** - always in `tests/` directory
2. **Separate unit from integration** - different execution requirements
3. **Use fixtures for shared setup** - reduce duplication
4. **Test error paths explicitly** - not just happy paths
5. **Each test should be independent** - no shared state

### Naming Conventions

| Type | Convention | Example |
|------|-----------|---------|
| **Test files** | `test_*.py` or `*_test.py` | `test_factory.py` |
| **Test functions** | `test_*` | `test_create_agent_validates_schema` |
| **Test classes** | `Test*` | `TestAgentFactory` |

### Test Structure

```python
def test_function_does_something():
    """Docstring explaining what is being tested"""
    # Arrange - set up test data
    schema = {"foo": "bar"}

    # Act - execute the function
    result = function_under_test(schema)

    # Assert - verify the outcome
    assert result.foo == "bar"
```

### Mocking Guidelines

**Python:**
- Mock only when absolutely necessary
- Prefer dependency injection over mocking
- Use pytest fixtures for test data
- Mock external APIs, not internal logic

**Rust:**
- Use test doubles for external I/O
- Prefer trait-based dependency injection
- Use mock traits for external services

### Property-Based Testing

For complex logic, use property-based testing:

**Python:**
```python
from hypothesis import given, strategies as st

@given(st.text(), st.integers(min_value=0))
def test_function_with_any_input(text, number):
    result = function_under_test(text, number)
    assert isinstance(result, str)
```

**Rust:**
```rust
use proptest::prelude::*;

proptest! {
    #[test]
    fn test_function_with_any_input(s in "\\PC*", n in 0..1000) {
        let result = function_under_test(&s, n);
        assert!(result.is_ok());
    }
}
```

### Test Independence

Each test should be independent and idempotent:

- No shared mutable state between tests
- Clean up resources after each test
- Use pytest fixtures with `autouse=False`
- Avoid test execution order dependencies
