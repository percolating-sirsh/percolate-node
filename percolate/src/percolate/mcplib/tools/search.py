"""Knowledge base search MCP tool."""

from typing import Any
from loguru import logger

from percolate.memory import get_database


async def search_knowledge_base(
    query: str,
    tenant_id: str,
    limit: int = 10,
    include_embeddings: bool = False,
) -> dict[str, Any]:
    """Search REM memory for relevant information.

    Performs hybrid search across Resources, Entities, and Moments:
    - Vector search for semantic similarity
    - Fuzzy search for entity name matching
    - Graph traversal for relationship discovery

    Args:
        query: Search query string
        tenant_id: Tenant identifier for data scoping
        limit: Maximum results to return
        include_embeddings: Whether to include embedding vectors

    Returns:
        Search results with resources, entities, and moments

    Example:
        >>> results = await search_knowledge_base(
        ...     query="What is percolate?",
        ...     tenant_id="tenant-123"
        ... )
        >>> len(results["resources"])
        5
    """
    db = get_database()

    if not db:
        logger.warning("REM database unavailable - returning empty results")
        return {
            "query": query,
            "tenant_id": tenant_id,
            "results": [],
            "total": 0,
            "note": "REM database unavailable (percolate-rocks not installed or not working)",
        }

    try:
        # Note: rem search is not implemented in v0.2.0
        # When it's ready, use: results = db.search(query, schema="resources", top_k=limit)
        # For now, try using export if data exists
        logger.debug(f"Search not yet implemented - query: {query}")

        return {
            "query": query,
            "tenant_id": tenant_id,
            "results": [],
            "total": 0,
            "note": "Search not yet implemented in percolate-rocks v0.2.0 (rem search is TODO)",
        }

    except Exception as e:
        logger.error(f"Search failed: {e}")
        return {
            "query": query,
            "tenant_id": tenant_id,
            "results": [],
            "total": 0,
            "error": str(e),
        }
