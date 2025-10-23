"""REM Database implementation with RocksDB and HNSW."""

import hashlib
from pathlib import Path
from typing import Optional
from uuid import UUID

import hnswlib
import numpy as np
import orjson
import rocksdict

from .index import SecondaryIndex
from .models import Direction, Edge, Entity, Moment, Order, Resource
from .predicates import And, Eq, Or, Query


class REMDatabase:
    """RocksDB-based REM database with vector search."""

    def __init__(
        self,
        tenant_id: str,
        path: str | Path,
        vector_dim: int = 768,
        indexed_fields: list[str] | None = None,
    ):
        """Initialize database for tenant.

        Args:
            tenant_id: Unique tenant identifier
            path: Base path for database storage
            vector_dim: Vector embedding dimension
            indexed_fields: Fields to automatically index for entities/resources
                           Default: ["type", "status"] for common lookups
        """
        self.tenant_id = tenant_id
        self.path = Path(path)
        self.vector_dim = vector_dim

        # Create tenant directory
        self.db_path = self.path / tenant_id
        self.db_path.mkdir(parents=True, exist_ok=True)

        # Open RocksDB via rocksdict (Rust bindings)
        self.db = rocksdict.Rdict(str(self.db_path / "db"))

        # Initialize HNSW index
        self.vector_index: Optional[hnswlib.Index] = None
        self._vector_count = 0

        # Initialize secondary indexes
        self.indexed_fields = indexed_fields or ["type", "status"]
        self.entity_index = SecondaryIndex(self, "entity")
        self.resource_index = SecondaryIndex(self, "resource")

    def _key(self, prefix: str, *parts: str) -> bytes:
        """Generate scoped key."""
        key = f"{prefix}:{self.tenant_id}:{':'.join(parts)}"
        return key.encode()

    def _put(self, key: bytes, value: dict) -> None:
        """Store JSON value."""
        self.db[key] = orjson.dumps(value)

    def _get(self, key: bytes) -> Optional[dict]:
        """Get JSON value."""
        data = self.db.get(key)
        return orjson.loads(data) if data else None

    def _delete(self, key: bytes) -> None:
        """Delete key."""
        del self.db[key]

    def _scan_prefix(self, prefix: bytes) -> list[dict]:
        """Scan all keys with prefix."""
        results = []
        # rocksdict doesn't have iterkeys, use keys() with prefix
        for key in self.db.keys():
            if key.startswith(prefix):
                data = self.db.get(key)
                if data:
                    results.append(orjson.loads(data))
        return results

    # Resource operations
    def create_resource(self, resource: Resource) -> UUID:
        """Create a resource."""
        key = self._key("resource", str(resource.id))
        self._put(key, resource.model_dump(mode="json"))
        return resource.id

    def get_resource(self, resource_id: UUID) -> Optional[Resource]:
        """Get resource by ID."""
        key = self._key("resource", str(resource_id))
        data = self._get(key)
        return Resource(**data) if data else None

    def delete_resource(self, resource_id: UUID) -> None:
        """Delete resource."""
        key = self._key("resource", str(resource_id))
        self._delete(key)

    def query_resources(self, query: Query) -> list[Resource]:
        """Query resources with predicates."""
        # Scan all resources for this tenant
        prefix = self._key("resource")
        resources = [Resource(**data) for data in self._scan_prefix(prefix)]

        # Apply predicate filter
        resources = [r for r in resources if query.predicate.evaluate(r)]

        # Apply sorting
        if query.order_by:
            field, order = query.order_by
            # Get sample to determine type for default
            sample_val = Eq._get_field(resources[0], field) if resources else None
            default = type(sample_val)() if sample_val is not None else ""
            resources.sort(
                key=lambda r: Eq._get_field(r, field) if Eq._get_field(r, field) is not None else default,
                reverse=(order == Order.DESC),
            )

        # Apply offset and limit
        if query.offset:
            resources = resources[query.offset :]
        if query.limit:
            resources = resources[: query.limit]

        return resources

    # Entity operations
    def create_entity(self, entity: Entity) -> UUID:
        """Create an entity."""
        key = self._key("entity", str(entity.id))
        self._put(key, entity.model_dump(mode="json"))

        # Update indexes for indexed fields
        for field in self.indexed_fields:
            value = Eq._get_field(entity, field)
            if value is not None:
                self.entity_index.add(entity.id, field, value)

        return entity.id

    def get_entity(self, entity_id: UUID) -> Optional[Entity]:
        """Get entity by ID."""
        key = self._key("entity", str(entity_id))
        data = self._get(key)
        return Entity(**data) if data else None

    def delete_entity(self, entity_id: UUID) -> None:
        """Delete entity."""
        key = self._key("entity", str(entity_id))
        self._delete(key)

    def query_entities(self, query: Query) -> list[Entity]:
        """Query entities with predicates."""
        prefix = self._key("entity")
        entities = [Entity(**data) for data in self._scan_prefix(prefix)]

        # Apply predicate filter
        entities = [e for e in entities if query.predicate.evaluate(e)]

        # Apply sorting
        if query.order_by:
            field, order = query.order_by
            # Get sample to determine type for default
            sample_val = Eq._get_field(entities[0], field) if entities else None
            default = type(sample_val)() if sample_val is not None else ""
            entities.sort(
                key=lambda e: Eq._get_field(e, field) if Eq._get_field(e, field) is not None else default,
                reverse=(order == Order.DESC),
            )

        # Apply offset and limit
        if query.offset:
            entities = entities[query.offset :]
        if query.limit:
            entities = entities[: query.limit]

        return entities

    # Edge operations (entity graph)
    def create_edge(self, edge: Edge) -> None:
        """Create edge between entities."""
        # Store edge with composite key
        key = self._key("edge", str(edge.src_id), str(edge.dst_id), edge.edge_type)
        self._put(key, edge.model_dump(mode="json"))

    def get_edges(
        self, entity_id: UUID, direction: Direction = Direction.OUTGOING
    ) -> list[Edge]:
        """Get edges for entity."""
        edges = []

        if direction in (Direction.OUTGOING, Direction.BOTH):
            # Outgoing edges (src_id matches)
            prefix = self._key("edge", str(entity_id))
            edges.extend([Edge(**data) for data in self._scan_prefix(prefix)])

        if direction in (Direction.INCOMING, Direction.BOTH):
            # Incoming edges (dst_id matches) - requires scan
            # This is inefficient - would need index in production
            prefix = self._key("edge")
            all_edges = [Edge(**data) for data in self._scan_prefix(prefix)]
            edges.extend([e for e in all_edges if e.dst_id == entity_id])

        return edges

    def traverse(
        self,
        start: UUID,
        edge_type: str | None = None,
        direction: Direction = Direction.OUTGOING,
        max_depth: int = 3,
    ) -> list[Entity]:
        """Traverse entity graph."""
        visited = set()
        entities = []
        queue = [(start, 0)]

        while queue:
            entity_id, depth = queue.pop(0)

            if entity_id in visited or depth > max_depth:
                continue

            visited.add(entity_id)
            entity = self.get_entity(entity_id)
            if entity:
                entities.append(entity)

            # Get edges
            edges = self.get_edges(entity_id, direction)
            if edge_type:
                edges = [e for e in edges if e.edge_type == edge_type]

            # Add neighbors to queue
            for edge in edges:
                next_id = edge.dst_id if direction != Direction.INCOMING else edge.src_id
                if next_id not in visited:
                    queue.append((next_id, depth + 1))

        return entities[1:]  # Exclude start entity

    # Moment operations
    def create_moment(self, moment: Moment) -> UUID:
        """Create a moment."""
        key = self._key("moment", str(moment.id))
        self._put(key, moment.model_dump(mode="json"))

        # Create time index
        time_key = self._key("moment_time", moment.timestamp.isoformat(), str(moment.id))
        self._put(time_key, {"moment_id": str(moment.id)})

        return moment.id

    def get_moment(self, moment_id: UUID) -> Optional[Moment]:
        """Get moment by ID."""
        key = self._key("moment", str(moment_id))
        data = self._get(key)
        return Moment(**data) if data else None

    def query_moments(self, query: Query) -> list[Moment]:
        """Query moments with predicates."""
        prefix = self._key("moment")
        moments = [Moment(**data) for data in self._scan_prefix(prefix)]

        # Apply predicate filter
        moments = [m for m in moments if query.predicate.evaluate(m)]

        # Apply sorting
        if query.order_by:
            field, order = query.order_by
            # Get sample to determine type for default
            sample_val = Eq._get_field(moments[0], field) if moments else None
            default = type(sample_val)() if sample_val is not None else ""
            moments.sort(
                key=lambda m: Eq._get_field(m, field) if Eq._get_field(m, field) is not None else default,
                reverse=(order == Order.DESC),
            )

        # Apply offset and limit
        if query.offset:
            moments = moments[query.offset :]
        if query.limit:
            moments = moments[: query.limit]

        return moments

    # Vector operations
    def _init_vector_index(self, max_elements: int = 100000) -> None:
        """Initialize HNSW index."""
        if self.vector_index is not None:
            return

        self.vector_index = hnswlib.Index(space="cosine", dim=self.vector_dim)
        self.vector_index.init_index(max_elements=max_elements, ef_construction=200, M=16)
        self.vector_index.set_ef(50)

    def set_embedding(self, resource_id: UUID, vector: np.ndarray | list[float]) -> None:
        """Set embedding for resource."""
        if isinstance(vector, list):
            vector = np.array(vector, dtype=np.float32)

        if self.vector_index is None:
            self._init_vector_index()

        # Use hash of UUID as HNSW ID
        hnsw_id = int(hashlib.md5(str(resource_id).encode()).hexdigest()[:8], 16)

        # Add to index
        self.vector_index.add_items(vector, hnsw_id)
        self._vector_count += 1

        # Store mapping
        mapping_key = self._key("vector_map", str(hnsw_id))
        self._put(mapping_key, {"resource_id": str(resource_id)})

    def search_similar(
        self, query_vector: np.ndarray | list[float], top_k: int = 10, min_score: float = 0.0
    ) -> list[tuple[Resource, float]]:
        """Search for similar resources by vector."""
        if self.vector_index is None or self._vector_count == 0:
            return []

        if isinstance(query_vector, list):
            query_vector = np.array(query_vector, dtype=np.float32)

        # Search HNSW
        labels, distances = self.vector_index.knn_query(query_vector, k=min(top_k, self._vector_count))

        # Convert distances to similarity scores (cosine)
        # hnswlib returns squared distances for cosine
        scores = 1.0 - distances[0]

        # Get resources
        results = []
        for hnsw_id, score in zip(labels[0], scores):
            if score < min_score:
                continue

            # Get resource_id from mapping
            mapping_key = self._key("vector_map", str(hnsw_id))
            mapping = self._get(mapping_key)
            if not mapping:
                continue

            resource_id = UUID(mapping["resource_id"])
            resource = self.get_resource(resource_id)
            if resource:
                results.append((resource, float(score)))

        return results

    def search_hybrid(
        self,
        query_vector: np.ndarray | list[float],
        query: Query,
        top_k: int = 50,
        min_score: float = 0.7,
    ) -> list[tuple[Resource, float]]:
        """Hybrid search: vector + predicate filtering."""
        # Get vector candidates (more than needed for filtering)
        candidates = self.search_similar(query_vector, top_k=top_k, min_score=min_score)

        # Apply predicate filter
        filtered = [(r, s) for r, s in candidates if query.predicate.evaluate(r)]

        # Apply limit
        if query.limit:
            filtered = filtered[: query.limit]

        return filtered

    def close(self) -> None:
        """Close database."""
        if hasattr(self, 'db'):
            self.db.close()
        self.vector_index = None
