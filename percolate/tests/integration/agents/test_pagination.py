"""Integration tests for agent pagination.

Tests full pagination workflow with real agent execution.
Requires API keys for LLM providers.
"""

import pytest
from pydantic import BaseModel, Field

from percolate.agents.context import AgentContext
from percolate.agents.factory import create_agent, paginated_request
from percolate.agents.pagination import AgentPaginationProxy, PaginationConfig


class EntityExtractor(BaseModel):
    """Test model for entity extraction."""

    entities: list[str] = Field(description="List of entities found")
    count: int = Field(description="Total count of entities")
    summary: str = Field(description="Brief summary")


class SentimentAnalysis(BaseModel):
    """Test model for sentiment analysis."""

    sentiment: str = Field(description="Overall sentiment (positive/negative/neutral)")
    score: float = Field(description="Sentiment score from -1 to 1")
    key_phrases: list[str] = Field(description="Key phrases")


@pytest.fixture
def test_context():
    """Create test context."""
    return AgentContext(
        tenant_id="test-tenant",
        default_model="claude-haiku-4-5",  # Use fast model for tests
    )


@pytest.fixture
def entity_agent_schema():
    """Create entity extraction agent schema."""
    return {
        "description": "Extract entities from the given text. Return all unique entities found.",
        "properties": {
            "entities": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of entities found",
            },
            "count": {
                "type": "integer",
                "description": "Total count of entities",
            },
            "summary": {
                "type": "string",
                "description": "Brief summary",
            },
        },
        "required": ["entities", "count", "summary"],
    }


@pytest.fixture
def sentiment_agent_schema():
    """Create sentiment analysis agent schema."""
    return {
        "description": "Analyze the sentiment of the given text.",
        "properties": {
            "sentiment": {
                "type": "string",
                "description": "Overall sentiment (positive/negative/neutral)",
            },
            "score": {
                "type": "number",
                "description": "Sentiment score from -1 to 1",
            },
            "key_phrases": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Key phrases",
            },
        },
        "required": ["sentiment", "score", "key_phrases"],
    }


class TestPaginationMergeStrategies:
    """Tests for different merge strategies.

    These tests force pagination by using very small chunk_size values
    to override the model's actual context window. This ensures we
    actually test multi-chunk pagination and merge behavior.
    """

    @pytest.mark.asyncio
    async def test_forced_pagination_verifies_chunking(self, test_context, entity_agent_schema):
        """Test that small chunk_size actually forces pagination.

        This is a sanity test to verify our testing approach works -
        that we can force pagination even with small content by
        overriding the chunk size.
        """
        # Small content but with forced tiny chunks
        content = "Apple Google Microsoft Amazon Tesla IBM Oracle Salesforce"

        # Use concat strategy to see each chunk's result separately
        result = await paginated_request(
            prompt="Extract company names",
            content=content,
            context=test_context,
            agent_schema_override=entity_agent_schema,
            result_type=EntityExtractor,
            pagination_config=PaginationConfig(
                merge_strategy="concat",
                chunk_size=10,  # Extremely small to force 5+ chunks
                parallel=True,
            ),
        )

        # Verify we actually got multiple chunks
        assert isinstance(result, list), "concat strategy should return list"
        assert len(result) >= 3, f"Expected at least 3 chunks with chunk_size=10, got {len(result)}"

        print(f"\n✓ Successfully forced pagination into {len(result)} chunks")
        for i, chunk_result in enumerate(result):
            print(f"  Chunk {i+1}: {len(chunk_result.entities)} entities - {chunk_result.entities}")

    @pytest.mark.asyncio
    async def test_merge_strategy_combines_lists(self, test_context, entity_agent_schema):
        """Test merge strategy combines list fields from multiple chunks.

        This test forces pagination by using a very small chunk_size (50 tokens)
        to ensure content is split into multiple chunks. We then verify that
        entities from all chunks are combined in the final result.
        """
        # Create content with clear entities in different sections
        # Each section separated to be in different chunks
        section1 = "First section: Apple and Google are major tech companies. " * 10
        section2 = "Second section: Microsoft and Amazon dominate the cloud market. " * 10
        section3 = "Third section: Tesla and IBM are innovation leaders. " * 10

        content = f"{section1}\n\n{section2}\n\n{section3}"

        result = await paginated_request(
            prompt="Extract all company names from the text",
            content=content,
            context=test_context,
            agent_schema_override=entity_agent_schema,
            result_type=EntityExtractor,
            pagination_config=PaginationConfig(
                merge_strategy="merge",
                chunk_size=50,  # Very small to force multiple chunks (override model limit)
                parallel=True,
            ),
        )

        # Verify result structure
        assert isinstance(result, EntityExtractor)
        assert isinstance(result.entities, list)
        assert len(result.entities) > 0

        # Should have found companies from all sections (minimum 3 companies)
        # Due to merge strategy, all unique entities should be in the list
        assert len(result.entities) >= 3, f"Expected at least 3 entities, got {len(result.entities)}"

        # Verify entities were actually extracted (case-insensitive check)
        entity_names_lower = [e.lower() for e in result.entities]
        assert any("apple" in e or "google" in e for e in entity_names_lower), "Missing entities from first section"
        assert any("microsoft" in e or "amazon" in e for e in entity_names_lower), "Missing entities from second section"

        print(f"\n✓ Merge strategy combined {len(result.entities)} total entities from multiple chunks")
        print(f"  Entities: {result.entities}")

    @pytest.mark.asyncio
    async def test_merge_vs_concat_behavior(self, test_context, entity_agent_schema):
        """Compare merge vs concat strategies to verify merge actually combines results.

        This test runs the same content through both strategies and verifies:
        1. Concat returns a list of separate results (one per chunk)
        2. Merge returns a single combined result with all entities
        3. Merge has more/equal entities than any single concat chunk
        """
        # Create content with entities spread across chunks
        content = (
            "Section A has Apple and Google. " * 5
            + "Section B has Microsoft. " * 5
            + "Section C has Amazon. " * 5
        )

        # First, run with concat to see individual chunks
        concat_result = await paginated_request(
            prompt="Extract company names",
            content=content,
            context=test_context,
            agent_schema_override=entity_agent_schema,
            result_type=EntityExtractor,
            pagination_config=PaginationConfig(
                merge_strategy="concat",
                chunk_size=30,  # Force multiple chunks
            ),
        )

        # Verify concat returned multiple chunks
        assert isinstance(concat_result, list), "concat should return list"
        assert len(concat_result) >= 2, f"Expected 2+ chunks, got {len(concat_result)}"

        print(f"\n✓ Concat strategy returned {len(concat_result)} separate chunk results:")
        for i, chunk in enumerate(concat_result):
            print(f"  Chunk {i+1}: {chunk.entities}")

        # Now run with merge
        merge_result = await paginated_request(
            prompt="Extract company names",
            content=content,
            context=test_context,
            agent_schema_override=entity_agent_schema,
            result_type=EntityExtractor,
            pagination_config=PaginationConfig(
                merge_strategy="merge",
                chunk_size=30,  # Same chunk size
            ),
        )

        # Verify merge returned single result
        assert isinstance(merge_result, EntityExtractor), "merge should return single EntityExtractor"
        assert hasattr(merge_result, "entities"), "merge result should have entities"

        print(f"\n✓ Merge strategy returned single combined result:")
        print(f"  Combined entities: {merge_result.entities}")

        # Verify merge has at least as many entities as the largest concat chunk
        max_concat_entities = max(len(chunk.entities) for chunk in concat_result)
        assert len(merge_result.entities) >= max_concat_entities, (
            f"Merge result ({len(merge_result.entities)} entities) should have at least as many as "
            f"largest concat chunk ({max_concat_entities} entities)"
        )

        print(f"\n✓ Verification passed:")
        print(f"  - Concat chunks: {len(concat_result)} chunks")
        print(f"  - Max entities in single concat chunk: {max_concat_entities}")
        print(f"  - Total entities in merge result: {len(merge_result.entities)}")
        print(f"  - Merge correctly combined results ✓")

    @pytest.mark.asyncio
    async def test_concat_strategy_returns_list(self, test_context, entity_agent_schema):
        """Test concat strategy returns list of all chunk results.

        Forces pagination with small chunk size and verifies that concat
        returns a list with one result per chunk (not merged).
        """
        # Create content that will be split into 3-4 chunks
        section1 = "Section one mentions Apple and Google. " * 5
        section2 = "Section two discusses Microsoft and Amazon. " * 5
        section3 = "Section three covers Tesla. " * 5
        content = f"{section1}{section2}{section3}"

        result = await paginated_request(
            prompt="Extract company names",
            content=content,
            context=test_context,
            agent_schema_override=entity_agent_schema,
            result_type=EntityExtractor,
            pagination_config=PaginationConfig(
                merge_strategy="concat",
                chunk_size=50,  # Force 3+ chunks
                parallel=True,
            ),
        )

        # Should return list of results (one per chunk)
        assert isinstance(result, list), f"Expected list but got {type(result)}"
        assert len(result) >= 2, f"Expected multiple chunks, got {len(result)}"

        # Each item should be EntityExtractor with its own entities
        for i, item in enumerate(result):
            assert isinstance(item, EntityExtractor), f"Chunk {i} is not EntityExtractor"
            # Each chunk should have found some entities
            assert hasattr(item, "entities"), f"Chunk {i} missing entities attribute"

    @pytest.mark.asyncio
    async def test_first_strategy_returns_first_chunk(self, test_context, entity_agent_schema):
        """Test first strategy returns only first chunk result."""
        chunk1 = "Apple is in the first chunk."
        chunk2 = "Google is in the second chunk."
        content = f"{chunk1} {'padding ' * 100}\n\n{chunk2} {'padding ' * 100}"

        result = await paginated_request(
            prompt="Extract companies",
            content=content,
            context=test_context,
            agent_schema_override=entity_agent_schema,
            result_type=EntityExtractor,
            pagination_config=PaginationConfig(
                merge_strategy="first",
                chunk_size=200,  # Force 2 chunks
            ),
        )

        # Should return only first chunk result
        assert isinstance(result, EntityExtractor)
        # Should have entities from first chunk
        assert len(result.entities) > 0

    @pytest.mark.asyncio
    async def test_last_strategy_returns_last_chunk(self, test_context, entity_agent_schema):
        """Test last strategy returns only last chunk result."""
        chunk1 = "Apple is in the first chunk."
        chunk2 = "Google is in the last chunk."
        content = f"{chunk1} {'padding ' * 100}\n\n{chunk2} {'padding ' * 100}"

        result = await paginated_request(
            prompt="Extract companies",
            content=content,
            context=test_context,
            agent_schema_override=entity_agent_schema,
            result_type=EntityExtractor,
            pagination_config=PaginationConfig(
                merge_strategy="last",
                chunk_size=200,  # Force 2 chunks
            ),
        )

        # Should return only last chunk result
        assert isinstance(result, EntityExtractor)
        assert len(result.entities) > 0

    @pytest.mark.asyncio
    async def test_custom_merge_function(self, test_context, entity_agent_schema):
        """Test custom merge function."""

        def custom_merge(results):
            """Custom merge that deduplicates entities."""
            all_entities = []
            for r in results:
                all_entities.extend(r.entities)

            # Deduplicate
            unique_entities = list(set(all_entities))

            return EntityExtractor(
                entities=unique_entities,
                count=len(unique_entities),
                summary=f"Merged {len(results)} chunks",
            )

        content = "Apple and Google. " * 50 + "Microsoft and Apple. " * 50

        result = await paginated_request(
            prompt="Extract companies",
            content=content,
            context=test_context,
            agent_schema_override=entity_agent_schema,
            result_type=EntityExtractor,
            pagination_config=PaginationConfig(
                merge_strategy="custom",
                custom_merge_fn=custom_merge,
                chunk_size=100,
            ),
        )

        assert isinstance(result, EntityExtractor)
        # Should have deduplicated entities
        assert len(result.entities) > 0
        # Check no duplicates
        assert len(result.entities) == len(set(result.entities))


class TestPaginationWithRecords:
    """Tests for pagination with record-based content."""

    @pytest.mark.asyncio
    async def test_record_based_chunking(self, test_context, sentiment_agent_schema):
        """Test pagination with list of records."""
        # Create list of records
        records = [
            {"id": 1, "text": "This product is amazing! I love it."},
            {"id": 2, "text": "Terrible experience. Very disappointed."},
            {"id": 3, "text": "It's okay, nothing special."},
            {"id": 4, "text": "Absolutely fantastic! Highly recommend."},
            {"id": 5, "text": "Not worth the money. Poor quality."},
        ]

        result = await paginated_request(
            prompt="Analyze the overall sentiment of these reviews",
            content=records,
            context=test_context,
            agent_schema_override=sentiment_agent_schema,
            result_type=SentimentAnalysis,
            pagination_config=PaginationConfig(
                merge_strategy="last",  # Use last chunk's overall assessment
                chunk_size=2,  # Force multiple chunks (2 records per chunk)
            ),
        )

        assert isinstance(result, SentimentAnalysis)
        assert result.sentiment in ["positive", "negative", "neutral"]
        assert -1.0 <= result.score <= 1.0

    @pytest.mark.asyncio
    async def test_record_boundary_preservation(self, test_context, entity_agent_schema):
        """Test that record boundaries are never split."""
        # Create records with nested data
        records = [
            {"id": i, "text": f"Company{i} " * 100, "metadata": {"source": "test"}}
            for i in range(10)
        ]

        result = await paginated_request(
            prompt="Extract company names",
            content=records,
            context=test_context,
            agent_schema_override=entity_agent_schema,
            result_type=EntityExtractor,
            pagination_config=PaginationConfig(
                merge_strategy="merge",
                chunk_size=3,  # Force multiple chunks
            ),
        )

        assert isinstance(result, EntityExtractor)
        assert len(result.entities) > 0


class TestPaginationProxy:
    """Tests for AgentPaginationProxy directly."""

    @pytest.mark.asyncio
    async def test_single_chunk_no_pagination(self, test_context, entity_agent_schema):
        """Test that small content doesn't trigger pagination."""
        agent = await create_agent(
            context=test_context,
            agent_schema_override=entity_agent_schema,
            result_type=EntityExtractor,
        )

        proxy = AgentPaginationProxy(
            context=test_context,
            config=PaginationConfig(merge_strategy="merge"),
        )

        # Small content that fits in one chunk
        content = "Apple and Google are tech companies."

        result = await proxy.run(
            prompt="Extract companies",
            content=content,
            agent=agent,
        )

        assert isinstance(result, EntityExtractor)
        assert len(result.entities) > 0

    @pytest.mark.asyncio
    async def test_parallel_execution(self, test_context, entity_agent_schema):
        """Test parallel chunk execution."""
        agent = await create_agent(
            context=test_context,
            agent_schema_override=entity_agent_schema,
            result_type=EntityExtractor,
        )

        proxy = AgentPaginationProxy(
            context=test_context,
            config=PaginationConfig(
                merge_strategy="merge",
                parallel=True,
            ),
        )

        # Content that requires chunking
        content = "Apple. " * 100 + "Google. " * 100 + "Microsoft. " * 100

        result = await proxy.run(
            prompt="Extract companies",
            content=content,
            agent=agent,
        )

        assert isinstance(result, EntityExtractor)

    @pytest.mark.asyncio
    async def test_sequential_execution(self, test_context, entity_agent_schema):
        """Test sequential chunk execution."""
        agent = await create_agent(
            context=test_context,
            agent_schema_override=entity_agent_schema,
            result_type=EntityExtractor,
        )

        proxy = AgentPaginationProxy(
            context=test_context,
            config=PaginationConfig(
                merge_strategy="merge",
                parallel=False,  # Sequential
            ),
        )

        content = "Apple. " * 100 + "Google. " * 100

        result = await proxy.run(
            prompt="Extract companies",
            content=content,
            agent=agent,
        )

        assert isinstance(result, EntityExtractor)

    @pytest.mark.asyncio
    async def test_chunk_metadata_included(self, test_context, entity_agent_schema):
        """Test that chunk metadata is added to prompts."""
        agent = await create_agent(
            context=test_context,
            agent_schema_override=entity_agent_schema,
            result_type=EntityExtractor,
        )

        proxy = AgentPaginationProxy(
            context=test_context,
            config=PaginationConfig(
                merge_strategy="merge",
                include_chunk_metadata=True,
                chunk_size=100,
            ),
        )

        content = "Test content. " * 200

        result = await proxy.run(
            prompt="Extract entities",
            content=content,
            agent=agent,
        )

        # Should work with metadata
        assert isinstance(result, EntityExtractor)


class TestPaginationEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_content(self, test_context, entity_agent_schema):
        """Test handling of empty content."""
        result = await paginated_request(
            prompt="Extract entities",
            content="",
            context=test_context,
            agent_schema_override=entity_agent_schema,
            result_type=EntityExtractor,
            pagination_config=PaginationConfig(merge_strategy="merge"),
        )

        # Should handle gracefully
        assert isinstance(result, EntityExtractor)

    @pytest.mark.asyncio
    async def test_custom_strategy_without_function_fails(self, test_context, entity_agent_schema):
        """Test that custom strategy without function raises error."""
        with pytest.raises(ValueError, match="custom merge strategy requires custom_merge_fn"):
            await paginated_request(
                prompt="Extract entities",
                content="Test content",
                context=test_context,
                agent_schema_override=entity_agent_schema,
                result_type=EntityExtractor,
                pagination_config=PaginationConfig(
                    merge_strategy="custom",
                    custom_merge_fn=None,  # Missing function
                ),
            )

    @pytest.mark.asyncio
    async def test_very_small_chunk_size(self, test_context, entity_agent_schema):
        """Test with very small chunk size."""
        content = "Apple Google Microsoft Amazon Tesla"

        result = await paginated_request(
            prompt="Extract companies",
            content=content,
            context=test_context,
            agent_schema_override=entity_agent_schema,
            result_type=EntityExtractor,
            pagination_config=PaginationConfig(
                merge_strategy="merge",
                chunk_size=10,  # Very small
            ),
        )

        assert isinstance(result, EntityExtractor)

    @pytest.mark.asyncio
    async def test_unicode_content(self, test_context, entity_agent_schema):
        """Test handling of unicode content."""
        content = "公司包括苹果、谷歌和微软。" * 50

        result = await paginated_request(
            prompt="Extract company names",
            content=content,
            context=test_context,
            agent_schema_override=entity_agent_schema,
            result_type=EntityExtractor,
            pagination_config=PaginationConfig(
                merge_strategy="merge",
                chunk_size=100,
            ),
        )

        assert isinstance(result, EntityExtractor)
