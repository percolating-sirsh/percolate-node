"""MCP resources for agent-let schema discovery."""

import json
from pathlib import Path
from fastmcp import FastMCP


def register_agentlet_resources(mcp: FastMCP) -> None:
    """Register agent-let schemas as MCP resources.

    Scans the schema/agentlets directory and registers each schema as
    an MCP resource for discovery by clients. Resources use the URI
    format: agentlet://{short_name}

    Args:
        mcp: FastMCP server instance to register resources with

    Example:
        >>> mcp = FastMCP(...)
        >>> register_agentlet_resources(mcp)
        >>> # Resources now available at:
        >>> # - agentlet://researcher
        >>> # - agentlet://classifier
    """
    agentlets_dir = _get_agentlets_dir()

    if not agentlets_dir.exists():
        # No schemas available yet
        return

    for schema_file in agentlets_dir.glob("*.json"):
        uri = f"agentlet://{schema_file.stem}"

        # Load schema once at registration time
        with open(schema_file) as f:
            schema = json.load(f)

        # Register as MCP resource using closure over schema
        @mcp.resource(uri)
        def get_agentlet(uri=uri, schema=schema) -> str:
            """Get agent-let schema definition.

            Returns:
                JSON-formatted agent-let schema
            """
            return json.dumps(schema, indent=2)


def register_user_agentlets_resource(mcp: FastMCP, tenant_id: str) -> None:
    """Register user agent-let list resource for tenant.

    Provides a resource listing all agent-lets created by a specific
    tenant. Used for dynamic agent discovery in user-scoped contexts.

    Args:
        mcp: FastMCP server instance
        tenant_id: Tenant identifier for scoping

    Example:
        >>> register_user_agentlets_resource(mcp, "tenant-123")
        >>> # Resource: user-agentlets://tenant-123
    """
    uri = f"user-agentlets://{tenant_id}"

    @mcp.resource(uri)
    def get_user_agentlets() -> str:
        """List user-created agent-lets for tenant.

        Returns:
            JSON list of user agent metadata
        """
        # TODO: Implement user agent listing from storage
        return json.dumps([])


def _get_agentlets_dir() -> Path:
    """Get path to system agent-let schemas directory."""
    return Path(__file__).parent.parent.parent.parent.parent / "schema" / "agentlets"
