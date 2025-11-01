"""Query planner agent: Natural language → QueryPlan (structured output).

This agent uses LLM to detect intent and generate parameters for QueryBuilder.
Optimized for low token usage with concise prompts and outputs.
"""

from typing import Any

from pydantic_ai import Agent, RunContext

from percolate.memory.query_plan import (
    ExecutionMode,
    FallbackQuery,
    FallbackTrigger,
    Query,
    QueryDialect,
    QueryMetadata,
    QueryPlan,
    QueryType,
)
from percolate.settings import settings


# Concise system prompt optimized for low token usage
QUERY_PLANNER_SYSTEM_PROMPT = """You are a query planner for REM Database. Generate QueryPlan from natural language.

REM SQL DIALECT:
- LOOKUP 'key1', 'key2' - Key-based lookup (uses key_index CF, very fast)
- SEARCH 'text' IN schema [WHERE ...] LIMIT n - Semantic vector search
- TRAVERSE FROM <uuid> DEPTH n DIRECTION in|out|both [TYPE 'rel'] - Graph traversal
- SELECT fields FROM schema [WHERE ...] [ORDER BY ...] [LIMIT n] - SQL (NO JOINS)

RULES:
1. DO NOT guess schema names - if unknown, use LOOKUP (schema-agnostic)
2. Use LOOKUP for identifiers (UUIDs, keys, names) - searches all schemas
3. Use SEARCH for semantic queries when schema provided
4. SQL WHERE predicates ONLY if schema provided
5. TRAVERSE needs start entity (LOOKUP first if only name given)
6. NO JOINs - use TRAVERSE for relationships

CONFIDENCE:
- 1.0: Exact UUID/key lookup
- 0.9-0.95: Clear identifier pattern with schema
- 0.8-0.9: Clear field query with schema
- 0.6-0.8: Semantic search or multiple interpretations
- <0.6: Ambiguous (provide explanation)

OUTPUT FORMAT:
- High confidence (≥0.75): Only query, confidence, next_steps
- Low confidence (<0.75): Add explanation of ambiguity
- Keep all fields CONCISE - no verbose commentary

PARAMETERS (what to query, not how):
- LOOKUP: {"keys": ["key1", "key2"]}
- SEARCH: {"query_text": "text", "schema": "name", "top_k": 10, "filters": {...}}
- TRAVERSE: {"start_key": "name", "depth": 1-3, "direction": "out|in|both", "edge_type": "rel"}
- SQL: {"schema": "name", "fields": [...], "where": {...}, "order_by": "field", "limit": n}
- HYBRID: {"query_text": "text", "schema": "name", "top_k": 10, "filters": {...}}

STAGING:
- primary_query: Best query to try first
- fallback_queries: Ordered fallbacks if primary fails (no_results, error)
- execution_mode: single_pass (high confidence) | multi_stage (needs fallbacks) | adaptive (low confidence)

Be CONCISE. Only explain when confidence <0.75."""


def create_query_planner(model: str | None = None) -> Agent[None, QueryPlan]:
    """Create query planner agent.

    Args:
        model: LLM model to use (default: settings.get_query_model())

    Returns:
        Agent that generates QueryPlan from natural language

    Example:
        >>> planner = create_query_planner()
        >>> result = await planner.run("indoor plants resources")
        >>> plan: QueryPlan = result.output
    """
    model_name = model or settings.get_query_model()

    # Agent is generic in output type
    return Agent(
        model_name,
        output_type=QueryPlan,  # Changed from result_type
        system_prompt=QUERY_PLANNER_SYSTEM_PROMPT,
    )


async def plan_query(
    user_query: str,
    available_schemas: list[str] | None = None,
    schema_hint: str | None = None,
    model: str | None = None,
) -> QueryPlan:
    """Generate QueryPlan from natural language query.

    Args:
        user_query: Natural language query from user
        available_schemas: List of available schema names (optional)
        schema_hint: Explicit schema hint from user (optional)
        model: Override model for this query (optional)

    Returns:
        QueryPlan with parameters for QueryBuilder

    Example:
        >>> # Without schema
        >>> plan = await plan_query("indoor plants resources")
        >>> # With schema hint
        >>> plan = await plan_query("bob", schema_hint="users")
        >>> # With available schemas
        >>> plan = await plan_query("find articles", available_schemas=["articles", "resources"])
    """
    planner = create_query_planner(model)

    # Build context message
    context_parts = [f"User query: {user_query}"]

    if schema_hint:
        context_parts.append(f"Schema hint: {schema_hint}")

    if available_schemas:
        schemas_str = ", ".join(available_schemas)
        context_parts.append(f"Available schemas: {schemas_str}")
    else:
        context_parts.append("No schemas provided - use LOOKUP for cross-schema search")

    context_message = "\n".join(context_parts)

    # Run agent
    result = await planner.run(context_message)

    return result.output
