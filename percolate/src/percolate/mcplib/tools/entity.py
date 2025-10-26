"""Entity lookup MCP tool."""

from typing import Any
from loguru import logger

from percolate.memory import get_database


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
    db = get_database()

    if not db:
        raise RuntimeError("REM database unavailable (percolate-rocks not installed or not working)")

    try:
        # Note: rem get is not implemented in v0.2.0
        # When ready: entity = db.get(entity_id)
        logger.debug(f"Entity lookup not yet implemented - entity_id: {entity_id}")

        raise NotImplementedError(
            "Entity lookup not yet implemented in percolate-rocks v0.2.0 (rem get is TODO)"
        )

    except NotImplementedError:
        raise
    except Exception as e:
        logger.error(f"Entity lookup failed: {e}")
        raise RuntimeError(f"Failed to lookup entity {entity_id}: {e}")
