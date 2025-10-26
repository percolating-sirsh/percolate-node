"""Agent pagination for processing large inputs.

Chunks data, runs agent on each chunk, merges results.
Agent already has system prompt - we just paginate the input data.

Usage:
    agent = await create_agent(...)  # Has system prompt in schema

    result = await paginated_request(
        agent=agent,
        content=large_document,
        config=PaginationConfig(merge_strategy="merge", chunk_size=50)
    )
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Literal

from loguru import logger
from pydantic import BaseModel
from pydantic_ai import Agent

from percolate.utils.chunking import (
    chunk_by_records,
    chunk_by_tokens,
    is_list_content,
)

MergeStrategy = Literal["concat", "merge", "first", "last", "custom"]


class PaginationConfig(BaseModel):
    """Configuration for pagination."""

    chunk_size: int | None = None
    merge_strategy: MergeStrategy = "last"
    custom_merge_fn: Callable[[list[Any]], Any] | None = None
    parallel: bool = True
    include_chunk_metadata: bool = True
    model_name: str = "claude-sonnet-4-5"


async def paginated_request(
    agent: Agent,
    content: str | list,
    config: PaginationConfig,
) -> Any:
    """Execute agent with automatic pagination.

    The agent already has its system prompt and schema. This function
    just chunks the input data, runs the agent on each chunk, and merges results.

    Args:
        agent: Pre-configured agent with model and schema
        content: Large input (string or list of records)
        config: Pagination configuration

    Returns:
        Merged result according to merge strategy

    Example:
        >>> agent = await create_agent(...)  # System prompt in schema
        >>> result = await paginated_request(
        ...     agent=agent,
        ...     content=large_doc,
        ...     config=PaginationConfig(merge_strategy="merge", chunk_size=50)
        ... )
    """
    # Validate
    if config.merge_strategy == "custom" and not config.custom_merge_fn:
        raise ValueError("custom merge strategy requires custom_merge_fn")

    # Chunk content
    if is_list_content(content):
        logger.info("Using record-based chunking")
        if isinstance(content, str):
            content = json.loads(content)
        chunks = chunk_by_records(content, config.model_name, max_records_per_chunk=config.chunk_size)  # type: ignore
    else:
        logger.info("Using token-based chunking")
        if isinstance(content, list):
            content = json.dumps(content, indent=2)
        chunks = chunk_by_tokens(content, config.model_name, max_chunk_tokens=config.chunk_size)  # type: ignore

    logger.info(f"Split into {len(chunks)} chunks")

    # Single chunk - no pagination needed
    if len(chunks) == 1:
        logger.info("Single chunk, executing directly")
        result = await agent.run(chunks[0])
        return result.data

    # Execute chunks
    if config.parallel:
        logger.info(f"Executing {len(chunks)} chunks in parallel")
        tasks = [
            _execute_chunk(agent, chunk, i, len(chunks), config.include_chunk_metadata)
            for i, chunk in enumerate(chunks)
        ]
        results = await asyncio.gather(*tasks)
    else:
        logger.info(f"Executing {len(chunks)} chunks sequentially")
        results = []
        for i, chunk in enumerate(chunks):
            result = await _execute_chunk(agent, chunk, i, len(chunks), config.include_chunk_metadata)
            results.append(result)

    # Merge results
    logger.info(f"Merging {len(results)} results with strategy={config.merge_strategy}")
    return _merge_results(results, config.merge_strategy, config.custom_merge_fn)


async def _execute_chunk(
    agent: Agent,
    chunk: str,
    chunk_index: int,
    total_chunks: int,
    include_metadata: bool,
) -> Any:
    """Execute agent on single chunk."""
    if include_metadata:
        chunk_input = f"[Processing part {chunk_index + 1}/{total_chunks}]\n\n{chunk}"
    else:
        chunk_input = chunk

    logger.debug(f"Executing chunk {chunk_index + 1}/{total_chunks}")
    result = await agent.run(chunk_input)
    logger.debug(f"Completed chunk {chunk_index + 1}/{total_chunks}")
    return result.data


def _merge_results(
    results: list[Any],
    strategy: MergeStrategy,
    custom_fn: Callable[[list[Any]], Any] | None = None,
) -> Any:
    """Merge paginated results."""
    if not results:
        return None

    if strategy == "first":
        return results[0]
    if strategy == "last":
        return results[-1]
    if strategy == "concat":
        return results
    if strategy == "merge":
        return _merge_recursive(results)
    if strategy == "custom":
        if not custom_fn:
            raise ValueError("custom strategy requires custom_merge_fn")
        return custom_fn(results)

    raise ValueError(f"Unknown merge strategy: {strategy}")


def _merge_recursive(results: list[Any]) -> Any:
    """Merge structured outputs recursively.

    Rules:
    - List fields: Extend all items
    - Dict fields: Recursive merge
    - Primitives: Keep first value
    """
    if not results:
        return None

    first = results[0]
    is_pydantic = isinstance(first, BaseModel)

    if is_pydantic:
        dict_results = [r.model_dump() if isinstance(r, BaseModel) else r for r in results]
        merged_dict = _merge_dicts(dict_results)
        return type(first)(**merged_dict)

    if isinstance(first, dict):
        return _merge_dicts(results)

    return first


def _merge_dicts(dicts: list[dict]) -> dict:
    """Merge list of dicts."""
    if not dicts:
        return {}

    merged = {}
    all_keys = set()
    for d in dicts:
        all_keys.update(d.keys())

    for key in all_keys:
        values = [d.get(key) for d in dicts if key in d]
        if not values:
            continue

        first_value = values[0]

        # List fields: extend
        if isinstance(first_value, list):
            merged_list = []
            for v in values:
                if isinstance(v, list):
                    merged_list.extend(v)
            merged[key] = merged_list

        # Dict fields: recursive merge
        elif isinstance(first_value, dict):
            merged[key] = _merge_dicts([v for v in values if isinstance(v, dict)])

        # Primitives: keep first
        else:
            merged[key] = first_value

    return merged
