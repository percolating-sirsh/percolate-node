"""Integration tests for MCP server over StreamableHTTP.

Tests the FastMCP server running with StreamableHTTP protocol.
Requires the server to be running at http://127.0.0.1:8765.

Run server with: uv run percolate serve
"""

import asyncio
import json

import httpx
import pytest


BASE_URL = "http://127.0.0.1:8765"
TIMEOUT = 30.0

# Skip all tests in this module if server is not running
pytestmark = pytest.mark.skip(reason="Requires running server at http://127.0.0.1:8765. Run: uv run percolate serve --port 8765")


@pytest.fixture
def mcp_client():
    """HTTP client for MCP endpoint."""
    return httpx.AsyncClient(timeout=TIMEOUT)


@pytest.mark.asyncio
async def test_mcp_initialize(mcp_client: httpx.AsyncClient):
    """Test MCP session initialization."""
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"},
        },
    }

    response = await mcp_client.post(
        f"{BASE_URL}/mcp",
        json=init_request,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    result = response.json()
    assert "result" in result
    assert result["result"]["protocolVersion"] == "2024-11-05"
    assert "serverInfo" in result["result"]


@pytest.mark.asyncio
async def test_mcp_list_tools(mcp_client: httpx.AsyncClient):
    """Test listing available MCP tools."""
    list_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }

    response = await mcp_client.post(
        f"{BASE_URL}/mcp",
        json=list_request,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    result = response.json()
    assert "result" in result
    assert "tools" in result["result"]

    tools = result["result"]["tools"]
    assert len(tools) > 0

    # Verify expected tools exist
    tool_names = {tool["name"] for tool in tools}
    assert "ask_agent" in tool_names
    assert "search_knowledge_base" in tool_names


@pytest.mark.asyncio
async def test_mcp_call_ask_agent(mcp_client: httpx.AsyncClient):
    """Test calling ask_agent tool via MCP."""
    call_request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "ask_agent",
            "arguments": {
                "agent_uri": "percolate-test-agent",
                "tenant_id": "test-tenant",
                "prompt": "Test MCP integration",
            },
        },
    }

    response = await mcp_client.post(
        f"{BASE_URL}/mcp",
        json=call_request,
        headers={"Content-Type": "application/json"},
        timeout=60.0,
    )

    assert response.status_code == 200
    result = response.json()
    assert "result" in result

    content = result["result"].get("content", [])
    assert len(content) > 0
    assert content[0]["type"] == "text"

    # Parse agent response
    text_content = content[0]["text"]
    agent_result = json.loads(text_content)

    assert agent_result["status"] == "success"
    assert "response" in agent_result
    assert "answer" in agent_result["response"]
    assert "confidence" in agent_result["response"]


@pytest.mark.asyncio
async def test_mcp_list_resources(mcp_client: httpx.AsyncClient):
    """Test listing available MCP resources."""
    list_request = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "resources/list",
        "params": {},
    }

    response = await mcp_client.post(
        f"{BASE_URL}/mcp",
        json=list_request,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    result = response.json()
    assert "result" in result
    assert "resources" in result["result"]

    resources = result["result"]["resources"]
    assert len(resources) > 0

    # Verify resource structure
    for resource in resources:
        assert "uri" in resource
        assert "name" in resource
