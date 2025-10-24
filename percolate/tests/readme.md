# Percolate Test Suite

This directory contains all tests for the Percolate project, organized into **unit tests** and **integration tests**.

## Directory Structure

```
tests/
├── README.md              # This file
├── fixtures/              # Shared test fixtures and data
│   ├── agentlets/         # Sample agent schemas
│   └── documents/         # Test documents
├── unit/                  # Unit tests (fast, no external services)
│   ├── agents/            # Agent factory and context tests
│   ├── mcp/               # MCP tool logic tests
│   ├── auth/              # Auth model and crypto tests
│   └── test_imports.py    # Dependency verification
└── integration/           # Integration tests (real connections)
    ├── agents/            # Full agent execution tests
    ├── mcp/               # MCP server protocol tests
    └── auth/              # OAuth flow tests
```

## Test Categories

### Unit Tests (`tests/unit/`)

**Characteristics:**
- No external services (no HTTP server, no database, no file I/O)
- Fast execution (< 1 second per test)
- Minimal mocking (only when absolutely necessary)
- Test pure logic and data transformations

**Examples:**
- Agent context creation
- MCP tool argument validation
- Auth model instantiation
- Pydantic schema validation

**Run unit tests:**
```bash
uv run pytest tests/unit/ -v
```

### Integration Tests (`tests/integration/`)

**Characteristics:**
- Real external connections (HTTP server, database, etc.)
- May be slower (acceptable up to 10 seconds per test)
- Require services to be running
- Test end-to-end workflows

**Examples:**
- MCP server JSON-RPC protocol
- Full agent execution with LLM calls
- OAuth token exchange flows
- Database operations

**Run integration tests:**
```bash
# Start the server first
uv run percolate serve &

# Run integration tests
uv run pytest tests/integration/ -v
```

## Running Tests

### All Tests
```bash
uv run pytest
```

### Unit Tests Only (Fast)
```bash
uv run pytest tests/unit/
```

### Integration Tests Only
```bash
# Requires server running
uv run percolate serve &
uv run pytest tests/integration/
```

### Specific Test File
```bash
uv run pytest tests/unit/mcp/test_tools.py -v
```

### Specific Test Function
```bash
uv run pytest tests/unit/mcp/test_tools.py::test_ask_agent_basic -v
```

### With Coverage
```bash
uv run pytest --cov=percolate --cov-report=html
```

## Writing Tests

### Test Naming Conventions

- **Test files**: `test_*.py` or `*_test.py`
- **Test functions**: `test_*`
- **Test classes**: `Test*`

### Unit Test Example

```python
# tests/unit/mcp/test_tools.py
import pytest
from percolate.mcp.tools.agent import ask_agent

@pytest.mark.asyncio
async def test_ask_agent_basic():
    """Test ask_agent tool with basic arguments."""
    result = await ask_agent(
        agent_uri="test-agent",
        tenant_id="test-tenant",
        prompt="Test prompt",
    )

    assert result["status"] == "success"
    assert "response" in result
```

### Integration Test Example

```python
# tests/integration/mcp/test_mcp_server.py
import httpx
import pytest

@pytest.mark.asyncio
async def test_mcp_list_tools():
    """Test listing MCP tools via HTTP."""
    async with httpx.AsyncClient() as client:
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }

        response = await client.post(
            "http://127.0.0.1:8765/mcp",
            json=request
        )

        assert response.status_code == 200
        result = response.json()
        assert "tools" in result["result"]
```

## Best Practices

### General Principles

1. **Independence**: Each test should be independent and idempotent
2. **Clarity**: Test names should describe what they test
3. **Single Responsibility**: One test should verify one behavior
4. **Error Testing**: Test both success and error paths
5. **Minimal Mocking**: Prefer real implementations over mocks

### Unit Test Guidelines

- No network I/O
- No file system I/O (except reading static fixtures)
- No database connections
- Mock external dependencies sparingly
- Fast execution (< 1s per test)

### Integration Test Guidelines

- Test real end-to-end workflows
- Use actual HTTP connections
- Clean up resources after tests
- Document required services
- Acceptable slower execution (< 10s per test)

### Fixtures

Use pytest fixtures for shared test data:

```python
# tests/fixtures/conftest.py
import pytest

@pytest.fixture
def sample_agent_schema():
    return {
        "fully_qualified_name": "test-agent",
        "version": "1.0.0",
        "description": "Test agent",
        "output_schema": {
            "type": "object",
            "properties": {
                "answer": {"type": "string"}
            }
        }
    }
```

## Continuous Integration

Tests run automatically on:
- Pull request creation
- Push to main branch
- Nightly builds

CI configuration:
```yaml
# .github/workflows/test.yml
- name: Run unit tests
  run: uv run pytest tests/unit/

- name: Run integration tests
  run: |
    uv run percolate serve &
    sleep 5
    uv run pytest tests/integration/
```

## Troubleshooting

### Integration Tests Failing

**Problem**: Connection refused errors

**Solution**: Ensure the server is running:
```bash
uv run percolate serve
```

### Import Errors

**Problem**: Cannot import percolate modules

**Solution**: Install dependencies:
```bash
uv sync
```

### Async Test Warnings

**Problem**: RuntimeWarning about async fixtures

**Solution**: Mark tests with `@pytest.mark.asyncio`:
```python
@pytest.mark.asyncio
async def test_my_async_function():
    ...
```

## References

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [Coverage.py](https://coverage.readthedocs.io/)
- [CLAUDE.md Testing Section](../../CLAUDE.md#testing)
