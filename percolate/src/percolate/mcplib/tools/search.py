"""Knowledge base search MCP tool."""

from typing import Any
from loguru import logger

from percolate.memory import get_database


async def search_knowledge_base(
    query: str,
    tenant_id: str,
    limit: int = 10,
    schema: str = "resources",
) -> dict[str, Any]:
    """Search REM memory for semantically similar entities.

    Performs vector similarity search using HNSW index over entity embeddings.
    The search targets a specific schema/table (default: "resources" for documents).

    How it works:
    1. Generates embedding for the query using the schema's embedding provider
    2. Searches HNSW index for nearest neighbors
    3. Returns entities ranked by cosine similarity

    Args:
        query: Natural language search query
        tenant_id: Tenant identifier for data scoping
        limit: Maximum number of results to return (default: 10)
        schema: Schema/table to search (default: "resources" for testing).
               Only schemas with embedding_fields configured can be searched.

    Returns:
        Dictionary with:
        - query: Echo of the search query
        - tenant_id: Echo of the tenant ID
        - results: List of dicts with "entity" (full entity data) and "score" (similarity 0-1)
        - total: Number of results returned

    Example:
        >>> results = await search_knowledge_base(
        ...     query="low maintenance plants for apartments",
        ...     tenant_id="percolating-plants",
        ...     limit=5
        ... )
        >>> results["results"][0]["entity"]["name"]
        'Snake Plant'
        >>> results["results"][0]["score"]
        0.89

    Notes:
        - Returns empty results if database unavailable (graceful degradation)
        - Schema must have embedding_fields configured or search will fail
        - Default schema "resources" is suitable for document/content search
        - For entity search (products, customers), specify the entity schema name
    """
    db = get_database(tenant_id=tenant_id)

    if not db:
        logger.warning("REM database unavailable - returning empty results")
        return {
            "query": query,
            "tenant_id": tenant_id,
            "schema": schema,
            "results": [],
            "total": 0,
            "error": "REM database unavailable (percolate-rocks not installed or initialized)",
        }

    try:
        # Call Rust HNSW vector search (fully implemented)
        # Returns list of (entity_dict, score) tuples
        raw_results = db.search(query=query, schema=schema, top_k=limit)

        # Convert from tuples to structured dicts for JSON serialization
        results = [
            {
                "entity": entity_dict,  # Full entity with properties
                "score": float(score),  # Similarity score (0.0 to 1.0)
            }
            for entity_dict, score in raw_results
        ]

        logger.debug(f"Search returned {len(results)} results for query: {query[:50]}")

        return {
            "query": query,
            "tenant_id": tenant_id,
            "schema": schema,
            "results": results,
            "total": len(results),
        }

    except Exception as e:
        logger.error(f"Search failed for query '{query}': {e}")
        return {
            "query": query,
            "tenant_id": tenant_id,
            "schema": schema,
            "results": [],
            "total": 0,
            "error": str(e),
        }
