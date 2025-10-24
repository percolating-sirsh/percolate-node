# Python bindings for percolate-rocks

## Overview

Python bindings for the Rust-based REM database using PyO3. Provides a high-level Python API with full async support for embeddings.

## Installation

### Development install

```bash
# Install maturin
uv tool install maturin

# Build and install in development mode
maturin develop --features pyo3,async
```

### Production build

```bash
# Build optimized wheel
maturin build --release --features pyo3,async

# Install the wheel
pip install target/wheels/percolate_rocks-*.whl
```

## Usage

### Basic operations

```python
from percolate_rocks import REMDatabase

# Create database
db = REMDatabase(tenant_id="my-tenant", path="./my-db")

# Register schema
db.register_schema(
    "resources",
    {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "content": {"type": "string"}
        },
        "required": ["name", "content"]
    },
    indexed_fields=["name"],
    embedding_fields=["content"]
)

# Insert entity
entity_id = db.insert(
    "resources",
    {"name": "Test", "content": "This is a test document"}
)

# Get entity
entity = db.get(entity_id)
print(entity)

# Scan all entities
entities = db.scan()

# Scan by type
resources = db.scan_by_type("resources")

# Delete entity (soft delete)
db.delete(entity_id)
```

### Async embeddings

```python
import asyncio
from percolate_rocks import REMDatabase

async def main():
    db = REMDatabase(tenant_id="async-test", path="./async-db")

    # Register schema with embedding fields
    db.register_schema(
        "resources",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "content": {"type": "string"}
            }
        },
        embedding_fields=["content"]
    )

    # Insert with automatic embedding generation
    entity_id = await db.insert_with_embedding(
        "resources",
        {
            "name": "Rust Programming",
            "content": "Rust is a systems programming language"
        }
    )

    # Check embedding was generated
    entity = db.get(entity_id)
    print(f"Embedding dimensions: {len(entity['properties']['embedding'])}")
    # Output: Embedding dimensions: 384

asyncio.run(main())
```

### Schema validation

```python
from percolate_rocks import REMDatabase

db = REMDatabase(tenant_id="test", path="./db")

# Register strict schema
db.register_schema(
    "users",
    {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer", "minimum": 0}
        },
        "required": ["name", "age"]
    }
)

# Valid insert
db.insert("users", {"name": "Alice", "age": 30})

# Invalid insert - raises RuntimeError
try:
    db.insert("users", {"name": "Bob"})  # Missing 'age'
except RuntimeError as e:
    print(f"Validation error: {e}")
```

## API reference

### REMDatabase

#### Constructor

```python
REMDatabase(tenant_id: str, path: str) -> REMDatabase
```

Create a new database instance.

- `tenant_id`: Tenant identifier for multi-tenancy
- `path`: Path to database directory

#### Methods

##### insert

```python
insert(table: str, properties: Dict[str, Any]) -> str
```

Insert entity into table (synchronous, no embeddings).

Returns entity ID as UUID string.

##### insert_with_embedding (async)

```python
async insert_with_embedding(table: str, properties: Dict[str, Any]) -> str
```

Insert entity with automatic embedding generation.

Generates embeddings for fields marked in `schema.embedding_fields`.

Returns entity ID as UUID string.

##### get

```python
get(entity_id: str) -> Optional[Dict[str, Any]]
```

Get entity by ID.

Returns entity data or None if not found.

##### scan

```python
scan() -> List[Dict[str, Any]]
```

Scan all entities.

##### scan_by_type

```python
scan_by_type(table: str) -> List[Dict[str, Any]]
```

Scan entities by type/table.

##### delete

```python
delete(entity_id: str) -> None
```

Delete entity (soft delete - adds `deleted_at` timestamp).

##### register_schema

```python
register_schema(
    name: str,
    schema: Dict[str, Any],
    indexed_fields: Optional[List[str]] = None,
    embedding_fields: Optional[List[str]] = None
) -> None
```

Register JSON Schema for validation.

- `name`: Schema name
- `schema`: JSON Schema definition
- `indexed_fields`: Fields to index for fast lookup
- `embedding_fields`: Fields to automatically embed

##### get_schema

```python
get_schema(name: str) -> Dict[str, Any]
```

Get schema by name.

Returns schema definition with metadata.

##### list_schemas

```python
list_schemas() -> List[str]
```

List all registered schema names.

##### has_embeddings

```python
has_embeddings() -> bool
```

Check if embedding provider is enabled.

## Testing

```bash
# Run Python tests
python3 python/tests/test_python_bindings.py
```

## Features

- ✅ Synchronous entity operations (insert, get, scan, delete)
- ✅ Async embedding generation with `embed_anything`
- ✅ JSON Schema validation
- ✅ Multi-tenant support
- ✅ Type stubs for IDE support
- ✅ 384-dimensional embeddings (all-MiniLM-L6-v2)
- ✅ Soft delete with `deleted_at` timestamp

## Implementation details

### Embedding model

- **Model**: sentence-transformers/all-MiniLM-L6-v2
- **Dimensions**: 384
- **Library**: `embed_anything` v0.6 (Rust-native, ONNX-based)

### Database backend

- **Storage**: RocksDB with column families
- **Serialization**: JSON for entity properties
- **Key encoding**: tenant-scoped with UUID identifiers

### PyO3 bindings

- **Python**: PyO3 v0.20 with abi3 support
- **Async**: pyo3-asyncio with tokio runtime
- **Type conversion**: pythonize for serde_json ↔ Python dict

## Next steps

- Vector similarity search
- SQL query layer
- gRPC replication
- Parquet export
