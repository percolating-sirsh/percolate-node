"""Agent-let discovery and schema loading."""

from pathlib import Path
from typing import Any
import json


def load_agentlet_schema(uri: str) -> dict[str, Any]:
    """Load agent-let schema by URI.

    Resolves agent-let schema from local filesystem or remote storage.
    Supports both system agents (built-in) and user agents (tenant-scoped).

    URI formats:
    - System: 'researcher' → schema/agentlets/researcher.json
    - User: 'user/{tenant_id}/{name}' → tenant-scoped storage

    Args:
        uri: Agent-let URI identifier

    Returns:
        Agent-let schema as JSON dict

    Raises:
        FileNotFoundError: If schema does not exist

    Example:
        >>> schema = load_agentlet_schema("researcher")
        >>> schema["fully_qualified_name"]
        'percolate.agents.researcher.Researcher'
    """
    # System agent from schema directory
    if not uri.startswith("user/"):
        schema_path = _get_system_agentlet_path(uri)
        if not schema_path.exists():
            raise FileNotFoundError(f"System agent schema not found: {uri}")

        with open(schema_path) as f:
            return json.load(f)

    # User agent from tenant-scoped storage
    # TODO: Implement user agent loading from REM/storage
    raise NotImplementedError("User agent loading not yet implemented")


def list_system_agentlets() -> list[dict[str, Any]]:
    """List all available system agent-let schemas.

    Scans the schema/agentlets directory and returns metadata for all
    system agents. Used for agent discovery via MCP resources or CLI.

    Returns:
        List of agent metadata dicts (short_name, version, description)

    Example:
        >>> agents = list_system_agentlets()
        >>> [a["short_name"] for a in agents]
        ['researcher', 'classifier', 'summarizer']
    """
    agentlets_dir = _get_agentlets_dir()
    agents = []

    for schema_file in agentlets_dir.glob("*.json"):
        with open(schema_file) as f:
            schema = json.load(f)
            agents.append({
                "short_name": schema.get("short_name", schema_file.stem),
                "version": schema.get("version", "1.0.0"),
                "description": schema.get("description", ""),
                "uri": schema_file.stem,
            })

    return agents


def list_user_agentlets(tenant_id: str) -> list[dict[str, Any]]:
    """List agent-lets created by a specific tenant.

    Retrieves all user-created agents for a tenant from storage.
    Used for per-user agent management and discovery.

    Args:
        tenant_id: Tenant identifier for scoping

    Returns:
        List of user agent metadata dicts

    Example:
        >>> agents = list_user_agentlets("tenant-123")
        >>> [a["short_name"] for a in agents]
        ['my-custom-agent', 'team-classifier']
    """
    # TODO: Implement user agent listing from REM/storage
    raise NotImplementedError("User agent listing not yet implemented")


def _get_agentlets_dir() -> Path:
    """Get path to system agent-let schemas directory."""
    # Relative to percolate package (src/percolate/schema/agentlets)
    return Path(__file__).parent.parent / "schema" / "agentlets"


def _get_system_agentlet_path(uri: str) -> Path:
    """Get filesystem path for system agent-let schema."""
    return _get_agentlets_dir() / f"{uri}.json"
