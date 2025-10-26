"""REM database singleton for percolate."""

import os
from pathlib import Path

from loguru import logger

# Import will fail until percolate-rocks is installed
try:
    from rem_db import Database
    REM_DB_AVAILABLE = True
except ImportError:
    logger.warning("percolate-rocks not installed - session persistence disabled")
    Database = None  # type: ignore
    REM_DB_AVAILABLE = False


# Module-level singleton (avoid lru_cache caching exceptions)
_database_instance = None
_database_initialized = False


def get_database(
    db_path: str | None = None,
    tenant_id: str = "default"
) -> "Database | None":
    """Get or create REM database singleton.

    Args:
        db_path: Optional database path override (defaults to settings)
        tenant_id: Tenant identifier for data isolation

    Returns:
        Database instance or None if percolate-rocks not available

    Example:
        >>> db = get_database()
        >>> if db:
        ...     db.insert("sessions", {"session_id": "123", "data": "..."})
    """
    global _database_instance, _database_initialized

    # Return cached instance or None
    if _database_initialized:
        return _database_instance

    if not REM_DB_AVAILABLE:
        _database_initialized = True
        return None

    if db_path is None:
        # Try environment variable first, then default
        db_path = os.getenv("P8_DB_PATH", os.path.expanduser("~/.p8/db"))

    # Ensure parent directory exists
    db_dir = Path(db_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Set environment variables for Database to use
        os.environ["P8_DB_PATH"] = str(db_path)
        os.environ["P8_TENANT_ID"] = tenant_id

        logger.info(f"Initializing REM database at {db_path} for tenant {tenant_id}")
        # Database() uses environment variables (P8_DB_PATH, P8_TENANT_ID)
        _database_instance = Database()
        _database_initialized = True
        return _database_instance
    except Exception as e:
        logger.error(f"Failed to initialize REM database: {e}")
        _database_initialized = True
        return None
