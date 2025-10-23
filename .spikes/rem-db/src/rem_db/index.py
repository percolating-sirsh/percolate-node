"""Secondary indexes for fast predicate queries."""

from typing import Any
from uuid import UUID

import orjson


class SecondaryIndex:
    """Secondary index for fast lookups by field value."""

    def __init__(self, db, index_name: str):
        """Initialize index."""
        self.db = db
        self.index_name = index_name

    def _index_key(self, field: str, value: Any) -> bytes:
        """Generate index key for field=value."""
        # Normalize value for key
        if isinstance(value, bool):
            value_str = "1" if value else "0"
        elif isinstance(value, (int, float)):
            value_str = str(value)
        elif isinstance(value, str):
            value_str = value
        else:
            value_str = str(value)

        return self.db._key(f"idx:{self.index_name}", field, value_str)

    def add(self, entity_id: UUID, field: str, value: Any) -> None:
        """Add entity to index for field=value."""
        key = self._index_key(field, value)

        # Get existing list or create new
        data = self.db._get(key)
        if data:
            ids = data.get("ids", [])
        else:
            ids = []

        # Add ID if not already present
        id_str = str(entity_id)
        if id_str not in ids:
            ids.append(id_str)
            self.db._put(key, {"ids": ids})

    def get(self, field: str, value: Any) -> list[str]:
        """Get all entity IDs where field=value."""
        key = self._index_key(field, value)
        data = self.db._get(key)
        return data.get("ids", []) if data else []

    def remove(self, entity_id: UUID, field: str, value: Any) -> None:
        """Remove entity from index for field=value."""
        key = self._index_key(field, value)
        data = self.db._get(key)

        if data:
            ids = data.get("ids", [])
            id_str = str(entity_id)
            if id_str in ids:
                ids.remove(id_str)
                if ids:
                    self.db._put(key, {"ids": ids})
                else:
                    self.db._delete(key)
