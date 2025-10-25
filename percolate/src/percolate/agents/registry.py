"""Agent-let discovery and schema loading.

Agent-lets are stored as entities in percolate-rocks database with embeddings
for similarity search. System agents are loaded from filesystem, user agents
from database with tenant isolation.
"""

from pathlib import Path
from typing import Any
import json

# TODO: Import percolate-rocks package once available
# from percolate_rocks import Database


def load_agentlet_schema(uri: str, tenant_id: str = "default") -> dict[str, Any]:
    """Load agent-let schema by URI from percolate-rocks or filesystem.

    URI formats:
    - System: 'researcher' → schema/agentlets/researcher.json
    - System: 'system/classifier' → schema/agentlets/classifier.json
    - User: 'user/{tenant_id}/{name}' → percolate-rocks entity lookup

    Priority:
    1. Try percolate-rocks database entity lookup (future)
    2. Fall back to filesystem for system schemas
    3. Raise error if not found

    Database configuration is handled by percolate-rocks package settings/env vars.
    Default location: ~/.p8/db/

    Args:
        uri: Agent-let schema URI
        tenant_id: Tenant scope for user agent-lets (isolated in percolate-rocks)

    Returns:
        Agent-let schema as dict

    Raises:
        FileNotFoundError: If schema not found in database or filesystem
        PermissionError: If trying to access another tenant's agents

    Example:
        >>> schema = load_agentlet_schema("researcher")
        >>> schema["fully_qualified_name"]
        'percolate.agents.researcher.Researcher'

        >>> schema = load_agentlet_schema("user/tenant-123/custom-agent", tenant_id="tenant-123")
    """
    # User agent from percolate-rocks database
    if uri.startswith("user/"):
        return _load_user_agentlet(uri, tenant_id)

    # System agent from filesystem (with DB cache future optimization)
    return _load_system_agentlet(uri)


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

    Retrieves all user-created agents for a tenant from percolate-rocks.
    Agent-lets are stored as regular entities with category='agent' (TBD).

    Args:
        tenant_id: Tenant identifier for scoping

    Returns:
        List of user agent metadata dicts

    Example:
        >>> agents = list_user_agentlets("tenant-123")
        >>> [a["short_name"] for a in agents]
        ['my-custom-agent', 'team-classifier']
    """
    # TODO: Implement percolate-rocks database query
    # Agent-lets are stored as entities with category='agent' (TBD)
    # db = Database()  # Uses settings/env for db location
    # results = db.search(
    #     query="",  # Empty query returns all
    #     filters={"tenant_id": tenant_id, "category": "agent"},
    #     limit=1000
    # )
    # return results

    raise NotImplementedError(
        f"User agent listing not yet implemented\n"
        f"TODO: Query percolate-rocks for tenant '{tenant_id}' agent entities"
    )


def _load_user_agentlet(uri: str, tenant_id: str) -> dict[str, Any]:
    """Load user-scoped agent-let from percolate-rocks database.

    User agent-lets are stored as regular entities with:
    - schema: User defines schema name when creating (e.g., 'my-agent-schema')
    - category: 'agent' (TBD - for filtering/discovery)
    - Tenant isolation: Entity stored under tenant's namespace
    - Embeddings: description field for agent similarity search

    Args:
        uri: User agent URI (e.g., 'user/tenant-123/my-agent')
        tenant_id: Tenant identifier for isolation

    Returns:
        Agent-let entity as dict (contains the full agent schema)

    Raises:
        FileNotFoundError: If agent not found for this tenant
        PermissionError: If tenant mismatch
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

    # TODO: Replace with percolate-rocks entity search
    # db = Database()  # Uses settings/env for db location
    # Build entity key from URI
    # entity_key = f"user.{tenant_id}.{agent_name}"
    #
    # Search for entity by key or short_name
    # results = db.search(
    #     schema_name="*",  # Search across all schemas
    #     query="",  # No semantic query, just filter
    #     filters={
    #         "category": "agent",
    #         "short_name": agent_name
    #     },
    #     limit=1
    # )
    #
    # if not results:
    #     raise FileNotFoundError(f"Agent-let not found: {uri}")
    #
    # return results[0]  # Return the entity as dict

    raise FileNotFoundError(
        f"User agent-let not found: {uri}\n"
        f"TODO: Implement percolate-rocks entity search:\n"
        f"  - Search across schemas with category='agent'\n"
        f"  - Filter by short_name='{agent_name}'\n"
        f"  - Tenant: {tenant_id}"
    )


def _load_system_agentlet(uri: str) -> dict[str, Any]:
    """Load system agent-let from filesystem.

    System agent-lets are shipped with percolate in schema/agentlets/.
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


def _get_agentlets_dir() -> Path:
    """Get path to system agent-let schemas directory."""
    # Relative to percolate package (src/percolate/schema/agentlets)
    return Path(__file__).parent.parent / "schema" / "agentlets"


def _get_system_agentlet_path(uri: str) -> Path:
    """Get filesystem path for system agent-let schema."""
    return _get_agentlets_dir() / f"{uri}.json"
