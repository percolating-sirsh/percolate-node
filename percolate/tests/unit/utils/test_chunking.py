"""Unit tests for chunking utilities.

Tests token-aware and record-based chunking without external dependencies.
"""

import json

import pytest

from percolate.utils.chunking import (
    chunk_by_records,
    chunk_by_tokens,
    estimate_record_count,
    estimate_tokens,
    get_optimal_chunk_size,
    is_list_content,
)


class TestOptimalChunkSize:
    """Tests for optimal chunk size calculation."""

    def test_claude_sonnet_chunk_size(self):
        """Test chunk size for Claude Sonnet 4.5."""
        size = get_optimal_chunk_size("claude-sonnet-4-5")
        # 200k context - 2000 overhead - 40k buffer (20%)
        assert size == 158_000

    def test_gpt4_chunk_size(self):
        """Test chunk size for GPT-4.1."""
        size = get_optimal_chunk_size("gpt-4.1")
        # 128k context - 2000 overhead - 25.6k buffer (20%)
        assert size == 100_400

    def test_unknown_model_defaults(self):
        """Test unknown model uses conservative default."""
        size = get_optimal_chunk_size("unknown-model")
        # 100k default - 2000 overhead - 20k buffer
        assert size == 78_000

    def test_custom_overhead(self):
        """Test custom overhead configuration."""
        size = get_optimal_chunk_size(
            "claude-sonnet-4-5",
            overhead_tokens=5000,
            response_buffer_ratio=0.1,
        )
        # 200k - 5000 - 20k (10% buffer)
        assert size == 175_000


class TestTokenEstimation:
    """Tests for token estimation."""

    def test_short_text_estimation(self):
        """Test estimation for short text."""
        text = "Hello world"
        tokens = estimate_tokens(text, "claude-sonnet-4-5")
        # Should be around 2-3 tokens
        assert 1 <= tokens <= 5

    def test_long_text_estimation(self):
        """Test estimation scales with content."""
        short = "word " * 100
        long = "word " * 1000

        short_tokens = estimate_tokens(short, "claude-sonnet-4-5")
        long_tokens = estimate_tokens(long, "claude-sonnet-4-5")

        # Long should be ~10x more tokens
        assert long_tokens > short_tokens * 5
        assert long_tokens < short_tokens * 15

    def test_empty_text(self):
        """Test empty text returns 0 tokens."""
        tokens = estimate_tokens("", "claude-sonnet-4-5")
        assert tokens == 0


class TestTokenChunking:
    """Tests for token-based text chunking."""

    def test_small_content_single_chunk(self):
        """Test content that fits in single chunk."""
        content = "word " * 100  # Small content
        chunks = chunk_by_tokens(content, "claude-sonnet-4-5")
        assert len(chunks) == 1
        assert chunks[0] == content

    def test_large_content_multiple_chunks(self):
        """Test content requiring multiple chunks."""
        # Create large content
        content = "word " * 100_000  # ~100k tokens
        chunks = chunk_by_tokens(content, "claude-sonnet-4-5", max_chunk_tokens=30_000)

        assert len(chunks) > 1
        # All chunks should be within limit
        for chunk in chunks:
            tokens = estimate_tokens(chunk, "claude-sonnet-4-5")
            assert tokens <= 30_000

    def test_sentence_boundary_splitting(self):
        """Test that chunking prefers sentence boundaries."""
        content = "This is sentence one. " * 1000 + "This is sentence two. " * 1000
        chunks = chunk_by_tokens(content, "claude-sonnet-4-5", max_chunk_tokens=1000)

        # Check that chunks end on sentence boundaries
        for chunk in chunks[:-1]:  # Except possibly last chunk
            # Should end with period or be at boundary
            assert chunk.rstrip().endswith(".")

    def test_very_long_sentence_splits(self):
        """Test handling of sentences longer than chunk size."""
        # Single very long sentence
        long_sentence = "word" * 100_000  # No spaces, no sentence boundaries
        chunks = chunk_by_tokens(long_sentence, "claude-sonnet-4-5", max_chunk_tokens=1000)

        assert len(chunks) > 1
        # Each chunk should be under limit
        for chunk in chunks:
            tokens = estimate_tokens(chunk, "claude-sonnet-4-5")
            assert tokens <= 1500  # Some tolerance

    def test_empty_content(self):
        """Test empty content returns empty list."""
        chunks = chunk_by_tokens("", "claude-sonnet-4-5")
        assert chunks == [""]


class TestListContentDetection:
    """Tests for list content type detection."""

    def test_python_list(self):
        """Test detection of Python lists."""
        assert is_list_content([{"id": 1}, {"id": 2}])
        assert is_list_content([1, 2, 3])
        assert is_list_content([])

    def test_json_array_string(self):
        """Test detection of JSON array strings."""
        assert is_list_content('[{"id": 1}, {"id": 2}]')
        assert is_list_content("[]")
        assert is_list_content('[1, 2, 3]')

    def test_plain_text_not_list(self):
        """Test plain text is not detected as list."""
        assert not is_list_content("plain text")
        assert not is_list_content("not a list")

    def test_json_object_not_list(self):
        """Test JSON object is not detected as list."""
        assert not is_list_content('{"key": "value"}')

    def test_invalid_json_not_list(self):
        """Test invalid JSON is not detected as list."""
        assert not is_list_content("[invalid json")


class TestRecordChunking:
    """Tests for record-based chunking."""

    def test_small_record_set_single_chunk(self):
        """Test small record set fits in single chunk."""
        records = [{"id": i, "data": "x" * 10} for i in range(10)]
        chunks = chunk_by_records(records, "claude-sonnet-4-5")
        assert len(chunks) == 1

        # Verify valid JSON
        parsed = json.loads(chunks[0])
        assert len(parsed) == 10

    def test_large_record_set_multiple_chunks(self):
        """Test large record set splits into chunks."""
        # Create 1000 records with some data
        records = [{"id": i, "data": "x" * 100} for i in range(1000)]
        chunks = chunk_by_records(records, "claude-sonnet-4-5", max_records_per_chunk=100)

        assert len(chunks) == 10  # 1000 / 100

        # Verify all chunks are valid JSON
        total_records = 0
        for chunk in chunks:
            parsed = json.loads(chunk)
            assert isinstance(parsed, list)
            assert len(parsed) <= 100
            total_records += len(parsed)

        assert total_records == 1000

    def test_record_boundary_preservation(self):
        """Test that records are never split."""
        records = [{"id": i, "nested": {"data": "x" * 1000}} for i in range(50)]
        chunks = chunk_by_records(records, "claude-sonnet-4-5", max_records_per_chunk=10)

        # Each chunk should have complete, valid records
        for chunk in chunks:
            parsed = json.loads(chunk)
            assert isinstance(parsed, list)
            for record in parsed:
                assert "id" in record
                assert "nested" in record
                assert "data" in record["nested"]

    def test_empty_record_list(self):
        """Test empty record list."""
        chunks = chunk_by_records([], "claude-sonnet-4-5")
        assert chunks == []

    def test_single_record(self):
        """Test single record."""
        records = [{"id": 1, "data": "test"}]
        chunks = chunk_by_records(records, "claude-sonnet-4-5")
        assert len(chunks) == 1

        parsed = json.loads(chunks[0])
        assert parsed == records


class TestRecordCountEstimation:
    """Tests for record count estimation."""

    def test_estimate_small_records(self):
        """Test estimation for small records."""
        records = [{"id": i} for i in range(100)]
        stats = estimate_record_count(records, "claude-sonnet-4-5")

        assert stats["total_records"] == 100
        assert stats["total_tokens"] > 0
        assert stats["avg_tokens_per_record"] > 0
        assert stats["optimal_records_per_chunk"] > 0
        assert stats["estimated_chunks"] >= 1

    def test_estimate_large_records(self):
        """Test estimation for large records."""
        # Create larger records that will definitely need chunking
        records = [{"id": i, "data": "x" * 10000} for i in range(1000)]
        stats = estimate_record_count(records, "claude-sonnet-4-5")

        # Large records should have higher avg tokens
        assert stats["avg_tokens_per_record"] > 1000
        # Should need multiple chunks
        assert stats["estimated_chunks"] > 1

    def test_estimate_empty_list(self):
        """Test estimation for empty list."""
        stats = estimate_record_count([], "claude-sonnet-4-5")

        assert stats["total_records"] == 0
        assert stats["total_tokens"] == 0
        assert stats["avg_tokens_per_record"] == 0
        assert stats["optimal_records_per_chunk"] == 0
        assert stats["estimated_chunks"] == 0

    def test_estimate_samples_first_ten(self):
        """Test that estimation samples first 10 records."""
        # Create 100 records where first 10 are small, rest are large
        records = [{"id": i, "data": "x" * 10} for i in range(10)]
        records += [{"id": i, "data": "x" * 10000} for i in range(10, 100)]

        stats = estimate_record_count(records, "claude-sonnet-4-5")

        # Should be based on small records (first 10)
        assert stats["avg_tokens_per_record"] < 100

    def test_estimate_varies_by_model(self):
        """Test estimation varies by model context window."""
        records = [{"id": i, "data": "x" * 100} for i in range(100)]

        claude_stats = estimate_record_count(records, "claude-sonnet-4-5")
        gpt_stats = estimate_record_count(records, "gpt-4.1")

        # Claude has larger context, so should have more records per chunk
        assert claude_stats["optimal_records_per_chunk"] > gpt_stats["optimal_records_per_chunk"]


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_special_characters_in_text(self):
        """Test handling of special characters."""
        content = "Special chars: 你好 مرحبا שלום\n\t\r"
        chunks = chunk_by_tokens(content, "claude-sonnet-4-5")
        assert len(chunks) >= 1
        assert content in chunks[0]

    def test_unicode_emoji_in_text(self):
        """Test handling of unicode emoji."""
        content = "Hello 👋 World 🌍 Testing 🧪" * 1000
        chunks = chunk_by_tokens(content, "claude-sonnet-4-5", max_chunk_tokens=500)
        assert len(chunks) > 1

    def test_mixed_content_types_in_records(self):
        """Test records with mixed data types."""
        records = [
            {"str": "text", "int": 123, "float": 1.5, "bool": True, "null": None},
            {"list": [1, 2, 3], "nested": {"key": "value"}},
        ]
        chunks = chunk_by_records(records, "claude-sonnet-4-5")
        assert len(chunks) == 1

        parsed = json.loads(chunks[0])
        assert len(parsed) == 2

    def test_very_large_single_record(self):
        """Test single record that's very large."""
        # Single record with 100k characters
        records = [{"id": 1, "data": "x" * 100_000}]
        chunks = chunk_by_records(records, "claude-sonnet-4-5", max_records_per_chunk=1)

        # Should still work, 1 record per chunk
        assert len(chunks) == 1
        parsed = json.loads(chunks[0])
        assert len(parsed) == 1
