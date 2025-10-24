# CLI implementation roadmap

## Current status

### ✅ Implemented commands

1. **`init <name> [--path <path>]`**
   - Creates database at `~/.p8/db/<name>` (default) or custom path
   - Registers in `~/.p8/config.json`
   - Registers built-in schemas (resources)
   - Inserts sample entities with embeddings
   - Location: `src/bin/cli.rs:90-128`

2. **`list`**
   - Lists all registered databases from config
   - Shows name, path, tenant
   - Location: `src/bin/cli.rs:323-342`

3. **`schemas -d <db>`**
   - Lists all schemas in database
   - Shows indexed fields and embedding fields
   - Location: `src/bin/cli.rs:280-321`
   - **Issue:** Schemas not persisted (in-memory only)

4. **`search -d <db> <query> [--top-k N] [--min-score S]`**
   - Natural language semantic search
   - Generates query embedding
   - Computes cosine similarity
   - Returns top-k results above min-score
   - Location: `src/bin/cli.rs:158-241`
   - **Status:** ✅ Working

5. **`upsert -d <db> <table> --file <jsonl> [--key-field <field>]`**
   - Batch insert from JSONL file
   - Auto-registers schema if not exists
   - Smart key field resolution (uri → key → name → id)
   - Batch embedding generation
   - Location: `src/bin/cli.rs:344-462`
   - **Status:** ✅ Working

### ⚠️ Partially implemented

6. **`query -d <db> <sql> [--format <format>]`**
   - Location: `src/bin/cli.rs:130-156`
   - **Current behavior:** Scans all entities (ignores SQL)
   - **Missing:** SQL parser integration
   - **Needed:**
     - Integrate `sqlparser` crate
     - Parse single-table SELECT with WHERE
     - Execute predicates
     - Return filtered results

7. **`export -d <db> <table> --output <file>`**
   - Location: `src/bin/cli.rs:243-278`
   - **Current behavior:** Exports as JSON
   - **Missing:** Parquet encoding
   - **Needed:**
     - Add `arrow-rs` dependency
     - Convert entities to Arrow schema
     - Write Parquet file

## High priority additions

### 1. Entity lookup command

**Command:**
```bash
rem-db lookup -d <db> <id>
rem-db lookup -d <db> --name <name>
rem-db lookup -d <db> --key <key>
rem-db lookup -d <db> --uri <uri> [--chunk <ordinal>]
```

**Implementation:**
```rust
Lookup {
    #[arg(long, short)]
    db: String,

    /// Entity ID (UUID)
    id: Option<String>,

    /// Lookup by name field
    #[arg(long)]
    name: Option<String>,

    /// Lookup by key field
    #[arg(long)]
    key: Option<String>,

    /// Lookup by URI
    #[arg(long)]
    uri: Option<String>,

    /// Chunk ordinal (for URI lookup)
    #[arg(long, default_value = "0")]
    chunk: u64,
}
```

**Logic:**
```rust
Commands::Lookup { db, id, name, key, uri, chunk } => {
    let (path, tenant) = resolve_database(&db)?;
    let database = Database::open(&path, &tenant)?;

    let entity = if let Some(id_str) = id {
        // Direct ID lookup
        let uuid = Uuid::parse_str(&id_str)?;
        database.get_entity(uuid)?
    } else if let Some(uri_str) = uri {
        // Compute hash(uri:chunk) and lookup
        let key = format!("{}:{}", uri_str, chunk);
        let hash = blake3::hash(key.as_bytes());
        let mut uuid_bytes = [0u8; 16];
        uuid_bytes.copy_from_slice(&hash.as_bytes()[0..16]);
        let uuid = Uuid::from_bytes(uuid_bytes);
        database.get_entity(uuid)?
    } else if let Some(key_str) = key {
        // Compute hash(key) and lookup
        let hash = blake3::hash(key_str.as_bytes());
        let mut uuid_bytes = [0u8; 16];
        uuid_bytes.copy_from_slice(&hash.as_bytes()[0..16]);
        let uuid = Uuid::from_bytes(uuid_bytes);
        database.get_entity(uuid)?
    } else if let Some(name_str) = name {
        // Compute hash(name) and lookup
        let hash = blake3::hash(name_str.as_bytes());
        let mut uuid_bytes = [0u8; 16];
        uuid_bytes.copy_from_slice(&hash.as_bytes()[0..16]);
        let uuid = Uuid::from_bytes(uuid_bytes);
        database.get_entity(uuid)?
    } else {
        return Err("Must provide one of: id, name, key, or uri".into());
    };

    match entity {
        Some(e) => {
            println!("{}", serde_json::to_string_pretty(&e)?);
        }
        None => {
            println!("{}", "Entity not found".yellow());
        }
    }
}
```

**Priority:** 🔴 HIGH (essential for debugging and data access)

### 2. Schema persistence

**Problem:** Schemas are currently in-memory only, lost on database close.

**Solution:** Store schemas as entities with `category: "schema"`

**Implementation:**

**Step 1:** Add schema entity type to init:
```rust
// In register_builtin_schemas()
let schema_schema = json!({
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "category": {"type": "string"},
        "json_schema": {"type": "object"},
        "indexed_fields": {"type": "array"},
        "embedding_fields": {"type": "array"}
    },
    "required": ["name", "category", "json_schema"]
});

db.register_schema(
    "schemas".to_string(),
    schema_schema,
    vec!["category".to_string()],
    vec![],
)?;
```

**Step 2:** Modify `SchemaRegistry::register()` to persist:
```rust
// In src/memory/schema.rs
pub fn register(&self, schema: Schema, storage: &Storage, tenant_id: &str) -> Result<()> {
    // 1. Validate and compile
    let compiled = JSONSchema::compile(&schema.json_schema)
        .map_err(|e| DatabaseError::ValidationError(format!("Invalid schema: {}", e)))?;

    // 2. Store in memory
    self.schemas.write().unwrap().insert(schema.name.clone(), schema.clone());
    self.compiled.write().unwrap().insert(schema.name.clone(), compiled);

    // 3. Persist as entity
    let schema_entity = Entity {
        id: Uuid::new_v4(),
        entity_type: "schemas".to_string(),
        properties: json!({
            "name": schema.name,
            "category": "schema",
            "json_schema": schema.json_schema,
            "indexed_fields": schema.indexed_fields,
            "embedding_fields": schema.embedding_fields
        }),
        created_at: chrono::Utc::now(),
        updated_at: chrono::Utc::now(),
        deleted: false,
    };

    storage.put_entity(tenant_id, &schema_entity)?;

    Ok(())
}
```

**Step 3:** Load schemas on database open:
```rust
// In Database::open()
let schema_registry = Arc::new(SchemaRegistry::new());

// Load persisted schemas
let schema_entities = entity_store.scan_by_type(tenant_id, "schemas")?;
for entity in schema_entities {
    if let Some(name) = entity.properties.get("name").and_then(|v| v.as_str()) {
        let json_schema = entity.properties.get("json_schema").cloned().unwrap_or(json!({}));
        let indexed = entity.properties.get("indexed_fields")
            .and_then(|v| v.as_array())
            .map(|arr| arr.iter().filter_map(|v| v.as_str().map(String::from)).collect())
            .unwrap_or_default();
        let embedding = entity.properties.get("embedding_fields")
            .and_then(|v| v.as_array())
            .map(|arr| arr.iter().filter_map(|v| v.as_str().map(String::from)).collect())
            .unwrap_or_default();

        let schema = Schema::new(name.to_string(), json_schema, indexed, embedding);
        schema_registry.register(schema, &storage, tenant_id)?;
    }
}
```

**Priority:** 🔴 HIGH (blocks real usage)

### 3. SQL query execution

**Command:** `query -d <db> <sql>`

**Current:** Scans all entities, ignores SQL

**Target:** Execute simple SELECT with WHERE predicates

**Implementation:**

**Step 1:** Parse SQL:
```rust
use sqlparser::parser::Parser;
use sqlparser::dialect::GenericDialect;

let dialect = GenericDialect {};
let ast = Parser::parse_sql(&dialect, &query)?;

// Extract table name and WHERE clause
let statement = &ast[0];
if let sqlparser::ast::Statement::Query(query) = statement {
    // ... extract table, predicates
}
```

**Step 2:** Execute predicates:
```rust
// Scan table
let entities = database.scan_entities_by_type(&table)?;

// Filter by WHERE clause
let filtered: Vec<Entity> = entities.into_iter()
    .filter(|entity| {
        // Evaluate predicates against entity.properties
        evaluate_predicate(&where_clause, &entity.properties)
    })
    .collect();
```

**Step 3:** Format results:
```rust
match format.as_str() {
    "json" => println!("{}", serde_json::to_string_pretty(&filtered)?),
    "table" => print_table(&filtered),
    _ => return Err("Unknown format".into()),
}
```

**Priority:** 🟡 MEDIUM (nice to have, search works as alternative)

### 4. Single record insert

**Command:**
```bash
rem-db insert -d <db> <table> <json>
rem-db insert -d <db> <table> --file <json-file>
```

**Implementation:**
```rust
Insert {
    #[arg(long, short)]
    db: String,

    /// Table/schema name
    table: String,

    /// JSON data (inline)
    json: Option<String>,

    /// JSON file path
    #[arg(long)]
    file: Option<PathBuf>,
}
```

**Logic:**
```rust
Commands::Insert { db, table, json, file } => {
    let (path, tenant) = resolve_database(&db)?;
    let database = Database::open(&path, &tenant)?;

    let data = if let Some(json_str) = json {
        serde_json::from_str(&json_str)?
    } else if let Some(path) = file {
        let content = std::fs::read_to_string(path)?;
        serde_json::from_str(&content)?
    } else {
        return Err("Must provide --json or --file".into());
    };

    // Auto-register schema if needed
    if database.get_schema(&table).is_err() {
        // ... same as upsert
    }

    let entity_id = database
        .insert_entity_with_embedding(&table, data)
        .await?;

    println!("{} Inserted entity: {}", "✓".green(), entity_id);
}
```

**Priority:** 🟡 MEDIUM (batch insert covers most use cases)

## Medium priority additions

### 5. Register schema command

**Command:**
```bash
rem-db register-schema -d <db> <name> <schema-file>
```

**Implementation:**
```rust
RegisterSchema {
    #[arg(long, short)]
    db: String,

    /// Schema name
    name: String,

    /// JSON Schema file path
    schema_file: PathBuf,

    /// Indexed fields (comma-separated)
    #[arg(long)]
    indexed: Option<String>,

    /// Embedding fields (comma-separated)
    #[arg(long)]
    embedding: Option<String>,
}
```

**Priority:** 🟡 MEDIUM (auto-registration in upsert covers common cases)

### 6. Parquet export

**Dependencies:**
```toml
arrow = "53.0"
parquet = "53.0"
```

**Implementation:**
```rust
// Convert entities to Arrow RecordBatch
use arrow::array::*;
use arrow::datatypes::*;
use parquet::arrow::ArrowWriter;

let schema = Schema::new(vec![
    Field::new("id", DataType::Utf8, false),
    Field::new("entity_type", DataType::Utf8, false),
    Field::new("properties", DataType::Utf8, false),
    Field::new("created_at", DataType::Timestamp(TimeUnit::Millisecond, None), false),
]);

let mut id_builder = StringBuilder::new();
let mut type_builder = StringBuilder::new();
let mut props_builder = StringBuilder::new();
let mut created_builder = TimestampMillisecondBuilder::new();

for entity in &entities {
    id_builder.append_value(entity.id.to_string());
    type_builder.append_value(&entity.entity_type);
    props_builder.append_value(serde_json::to_string(&entity.properties)?);
    created_builder.append_value(entity.created_at.timestamp_millis());
}

let batch = RecordBatch::try_new(
    Arc::new(schema),
    vec![
        Arc::new(id_builder.finish()),
        Arc::new(type_builder.finish()),
        Arc::new(props_builder.finish()),
        Arc::new(created_builder.finish()),
    ],
)?;

let file = File::create(&output)?;
let mut writer = ArrowWriter::try_new(file, batch.schema(), None)?;
writer.write(&batch)?;
writer.close()?;
```

**Priority:** 🟡 MEDIUM (JSON export works, Parquet is optimization)

## Low priority additions

### 7. Delete command

**Command:**
```bash
rem-db delete -d <db> <id>
rem-db delete -d <db> --name <name>
```

**Note:** Soft delete only (sets `deleted: true`)

**Priority:** 🔵 LOW

### 8. Update command

**Command:**
```bash
rem-db update -d <db> <id> <json>
```

**Priority:** 🔵 LOW (upsert with same key achieves update)

### 9. Replication command

**Command:**
```bash
rem-db replicate -d <db> --to <peer-url>
rem-db replicate -d <db> --serve --port 9000
```

**Priority:** 🔵 LOW (Phase 4 feature)

## Summary of next steps

### Immediate (this week)

1. ✅ Implement `lookup` command - essential for debugging
2. ✅ Fix schema persistence - store as entities with category="schema"
3. ✅ Load schemas on database open

### Short-term (next week)

4. ⚠️ Integrate SQL parser for `query` command
5. ⚠️ Implement single `insert` command for convenience
6. ⚠️ Add `register-schema` command for explicit schema management

### Medium-term (next month)

7. ⚠️ Parquet export (replace JSON)
8. ⚠️ Background HNSW indexing thread
9. ⚠️ Delete/update commands

### Long-term (future)

10. ⚠️ Replication protocol (gRPC)
11. ⚠️ Mobile peer sync
12. ⚠️ Kubernetes cluster replication

## Testing checklist

For each new command:

- [ ] Build with `cargo build --release --bin rem-db --no-default-features`
- [ ] Test with local embeddings (default)
- [ ] Test with OpenAI embeddings (`P8_DEFAULT_EMBEDDING=text-embedding-3-small`)
- [ ] Test error cases (missing args, invalid data)
- [ ] Update USER_FLOW.md with examples
- [ ] Add to CLI help text
