"""Simple pagination example - lightweight API.

Shows the minimal code needed to use pagination.
"""

import asyncio

from pydantic import BaseModel, Field

from percolate.agents.context import AgentContext
from percolate.agents.factory import create_agent
from percolate.agents.pagination import PaginationConfig, paginated_request


class EntityExtractor(BaseModel):
    """Extract entities from text."""

    entities: list[str] = Field(description="List of entities")
    count: int = Field(description="Count")


async def main():
    """Simple pagination example."""

    # 1. Create agent normally
    schema = {
        "description": "Extract entities from text",
        "properties": {
            "entities": {"type": "array", "items": {"type": "string"}},
            "count": {"type": "integer"},
        },
        "required": ["entities", "count"],
    }

    agent = await create_agent(
        context=AgentContext(tenant_id="user-123"),
        agent_schema_override=schema,
        result_type=EntityExtractor,
        model_override="claude-haiku-4-5",
    )

    # 2. Use pagination for large content
    # The agent already knows what to do (schema has the prompt)
    # We just chunk the data
    large_content = "Apple Google Microsoft Amazon Tesla " * 100

    result = await paginated_request(
        agent=agent,  # Already knows to extract entities
        content=large_content,
        config=PaginationConfig(
            merge_strategy="merge",  # Combine results
            chunk_size=50,  # Force pagination for testing
        ),
    )

    print(f"Found {result.count} entities: {result.entities[:5]}...")


if __name__ == "__main__":
    asyncio.run(main())
