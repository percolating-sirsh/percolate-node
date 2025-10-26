"""Example usage of agent pagination for processing large inputs.

This example demonstrates how to use the paginated_request function
to handle inputs that exceed model context windows.
"""

import asyncio

from pydantic import BaseModel, Field

from percolate.agents.context import AgentContext
from percolate.agents.factory import paginated_request
from percolate.agents.pagination import PaginationConfig


class EntityExtractor(BaseModel):
    """Model for extracting entities from text."""

    entities: list[str] = Field(description="List of unique entities found")
    count: int = Field(description="Total count of entities")
    summary: str = Field(description="Brief summary of findings")


class SentimentAnalysis(BaseModel):
    """Model for sentiment analysis."""

    sentiment: str = Field(description="Overall sentiment (positive/negative/neutral)")
    score: float = Field(description="Sentiment score from -1 to 1")
    key_themes: list[str] = Field(description="Key themes identified")


# Define agent schemas
ENTITY_EXTRACTOR_SCHEMA = {
    "description": "Extract all entities (people, companies, locations) from the provided text.",
    "properties": {
        "entities": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of unique entities found",
        },
        "count": {"type": "integer", "description": "Total count of entities"},
        "summary": {"type": "string", "description": "Brief summary of findings"},
    },
    "required": ["entities", "count", "summary"],
}

SENTIMENT_SCHEMA = {
    "description": "Analyze the overall sentiment of the provided text.",
    "properties": {
        "sentiment": {
            "type": "string",
            "description": "Overall sentiment (positive/negative/neutral)",
        },
        "score": {"type": "number", "description": "Sentiment score from -1 to 1"},
        "key_themes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Key themes identified",
        },
    },
    "required": ["sentiment", "score", "key_themes"],
}


async def example_merge_strategy():
    """Example: Using merge strategy to combine list fields across chunks."""
    print("\n=== Example 1: Merge Strategy ===")

    # Simulate large document (in practice, this would be 100k+ tokens)
    large_document = """
    Apple and Google announced a partnership today.
    Microsoft is also joining the initiative.
    Amazon and Tesla are competitors in this space.
    IBM has been in the industry for decades.
    """ * 100  # Repeat to simulate large content

    context = AgentContext(tenant_id="user-123", default_model="claude-haiku-4-5")

    result = await paginated_request(
        prompt="Extract all company names from this document",
        content=large_document,
        context=context,
        agent_schema_override=ENTITY_EXTRACTOR_SCHEMA,
        result_type=EntityExtractor,
        pagination_config=PaginationConfig(
            merge_strategy="merge",  # Combine entities from all chunks
            chunk_size=500,  # Small chunks to demonstrate pagination
            parallel=True,  # Process chunks in parallel
        ),
    )

    print(f"Found {result.count} entities: {result.entities[:5]}...")
    print(f"Summary: {result.summary}")


async def example_concat_strategy():
    """Example: Using concat strategy for batch processing."""
    print("\n=== Example 2: Concat Strategy ===")

    # List of records to process
    records = [
        {"id": 1, "text": "This product is amazing!"},
        {"id": 2, "text": "Terrible experience."},
        {"id": 3, "text": "It's okay, nothing special."},
    ] * 50  # Simulate large dataset

    context = AgentContext(tenant_id="user-123", default_model="claude-haiku-4-5")

    results = await paginated_request(
        prompt="Analyze sentiment for each batch of reviews",
        content=records,
        context=context,
        agent_schema_override=SENTIMENT_SCHEMA,
        result_type=SentimentAnalysis,
        pagination_config=PaginationConfig(
            merge_strategy="concat",  # Return list of results (one per chunk)
            chunk_size=20,  # 20 records per chunk
        ),
    )

    print(f"Processed {len(results)} chunks")
    for i, result in enumerate(results):
        print(f"Chunk {i+1}: {result.sentiment} (score: {result.score:.2f})")


async def example_custom_merge():
    """Example: Using custom merge function for deduplication."""
    print("\n=== Example 3: Custom Merge Strategy ===")

    def deduplicate_entities(results):
        """Custom merge that deduplicates entities by name."""
        seen = set()
        merged_entities = []

        for result in results:
            for entity in result.entities:
                entity_lower = entity.lower()
                if entity_lower not in seen:
                    seen.add(entity_lower)
                    merged_entities.append(entity)

        return EntityExtractor(
            entities=merged_entities,
            count=len(merged_entities),
            summary=f"Merged {len(results)} chunks with deduplication",
        )

    content = """
    Apple and apple are the same company.
    Google and GOOGLE refer to the same entity.
    Microsoft, microsoft, and MICROSOFT are identical.
    """ * 100

    context = AgentContext(tenant_id="user-123", default_model="claude-haiku-4-5")

    result = await paginated_request(
        prompt="Extract company names",
        content=content,
        context=context,
        agent_schema_override=ENTITY_EXTRACTOR_SCHEMA,
        result_type=EntityExtractor,
        pagination_config=PaginationConfig(
            merge_strategy="custom",
            custom_merge_fn=deduplicate_entities,
            chunk_size=300,
        ),
    )

    print(f"Found {result.count} unique entities after deduplication")
    print(f"Entities: {result.entities}")


async def example_sequential_processing():
    """Example: Sequential processing for rate limit safety."""
    print("\n=== Example 4: Sequential Processing ===")

    content = "Sample text " * 1000  # Large content

    context = AgentContext(tenant_id="user-123", default_model="claude-haiku-4-5")

    result = await paginated_request(
        prompt="Extract entities",
        content=content,
        context=context,
        agent_schema_override=ENTITY_EXTRACTOR_SCHEMA,
        result_type=EntityExtractor,
        pagination_config=PaginationConfig(
            merge_strategy="merge",
            parallel=False,  # Process sequentially (safer for rate limits)
            chunk_size=500,
        ),
    )

    print(f"Processed content sequentially")
    print(f"Found {result.count} entities")


async def main():
    """Run all examples."""
    print("Agent Pagination Examples")
    print("=" * 50)

    # Note: These examples require API keys for LLM providers
    # Set ANTHROPIC_API_KEY environment variable before running

    try:
        await example_merge_strategy()
        await example_concat_strategy()
        await example_custom_merge()
        await example_sequential_processing()

        print("\n" + "=" * 50)
        print("All examples completed successfully!")

    except Exception as e:
        print(f"\nError: {e}")
        print("Make sure to set ANTHROPIC_API_KEY environment variable")


if __name__ == "__main__":
    asyncio.run(main())
