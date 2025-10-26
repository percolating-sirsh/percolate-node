"""Demo script to show pagination behavior without requiring API keys.

This script demonstrates:
1. How chunk_size override forces pagination
2. How different content gets chunked (text vs records)
3. Token estimation and chunk size calculation
"""

from percolate.utils.chunking import (
    chunk_by_records,
    chunk_by_tokens,
    estimate_record_count,
    estimate_tokens,
    get_optimal_chunk_size,
)


def demo_optimal_chunk_sizes():
    """Show optimal chunk sizes for different models."""
    print("\n" + "=" * 60)
    print("OPTIMAL CHUNK SIZES BY MODEL")
    print("=" * 60)

    models = [
        "claude-sonnet-4-5",
        "claude-opus-4",
        "gpt-4.1",
        "gpt-5",
    ]

    for model in models:
        size = get_optimal_chunk_size(model)
        context = {"claude-sonnet-4-5": 200_000, "claude-opus-4": 200_000, "gpt-4.1": 128_000, "gpt-5": 128_000}[
            model
        ]
        print(f"{model:20} | Context: {context:7,} | Usable: {size:7,} | Efficiency: {size/context*100:.1f}%")


def demo_text_chunking():
    """Show how text gets chunked with different chunk sizes."""
    print("\n" + "=" * 60)
    print("TEXT CHUNKING WITH FORCED SMALL CHUNK_SIZE")
    print("=" * 60)

    content = (
        "Apple and Google are major tech companies. Microsoft dominates enterprise. "
        "Amazon leads in cloud services. Tesla innovates in electric vehicles. "
        "IBM has a long history in computing. Oracle provides database solutions. "
    ) * 3  # Repeat 3x for ~400 tokens

    print(f"\nOriginal content length: {len(content)} characters")
    print(f"Estimated tokens: {estimate_tokens(content, 'claude-sonnet-4-5')}")

    # Show chunking with different sizes
    chunk_sizes = [50, 100, 200, None]  # None = optimal

    for chunk_size in chunk_sizes:
        chunks = chunk_by_tokens(content, "claude-sonnet-4-5", max_chunk_tokens=chunk_size)

        size_label = f"{chunk_size} tokens" if chunk_size else "optimal (158k)"
        print(f"\nChunk size: {size_label}")
        print(f"  → Created {len(chunks)} chunks")

        for i, chunk in enumerate(chunks[:3]):  # Show first 3
            token_count = estimate_tokens(chunk, "claude-sonnet-4-5")
            preview = chunk[:60] + "..." if len(chunk) > 60 else chunk
            print(f"  Chunk {i+1}: {token_count:3} tokens | {preview}")

        if len(chunks) > 3:
            print(f"  ... and {len(chunks) - 3} more chunks")


def demo_record_chunking():
    """Show how records get chunked preserving boundaries."""
    print("\n" + "=" * 60)
    print("RECORD CHUNKING (PRESERVES BOUNDARIES)")
    print("=" * 60)

    # Create sample records
    records = [
        {"id": i, "company": f"Company{i}", "description": f"Description for company {i}" * 10}
        for i in range(50)
    ]

    print(f"\nTotal records: {len(records)}")

    # Get statistics
    stats = estimate_record_count(records, "claude-sonnet-4-5")
    print(f"Estimated total tokens: {stats['total_tokens']:,}")
    print(f"Avg tokens per record: {stats['avg_tokens_per_record']}")
    print(f"Optimal records per chunk: {stats['optimal_records_per_chunk']}")
    print(f"Estimated chunks needed: {stats['estimated_chunks']}")

    # Chunk with forced small size to demonstrate
    print(f"\n--- With forced small chunk size (5 records) ---")
    chunks = chunk_by_records(records, "claude-sonnet-4-5", max_records_per_chunk=5)
    print(f"Created {len(chunks)} chunks")

    import json

    for i, chunk in enumerate(chunks[:3]):
        parsed = json.loads(chunk)
        print(f"Chunk {i+1}: {len(parsed)} records (IDs: {[r['id'] for r in parsed]})")

    if len(chunks) > 3:
        print(f"... and {len(chunks) - 3} more chunks")


def demo_pagination_scenario():
    """Show realistic pagination scenario."""
    print("\n" + "=" * 60)
    print("REALISTIC PAGINATION SCENARIO")
    print("=" * 60)

    # Simulate large document
    large_doc = """
    This is a long document that would exceed context window in production.
    It contains multiple sections with different information.
    """ * 500  # ~50k tokens

    print(f"\nDocument length: {len(large_doc):,} characters")
    token_count = estimate_tokens(large_doc, "claude-sonnet-4-5")
    print(f"Estimated tokens: {token_count:,}")

    # Show what would happen with different models
    models = ["claude-sonnet-4-5", "gpt-4.1"]

    for model in models:
        optimal = get_optimal_chunk_size(model)
        chunks = chunk_by_tokens(large_doc, model)

        print(f"\n{model}:")
        print(f"  Optimal chunk size: {optimal:,} tokens")
        print(f"  Would create: {len(chunks)} chunk(s)")
        print(f"  API calls needed: {len(chunks)}")
        print(f"  Overhead per call: ~2000 tokens (system + schema)")
        print(f"  Total tokens with overhead: {token_count + (len(chunks) * 2000):,}")

        if len(chunks) == 1:
            print(f"  ✓ Fits in single chunk - no pagination needed")
        else:
            print(f"  → Pagination required - {len(chunks)} parallel API calls")


def demo_forced_pagination_for_testing():
    """Show how to force pagination for testing."""
    print("\n" + "=" * 60)
    print("FORCING PAGINATION FOR TESTING")
    print("=" * 60)

    # Small content that normally fits in one chunk
    content = "Apple Google Microsoft Amazon Tesla"

    print(f"\nContent: '{content}'")
    print(f"Tokens: {estimate_tokens(content, 'claude-sonnet-4-5')}")

    # Without override - fits in one chunk
    normal_chunks = chunk_by_tokens(content, "claude-sonnet-4-5")
    print(f"\nWithout chunk_size override:")
    print(f"  → {len(normal_chunks)} chunk (no pagination)")

    # With override - forced into multiple chunks
    forced_chunks = chunk_by_tokens(content, "claude-sonnet-4-5", max_chunk_tokens=10)
    print(f"\nWith chunk_size=10 override:")
    print(f"  → {len(forced_chunks)} chunks (forced pagination)")
    for i, chunk in enumerate(forced_chunks):
        print(f"  Chunk {i+1}: '{chunk.strip()}'")

    print(f"\n✓ This allows testing pagination with small, fast test data!")


def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print("PAGINATION SYSTEM DEMONSTRATION")
    print("=" * 60)
    print("\nThis demo shows chunking behavior WITHOUT making API calls.")
    print("It demonstrates how chunk_size override enables pagination testing.")

    demo_optimal_chunk_sizes()
    demo_text_chunking()
    demo_record_chunking()
    demo_pagination_scenario()
    demo_forced_pagination_for_testing()

    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
    print("\nKey Takeaways:")
    print("1. chunk_size override forces pagination for testing")
    print("2. Text chunking preserves sentence boundaries")
    print("3. Record chunking never splits mid-record")
    print("4. Token estimation enables optimal chunk sizing")
    print("5. Models with larger context windows = fewer API calls")


if __name__ == "__main__":
    main()
