"""FastMCP server configuration and setup."""

from fastmcp import FastMCP

from percolate.mcp.resources import register_agentlet_resources
from percolate.mcp.tools.search import search_knowledge_base
from percolate.mcp.tools.entity import lookup_entity
from percolate.mcp.tools.parse import parse_document
from percolate.mcp.tools.agent import create_agent, ask_agent


def create_mcp_server() -> FastMCP:
    """Create and configure MCP server with tools and resources.

    Initializes FastMCP server with:
    - Knowledge base search tool
    - Entity lookup tool
    - Document parsing tool
    - Agent creation/execution tools
    - Agent-let schema resources

    Returns:
        Configured FastMCP server instance

    Example:
        >>> mcp = create_mcp_server()
        >>> # Run as standalone: mcp.run()
        >>> # Or mount in FastAPI: app.mount("/mcp", mcp)
    """
    mcp = FastMCP(
        name="Percolate MCP Server",
        version="0.1.0",
        instructions=(
            "MCP server for percolate personal AI node. "
            "Provides access to REM memory (Resources-Entities-Moments), "
            "agent-let execution, and document parsing."
        ),
    )

    # Register tools (imported from separate modules)
    mcp.tool()(search_knowledge_base)
    mcp.tool()(lookup_entity)
    mcp.tool()(parse_document)
    mcp.tool()(create_agent)
    mcp.tool()(ask_agent)

    # Register server info tool inline
    @mcp.tool()
    def about() -> dict[str, str]:
        """Get information about the Percolate MCP server.

        Returns:
            Server metadata including version and capabilities

        Example:
            >>> info = about()
            >>> info["version"]
            '0.1.0'
        """
        return {
            "name": "Percolate MCP Server",
            "version": "0.1.0",
            "capabilities": [
                "knowledge_base_search",
                "entity_lookup",
                "document_parsing",
                "agent_creation",
                "agent_execution",
            ],
        }

    # Register agent-let schemas as resources
    register_agentlet_resources(mcp)

    return mcp
