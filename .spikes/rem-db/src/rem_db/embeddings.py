"""Embedding provider registry and configuration.

## Dual embedding system

REM Database supports two embedding fields per entity:
- `embedding`: Default vector (fast, lower-dimensional)
- `embedding_alt`: Alternative vector (higher quality, optional)

This allows cost/quality tradeoffs - use default for most queries,
fallback to alt for precision when needed.

## Provider registry

Centralized mapping of embedding models to:
- Dimension count (384, 768, 1536, 3072, etc.)
- Library (sentence-transformers, openai, cohere)
- Distance metric (cosine, inner_product)
- Normalization status

## Supported providers

### Sentence Transformers (local inference, free)
- all-MiniLM-L6-v2: 384-dim, fast, general purpose
- all-mpnet-base-v2: 768-dim, high quality
- paraphrase-MiniLM-L6-v2: 384-dim, paraphrase detection

### OpenAI (API, $$$)
- text-embedding-3-small: 1536-dim
- text-embedding-3-large: 3072-dim
- text-embedding-ada-002: 1536-dim (legacy)

### Cohere (API, $$)
- embed-english-v3.0: 1024-dim
- embed-multilingual-v3.0: 1024-dim

## Usage

```python
from rem_db.embeddings import get_embedding_dimension, get_provider_config

# Get dimension for a provider
dim = get_embedding_dimension("all-MiniLM-L6-v2")  # 384

# Get full config
config = get_provider_config("all-mpnet-base-v2")
print(config.metric)  # "cosine"
print(config.normalized)  # False
```

## Design rationale

1. **Centralized registry**: Single source of truth for dimensions
2. **Model-specified dimensions**: Database reads from schema metadata
3. **Provider metadata**: Library, metric, normalization in one place
4. **Type safety**: Enum for provider names, NamedTuple for config
5. **Extensible**: Easy to add new providers
"""

from enum import Enum
from typing import NamedTuple


class EmbeddingProvider(str, Enum):
    """Supported embedding providers."""

    # Sentence Transformers
    ALL_MINILM_L6_V2 = "all-MiniLM-L6-v2"           # 384-dim, fast, general purpose
    ALL_MPNET_BASE_V2 = "all-mpnet-base-v2"         # 768-dim, high quality
    PARAPHRASE_MINILM_L6_V2 = "paraphrase-MiniLM-L6-v2"  # 384-dim, paraphrase detection

    # OpenAI
    TEXT_EMBEDDING_3_SMALL = "text-embedding-3-small"  # 1536-dim
    TEXT_EMBEDDING_3_LARGE = "text-embedding-3-large"  # 3072-dim
    TEXT_EMBEDDING_ADA_002 = "text-embedding-ada-002"  # 1536-dim

    # Cohere
    EMBED_ENGLISH_V3 = "embed-english-v3.0"         # 1024-dim
    EMBED_MULTILINGUAL_V3 = "embed-multilingual-v3.0"  # 1024-dim


class ProviderConfig(NamedTuple):
    """Embedding provider configuration."""

    name: str
    dimension: int
    library: str  # "sentence-transformers", "openai", "cohere"
    description: str
    metric: str  # "cosine" or "inner_product"
    normalized: bool  # Whether embeddings are pre-normalized


# Central registry of embedding providers with their dimensions
EMBEDDING_PROVIDERS: dict[str, ProviderConfig] = {
    # Sentence Transformers (local inference)
    "all-MiniLM-L6-v2": ProviderConfig(
        name="all-MiniLM-L6-v2",
        dimension=384,
        library="sentence-transformers",
        description="Fast and efficient, general purpose embeddings",
        metric="cosine",
        normalized=False
    ),
    "all-mpnet-base-v2": ProviderConfig(
        name="all-mpnet-base-v2",
        dimension=768,
        library="sentence-transformers",
        description="High quality general purpose embeddings",
        metric="cosine",
        normalized=False
    ),
    "paraphrase-MiniLM-L6-v2": ProviderConfig(
        name="paraphrase-MiniLM-L6-v2",
        dimension=384,
        library="sentence-transformers",
        description="Optimized for paraphrase detection and semantic similarity",
        metric="cosine",
        normalized=False
    ),

    # OpenAI (API-based) - Pre-normalized, use inner_product
    "text-embedding-3-small": ProviderConfig(
        name="text-embedding-3-small",
        dimension=1536,
        library="openai",
        description="OpenAI's efficient embedding model",
        metric="inner_product",
        normalized=True
    ),
    "text-embedding-3-large": ProviderConfig(
        name="text-embedding-3-large",
        dimension=3072,
        library="openai",
        description="OpenAI's highest quality embedding model",
        metric="inner_product",
        normalized=True
    ),
    "text-embedding-ada-002": ProviderConfig(
        name="text-embedding-ada-002",
        dimension=1536,
        library="openai",
        description="OpenAI's previous generation embedding model",
        metric="inner_product",
        normalized=True
    ),

    # Cohere (API-based)
    "embed-english-v3.0": ProviderConfig(
        name="embed-english-v3.0",
        dimension=1024,
        library="cohere",
        description="Cohere's English embedding model v3",
        metric="cosine",
        normalized=False
    ),
    "embed-multilingual-v3.0": ProviderConfig(
        name="embed-multilingual-v3.0",
        dimension=1024,
        library="cohere",
        description="Cohere's multilingual embedding model v3",
        metric="cosine",
        normalized=False
    ),
}


def get_embedding_dimension(provider: str) -> int:
    """Get embedding dimension for a provider.

    Args:
        provider: Provider name (e.g., "all-MiniLM-L6-v2")

    Returns:
        Embedding dimension

    Raises:
        ValueError: If provider not found

    Example:
        >>> get_embedding_dimension("all-MiniLM-L6-v2")
        384
    """
    if provider not in EMBEDDING_PROVIDERS:
        raise ValueError(
            f"Unknown embedding provider: {provider}. "
            f"Available: {list(EMBEDDING_PROVIDERS.keys())}"
        )
    return EMBEDDING_PROVIDERS[provider].dimension


def get_provider_config(provider: str) -> ProviderConfig:
    """Get full configuration for a provider.

    Args:
        provider: Provider name

    Returns:
        Provider configuration

    Raises:
        ValueError: If provider not found
    """
    if provider not in EMBEDDING_PROVIDERS:
        raise ValueError(
            f"Unknown embedding provider: {provider}. "
            f"Available: {list(EMBEDDING_PROVIDERS.keys())}"
        )
    return EMBEDDING_PROVIDERS[provider]


def list_providers() -> list[str]:
    """List all available embedding providers."""
    return list(EMBEDDING_PROVIDERS.keys())


def normalize_embedding(embedding: list[float]) -> list[float]:
    """Normalize embedding to unit length for consistent distance metrics.

    Args:
        embedding: Raw embedding vector

    Returns:
        Normalized embedding (length 1)

    Example:
        >>> emb = [1.0, 2.0, 3.0]
        >>> norm_emb = normalize_embedding(emb)
        >>> import math
        >>> math.isclose(sum(x*x for x in norm_emb), 1.0)
        True
    """
    import math

    norm = math.sqrt(sum(x * x for x in embedding))
    if norm == 0:
        return embedding
    return [x / norm for x in embedding]
