"""Percolate-Rocks Python bindings and protocol models.

This package provides:
- REM database Python bindings (PyO3)
- Parse protocol models (Source of Truth)
- Schema extensions
"""

__version__ = "0.1.0"

# Parse protocol models are exported for external use
from percolate_rocks.parse import (
    ParseJob,
    ParseResult,
    ParseStatus,
    ParseStorage,
    ParseContent,
    ParseQuality,
    ParseError,
    StorageStrategy,
    QualityFlag,
)

__all__ = [
    "ParseJob",
    "ParseResult",
    "ParseStatus",
    "ParseStorage",
    "ParseContent",
    "ParseQuality",
    "ParseError",
    "StorageStrategy",
    "QualityFlag",
]
