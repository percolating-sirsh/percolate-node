"""REM Database implementation with RocksDB and HNSW."""

import hashlib
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Type
from uuid import UUID, uuid4

import hnswlib
import numpy as np
import orjson
import rocksdict
from pydantic import BaseModel

from .embeddings import get_embedding_dimension, get_provider_config
from .index import SecondaryIndex
from .llm_query_builder import QueryBuilder, QueryResult
from .models import Agent, Direction, Edge, Entity, Message, Moment, Order, Resource, Session
from .predicates import And, Eq, Or, Query
from .schema import MCPTool, Schema
from .sql import SQLParser
from .worker import BackgroundWorker, Task, TaskType


class REMDatabase:
    """RocksDB-based REM database with vector search."""

    def __init__(
        self,
        tenant_id: str,
        path: str | Path,
        indexed_fields: list[str] | None = None,
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        """Initialize database for tenant.

        Args:
            tenant_id: Unique tenant identifier
            path: Base path for database storage
            indexed_fields: Fields to automatically index for entities/resources
                           Default: ["type", "status"] for common lookups
            embedding_model: Default embedding model (used for 'embedding' field)
        """
        self.tenant_id = tenant_id
        self.path = Path(path)

        # Initialize embedding model
        self._embedding_model = None
        self.embedding_dim = get_embedding_dimension(embedding_model)

        try:
            from sentence_transformers import SentenceTransformer
            self._embedding_model = SentenceTransformer(embedding_model)
        except ImportError:
            print(f"Warning: sentence-transformers not installed, auto-embedding disabled")
        except Exception as e:
            print(f"Warning: Failed to load embedding model: {e}")

        # Create tenant directory
        self.db_path = self.path / tenant_id
        self.db_path.mkdir(parents=True, exist_ok=True)

        # Open RocksDB via rocksdict (Rust bindings)
        self.db = rocksdict.Rdict(str(self.db_path / "db"))

        # Initialize HNSW index (for default 'embedding' field only)
        self.vector_index: Optional[hnswlib.Index] = None
        self._vector_count = 0
        self._index_path = self.db_path / "vector_index.hnsw"
        self._pending_embeddings: dict[UUID, list[float]] = {}  # Cache for async embeddings
        self._embedding_lock = threading.Lock()

        # Initialize background worker
        self.worker = BackgroundWorker()
        self.worker.start()

        # Initialize secondary indexes
        self.indexed_fields = indexed_fields or ["type", "status"]
        self.entity_index = SecondaryIndex(self, "entity")
        self.resource_index = SecondaryIndex(self, "resource")

        # Schema registry (in-memory cache + RocksDB storage)
        self._schemas: dict[str, Schema] = {}
        self._schemas_by_category: dict[str, list[str]] = {
            "system": [],
            "agents": [],
            "public": [],
            "user": []
        }
        self._load_schemas()
        self._register_builtin_schemas()

        # WAL (Write-Ahead Log) support for replication
        self._wal_seq = self._load_wal_seq()
        self._wal: list[tuple[int, dict]] = []  # In-memory WAL: [(seq_num, entry)]
        self._wal_lock = threading.Lock()

        # Load existing vector index if present (in background)
        self._load_vector_index_async()

    def close(self, wait: bool = True, timeout: float = 5.0) -> None:
        """Close database and stop background worker.

        Args:
            wait: Wait for pending tasks to complete
            timeout: Max seconds to wait for worker
        """
        if wait:
            self.worker.wait_idle(timeout=timeout)

        self.worker.stop(timeout=timeout)

    def wait_for_worker(self, timeout: float = 10.0) -> bool:
        """Wait for background worker to finish all tasks.

        Args:
            timeout: Max seconds to wait

        Returns:
            True if worker is idle, False if timeout
        """
        return self.worker.wait_idle(timeout=timeout)

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

    # Schema registry methods
    def _load_schemas(self) -> None:
        """Load schemas from RocksDB into memory."""
        prefix = self._key("schema")
        for data in self._scan_prefix(prefix):
            schema = Schema(**data)
            self._schemas[schema.name] = schema
            if schema.category not in self._schemas_by_category:
                self._schemas_by_category[schema.category] = []
            if schema.name not in self._schemas_by_category[schema.category]:
                self._schemas_by_category[schema.category].append(schema.name)

    def _generate_embedding(self, text: str) -> Optional[list[float]]:
        """Generate embedding for text using default model (sync).

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None if model unavailable
        """
        if not self._embedding_model:
            return None

        try:
            emb = self._embedding_model.encode(text, convert_to_numpy=True)
            return emb.tolist()
        except Exception as e:
            print(f"Warning: Failed to generate embedding: {e}")
            return None

    def _generate_embedding_async(
        self, text: str, entity_id: UUID, callback: Optional[callable] = None
    ) -> None:
        """Generate embedding for text in background.

        Args:
            text: Text to embed
            entity_id: Entity ID to associate with embedding
            callback: Optional callback(entity_id, embedding) when done
        """
        if not self._embedding_model:
            return

        def default_callback(ent_id: UUID, embedding: list[float]) -> None:
            """Default callback - store in pending cache."""
            with self._embedding_lock:
                self._pending_embeddings[ent_id] = embedding

        task = Task(
            type=TaskType.GENERATE_EMBEDDING,
            entity_id=entity_id,
            payload={
                "text": text,
                "model": self._embedding_model,
                "entity_id": entity_id
            },
            callback=callback or default_callback
        )
        self.worker.submit(task)

    def _register_builtin_schemas(self) -> None:
        """Register built-in system schemas (Resource, Agent, Session, Message)."""
        builtins = [
            ("resources", Resource),
            ("agents", Agent),
            ("sessions", Session),
            ("messages", Message),
        ]

        for name, model in builtins:
            if name not in self._schemas:
                self.register_schema(
                    name=name,
                    model=model,
                    description=model.__doc__ or f"{name.capitalize()} entity"
                )

    def register_schema(
        self,
        name: str,
        model: Type[BaseModel],
        description: str = "",
        system_prompt: Optional[str] = None,
        indexed_fields: Optional[list[str]] = None,
        mcp_tools: Optional[list[MCPTool]] = None,
    ) -> Schema:
        """Register a Pydantic model as a schema (table).

        Args:
            name: Schema/table name
            model: Pydantic model class
            description: Rich description (agent-let context)
            system_prompt: Agent-let system prompt for this entity type
            indexed_fields: Fields to create indexes on
            mcp_tools: MCP tools available for this entity type

        Returns:
            Registered Schema

        Example:
            >>> class Person(BaseModel):
            ...     name: str = Field(description="Full name")
            ...     email: str
            ...     role: str
            ...     team: str
            >>> db.register_schema(
            ...     name="person",
            ...     model=Person,
            ...     description="A person in the organization",
            ...     system_prompt="You are a person entity...",
            ...     indexed_fields=["role", "team"],
            ...     mcp_tools=[MCPTool(name="send_email", description="Send email")]
            ... )
        """
        schema = Schema.from_pydantic(
            name=name,
            model=model,
            description=description,
            system_prompt=system_prompt,
            indexed_fields=indexed_fields,
            mcp_tools=mcp_tools,
        )

        # Store in RocksDB
        key = self._key("schema", name)
        # Don't store pydantic_model (not serializable)
        schema_dict = schema.model_dump(exclude={"pydantic_model"})
        self._put(key, schema_dict)

        # Cache in memory
        self._schemas[name] = schema

        # Update category index
        if schema.category not in self._schemas_by_category:
            self._schemas_by_category[schema.category] = []
        if name not in self._schemas_by_category[schema.category]:
            self._schemas_by_category[schema.category].append(name)

        return schema

    def get_schema(self, name: str) -> Optional[Schema]:
        """Get schema by name."""
        return self._schemas.get(name)

    def list_schemas(self) -> list[str]:
        """List all registered schema names."""
        return list(self._schemas.keys())

    def list_schemas_by_category(self, category: str) -> list[str]:
        """List schema names in a specific category.

        Args:
            category: Category name (system, agents, public, user)

        Returns:
            List of schema names in that category
        """
        return self._schemas_by_category.get(category, [])

    def get_categories(self) -> list[str]:
        """Get all schema categories."""
        return list(self._schemas_by_category.keys())

    def insert(self, table: str, data: dict[str, Any]) -> UUID:
        """Insert entity into table (with schema validation).

        Args:
            table: Table/schema name
            data: Entity data

        Returns:
            Entity ID

        Raises:
            ValueError: If schema doesn't exist or validation fails

        Example:
            >>> db.insert("person", {
            ...     "name": "Alice",
            ...     "email": "alice@example.com",
            ...     "role": "engineer",
            ...     "team": "platform"
            ... })
        """
        schema = self.get_schema(table)
        if not schema:
            raise ValueError(f"Schema '{table}' not registered")

        # Validate against schema
        validated_data = schema.validate_data(data)

        # Auto-generate default embedding for content/description fields
        embed_field = None
        if "content" in validated_data:
            embed_field = "content"
        elif "description" in validated_data:
            embed_field = "description"

        if embed_field and not validated_data.get("embedding"):
            embedding = self._generate_embedding(validated_data[embed_field])
            if embedding:
                validated_data["embedding"] = embedding

        # All tables are stored as entities with type=table_name
        # Schema metadata tells us how to interpret and query each type
        entity = Entity(
            type=table,  # Schema name becomes entity type
            name=validated_data.get("name", f"{table}_{uuid4()}"),  # Use name if present
            properties=validated_data,
            embedding=validated_data.get("embedding"),
        )

        # Create entity (will auto-index based on schema.indexed_fields)
        entity_id = self.create_entity(entity)

        # Store default embedding in vector index if present
        if entity.embedding:
            self.set_embedding(entity_id, entity.embedding, entity_type="entity")

        # Add schema-specific indexes
        for field_name in schema.get_indexed_fields():
            if field_name in validated_data:
                self.entity_index.add(entity_id, field_name, validated_data[field_name])

        return entity_id

    def sql(self, query: str) -> list[dict[str, Any]]:
        """Execute SQL SELECT query.

        Supports:
        - SELECT field1, field2 FROM table
        - SELECT * FROM table
        - WHERE conditions (=, !=, >, <, >=, <=, IN, AND, OR)
        - WHERE embedding.cosine("query text") - semantic search
        - ORDER BY field ASC/DESC
        - LIMIT n
        - OFFSET n

        Args:
            query: SQL SELECT query

        Returns:
            List of result rows as dicts

        Example:
            >>> db.sql("SELECT name, email FROM person WHERE role = 'engineer' ORDER BY name LIMIT 10")
            [{"name": "Alice", "email": "alice@co"}, ...]
            >>> db.sql("SELECT * FROM resources WHERE embedding.cosine('programming') LIMIT 5")
            [{"name": "Python Guide", ...}, ...]
        """
        # Parse SQL
        parsed = SQLParser.parse(query)

        # Get schema
        schema = self.get_schema(parsed.table)
        if not schema:
            raise ValueError(f"Table '{parsed.table}' does not exist")

        # Check for similarity query (cosine or inner_product)
        if parsed.cosine_query:
            field, query_text, similarity_type = parsed.cosine_query

            # Validate field name
            if field != "embedding":
                raise ValueError(
                    f"Similarity search only supported on 'embedding' field, got '{field}'"
                )

            # Generate query embedding
            query_embedding = self._generate_embedding(query_text)
            if not query_embedding:
                raise ValueError("Failed to generate query embedding")

            # Perform vector search
            top_k = parsed.limit or 10
            min_score = 0.0  # Could add score threshold syntax later

            # Note: hnswlib with cosine space works for both cosine and inner_product
            # For normalized vectors, inner_product = cosine similarity
            results = self.search_similar(query_embedding, top_k=top_k, min_score=min_score)

            # Convert to dict format
            output = []
            for entity, score in results:
                if parsed.fields is None:
                    row = entity.properties if hasattr(entity, 'properties') else entity.model_dump()
                    row["_score"] = score  # Add similarity score
                    output.append(row)
                else:
                    row = {}
                    for f in parsed.fields:
                        if hasattr(entity, 'properties'):
                            row[f] = entity.properties.get(f)
                        else:
                            row[f] = getattr(entity, f, None)
                    row["_score"] = score
                    output.append(row)

            return output

        # Regular predicate-based query
        # Filter by entity type (table name) first
        query_obj = Query().filter(Eq("type", parsed.table))

        if parsed.where:
            # Combine table filter with WHERE clause
            query_obj = query_obj.filter(And([Eq("type", parsed.table), parsed.where]))

        if parsed.order_by:
            field, direction = parsed.order_by
            order = Order.ASC if direction == "ASC" else Order.DESC
            query_obj = query_obj.sort(field, order)

        if parsed.limit:
            query_obj = query_obj.take(parsed.limit)

        if parsed.offset:
            query_obj = query_obj.skip(parsed.offset)

        # Execute query - all tables are entities filtered by type
        entities = self.query_entities(query_obj)

        # Project fields (SELECT clause)
        results = []
        for entity in entities:
            if parsed.fields is None:
                # SELECT * - return all properties
                results.append(entity.properties)
            else:
                # SELECT specific fields
                row = {}
                for field in parsed.fields:
                    row[field] = entity.properties.get(field)
                results.append(row)

        return results

    def query_natural_language(
        self,
        natural_language: str,
        table: str,
        max_stages: int = 3,
        api_key: Optional[str] = None,
    ) -> dict[str, Any]:
        """Execute natural language query with multi-stage retrieval.

        Args:
            natural_language: User's natural language query
            table: Target table name
            max_stages: Maximum retrieval stages (default: 3)
            api_key: OpenAI API key (optional, uses OPENAI_API_KEY env var)

        Returns:
            Dict with results, query metadata, and execution info

        Example:
            >>> db.query_natural_language("find resources about Python", "resources")
            {
                "results": [...],
                "query": "SELECT * FROM resources WHERE embedding.cosine('Python') LIMIT 10",
                "confidence": 0.9,
                "stages": 1
            }
        """
        # Get schema for table
        schema = self.get_schema(table)
        if not schema:
            raise ValueError(f"Table '{table}' does not exist")

        # Initialize query builder
        builder = QueryBuilder(api_key=api_key)

        try:
            # Stage 1: Initial query
            query_result = builder.build_query(
                natural_language, schema.json_schema, table, max_stages
            )

            # Execute query
            results = self.sql(query_result.query)

            # Track execution metadata
            metadata = {
                "results": results,
                "query": query_result.query,
                "query_type": query_result.query_type,
                "confidence": query_result.confidence,
                "explanation": query_result.explanation,
                "stages": 1,
            }

            # Multi-stage retrieval: if no results and fallback available
            current_stage = 1
            while (
                len(results) == 0
                and query_result.fallback_query
                and current_stage < max_stages
            ):
                current_stage += 1

                # Execute fallback query
                results = self.sql(query_result.fallback_query)

                metadata["results"] = results
                metadata["fallback_query"] = query_result.fallback_query
                metadata["stages"] = current_stage

                # If still no results, could generate another fallback
                # For now, stop after one fallback
                break

            return metadata

        finally:
            builder.close()

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

    def lookup_entity(self, identifier: str) -> list[Entity]:
        """Global entity lookup by name, alias, or ID.

        Fast lookup across all entity types when table/schema is unknown.
        Use this when user provides an identifier without table context.

        Search strategy:
        1. Try UUID parse → direct key lookup
        2. Scan all entities, filter by name or aliases

        Args:
            identifier: Name, alias, or ID string to search for

        Returns:
            List of matching entities (empty if none found)

        Example:
            >>> db.lookup_entity("12345")  # Issue number
            [Entity(type="issue", name="Issue #12345", ...)]

            >>> db.lookup_entity("DHL")  # Carrier name
            [Entity(type="carrier", name="DHL", ...)]

            >>> db.lookup_entity("TAP-1234")  # Ticket code
            [Entity(type="issue", name="TAP-1234", ...)]
        """
        results = []

        # Try UUID parse first (fastest path)
        try:
            entity_id = UUID(identifier)
            entity = self.get_entity(entity_id)
            if entity:
                return [entity]
        except (ValueError, AttributeError):
            pass  # Not a valid UUID

        # Scan all entities and filter by name or aliases
        prefix = self._key("entity")
        all_entities = [Entity(**data) for data in self._scan_prefix(prefix)]

        for entity in all_entities:
            # Check name (case-insensitive)
            if entity.name.lower() == identifier.lower():
                results.append(entity)
                continue

            # Check aliases
            if identifier in entity.aliases or identifier.lower() in [a.lower() for a in entity.aliases]:
                results.append(entity)
                continue

            # Check common ID fields in properties
            properties = entity.properties or {}
            id_fields = [
                "id",
                "issue_number",
                "ticket_id",
                "employee_id",
                "code",
                "identifier",
            ]
            for field in id_fields:
                if field in properties and str(properties[field]) == identifier:
                    results.append(entity)
                    break

        return results

    def delete_entity(self, entity_id: UUID) -> None:
        """Delete entity."""
        key = self._key("entity", str(entity_id))
        self._delete(key)

    def query_entities(self, query: Query) -> list[Entity]:
        """Query entities with predicates.

        Uses secondary indexes when possible for better performance.
        """
        # Try to use index for simple Eq predicates on indexed fields
        candidate_ids = self._get_index_candidates(query.predicate)

        if candidate_ids is not None:
            # Index hit - only load candidate entities
            entities = []
            for entity_id in candidate_ids:
                entity = self.get_entity(UUID(entity_id))
                if entity and query.predicate.evaluate(entity):
                    entities.append(entity)
        else:
            # No index - full scan
            prefix = self._key("entity")
            entities = [Entity(**data) for data in self._scan_prefix(prefix)]
            entities = [e for e in entities if query.predicate.evaluate(e)]

        # Apply sorting
        if query.order_by:
            field, order = query.order_by
            # Determine default value based on type
            if entities:
                sample_val = Eq._get_field(entities[0], field)
                if isinstance(sample_val, (int, float)):
                    default = 0
                elif isinstance(sample_val, str):
                    default = ""
                elif isinstance(sample_val, datetime):
                    default = datetime.min
                else:
                    default = None
            else:
                default = None

            entities.sort(
                key=lambda e: Eq._get_field(e, field)
                if Eq._get_field(e, field) is not None
                else default,
                reverse=(order == Order.DESC),
            )

        # Apply offset and limit
        if query.offset:
            entities = entities[query.offset :]
        if query.limit:
            entities = entities[: query.limit]

        return entities

    def _get_index_candidates(self, predicate) -> Optional[list[str]]:
        """Get candidate IDs from index if predicate can use it.

        Returns None if index cannot be used (requires full scan).
        """
        # Simple Eq on indexed field
        if isinstance(predicate, Eq) and predicate.field in self.indexed_fields:
            return self.entity_index.get(predicate.field, predicate.value)

        # And with Eq predicates - intersect results
        if isinstance(predicate, And):
            all_candidates = []
            for sub in predicate.predicates:
                if isinstance(sub, Eq) and sub.field in self.indexed_fields:
                    candidates = self.entity_index.get(sub.field, sub.value)
                    if all_candidates:
                        # Intersect
                        all_candidates = list(set(all_candidates) & set(candidates))
                    else:
                        all_candidates = candidates

            return all_candidates if all_candidates else None

        # Or with Eq predicates - union results
        if isinstance(predicate, Or):
            all_candidates = []
            for sub in predicate.predicates:
                if isinstance(sub, Eq) and sub.field in self.indexed_fields:
                    candidates = self.entity_index.get(sub.field, sub.value)
                    all_candidates.extend(candidates)

            return list(set(all_candidates)) if all_candidates else None

        return None

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
    def _load_vector_index_async(self) -> None:
        """Load existing vector index from disk in background."""
        if not self._index_path.exists():
            return

        def load_index():
            try:
                index = hnswlib.Index(space="cosine", dim=self.embedding_dim)
                index.load_index(str(self._index_path))
                count = index.get_current_count()

                # Safely update index
                with self._embedding_lock:
                    self.vector_index = index
                    self._vector_count = count

            except Exception as e:
                print(f"Warning: Failed to load vector index: {e}")

        # Submit load task to background worker
        task = Task(
            type=TaskType.SAVE_INDEX,  # Reuse save task type
            payload={"callback": load_index}
        )
        self.worker.submit(task)

    def _save_vector_index_async(self) -> None:
        """Save vector index to disk in background."""
        if self.vector_index is None:
            return

        # Submit save task to background worker
        task = Task(
            type=TaskType.SAVE_INDEX,
            payload={
                "index": self.vector_index,
                "path": str(self._index_path)
            }
        )
        self.worker.submit(task)

    def _init_vector_index(self, max_elements: int = 100000) -> None:
        """Initialize HNSW index for default embeddings."""
        if self.vector_index is not None:
            return

        self.vector_index = hnswlib.Index(space="cosine", dim=self.embedding_dim)
        self.vector_index.init_index(max_elements=max_elements, ef_construction=200, M=16)
        self.vector_index.set_ef(50)

    def set_embedding(
        self,
        entity_id: UUID,
        vector: np.ndarray | list[float],
        entity_type: str = "resource"
    ) -> None:
        """Set default embedding for entity.

        Args:
            entity_id: Entity UUID
            vector: Embedding vector
            entity_type: Type of entity ("resource" or "entity")
        """
        if isinstance(vector, list):
            vector = np.array(vector, dtype=np.float32)

        if self.vector_index is None:
            self._init_vector_index()

        # Use hash of UUID as HNSW ID
        hnsw_id = int(hashlib.md5(str(entity_id).encode()).hexdigest()[:8], 16)

        # Add to index
        self.vector_index.add_items(vector, hnsw_id)
        self._vector_count += 1

        # Store mapping with entity type
        mapping_key = self._key("vector_map", str(hnsw_id))
        self._put(mapping_key, {"entity_id": str(entity_id), "entity_type": entity_type})

        # Save index to disk (async)
        self._save_vector_index_async()

    def search_similar(
        self,
        query_vector: np.ndarray | list[float],
        top_k: int = 10,
        min_score: float = 0.0
    ) -> list[tuple[Resource | Entity, float]]:
        """Search for similar entities/resources by vector.

        Args:
            query_vector: Query embedding vector
            top_k: Maximum results to return
            min_score: Minimum similarity score (0-1)

        Returns:
            List of (entity/resource, score) tuples
        """
        if self.vector_index is None or self._vector_count == 0:
            return []

        if isinstance(query_vector, list):
            query_vector = np.array(query_vector, dtype=np.float32)

        # Search HNSW
        labels, distances = self.vector_index.knn_query(query_vector, k=min(top_k, self._vector_count))

        # Convert distances to similarity scores (cosine)
        # hnswlib returns squared distances for cosine
        scores = 1.0 - distances[0]

        # Get entities/resources
        results = []
        for hnsw_id, score in zip(labels[0], scores):
            if score < min_score:
                continue

            # Get entity mapping
            mapping_key = self._key("vector_map", str(hnsw_id))
            mapping = self._get(mapping_key)
            if not mapping:
                continue

            entity_id = UUID(mapping["entity_id"])
            entity_type = mapping.get("entity_type", "resource")

            # Retrieve entity or resource
            if entity_type == "resource":
                item = self.get_resource(entity_id)
            else:
                item = self.get_entity(entity_id)

            if item:
                results.append((item, float(score)))

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

    # WAL (Write-Ahead Log) methods for replication

    def _load_wal_seq(self) -> int:
        """Load current WAL sequence number from disk."""
        seq_key = self._key("wal", "seq")
        seq_data = self._get(seq_key)
        return seq_data["seq"] if seq_data else 0

    def _save_wal_seq(self):
        """Save current WAL sequence number to disk."""
        seq_key = self._key("wal", "seq")
        self._put(seq_key, {"seq": self._wal_seq})

    def _next_seq(self) -> int:
        """Get next WAL sequence number."""
        with self._wal_lock:
            self._wal_seq += 1
            self._save_wal_seq()
            return self._wal_seq

    def get_current_seq(self) -> int:
        """Get current WAL sequence number."""
        return self._wal_seq

    def _append_wal(self, operation: str, key: bytes, value: bytes, tablespace: str = "default"):
        """Append entry to WAL.

        Args:
            operation: "PUT" or "DELETE"
            key: Key bytes
            value: Value bytes (empty for DELETE)
            tablespace: Tablespace/column family name
        """
        import time

        seq_num = self._next_seq()
        entry = {
            "seq_num": seq_num,
            "tenant_id": self.tenant_id,
            "tablespace": tablespace,
            "operation": operation,
            "key": key.hex() if isinstance(key, bytes) else key,
            "value": value.hex() if isinstance(value, bytes) else value,
            "timestamp": time.time_ns(),
        }

        with self._wal_lock:
            self._wal.append((seq_num, entry))

            # Keep only last 1000 entries in memory
            if len(self._wal) > 1000:
                self._wal = self._wal[-1000:]

        # Store to RocksDB (for historical catchup)
        wal_key = self._key("wal", f"entry:{seq_num}")
        self._put(wal_key, entry)

    def get_wal_entries(
        self, start_seq: int, end_seq: Optional[int] = None, limit: int = 100
    ) -> list[dict]:
        """Get WAL entries for replication.

        Args:
            start_seq: Starting sequence number (exclusive)
            end_seq: Ending sequence number (inclusive), None for current
            limit: Maximum entries to return

        Returns:
            List of WAL entry dicts
        """
        if end_seq is None:
            end_seq = self._wal_seq

        entries = []
        for seq in range(start_seq + 1, min(end_seq + 1, start_seq + limit + 1)):
            wal_key = self._key("wal", f"entry:{seq}")
            entry = self._get(wal_key)
            if entry:
                entries.append(entry)

        return entries
