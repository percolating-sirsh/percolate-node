"""Token-aware chunking utilities for handling large inputs.

This module provides utilities for splitting large text or record collections
into chunks that fit within model context windows. Uses tiktoken for accurate
token counting and supports both text-based and record-based chunking.

Key features:
- Accurate token counting using tiktoken (with fallback)
- Context window management with overhead accounting
- Record-boundary preservation (never splits records)
- Optimal chunk size calculation per model

Usage:
    # Text chunking
    chunks = chunk_by_tokens(long_text, "claude-sonnet-4-5")

    # Record chunking
    records = [{"id": 1, "data": "..."}, ...]
    chunks = chunk_by_records(records, "claude-sonnet-4-5")
"""

from __future__ import annotations

import json
from typing import Any, Optional

from loguru import logger

# Model context windows (in tokens)
MODEL_CONTEXT_WINDOWS = {
    # Anthropic
    "claude-sonnet-4-5": 200_000,
    "claude-sonnet-4-5-20250929": 200_000,
    "claude-opus-4": 200_000,
    "claude-opus-4-20250514": 200_000,
    "claude-haiku-4-5": 200_000,
    "claude-haiku-4-5-20251001": 200_000,
    # OpenAI
    "gpt-4.1": 128_000,
    "gpt-5": 128_000,
    "gpt-4o": 128_000,
    # Google
    "gemini-3-ultra": 1_000_000,
    "gemini-3-pro": 1_000_000,
    "gemini-3-flash": 1_000_000,
}

# Overhead estimates (in tokens)
DEFAULT_SYSTEM_PROMPT_OVERHEAD = 1500
DEFAULT_OUTPUT_SCHEMA_OVERHEAD = 500
DEFAULT_RESPONSE_BUFFER_RATIO = 0.2
JSON_RECORD_OVERHEAD = 5


def get_optimal_chunk_size(
    model_name: str,
    overhead_tokens: int = DEFAULT_SYSTEM_PROMPT_OVERHEAD + DEFAULT_OUTPUT_SCHEMA_OVERHEAD,
    response_buffer_ratio: float = DEFAULT_RESPONSE_BUFFER_RATIO,
) -> int:
    """Calculate optimal chunk size for a model.

    Accounts for:
    - Model context window
    - System prompt and schema overhead
    - Response buffer space

    Args:
        model_name: LLM model identifier
        overhead_tokens: System prompt + schema overhead (default: 2000)
        response_buffer_ratio: Reserve % for response (default: 20%)

    Returns:
        Maximum tokens per chunk

    Example:
        >>> get_optimal_chunk_size("claude-sonnet-4-5")
        158400  # 200k - 2000 - (200k * 0.2)
    """
    # Get context window for model (default to conservative 100k if unknown)
    context_window = MODEL_CONTEXT_WINDOWS.get(model_name, 100_000)

    # Calculate usable space
    response_buffer = int(context_window * response_buffer_ratio)
    usable_tokens = context_window - overhead_tokens - response_buffer

    logger.debug(
        f"Model {model_name}: context={context_window}, "
        f"overhead={overhead_tokens}, buffer={response_buffer}, "
        f"usable={usable_tokens}"
    )

    return usable_tokens


def estimate_tokens(content: str, model_name: str) -> int:
    """Estimate token count for content.

    Uses tiktoken for accurate counting with fallback to character-based
    estimation if tiktoken is not available.

    Args:
        content: Text to estimate
        model_name: Model for counting

    Returns:
        Estimated token count

    Example:
        >>> estimate_tokens("Hello world", "claude-sonnet-4-5")
        2
    """
    try:
        import tiktoken

        # Map model names to tiktoken encodings
        # Claude models use cl100k_base encoding (same as GPT-4)
        encoding_map = {
            "claude-sonnet-4-5": "cl100k_base",
            "claude-opus-4": "cl100k_base",
            "claude-haiku-4-5": "cl100k_base",
            "gpt-4.1": "cl100k_base",
            "gpt-5": "cl100k_base",
            "gpt-4o": "cl100k_base",
        }

        encoding_name = encoding_map.get(model_name, "cl100k_base")
        encoding = tiktoken.get_encoding(encoding_name)
        return len(encoding.encode(content))
    except ImportError:
        # Fallback to character-based estimation (~4 chars per token)
        logger.warning("tiktoken not available, using character-based estimation")
        return len(content) // 4
    except Exception as e:
        logger.warning(f"Token estimation failed: {e}, using character-based estimation")
        return len(content) // 4


def chunk_by_tokens(
    content: str,
    model_name: str,
    max_chunk_tokens: Optional[int] = None,
) -> list[str]:
    """Split content by token boundaries.

    Uses tiktoken for accurate token counting and splits content into chunks
    that fit within the specified token limit. Attempts to split on sentence
    boundaries where possible to maintain coherence.

    Args:
        content: Text to chunk
        model_name: Model for token counting
        max_chunk_tokens: Override optimal chunk size

    Returns:
        List of text chunks, each within token limit

    Example:
        >>> chunks = chunk_by_tokens(long_text, "claude-sonnet-4-5")
        >>> all(estimate_tokens(c, "claude-sonnet-4-5") <= get_optimal_chunk_size("claude-sonnet-4-5") for c in chunks)
        True
    """
    # Calculate chunk size if not provided
    chunk_size = max_chunk_tokens or get_optimal_chunk_size(model_name)

    # Check if content fits in single chunk
    total_tokens = estimate_tokens(content, model_name)
    if total_tokens <= chunk_size:
        logger.debug(f"Content fits in single chunk ({total_tokens} tokens)")
        return [content]

    logger.info(f"Splitting content ({total_tokens} tokens) into chunks of {chunk_size} tokens")

    chunks = []
    current_chunk = ""
    current_tokens = 0

    # Split on sentences for better coherence
    sentences = _split_into_sentences(content)

    for sentence in sentences:
        sentence_tokens = estimate_tokens(sentence, model_name)

        # If single sentence exceeds chunk size, split it further
        if sentence_tokens > chunk_size:
            # Save current chunk if non-empty
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
                current_tokens = 0

            # Split long sentence by character chunks
            char_chunks = _split_by_characters(sentence, chunk_size, model_name)
            chunks.extend(char_chunks[:-1])

            # Start new chunk with last piece
            current_chunk = char_chunks[-1]
            current_tokens = estimate_tokens(current_chunk, model_name)

        # Check if adding this sentence would exceed limit
        elif current_tokens + sentence_tokens > chunk_size:
            # Save current chunk and start new one
            chunks.append(current_chunk.strip())
            current_chunk = sentence
            current_tokens = sentence_tokens
        else:
            # Add sentence to current chunk
            current_chunk += (" " if current_chunk else "") + sentence
            current_tokens += sentence_tokens

    # Add final chunk if non-empty
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    logger.info(f"Created {len(chunks)} chunks")
    return chunks


def _split_into_sentences(text: str) -> list[str]:
    """Split text into sentences on common sentence boundaries.

    Args:
        text: Text to split

    Returns:
        List of sentences
    """
    # Simple sentence splitting on common terminators
    # This is a basic approach - could be enhanced with NLTK or spacy
    import re

    # Split on . ! ? followed by space and capital letter
    sentences = re.split(r'([.!?]+)\s+(?=[A-Z])', text)

    # Recombine punctuation with sentences
    result = []
    for i in range(0, len(sentences) - 1, 2):
        if i + 1 < len(sentences):
            result.append(sentences[i] + sentences[i + 1])
        else:
            result.append(sentences[i])

    # Add last part if exists
    if len(sentences) % 2 == 1:
        result.append(sentences[-1])

    return [s for s in result if s.strip()]


def _split_by_characters(text: str, max_tokens: int, model_name: str) -> list[str]:
    """Split text by character boundaries when sentence splitting isn't enough.

    Args:
        text: Text to split
        max_tokens: Maximum tokens per chunk
        model_name: Model for token counting

    Returns:
        List of text chunks
    """
    # Estimate characters per token (rough approximation)
    avg_chars_per_token = len(text) / estimate_tokens(text, model_name)
    chunk_chars = int(max_tokens * avg_chars_per_token * 0.9)  # 90% to be safe

    chunks = []
    for i in range(0, len(text), chunk_chars):
        chunk = text[i:i + chunk_chars]
        chunks.append(chunk)

    return chunks


def is_list_content(content: str | list) -> bool:
    """Detect if content is a list structure.

    Args:
        content: Content to check

    Returns:
        True if content is a list or JSON array string

    Example:
        >>> is_list_content([{"id": 1}, {"id": 2}])
        True
        >>> is_list_content('[{"id": 1}]')
        True
        >>> is_list_content("plain text")
        False
    """
    if isinstance(content, list):
        return True

    # Try parsing as JSON array
    if isinstance(content, str):
        try:
            parsed = json.loads(content)
            return isinstance(parsed, list)
        except (json.JSONDecodeError, ValueError):
            return False

    return False


def chunk_by_records(
    content: list[dict[str, Any]],
    model_name: str,
    max_records_per_chunk: Optional[int] = None,
) -> list[str]:
    """Chunk list by record boundaries (never splits records).

    Calculates optimal record count based on:
    - Average tokens per record (sampled from first 10)
    - JSON syntax overhead per record
    - Model context window

    Args:
        content: List of records (dicts)
        model_name: Model for token estimation
        max_records_per_chunk: Override calculated optimal

    Returns:
        List of JSON string chunks (complete records only)

    Example:
        >>> records = [{"id": 1, "data": "..."}, {"id": 2, "data": "..."}]
        >>> chunks = chunk_by_records(records, "claude-sonnet-4-5")
        >>> len(chunks) >= 1
        True
    """
    if not content:
        return []

    # Calculate optimal records per chunk
    if max_records_per_chunk is None:
        stats = estimate_record_count(content, model_name)
        max_records_per_chunk = stats["optimal_records_per_chunk"]

    logger.info(f"Chunking {len(content)} records into chunks of {max_records_per_chunk} records")

    # Split into chunks
    chunks = []
    for i in range(0, len(content), max_records_per_chunk):
        chunk_records = content[i:i + max_records_per_chunk]
        chunk_json = json.dumps(chunk_records, indent=2)
        chunks.append(chunk_json)

    logger.info(f"Created {len(chunks)} record chunks")
    return chunks


def estimate_record_count(
    content: list[dict[str, Any]],
    model_name: str,
) -> dict[str, int]:
    """Provide chunking statistics for records.

    Samples first 10 records to estimate average token count per record,
    then calculates optimal chunking parameters.

    Args:
        content: List of records
        model_name: Model for token estimation

    Returns:
        Dict with chunking statistics:
        - total_records: Total number of records
        - total_tokens: Estimated total tokens
        - avg_tokens_per_record: Average tokens per record
        - optimal_records_per_chunk: Recommended records per chunk
        - estimated_chunks: Estimated number of chunks needed

    Example:
        >>> records = [{"id": i, "data": "x" * 100} for i in range(100)]
        >>> stats = estimate_record_count(records, "claude-sonnet-4-5")
        >>> stats["total_records"]
        100
    """
    if not content:
        return {
            "total_records": 0,
            "total_tokens": 0,
            "avg_tokens_per_record": 0,
            "optimal_records_per_chunk": 0,
            "estimated_chunks": 0,
        }

    # Sample first 10 records to estimate average size
    sample_size = min(10, len(content))
    sample = content[:sample_size]
    sample_json = json.dumps(sample, indent=2)
    sample_tokens = estimate_tokens(sample_json, model_name)

    # Calculate average tokens per record (including JSON overhead)
    avg_tokens_per_record = sample_tokens // sample_size + JSON_RECORD_OVERHEAD

    # Calculate total tokens
    total_tokens = avg_tokens_per_record * len(content)

    # Calculate optimal records per chunk
    chunk_size = get_optimal_chunk_size(model_name)
    optimal_records_per_chunk = max(1, chunk_size // avg_tokens_per_record)

    # Calculate estimated chunks
    estimated_chunks = (len(content) + optimal_records_per_chunk - 1) // optimal_records_per_chunk

    stats = {
        "total_records": len(content),
        "total_tokens": total_tokens,
        "avg_tokens_per_record": avg_tokens_per_record,
        "optimal_records_per_chunk": optimal_records_per_chunk,
        "estimated_chunks": estimated_chunks,
    }

    logger.debug(f"Record stats: {stats}")
    return stats
