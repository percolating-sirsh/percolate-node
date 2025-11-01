"""Entity lookup MCP tool."""

from typing import Any
from loguru import logger

from percolate.memory import get_database


async def lookup_entity(
    entity_id: str,
    tenant_id: str,
    include_relationships: bool = False,
    depth: int = 1,
) -> dict[str, Any]:
    """Look up entity by ID or by schema:key format.

    Retrieves entity from REM memory. Supports two lookup modes:
    1. UUID lookup: Direct entity fetch by UUID
    2. Key lookup: Fetch by schema and key field (format: "schema:key_value")

    Args:
        entity_id: Entity identifier in one of two formats:
                  - UUID string: "550e8400-e29b-41d4-a716-446655440000"
                  - Schema:key format: "product:PP-1001-SM" or "customer:CUST-1001"
        tenant_id: Tenant identifier for data scoping
        include_relationships: Whether to include related entities (default: False).
                              Currently not implemented - reserved for future graph traversal.
        depth: Relationship traversal depth 1-3 (default: 1).
              Currently not implemented - reserved for future graph traversal.

    Returns:
        Dictionary with:
        - entity: Full entity data if found
        - entity_id: Echo of the entity_id requested
        - found: Boolean indicating if entity was found
        - lookup_mode: "uuid" or "key" depending on input format
        - error: Error message if lookup failed (optional)

    Examples:
        >>> # UUID lookup
        >>> result = await lookup_entity(
        ...     entity_id="550e8400-e29b-41d4-a716-446655440000",
        ...     tenant_id="percolating-plants"
        ... )
        >>> result["entity"]["properties"]["name"]
        'Monstera Deliciosa'

        >>> # Key lookup (schema:key_value format)
        >>> result = await lookup_entity(
        ...     entity_id="product:PP-1001-SM",
        ...     tenant_id="percolating-plants"
        ... )
        >>> result["entity"]["properties"]["product_code"]
        'PP-1001-SM'

    Notes:
        - UUID lookup is fastest (single RocksDB get)
        - Key lookup requires schema name and uses key index
        - Returns found=False if entity doesn't exist (not an error)
        - Raises RuntimeError only for database/system errors
        - include_relationships and depth are reserved for future implementation
    """
    db = get_database(tenant_id=tenant_id)

    if not db:
        raise RuntimeError(
            "REM database unavailable (percolate-rocks not installed or initialized)"
        )

    try:
        # Detect lookup mode: UUID vs schema:key format
        if ":" in entity_id and not _is_uuid(entity_id):
            # Key lookup mode: "schema:key_value"
            parts = entity_id.split(":", 1)
            if len(parts) != 2:
                return {
                    "entity_id": entity_id,
                    "found": False,
                    "error": f"Invalid entity_id format. Expected 'schema:key_value' or UUID, got: {entity_id}",
                }

            schema, key_value = parts
            lookup_mode = "key"

            # Call Rust key lookup (uses key index)
            # Returns list of entities (usually 0 or 1)
            entities = db.lookup(table=schema, key_value=key_value)

            if not entities:
                logger.debug(f"Entity not found for {schema}:{key_value}")
                return {
                    "entity_id": entity_id,
                    "found": False,
                    "lookup_mode": lookup_mode,
                }

            # Return first match (key fields should be unique)
            entity_dict = entities[0]

        else:
            # UUID lookup mode: Direct fetch
            lookup_mode = "uuid"

            try:
                # Call Rust UUID lookup (fastest path)
                # May raise exception if entity_id is not valid UUID format
                entity_dict = db.get(entity_id=entity_id)
            except (ValueError, RuntimeError) as e:
                # Invalid UUID format - return not found gracefully
                error_msg = str(e).lower()
                if "invalid" in error_msg or "uuid" in error_msg:
                    logger.debug(f"Invalid UUID format: {entity_id}")
                    return {
                        "entity_id": entity_id,
                        "found": False,
                        "lookup_mode": lookup_mode,
                        "error": f"Invalid UUID format: {entity_id}",
                    }
                # Other runtime errors should propagate
                raise

            if entity_dict is None:
                logger.debug(f"Entity not found for UUID: {entity_id}")
                return {
                    "entity_id": entity_id,
                    "found": False,
                    "lookup_mode": lookup_mode,
                }

        # Success - entity found
        result = {
            "entity": entity_dict,
            "entity_id": entity_id,
            "found": True,
            "lookup_mode": lookup_mode,
        }

        # TODO: Add relationship traversal if include_relationships=True
        # Could use db.traverse(start_id=entity_uuid, direction="both", depth=depth)
        # This would require extracting the UUID from entity_dict["id"]
        if include_relationships:
            logger.debug(
                f"Relationship traversal requested but not yet implemented (depth={depth})"
            )
            result["relationships_note"] = "Relationship traversal not yet implemented"

        return result

    except Exception as e:
        logger.error(f"Entity lookup failed for '{entity_id}': {e}")
        raise RuntimeError(f"Failed to lookup entity {entity_id}: {e}")


def _is_uuid(value: str) -> bool:
    """Check if string is a valid UUID format.

    Args:
        value: String to check

    Returns:
        True if value matches UUID format (8-4-4-4-12 hex digits)
    """
    import re

    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
    )
    return bool(uuid_pattern.match(value))
