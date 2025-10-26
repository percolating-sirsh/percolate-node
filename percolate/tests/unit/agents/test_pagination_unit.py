"""Unit tests for pagination proxy merge logic.

Tests the merge strategies without requiring actual agent execution.
Uses mocked agents to test pagination logic in isolation.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel, Field

from percolate.agents.pagination import PaginationConfig, paginated_request, _merge_results


class TestModel(BaseModel):
    """Test model for pagination."""

    items: list[str] = Field(description="List of items")
    count: int = Field(description="Count")
    summary: str = Field(description="Summary")


class NestedModel(BaseModel):
    """Model with nested structures."""

    data: list[dict] = Field(description="Data list")
    metadata: dict = Field(description="Metadata")
    total: int = Field(description="Total count")




@pytest.fixture
def mock_agent():
    """Create mock agent that returns TestModel."""

    async def mock_run(prompt: str):
        """Mock run that extracts items from prompt."""
        # Extract chunk content from prompt
        result = MagicMock()

        # Parse what chunk this is from prompt
        if "chunk 1" in prompt.lower() or "part 1" in prompt.lower():
            result.data = TestModel(items=["item1", "item2"], count=2, summary="chunk 1")
        elif "chunk 2" in prompt.lower() or "part 2" in prompt.lower():
            result.data = TestModel(items=["item3", "item4"], count=2, summary="chunk 2")
        elif "chunk 3" in prompt.lower() or "part 3" in prompt.lower():
            result.data = TestModel(items=["item5"], count=1, summary="chunk 3")
        else:
            # Default case - parse content for items
            result.data = TestModel(items=["item1"], count=1, summary="default")

        return result

    agent = MagicMock()
    agent.run = AsyncMock(side_effect=mock_run)
    return agent


class TestMergeStrategies:
    """Test different merge strategies in isolation."""

    def test_merge_strategy_combines_lists(self):
        """Test that merge strategy extends list fields."""
        results = [
            TestModel(items=["a", "b"], count=2, summary="first"),
            TestModel(items=["c", "d"], count=2, summary="second"),
            TestModel(items=["e"], count=1, summary="third"),
        ]

        merged = _merge_results(results, "merge")

        # List fields should be extended
        assert merged.items == ["a", "b", "c", "d", "e"]
        # Non-list fields should keep first value
        assert merged.count == 2  # First count
        assert merged.summary == "first"  # First summary

    def test_merge_strategy_with_nested_dicts(self):
        """Test merge with nested dict structures."""
        results = [
            NestedModel(
                data=[{"id": 1, "value": "a"}],
                metadata={"source": "chunk1", "version": 1},
                total=1,
            ),
            NestedModel(
                data=[{"id": 2, "value": "b"}],
                metadata={"source": "chunk2", "version": 2},
                total=1,
            ),
        ]

        merged = _merge_results(results, "merge")

        # List fields extended
        assert len(merged.data) == 2
        assert merged.data[0]["id"] == 1
        assert merged.data[1]["id"] == 2

        # Dict fields recursively merged (keeps first for non-lists)
        assert merged.metadata["source"] == "chunk1"  # First value
        assert merged.metadata["version"] == 1  # First value

        # Primitive fields keep first
        assert merged.total == 1

    def test_concat_strategy_returns_list(self):
        """Test concat strategy returns all results as list."""
        results = [
            TestModel(items=["a"], count=1, summary="first"),
            TestModel(items=["b"], count=1, summary="second"),
        ]

        merged = _merge_results(results, "concat")

        # Should return the list as-is
        assert isinstance(merged, list)
        assert len(merged) == 2
        assert merged[0].items == ["a"]
        assert merged[1].items == ["b"]

    def test_first_strategy_returns_first(self):
        """Test first strategy returns only first result."""

        results = [
            TestModel(items=["a"], count=1, summary="first"),
            TestModel(items=["b"], count=1, summary="second"),
        ]

        merged = _merge_results(results, "first")

        assert merged.items == ["a"]
        assert merged.summary == "first"

    def test_last_strategy_returns_last(self):
        """Test last strategy returns only last result."""

        results = [
            TestModel(items=["a"], count=1, summary="first"),
            TestModel(items=["b"], count=1, summary="second"),
        ]

        merged = _merge_results(results, "last")

        assert merged.items == ["b"]
        assert merged.summary == "second"

    def test_custom_merge_function(self):
        """Test custom merge function is called."""

        def custom_merge(results):
            """Custom merge that counts total items."""
            all_items = []
            for r in results:
                all_items.extend(r.items)
            return TestModel(items=all_items, count=len(all_items), summary="custom")

        results = [
            TestModel(items=["a", "b"], count=2, summary="first"),
            TestModel(items=["c"], count=1, summary="second"),
        ]

        merged = _merge_results(results, "custom", custom_merge)

        assert merged.items == ["a", "b", "c"]
        assert merged.count == 3
        assert merged.summary == "custom"

    def test_empty_results_list(self):
        """Test handling of empty results list."""

        merged = _merge_results([], "merge")
        assert merged is None

    def test_single_result_no_merge_needed(self):
        """Test single result returns as-is."""

        results = [TestModel(items=["a"], count=1, summary="only")]
        merged = _merge_results(results, "merge")

        assert merged.items == ["a"]
        assert merged.summary == "only"


class TestPaginationLogic:
    """Test pagination chunking logic."""

    @pytest.mark.asyncio
    async def test_small_content_no_pagination(self, mock_agent):
        """Test that small content doesn't trigger pagination."""
        content = "Short text"
        config = PaginationConfig(merge_strategy="merge")

        result = await paginated_request(agent=mock_agent, content=content, config=config)

        # Should only call agent once
        assert mock_agent.run.call_count == 1

    @pytest.mark.asyncio
    async def test_large_content_triggers_pagination(self, mock_agent):
        """Test that large content triggers multiple chunks."""
        content = "word " * 500
        config = PaginationConfig(merge_strategy="merge", chunk_size=100)

        result = await paginated_request(agent=mock_agent, content=content, config=config)

        # Should call agent multiple times
        assert mock_agent.run.call_count > 1

    @pytest.mark.asyncio
    async def test_record_content_pagination(self, mock_agent):
        """Test pagination with record-based content."""
        records = [{"id": i, "data": f"item{i}"} for i in range(20)]
        config = PaginationConfig(merge_strategy="merge", chunk_size=5)

        result = await paginated_request(agent=mock_agent, content=records, config=config)

        # Should chunk into 4 calls (20 records / 5 per chunk)
        assert mock_agent.run.call_count == 4


class TestErrorHandling:
    """Test error handling in pagination."""

    @pytest.mark.asyncio
    async def test_custom_strategy_without_function_fails(self, mock_agent):
        """Test that custom strategy without function raises error."""
        config = PaginationConfig(merge_strategy="custom", custom_merge_fn=None)

        with pytest.raises(ValueError, match="custom merge strategy requires custom_merge_fn"):
            await paginated_request(agent=mock_agent, content="test", config=config)

    def test_invalid_merge_strategy(self):
        """Test that invalid merge strategy raises error."""
        results = [TestModel(items=["a"], count=1, summary="test")]

        with pytest.raises(ValueError, match="Unknown merge strategy"):
            _merge_results(results, "invalid_strategy")  # type: ignore
