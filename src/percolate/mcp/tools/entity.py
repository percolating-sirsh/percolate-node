"""Entity lookup MCP tool."""

from typing import Any


async def lookup_entity(
    entity_id: str,
    tenant_id: str,
    include_relationships: bool = True,
    depth: int = 1,
) -> dict[str, Any]:
    """Look up entity by ID with optional relationship traversal.

    Retrieves entity from REM memory graph, optionally including
    connected entities up to a specified depth.

    Args:
        entity_id: Entity identifier
        tenant_id: Tenant identifier for data scoping
        include_relationships: Whether to include related entities
        depth: Relationship traversal depth (1-3)

    Returns:
        Entity data with properties and optional relationships

    Example:
        >>> entity = await lookup_entity(
        ...     entity_id="person-alice",
        ...     tenant_id="tenant-123",
        ...     depth=2
        ... )
        >>> entity["properties"]["name"]
        'Alice'
    """
    # TODO: Implement entity lookup via REM memory engine
    raise NotImplementedError("Entity lookup not yet implemented")
