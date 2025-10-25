"""Agent-let schema loading and discovery from percolate-rocks database.

This module provides schema registry functionality with percolate-rocks integration.
Agent-let schemas are stored as entities in the REM database with embeddings for
similarity search and discovery.

Key features:
- Load schemas from percolate-rocks database by URI
- Fallback to filesystem for system agent-lets
- Support for user-scoped agent-lets (tenant isolation)
- Agent similarity search via embeddings
"""

import json
from pathlib import Path
from typing import Any

# TODO: Import percolate-rocks database once Python bindings are ready
# from rem_db import Database


def load_agentlet_schema(uri: str, tenant_id: str = "default", db_path: str | None = None) -> dict[str, Any]:
    """Load agent-let schema by URI from percolate-rocks or filesystem.

    URI formats:
    - System: 'researcher' → schema/agentlets/researcher.json
    - System: 'system/classifier' → schema/agentlets/classifier.json
    - User: 'user/{tenant_id}/{name}' → percolate-rocks entity lookup

    Priority:
    1. Try percolate-rocks database entity lookup
    2. Fall back to filesystem for system schemas
    3. Raise error if not found

    Args:
        uri: Agent-let schema URI
        tenant_id: Tenant scope for user agent-lets (isolated in percolate-rocks)
        db_path: Path to percolate-rocks database (None = default ~/.p8/db/)

    Returns:
        Agent-let schema as dict

    Raises:
        FileNotFoundError: If schema not found in database or filesystem

    Example:
        >>> schema = load_agentlet_schema("researcher")
        >>> schema["description"]
        "You are a research assistant..."

        >>> schema = load_agentlet_schema("user/tenant-123/custom-agent", tenant_id="tenant-123")
    """
    # Parse URI to determine type
    if uri.startswith("user/"):
        # User-scoped agent-let in percolate-rocks
        return _load_user_agentlet(uri, tenant_id, db_path)
    else:
        # System agent-let from filesystem (with DB cache future optimization)
        return _load_system_agentlet(uri)


def _load_user_agentlet(uri: str, tenant_id: str, db_path: str | None) -> dict[str, Any]:
    """Load user-scoped agent-let from percolate-rocks database.

    User agent-lets are stored as entities with:
    - Schema: agentlet (registered in percolate-rocks)
    - Key field: fully_qualified_name (e.g., user.tenant-123.my-agent)
    - Tenant isolation: tenant_id column for WHERE queries
    - Embeddings: description field for agent similarity search

    Args:
        uri: User agent URI (e.g., 'user/tenant-123/my-agent')
        tenant_id: Tenant identifier for isolation
        db_path: Path to percolate-rocks database

    Returns:
        Agent-let schema dict

    Raises:
        FileNotFoundError: If agent not found for this tenant
    """
    # Parse user URI: user/{tenant_id}/{agent_name}
    parts = uri.split("/")
    if len(parts) != 3:
        raise ValueError(f"Invalid user agent URI: {uri}. Expected: user/{{tenant_id}}/{{agent_name}}")

    uri_tenant = parts[1]
    agent_name = parts[2]

    # Validate tenant isolation
    if uri_tenant != tenant_id:
        raise PermissionError(f"Tenant mismatch: URI tenant '{uri_tenant}' != context tenant '{tenant_id}'")

    # TODO: Replace with percolate-rocks database query once bindings are ready
    # db = Database(db_path or "~/.p8/db/")
    # result = db.query(
    #     """
    #     SELECT * FROM agentlet
    #     WHERE tenant_id = ? AND short_name = ?
    #     """,
    #     params=[tenant_id, agent_name]
    # )
    # if not result:
    #     raise FileNotFoundError(f"Agent-let not found: {uri}")
    # return result[0]

    # PLACEHOLDER: Simulate DB query result
    raise FileNotFoundError(
        f"User agent-let not found: {uri}\n"
        f"TODO: Implement percolate-rocks entity lookup:\n"
        f"  - Schema: agentlet\n"
        f"  - WHERE: tenant_id = '{tenant_id}' AND short_name = '{agent_name}'\n"
        f"  - DB path: {db_path or '~/.p8/db/'}"
    )


def _load_system_agentlet(uri: str) -> dict[str, Any]:
    """Load system agent-let from filesystem.

    System agent-lets are shipped with percolate-rocks in schema/agentlets/.
    These are available to all tenants and serve as templates.

    Future optimization: Cache in percolate-rocks for faster lookups.

    Args:
        uri: System agent URI (e.g., 'researcher', 'system/classifier')

    Returns:
        Agent-let schema dict

    Raises:
        FileNotFoundError: If schema file not found
    """
    # Remove 'system/' prefix if present
    if uri.startswith("system/"):
        uri = uri[7:]

    # Construct path to schema file
    schema_path = _get_system_agentlet_path(uri)

    if not schema_path.exists():
        raise FileNotFoundError(f"System agent-let not found: {uri} (path: {schema_path})")

    # Load and return schema
    with open(schema_path) as f:
        return json.load(f)


def _get_system_agentlet_path(uri: str) -> Path:
    """Get filesystem path for system agent-let schema.

    Args:
        uri: System agent URI (e.g., 'researcher')

    Returns:
        Path to schema JSON file
    """
    # Find schema directory relative to this file
    # src/agents/registry.py → schema/agentlets/{uri}.json
    current_file = Path(__file__)
    project_root = current_file.parent.parent.parent  # Up 3 levels
    schema_dir = project_root / "schema" / "agentlets"

    # Normalize URI to filename
    filename = f"{uri}.json"
    return schema_dir / filename


# TODO: Add agent discovery functions once percolate-rocks bindings are ready
#
# def list_agentlets(tenant_id: str, db_path: str | None = None) -> list[dict[str, Any]]:
#     """List all agent-lets available to this tenant (system + user)."""
#     pass
#
# def search_agentlets(query: str, tenant_id: str, limit: int = 10, db_path: str | None = None) -> list[dict[str, Any]]:
#     """Semantic search for agent-lets using embeddings."""
#     pass
