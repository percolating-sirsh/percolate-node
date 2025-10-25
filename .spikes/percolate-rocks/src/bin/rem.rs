//! REM Database CLI
//!
//! Command-line interface for Resources-Entities-Moments database.

use clap::{Parser, Subcommand};
use percolate_rocks::database::Database;
use std::path::PathBuf;

/// REM Database CLI - Resources-Entities-Moments
#[derive(Parser)]
#[command(name = "rem")]
#[command(about = "High-performance embedded database for semantic search, graph queries, and structured data", long_about = None)]
#[command(version)]
struct Cli {
    /// Database path (overrides P8_DB_PATH)
    #[arg(long, env = "P8_DB_PATH", default_value = "~/.p8/db")]
    db_path: PathBuf,

    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Initialize database
    Init {
        /// Custom database path
        #[arg(long)]
        path: Option<PathBuf>,
    },

    /// Schema management
    #[command(subcommand)]
    Schema(SchemaCommands),

    /// Insert entity
    Insert {
        /// Table/schema name
        table: String,

        /// JSON data (or use --batch for stdin)
        json: Option<String>,

        /// Batch insert from stdin (JSONL format)
        #[arg(long)]
        batch: bool,
    },

    /// Get entity by UUID
    Get {
        /// Entity UUID
        uuid: String,
    },

    /// Update entity
    Update {
        /// Entity UUID
        uuid: String,

        /// JSON updates (partial or full)
        updates: String,
    },

    /// Delete entity
    Delete {
        /// Entity UUID
        uuid: String,

        /// Hard delete (permanent removal)
        #[arg(long)]
        hard: bool,
    },

    /// List entities in table
    List {
        /// Table/schema name
        table: String,

        /// Include soft-deleted entities
        #[arg(long)]
        include_deleted: bool,

        /// Maximum number of results
        #[arg(long)]
        limit: Option<usize>,
    },

    /// Count entities in table
    Count {
        /// Table/schema name
        table: String,

        /// Include soft-deleted entities
        #[arg(long)]
        include_deleted: bool,
    },

    /// Global key lookup
    Lookup {
        /// Key value to lookup
        key: String,
    },

    /// Add edge between entities
    AddEdge {
        /// Source entity UUID
        src: String,

        /// Destination entity UUID
        dst: String,

        /// Relationship type
        rel_type: String,

        /// Optional edge properties (JSON)
        #[arg(long)]
        properties: Option<String>,
    },

    /// Get edges from entity
    GetEdges {
        /// Entity UUID
        uuid: String,

        /// Relationship type filter
        #[arg(long)]
        rel_type: Option<String>,

        /// Direction: out (default), in, both
        #[arg(long, default_value = "out")]
        direction: String,
    },

    /// Delete edge between entities
    DeleteEdge {
        /// Source entity UUID
        src: String,

        /// Destination entity UUID
        dst: String,

        /// Relationship type
        rel_type: String,
    },

    /// Ingest file (parse and chunk)
    Ingest {
        /// File path
        file: PathBuf,

        /// Schema name
        #[arg(long)]
        schema: String,
    },

    /// Semantic search
    Search {
        /// Search query
        query: String,

        /// Schema name
        #[arg(long)]
        schema: String,

        /// Number of results
        #[arg(long, default_value = "10")]
        top_k: usize,
    },

    /// SQL query
    Query {
        /// SQL query string
        sql: String,
    },

    /// Natural language query
    Ask {
        /// Question in natural language
        question: String,

        /// Show query plan without executing
        #[arg(long)]
        plan: bool,
    },

    /// Graph traversal
    Traverse {
        /// Starting entity UUID
        uuid: String,

        /// Traversal depth
        #[arg(long, default_value = "2")]
        depth: usize,

        /// Direction: in, out, both
        #[arg(long, default_value = "out")]
        direction: String,
    },

    /// Export data
    Export {
        /// Table to export (or --all)
        table: Option<String>,

        /// Export all tables
        #[arg(long)]
        all: bool,

        /// Output path
        #[arg(long)]
        output: PathBuf,
    },

    /// Start replication server
    Serve {
        /// Host to bind
        #[arg(long, default_value = "0.0.0.0")]
        host: String,

        /// Port to bind
        #[arg(long, env = "P8_REPLICATION_PORT", default_value = "50051")]
        port: u16,
    },

    /// Replicate from primary
    Replicate {
        /// Primary host:port
        #[arg(long)]
        primary: String,

        /// Follow mode (continuous sync)
        #[arg(long)]
        follow: bool,
    },

    /// Replication status
    #[command(subcommand)]
    Replication(ReplicationCommands),
}

#[derive(Subcommand)]
enum SchemaCommands {
    /// Add schema from file or template
    Add {
        /// Schema file (JSON/YAML) or Python module::Class
        file: Option<PathBuf>,

        /// Schema name (when using template)
        #[arg(long)]
        name: Option<String>,

        /// Template name (resources, entities, agentlets, moments)
        #[arg(long)]
        template: Option<String>,

        /// Output file (save without registering)
        #[arg(long)]
        output: Option<PathBuf>,
    },

    /// List registered schemas
    List,

    /// Show schema definition
    Show {
        /// Schema name
        name: String,
    },

    /// List available templates
    Templates,
}

#[derive(Subcommand)]
enum ReplicationCommands {
    /// Show WAL status
    WalStatus,

    /// Show replication status
    Status,
}

fn main() -> anyhow::Result<()> {
    let cli = Cli::parse();

    // Expand ~ in path
    let db_path = shellexpand::tilde(&cli.db_path.to_string_lossy()).to_string();
    let db_path = PathBuf::from(db_path);

    match cli.command {
        Commands::Init { path } => {
            let init_path = path.unwrap_or(db_path);
            cmd_init(&init_path)?;
        }
        Commands::Schema(cmd) => match cmd {
            SchemaCommands::Add {
                file,
                name,
                template,
                output,
            } => {
                cmd_schema_add(&db_path, file, name, template, output)?;
            }
            SchemaCommands::List => {
                cmd_schema_list(&db_path)?;
            }
            SchemaCommands::Show { name } => {
                cmd_schema_show(&db_path, &name)?;
            }
            SchemaCommands::Templates => {
                cmd_schema_templates()?;
            }
        },
        Commands::Insert { table, json, batch } => {
            cmd_insert(&db_path, &table, json.as_deref(), batch)?;
        }
        Commands::Get { uuid } => {
            cmd_get(&db_path, &uuid)?;
        }
        Commands::Update { uuid, updates } => {
            cmd_update(&db_path, &uuid, &updates)?;
        }
        Commands::Delete { uuid, hard } => {
            cmd_delete(&db_path, &uuid, hard)?;
        }
        Commands::List { table, include_deleted, limit } => {
            cmd_list(&db_path, &table, include_deleted, limit)?;
        }
        Commands::Count { table, include_deleted } => {
            cmd_count(&db_path, &table, include_deleted)?;
        }
        Commands::Lookup { key } => {
            cmd_lookup(&db_path, &key)?;
        }
        Commands::AddEdge { src, dst, rel_type, properties } => {
            cmd_add_edge(&db_path, &src, &dst, &rel_type, properties.as_deref())?;
        }
        Commands::GetEdges { uuid, rel_type, direction } => {
            cmd_get_edges(&db_path, &uuid, rel_type.as_deref(), &direction)?;
        }
        Commands::DeleteEdge { src, dst, rel_type } => {
            cmd_delete_edge(&db_path, &src, &dst, &rel_type)?;
        }
        Commands::Ingest { file, schema } => {
            cmd_ingest(&db_path, &file, &schema)?;
        }
        Commands::Search {
            query,
            schema,
            top_k,
        } => {
            cmd_search(&db_path, &query, &schema, top_k)?;
        }
        Commands::Query { sql } => {
            cmd_query(&db_path, &sql)?;
        }
        Commands::Ask { question, plan } => {
            cmd_ask(&db_path, &question, plan)?;
        }
        Commands::Traverse {
            uuid,
            depth,
            direction,
        } => {
            cmd_traverse(&db_path, &uuid, depth, &direction)?;
        }
        Commands::Export { table, all, output } => {
            cmd_export(&db_path, table.as_deref(), all, &output)?;
        }
        Commands::Serve { host, port } => {
            cmd_serve(&db_path, &host, port)?;
        }
        Commands::Replicate { primary, follow } => {
            cmd_replicate(&db_path, &primary, follow)?;
        }
        Commands::Replication(cmd) => match cmd {
            ReplicationCommands::WalStatus => {
                cmd_replication_wal_status(&db_path)?;
            }
            ReplicationCommands::Status => {
                cmd_replication_status(&db_path)?;
            }
        },
    }

    Ok(())
}

// ============================================================================
// IMPLEMENTED COMMANDS
// ============================================================================

fn cmd_init(path: &PathBuf) -> anyhow::Result<()> {
    println!("Initializing database at: {}", path.display());

    // Create directory if it doesn't exist
    std::fs::create_dir_all(path)?;

    // Open database (will create if doesn't exist)
    let db = Database::open(path)?;

    println!("✓ Database initialized successfully");
    println!("  Path: {}", path.display());
    println!("  Column families: 7");
    println!("  Builtin schemas: {}", db.list_schemas()?.len());
    println!("  Ready for use");

    Ok(())
}

fn cmd_insert(
    db_path: &PathBuf,
    table: &str,
    json: Option<&str>,
    batch: bool,
) -> anyhow::Result<()> {
    let db = Database::open(db_path)?;

    if batch {
        println!("Batch insert not yet implemented");
        println!("Will read JSONL from stdin and batch insert to '{}'", table);
        return Ok(());
    }

    if let Some(json_data) = json {
        // Parse JSON
        let data: serde_json::Value = serde_json::from_str(json_data)?;

        // Insert entity (with schema validation)
        let id = db.insert("default", table, data)?;

        println!("✓ Inserted entity");
        println!("  ID: {}", id);
        println!("  Table: {}", table);
    } else {
        anyhow::bail!("Either provide JSON data or use --batch flag");
    }

    Ok(())
}

fn cmd_get(db_path: &PathBuf, uuid_str: &str) -> anyhow::Result<()> {
    let db = Database::open(db_path)?;

    // Parse UUID
    let id = uuid::Uuid::parse_str(uuid_str)?;

    // Get entity
    match db.get("default", id)? {
        Some(entity) => {
            println!("{}", serde_json::to_string_pretty(&entity)?);
        }
        None => {
            println!("Entity not found: {}", id);
        }
    }

    Ok(())
}

fn cmd_lookup(db_path: &PathBuf, key: &str) -> anyhow::Result<()> {
    let db = Database::open(db_path)?;

    // Get all schemas to search across
    let schemas = db.list_schemas()?;

    println!("Looking up key: {}", key);
    println!();

    let mut found = false;

    // Search each schema for the key
    for schema_name in schemas {
        if let Some(entity) = db.get_by_key("default", &schema_name, key)? {
            found = true;
            println!("✓ Found in table: {}", schema_name);
            println!("  ID: {}", entity.system.id);
            println!("  Created: {}", entity.system.created_at);
            println!("  Modified: {}", entity.system.modified_at);
            println!("  Properties:");

            let formatted = serde_json::to_string_pretty(&entity.properties)?;
            for line in formatted.lines() {
                println!("    {}", line);
            }
            println!();
        }
    }

    if !found {
        println!("✗ No entity found with key: {}", key);
    }

    Ok(())
}

fn cmd_add_edge(
    db_path: &PathBuf,
    src_str: &str,
    dst_str: &str,
    rel_type: &str,
    properties_str: Option<&str>,
) -> anyhow::Result<()> {
    let db = Database::open(db_path)?;

    // Parse UUIDs
    let src_id = uuid::Uuid::parse_str(src_str)?;
    let dst_id = uuid::Uuid::parse_str(dst_str)?;

    // Parse optional properties
    let properties = if let Some(props_str) = properties_str {
        Some(serde_json::from_str(props_str)?)
    } else {
        None
    };

    // Add edge
    let edge = db.add_edge("default", src_id, dst_id, rel_type, properties)?;

    println!("✓ Edge created");
    println!("  From: {}", edge.src);
    println!("  To: {}", edge.dst);
    println!("  Type: {}", edge.rel_type);
    println!("  Created: {}", edge.data.created_at);

    if !edge.data.properties.is_empty() {
        println!("  Properties:");
        let formatted = serde_json::to_string_pretty(&edge.data.properties)?;
        for line in formatted.lines() {
            println!("    {}", line);
        }
    }

    Ok(())
}

fn cmd_get_edges(
    db_path: &PathBuf,
    uuid_str: &str,
    rel_type: Option<&str>,
    direction: &str,
) -> anyhow::Result<()> {
    let db = Database::open(db_path)?;

    // Parse UUID
    let id = uuid::Uuid::parse_str(uuid_str)?;

    // Get edges based on direction
    let edges = match direction {
        "out" => db.get_edges(id, rel_type)?,
        "in" => db.get_incoming_edges(id, rel_type)?,
        "both" => {
            let mut all_edges = db.get_edges(id, rel_type)?;
            let incoming = db.get_incoming_edges(id, rel_type)?;
            all_edges.extend(incoming);
            all_edges
        }
        _ => anyhow::bail!("Invalid direction: {}. Use 'out', 'in', or 'both'", direction),
    };

    if edges.is_empty() {
        println!("No edges found for entity {}", id);
        return Ok(());
    }

    println!("Found {} edge(s)", edges.len());
    println!();

    for (i, edge) in edges.iter().enumerate() {
        println!("Edge {}:", i + 1);
        println!("  From: {}", edge.src);
        println!("  To: {}", edge.dst);
        println!("  Type: {}", edge.rel_type);
        println!("  Created: {}", edge.data.created_at);

        if !edge.data.properties.is_empty() {
            println!("  Properties:");
            let formatted = serde_json::to_string_pretty(&edge.data.properties)?;
            for line in formatted.lines() {
                println!("    {}", line);
            }
        }
        println!();
    }

    Ok(())
}

fn cmd_delete_edge(
    db_path: &PathBuf,
    src_str: &str,
    dst_str: &str,
    rel_type: &str,
) -> anyhow::Result<()> {
    let db = Database::open(db_path)?;

    // Parse UUIDs
    let src_id = uuid::Uuid::parse_str(src_str)?;
    let dst_id = uuid::Uuid::parse_str(dst_str)?;

    // Delete edge
    db.delete_edge(src_id, dst_id, rel_type)?;

    println!("✓ Edge deleted");
    println!("  From: {}", src_id);
    println!("  To: {}", dst_id);
    println!("  Type: {}", rel_type);

    Ok(())
}

fn cmd_update(db_path: &PathBuf, uuid_str: &str, updates_str: &str) -> anyhow::Result<()> {
    let db = Database::open(db_path)?;

    // Parse UUID
    let id = uuid::Uuid::parse_str(uuid_str)?;

    // Parse updates JSON
    let updates: serde_json::Value = serde_json::from_str(updates_str)?;

    // Update entity
    let entity = db.update("default", id, updates)?;

    println!("✓ Entity updated");
    println!("  ID: {}", entity.system.id);
    println!("  Type: {}", entity.system.entity_type);
    println!("  Modified: {}", entity.system.modified_at);
    println!("  Properties:");
    let formatted = serde_json::to_string_pretty(&entity.properties)?;
    for line in formatted.lines() {
        println!("    {}", line);
    }

    Ok(())
}

fn cmd_delete(db_path: &PathBuf, uuid_str: &str, hard: bool) -> anyhow::Result<()> {
    let db = Database::open(db_path)?;

    // Parse UUID
    let id = uuid::Uuid::parse_str(uuid_str)?;

    if hard {
        // Hard delete (permanent)
        db.hard_delete("default", id)?;
        println!("✓ Entity permanently deleted");
        println!("  ID: {}", id);
    } else {
        // Soft delete
        let entity = db.delete("default", id)?;
        println!("✓ Entity soft deleted");
        println!("  ID: {}", entity.system.id);
        println!("  Type: {}", entity.system.entity_type);
        println!("  Deleted at: {}", entity.system.deleted_at.unwrap_or_default());
    }

    Ok(())
}

fn cmd_list(
    db_path: &PathBuf,
    table: &str,
    include_deleted: bool,
    limit: Option<usize>,
) -> anyhow::Result<()> {
    let db = Database::open(db_path)?;

    // List entities
    let entities = db.list("default", table, include_deleted, limit)?;

    println!("Entities in '{}' (found: {})", table, entities.len());
    println!();

    for entity in entities {
        let deleted_marker = if entity.is_deleted() { " [DELETED]" } else { "" };
        println!("• ID: {}{}", entity.system.id, deleted_marker);
        println!("  Created: {}", entity.system.created_at);
        println!("  Modified: {}", entity.system.modified_at);

        let formatted = serde_json::to_string_pretty(&entity.properties)?;
        for line in formatted.lines() {
            println!("  {}", line);
        }
        println!();
    }

    Ok(())
}

fn cmd_count(db_path: &PathBuf, table: &str, include_deleted: bool) -> anyhow::Result<()> {
    let db = Database::open(db_path)?;

    // Count entities
    let count = db.count("default", table, include_deleted)?;

    let deleted_note = if include_deleted { " (including deleted)" } else { "" };
    println!("Count: {}{}", count, deleted_note);
    println!("Table: {}", table);

    Ok(())
}

// ============================================================================
// STUBBED COMMANDS (Not Yet Implemented)
// ============================================================================

fn cmd_schema_add(
    db_path: &PathBuf,
    file: Option<PathBuf>,
    name: Option<String>,
    template: Option<String>,
    output: Option<PathBuf>,
) -> anyhow::Result<()> {
    let db = Database::open(db_path)?;

    // Handle file-based schema registration
    if let Some(schema_file) = file {
        let content = std::fs::read_to_string(&schema_file)?;
        let schema: serde_json::Value = if schema_file.extension().and_then(|s| s.to_str()) == Some("yaml")
            || schema_file.extension().and_then(|s| s.to_str()) == Some("yml") {
            // Parse YAML
            serde_yaml::from_str(&content)?
        } else {
            // Parse JSON
            serde_json::from_str(&content)?
        };

        // Extract schema name
        let schema_name = schema.get("short_name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| anyhow::anyhow!("Schema missing 'short_name' field"))?
            .to_string();

        // Register schema
        db.register_schema(&schema_name, schema)?;

        println!("✓ Schema registered: {}", schema_name);
        println!("  File: {}", schema_file.display());

        return Ok(());
    }

    // Handle template-based schema creation
    if let Some(template_name) = template {
        let schema_name = name.ok_or_else(|| anyhow::anyhow!("--name required when using --template"))?;

        // Get template schema (only builtin templates supported for now)
        let template_schema = match template_name.as_str() {
            "resources" => percolate_rocks::schema::builtin::resources_table_schema(),
            "documents" => percolate_rocks::schema::builtin::documents_table_schema(),
            "schemas" => percolate_rocks::schema::builtin::schemas_table_schema(),
            _ => anyhow::bail!("Unknown template: {} (available: resources, documents, schemas)", template_name),
        };

        // Customize schema with new name
        let mut schema = template_schema.clone();
        if let Some(obj) = schema.as_object_mut() {
            obj.insert("short_name".to_string(), serde_json::Value::String(schema_name.clone()));
            if let Some(extra) = obj.get_mut("json_schema_extra").and_then(|v| v.as_object_mut()) {
                extra.insert("category".to_string(), serde_json::Value::String("user".to_string()));
            }
        }

        // Output to file or register
        if let Some(output_file) = output {
            let content = serde_json::to_string_pretty(&schema)?;
            std::fs::write(&output_file, content)?;
            println!("✓ Schema saved to: {}", output_file.display());
            println!("  Template: {}", template_name);
            println!("  Name: {}", schema_name);
        } else {
            // Register directly
            db.register_schema(&schema_name, schema)?;
            println!("✓ Schema registered: {}", schema_name);
            println!("  Template: {}", template_name);
        }

        return Ok(());
    }

    anyhow::bail!("Either provide a schema file or use --template with --name")
}

fn cmd_schema_list(db_path: &PathBuf) -> anyhow::Result<()> {
    let db = Database::open(db_path)?;
    let schemas = db.list_schemas()?;

    println!("Registered schemas ({}):", schemas.len());
    for name in schemas {
        println!("  - {}", name);
    }

    Ok(())
}

fn cmd_schema_show(db_path: &PathBuf, name: &str) -> anyhow::Result<()> {
    let db = Database::open(db_path)?;
    let schema = db.get_schema(name)?;

    println!("{}", serde_json::to_string_pretty(&schema)?);

    Ok(())
}

fn cmd_schema_templates() -> anyhow::Result<()> {
    println!("Available schema templates:");
    println!("  - resources: Chunked documents with embeddings (URI-based)");
    println!("  - entities: Generic structured data (name-based)");
    println!("  - agentlets: AI agent definitions (with tools/resources)");
    println!("  - moments: Temporal classifications (time-range queries)");
    Ok(())
}

fn cmd_ingest(_db_path: &PathBuf, file: &PathBuf, schema: &str) -> anyhow::Result<()> {
    println!("Ingest not yet implemented");
    println!("  File: {}", file.display());
    println!("  Schema: {}", schema);
    println!("\nRequires: document chunker, PDF parser");
    Ok(())
}

fn cmd_search(
    _db_path: &PathBuf,
    query: &str,
    schema: &str,
    top_k: usize,
) -> anyhow::Result<()> {
    println!("Semantic search not yet implemented");
    println!("  Query: {}", query);
    println!("  Schema: {}", schema);
    println!("  Top-K: {}", top_k);
    println!("\nRequires: HNSW vector index, embedding provider");
    Ok(())
}

fn cmd_query(db_path: &PathBuf, sql: &str) -> anyhow::Result<()> {
    let db = Database::open(db_path)?;
    let results = db.query_sql("default", sql)?;

    // Format and display results
    println!("{}", serde_json::to_string_pretty(&results)?);
    Ok(())
}

fn cmd_ask(_db_path: &PathBuf, question: &str, plan: bool) -> anyhow::Result<()> {
    println!("Natural language query not yet implemented");
    println!("  Question: {}", question);
    println!("  Plan only: {}", plan);
    println!("\nRequires: LLM query builder, OpenAI API");
    Ok(())
}

fn cmd_traverse(
    db_path: &PathBuf,
    uuid_str: &str,
    depth: usize,
    direction_str: &str,
) -> anyhow::Result<()> {
    use percolate_rocks::graph::TraversalDirection;

    let db = Database::open(db_path)?;

    // Parse UUID
    let start_id = uuid::Uuid::parse_str(uuid_str)?;

    // Parse direction
    let direction = match direction_str {
        "out" => TraversalDirection::Out,
        "in" => TraversalDirection::In,
        "both" => TraversalDirection::Both,
        _ => anyhow::bail!("Invalid direction: {}. Use 'out', 'in', or 'both'", direction_str),
    };

    // Perform BFS traversal
    let nodes = db.traverse_bfs(start_id, direction, depth, None)?;

    println!("Graph traversal from {} (depth: {}, direction: {})", start_id, depth, direction_str);
    println!("Found {} node(s)", nodes.len());
    println!();

    // Get and display each entity
    for (i, node_id) in nodes.iter().enumerate() {
        // Try to get entity (it might not exist if it was deleted)
        if let Some(entity) = db.get("default", *node_id)? {
            println!("{}. ID: {}", i + 1, node_id);
            println!("   Type: {}", entity.system.entity_type);

            // Show name if available
            if let Some(name) = entity.properties.get("name") {
                println!("   Name: {}", name.as_str().unwrap_or(""));
            }

            // Show email if available
            if let Some(email) = entity.properties.get("email") {
                println!("   Email: {}", email.as_str().unwrap_or(""));
            }
        } else {
            println!("{}. ID: {} (entity not found)", i + 1, node_id);
        }
        println!();
    }

    Ok(())
}

fn cmd_export(
    _db_path: &PathBuf,
    table: Option<&str>,
    all: bool,
    output: &PathBuf,
) -> anyhow::Result<()> {
    println!("Export not yet implemented");
    if let Some(t) = table {
        println!("  Table: {}", t);
    }
    println!("  All: {}", all);
    println!("  Output: {}", output.display());
    println!("\nRequires: Parquet writer");
    Ok(())
}

fn cmd_serve(_db_path: &PathBuf, host: &str, port: u16) -> anyhow::Result<()> {
    println!("Replication server not yet implemented");
    println!("  Host: {}", host);
    println!("  Port: {}", port);
    println!("\nRequires: gRPC server, WAL streaming");
    Ok(())
}

fn cmd_replicate(_db_path: &PathBuf, primary: &str, follow: bool) -> anyhow::Result<()> {
    println!("Replication client not yet implemented");
    println!("  Primary: {}", primary);
    println!("  Follow: {}", follow);
    println!("\nRequires: gRPC client, WAL consumer");
    Ok(())
}

fn cmd_replication_wal_status(_db_path: &PathBuf) -> anyhow::Result<()> {
    println!("WAL status not yet implemented");
    println!("Requires: WAL module");
    Ok(())
}

fn cmd_replication_status(_db_path: &PathBuf) -> anyhow::Result<()> {
    println!("Replication status not yet implemented");
    println!("Requires: replication state machine");
    Ok(())
}
