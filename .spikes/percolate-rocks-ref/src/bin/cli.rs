//! REM Database CLI with database name pattern.

use clap::{Parser, Subcommand};
use colored::*;
use percolate_rocks::{config::Config, embeddings::cosine_similarity, Database, Entity};
use serde_json::json;
use std::path::PathBuf;
use uuid::Uuid;

#[derive(Parser)]
#[command(name = "rem-db")]
#[command(about = "REM Database - RocksDB + Vectors + SQL", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Initialize database with system schemas
    Init {
        /// Database name
        name: String,

        /// Custom database path (default: ~/.p8/db/<name>)
        #[arg(long)]
        path: Option<PathBuf>,
    },

    /// Execute SQL query
    Query {
        /// Database name
        #[arg(long, short)]
        db: String,

        /// SQL query string
        query: String,

        /// Output format (table or json)
        #[arg(long, default_value = "table")]
        format: String,
    },

    /// Natural language semantic search
    Search {
        /// Database name
        #[arg(long, short)]
        db: String,

        /// Search query
        query: String,

        /// Number of results
        #[arg(long, default_value = "10")]
        top_k: usize,

        /// Minimum similarity score
        #[arg(long, default_value = "0.7")]
        min_score: f32,
    },

    /// Export data to Parquet
    Export {
        /// Database name
        #[arg(long, short)]
        db: String,

        /// Table/schema name to export
        table: String,

        /// Output file path
        #[arg(long)]
        output: PathBuf,
    },

    /// List schemas
    Schemas {
        /// Database name
        #[arg(long, short)]
        db: String,
    },

    /// List all databases
    List,

    /// Create schema from template or file
    CreateSchema {
        /// Database name
        #[arg(long, short)]
        db: String,

        /// New schema name
        name: String,

        /// Template schema to clone (e.g., "resources")
        #[arg(long)]
        template: Option<String>,

        /// JSON Schema file path
        #[arg(long)]
        file: Option<PathBuf>,

        /// Indexed fields (comma-separated)
        #[arg(long)]
        indexed: Option<String>,

        /// Embedding fields (comma-separated)
        #[arg(long)]
        embedding: Option<String>,
    },

    /// Lookup entity by ID, name, key, or URI
    Lookup {
        /// Database name
        #[arg(long, short)]
        db: String,

        /// Entity ID (UUID)
        #[arg(long)]
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
    },

    /// Upsert data from JSONL file
    Upsert {
        /// Database name
        #[arg(long, short)]
        db: String,

        /// Table/schema name
        table: String,

        /// JSONL file path
        #[arg(long)]
        file: PathBuf,

        /// Key field for upsert (defaults to "id")
        #[arg(long, default_value = "id")]
        key_field: String,
    },

    /// Ask natural language query with LLM-powered query builder
    Ask {
        /// Database name
        #[arg(long, short)]
        db: String,

        /// Natural language query
        query: String,

        /// Optional schema/table name (auto-detected if not provided)
        #[arg(long)]
        schema: Option<String>,

        /// Maximum retrieval stages for fallbacks
        #[arg(long, default_value = "3")]
        max_stages: usize,

        /// Output format (json or table)
        #[arg(long, default_value = "table")]
        format: String,
    },
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cli = Cli::parse();

    match cli.command {
        Commands::Init { name, path } => {
            println!("{}", "Initializing database...".cyan());

            // Determine database path
            let db_path = if let Some(custom_path) = path {
                custom_path
            } else {
                Config::default_db_dir()?.join(&name)
            };

            // Create database
            let db = Database::open(&db_path, &name)?;

            // Register in config
            let mut config = Config::load()?;
            config.register(name.clone(), db_path.clone(), None)?;

            // Register built-in schemas
            register_builtin_schemas(&db)?;

            let schemas = db.list_schemas();
            println!(
                "{} Registered {} system schemas:",
                "✓".green(),
                schemas.len()
            );
            for schema_name in &schemas {
                let schema = db.get_schema(schema_name)?;
                println!("  • {} ({})", schema_name, schema.name);
            }

            // Insert some example resources
            println!("\n{}", "Creating system entities...".cyan());
            insert_system_entities(&db).await?;

            println!("\n{} Database initialized: {}", "✓".green(), name);
            println!("   Path: {}", db_path.display());
        }

        Commands::Query { db, query, format } => {
            println!("{} Executing query...", "→".cyan());

            let (path, tenant) = resolve_database(&db)?;
            let database = Database::open(&path, &tenant)?;

            // For now, just scan entities (SQL parser not implemented yet)
            // In production, this would parse and execute the SQL
            println!(
                "{}",
                "Note: Full SQL support coming soon. Showing all entities for now.".yellow()
            );

            let entities = database.scan_entities()?;

            if format == "json" {
                println!("{}", serde_json::to_string_pretty(&entities)?);
            } else {
                println!("\n{} Found {} entities:", "✓".green(), entities.len());
                for entity in entities.iter().take(10) {
                    println!("  • {} (type: {})", entity.id, entity.entity_type);
                }
                if entities.len() > 10 {
                    println!("  ... and {} more", entities.len() - 10);
                }
            }
        }

        Commands::Search {
            db,
            query,
            top_k,
            min_score,
        } => {
            println!("{} Searching for: {}", "→".cyan(), query.bright_white());

            let (path, tenant) = resolve_database(&db)?;
            let database = Database::open(&path, &tenant)?;

            // Generate query embedding
            if let Some(provider) = &database.embedding_provider {
                let query_embedding = provider.embed(&query).await?;

                // Get all entities with embeddings and calculate similarity
                let entities = database.scan_entities()?;
                let mut results: Vec<_> = entities
                    .iter()
                    .filter_map(|entity| {
                        // Extract embedding from properties
                        if let Some(emb_value) = entity.properties.get("embedding") {
                            if let Some(emb_array) = emb_value.as_array() {
                                let embedding: Vec<f32> = emb_array
                                    .iter()
                                    .filter_map(|v| v.as_f64().map(|f| f as f32))
                                    .collect();

                                if embedding.len() == query_embedding.len() {
                                    let score = cosine_similarity(&query_embedding, &embedding);
                                    if score >= min_score {
                                        return Some((entity, score));
                                    }
                                }
                            }
                        }
                        None
                    })
                    .collect();

                // Sort by score descending
                results.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
                results.truncate(top_k);

                if results.is_empty() {
                    println!("{}", "No results found".yellow());
                    println!("Try lowering --min-score (currently {})", min_score);
                    return Ok(());
                }

                println!("\n{} Found {} results:\n", "✓".green(), results.len());

                for (i, (entity, score)) in results.iter().enumerate() {
                    println!(
                        "{}. {} {}",
                        (i + 1).to_string().cyan().bold(),
                        entity
                            .properties
                            .get("name")
                            .and_then(|v| v.as_str())
                            .unwrap_or("Unnamed"),
                        format!("(score: {:.3})", score).dimmed()
                    );

                    // Show content preview
                    if let Some(content) = entity
                        .properties
                        .get("content")
                        .or_else(|| entity.properties.get("description"))
                        .and_then(|v| v.as_str())
                    {
                        let preview = if content.len() > 200 {
                            format!("{}...", &content[..200])
                        } else {
                            content.to_string()
                        };
                        println!("   {}\n", preview.dimmed());
                    }
                }
            } else {
                println!("{}", "Error: Embedding provider not available".red());
                return Err("Embeddings not enabled".into());
            }
        }

        Commands::Export { db, table, output } => {
            println!(
                "{} Exporting table '{}' to {}",
                "→".cyan(),
                table,
                output.display()
            );

            let (path, tenant) = resolve_database(&db)?;
            let database = Database::open(&path, &tenant)?;

            // Get entities by type
            let entities = database.scan_entities_by_type(&table)?;

            if entities.is_empty() {
                println!("{}", "No entities found in table".yellow());
                return Ok(());
            }

            // For now, export as JSON (Parquet export requires arrow crate)
            println!(
                "{}",
                "Note: Parquet export coming soon. Exporting as JSON for now.".yellow()
            );

            let json_output = output.with_extension("json");
            let json_data = serde_json::to_string_pretty(&entities)?;
            std::fs::write(&json_output, json_data)?;

            println!(
                "{} Exported {} entities to {}",
                "✓".green(),
                entities.len(),
                json_output.display()
            );
        }

        Commands::Schemas { db } => {
            let (path, tenant) = resolve_database(&db)?;
            let database = Database::open(&path, &tenant)?;

            let schemas = database.list_schemas();

            if schemas.is_empty() {
                println!("{}", "No schemas registered".yellow());
                println!("Run: rem-db init {}", db);
                return Ok(());
            }

            println!("{} Database: {}", "✓".green(), db.bright_white());
            println!("{}", "Registered schemas:".cyan().bold());
            println!();

            for schema_name in schemas {
                let schema = database.get_schema(&schema_name)?;
                println!("  {} {}", "•".green(), schema_name.bright_white());
                println!("    Indexed fields: {:?}", schema.indexed_fields);
                println!("    Embedding fields: {:?}", schema.embedding_fields);
                println!();
            }
        }

        Commands::List => {
            let config = Config::load()?;
            let databases = config.list();

            if databases.is_empty() {
                println!("{}", "No databases registered".yellow());
                println!("Run: rem-db init <name>");
                return Ok(());
            }

            println!("{}", "Registered databases:".cyan().bold());
            println!();

            for db_config in databases {
                println!("  {} {}", "•".green(), db_config.name.bright_white());
                println!("    Path: {}", db_config.path.display().to_string().dimmed());
                println!("    Tenant: {}", db_config.tenant.dimmed());
                println!();
            }
        }

        Commands::CreateSchema {
            db,
            name,
            template,
            file,
            indexed,
            embedding,
        } => {
            println!(
                "{} Creating schema '{}' in database '{}'",
                "→".cyan(),
                name,
                db
            );

            let (path, tenant) = resolve_database(&db)?;
            let database = Database::open(&path, &tenant)?;

            // Get schema from template or file
            let (pydantic_schema, indexed_fields, embedding_fields) = if let Some(template_name) = template {
                // Clone from existing schema
                let template_schema = database.get_schema(&template_name)
                    .map_err(|_| format!("Template schema '{}' not found", template_name))?;

                println!("  {} Using template: {}", "→".cyan(), template_name);

                (
                    template_schema.raw_schema.clone(),
                    template_schema.indexed_fields.clone(),
                    template_schema.embedding_fields.clone(),
                )
            } else if let Some(file_path) = file {
                // Load from file (full Pydantic JSON or simple JSON Schema)
                let content = std::fs::read_to_string(&file_path)?;
                let schema: serde_json::Value = serde_json::from_str(&content)?;

                println!("  {} Loaded schema from: {}", "→".cyan(), file_path.display());

                // Extract REM fields if present in file
                let indexed = schema.get("indexed_fields")
                    .and_then(|v| v.as_array())
                    .map(|arr| arr.iter().filter_map(|v| v.as_str().map(String::from)).collect())
                    .unwrap_or_default();

                let embedding = schema.get("embedding_fields")
                    .and_then(|v| v.as_array())
                    .map(|arr| arr.iter().filter_map(|v| v.as_str().map(String::from)).collect())
                    .unwrap_or_default();

                (schema, indexed, embedding)
            } else {
                return Err("Must provide either --template or --file".into());
            };

            // Parse indexed and embedding fields from CLI if provided
            let indexed_fields = if let Some(fields) = indexed {
                fields.split(',').map(|s| s.trim().to_string()).collect()
            } else {
                indexed_fields
            };

            let embedding_fields = if let Some(fields) = embedding {
                fields.split(',').map(|s| s.trim().to_string()).collect()
            } else {
                embedding_fields
            };

            // Register the schema
            database.register_schema(
                name.clone(),
                pydantic_schema,
                indexed_fields.clone(),
                embedding_fields.clone(),
            )?;

            println!("{} Schema '{}' created successfully", "✓".green(), name);
            println!("   Indexed fields: {:?}", indexed_fields);
            println!("   Embedding fields: {:?}", embedding_fields);
        }

        Commands::Lookup {
            db,
            id,
            name,
            key,
            uri,
            chunk,
        } => {
            let (path, tenant) = resolve_database(&db)?;
            let database = Database::open(&path, &tenant)?;

            // Determine lookup strategy and compute UUID
            let entity_id = if let Some(id_str) = id {
                // Direct ID lookup
                Uuid::parse_str(&id_str)
                    .map_err(|_| format!("Invalid UUID: {}", id_str))?
            } else if let Some(uri_str) = uri {
                // Compute hash(uri:chunk) for URI-based lookup
                let key_string = format!("{}:{}", uri_str, chunk);
                let hash = blake3::hash(key_string.as_bytes());
                let hash_bytes = hash.as_bytes();
                let mut uuid_bytes = [0u8; 16];
                uuid_bytes.copy_from_slice(&hash_bytes[0..16]);
                Uuid::from_bytes(uuid_bytes)
            } else if let Some(key_str) = key {
                // Compute hash(key) for key-based lookup
                let hash = blake3::hash(key_str.as_bytes());
                let hash_bytes = hash.as_bytes();
                let mut uuid_bytes = [0u8; 16];
                uuid_bytes.copy_from_slice(&hash_bytes[0..16]);
                Uuid::from_bytes(uuid_bytes)
            } else if let Some(name_str) = name {
                // Compute hash(name) for name-based lookup
                let hash = blake3::hash(name_str.as_bytes());
                let hash_bytes = hash.as_bytes();
                let mut uuid_bytes = [0u8; 16];
                uuid_bytes.copy_from_slice(&hash_bytes[0..16]);
                Uuid::from_bytes(uuid_bytes)
            } else {
                return Err("Must provide one of: --id, --name, --key, or --uri".into());
            };

            // Lookup entity
            match database.get_entity(entity_id)? {
                Some(entity) => {
                    println!("{} Found entity:", "✓".green());
                    println!("\n{}", serde_json::to_string_pretty(&entity)?);
                }
                None => {
                    println!("{} Entity not found", "✗".yellow());
                    println!("   ID: {}", entity_id);
                }
            }
        }

        Commands::Upsert {
            db,
            table,
            file,
            key_field,
        } => {
            println!(
                "{} Upserting data from {} to table '{}'",
                "→".cyan(),
                file.display(),
                table
            );

            let (path, tenant) = resolve_database(&db)?;
            let database = Database::open(&path, &tenant)?;

            // Read JSONL file
            let file_content = std::fs::read_to_string(&file)?;
            let mut entities = Vec::new();

            for (line_num, line) in file_content.lines().enumerate() {
                if line.trim().is_empty() {
                    continue;
                }

                match serde_json::from_str::<serde_json::Value>(line) {
                    Ok(value) => entities.push(value),
                    Err(e) => {
                        println!(
                            "{} Error parsing line {}: {}",
                            "✗".red(),
                            line_num + 1,
                            e
                        );
                        return Err(e.into());
                    }
                }
            }

            if entities.is_empty() {
                println!("{}", "No entities found in file".yellow());
                return Ok(());
            }

            println!(
                "{} Parsed {} entities from file",
                "✓".green(),
                entities.len()
            );

            // Auto-register schema if it doesn't exist
            if database.get_schema(&table).is_err() {
                println!("{} Registering schema for table '{}'", "→".cyan(), table);

                // Infer schema from first entity
                let schema_props = if let Some(first_entity) = entities.first() {
                    if let Some(obj) = first_entity.as_object() {
                        let mut props = serde_json::Map::new();
                        for (key, value) in obj {
                            let type_name = match value {
                                serde_json::Value::String(_) => "string",
                                serde_json::Value::Number(_) => "number",
                                serde_json::Value::Bool(_) => "boolean",
                                serde_json::Value::Array(_) => "array",
                                serde_json::Value::Object(_) => "object",
                                serde_json::Value::Null => "string",
                            };
                            props.insert(key.clone(), json!({"type": type_name}));
                        }
                        props
                    } else {
                        serde_json::Map::new()
                    }
                } else {
                    serde_json::Map::new()
                };

                let schema = json!({
                    "type": "object",
                    "properties": schema_props
                });

                // Detect fields with "content" or "description" for embeddings
                let embedding_fields = if schema_props.contains_key("content") {
                    vec!["content".to_string()]
                } else if schema_props.contains_key("description") {
                    vec!["description".to_string()]
                } else {
                    Vec::new()
                };

                database.register_schema(
                    table.clone(),
                    schema,
                    vec![],
                    embedding_fields.clone(),
                )?;

                println!(
                    "  {} Schema registered with embedding fields: {:?}",
                    "✓".green(),
                    embedding_fields
                );
            }

            // Batch insert with embeddings
            let entity_ids = database
                .batch_insert_with_embedding(&table, entities, Some(&key_field))
                .await?;

            println!(
                "{} Upserted {} entities to table '{}'",
                "✓".green(),
                entity_ids.len(),
                table
            );
            println!("   Key field: {}", key_field.dimmed());
        }

        Commands::Ask {
            db,
            query,
            schema,
            max_stages,
            format,
        } => {
            use percolate_rocks::query::{QueryBuilder, QueryType, SqlQuery};

            println!("{} Natural language query: \"{}\"", "→".cyan(), query);

            let (path, tenant) = resolve_database(&db)?;
            let database = Database::open(&path, &tenant)?;

            // Step 1: Determine schema (auto-detect if not provided)
            let target_schema = if let Some(schema_name) = schema {
                println!("   {} Using schema: {}", "→".dimmed(), schema_name);
                schema_name.clone()
            } else {
                println!("   {} Auto-detecting schema...", "→".dimmed());
                let candidates = database.auto_detect_schema(&query, 5).await?;

                if candidates.is_empty() {
                    println!("{} No schemas found in database", "✗".red());
                    return Err("No schemas available".into());
                }

                if candidates.len() == 1 {
                    let (name, desc) = &candidates[0];
                    println!("   {} Auto-selected schema: {} - {}", "✓".green(), name, desc.dimmed());
                    name.clone()
                } else {
                    // Show candidates and pick first (in future, ask LLM to choose)
                    println!("   {} Found {} candidate schemas:", "→".dimmed(), candidates.len());
                    for (i, (name, desc)) in candidates.iter().enumerate() {
                        println!("      {}. {} - {}", i + 1, name, desc.dimmed());
                    }
                    let (name, _) = &candidates[0];
                    println!("   {} Selecting: {}", "✓".green(), name);
                    name.clone()
                }
            };

            // Step 2: Get schema details
            let schema_obj = database.get_schema(&target_schema)?;
            let schema_json = schema_obj.validation_schema();

            println!("   {} Building query with LLM...", "→".dimmed());

            // Step 3: Use LLM to build query
            let query_builder = QueryBuilder::new(None, None)?;
            let query_result = query_builder
                .build_query(&query, &schema_json, &target_schema, max_stages)
                .await?;

            println!(
                "{} Query type: {:?} (confidence: {:.2})",
                "✓".green(),
                query_result.query_type,
                query_result.confidence
            );
            println!("   Generated query: {}", query_result.query.cyan());

            if let Some(explanation) = &query_result.explanation {
                println!("   Note: {}", explanation.yellow());
            }

            // Step 4: Execute query based on type
            match query_result.query_type {
                QueryType::KeyValue => {
                    println!("\n{} Executing key-value lookup...", "→".cyan());

                    // Parse SQL to extract key field and value
                    let sql_query = match SqlQuery::parse(&query_result.query) {
                        Ok(q) => q,
                        Err(e) => {
                            println!("{} Failed to parse lookup query: {}", "✗".red(), e);
                            return Ok(());
                        }
                    };

                    if sql_query.predicates.is_empty() {
                        println!("{} No lookup key specified", "✗".yellow());
                        return Ok(());
                    }

                    // Get the first predicate (key lookup)
                    let predicate = &sql_query.predicates[0];
                    let key_field = &predicate.field;
                    let key_value = &predicate.value;

                    println!("   {} Looking up by {}: {}", "→".dimmed(), key_field, key_value);

                    // Generate deterministic UUID from key
                    let lookup_key = if key_field == "uri" {
                        // For URI, include chunk_ordinal (default 0)
                        format!("{}:0", key_value)
                    } else {
                        key_value.clone()
                    };

                    let hash = blake3::hash(lookup_key.as_bytes());
                    let mut uuid_bytes = [0u8; 16];
                    uuid_bytes.copy_from_slice(&hash.as_bytes()[0..16]);
                    let entity_id = Uuid::from_bytes(uuid_bytes);

                    // Try exact lookup
                    match database.get_entity(entity_id)? {
                        Some(entity) => {
                            println!("{} Found entity (exact match):\n", "✓".green());
                            if format == "json" {
                                println!("{}", serde_json::to_string_pretty(&entity)?);
                            } else {
                                println!("ID: {}", entity.id.to_string().dimmed());
                                println!("{}", serde_json::to_string_pretty(&entity.properties)?);
                            }
                        }
                        None => {
                            println!("{} No exact match found", "!".yellow());
                            println!("   {} Trying fuzzy fallback...", "→".dimmed());

                            // Fallback: scan and match by field value
                            let all_entities = database.scan_entities_by_type(&target_schema)?;
                            let matches: Vec<&Entity> = all_entities
                                .iter()
                                .filter(|e| {
                                    if let Some(field_val) = e.properties.get(key_field) {
                                        if let Some(val_str) = field_val.as_str() {
                                            // Fuzzy match: case-insensitive contains
                                            val_str.to_lowercase().contains(&key_value.to_lowercase())
                                        } else {
                                            false
                                        }
                                    } else {
                                        false
                                    }
                                })
                                .collect();

                            if matches.is_empty() {
                                println!("{} No fuzzy matches found", "✗".yellow());
                            } else {
                                println!("{} Found {} fuzzy match(es):\n", "✓".green(), matches.len());
                                for (i, entity) in matches.iter().enumerate() {
                                    if format == "json" {
                                        println!("{}", serde_json::to_string_pretty(entity)?);
                                    } else {
                                        println!("{}. {} [fuzzy]", i + 1, entity.id.to_string().dimmed());
                                        println!("   {}", serde_json::to_string_pretty(&entity.properties)?);
                                    }
                                }
                            }
                        }
                    }
                }
                QueryType::Sql => {
                    println!("\n{} Executing SQL query...", "→".cyan());

                    // Parse SQL query
                    let sql_query = match SqlQuery::parse(&query_result.query) {
                        Ok(q) => q,
                        Err(e) => {
                            println!("{} Failed to parse SQL: {}", "✗".red(), e);
                            println!("   Query: {}", query_result.query.dimmed());
                            return Ok(());
                        }
                    };

                    println!("   {} Parsed: {} predicate(s)", "→".dimmed(), sql_query.predicates.len());

                    // Get all entities of the target type
                    let all_entities = database.scan_entities_by_type(&target_schema)?;

                    // Execute query (filter by predicates)
                    let results = sql_query.execute(all_entities);

                    if results.is_empty() {
                        println!("{} No results found", "✗".yellow());
                    } else {
                        println!("{} Found {} results:\n", "✓".green(), results.len());

                        for (i, entity) in results.iter().enumerate() {
                            if format == "json" {
                                println!("{}", serde_json::to_string_pretty(entity)?);
                            } else {
                                println!("{}. {}", i + 1, entity.id.to_string().dimmed());
                                println!("   {}", serde_json::to_string_pretty(&entity.properties)?);
                            }
                        }
                    }
                }
                QueryType::Vector => {
                    println!("\n{} Executing semantic search...", "→".cyan());

                    // Extract query text from vector search syntax
                    // Expected: SELECT * FROM table WHERE embedding.cosine("query text")
                    let search_text = if let Some(start) = query_result.query.find("embedding.") {
                        let after_func = &query_result.query[start..];
                        if let Some(quote_start) = after_func.find('"') {
                            let after_quote = &after_func[quote_start + 1..];
                            if let Some(quote_end) = after_quote.find('"') {
                                &after_quote[..quote_end]
                            } else {
                                &query // Fallback to original query
                            }
                        } else {
                            &query
                        }
                    } else {
                        &query
                    };

                    let results = database.search(&target_schema, search_text, 10).await?;

                    if results.is_empty() {
                        println!("{} No results found", "✗".yellow());
                    } else {
                        println!("{} Found {} results:\n", "✓".green(), results.len());

                        for (i, (entity, score)) in results.iter().enumerate() {
                            if format == "json" {
                                println!("{}", serde_json::to_string_pretty(entity)?);
                            } else {
                                println!("{}. [score: {:.3}]", i + 1, score);
                                println!("   {}", serde_json::to_string_pretty(&entity.properties)?);
                            }
                        }
                    }

                    // Handle fallback if needed
                    if results.is_empty() && query_result.fallback_query.is_some() {
                        println!("\n{} Trying fallback query...", "→".cyan());
                        println!("   {} Fallback queries not yet implemented", "!".yellow());
                    }
                }
            }
        }
    }

    Ok(())
}

/// Resolve database path from name or path.
fn resolve_database(name_or_path: &str) -> Result<(PathBuf, String), Box<dyn std::error::Error>> {
    let config = Config::load()?;
    let (path, tenant) = config.resolve_path(name_or_path)?;
    Ok((path, tenant))
}

/// Register built-in schemas (Resource, Agent, Session, Message).
fn register_builtin_schemas(db: &Database) -> Result<(), Box<dyn std::error::Error>> {
    // 1. Schema meta-schema (bootstrap - defines schema structure itself)
    let schema_schema = json!({
        "title": "Schema",
        "description": "Meta-schema defining the structure of schema entities",
        "version": "1.0.0",
        "short_name": "schema",
        "fully_qualified_name": "rem.schemas.schema",
        "properties": {
            "title": {"type": "string", "description": "Schema title"},
            "description": {"type": "string", "description": "Schema description"},
            "version": {"type": "string", "description": "Schema version (semver)"},
            "short_name": {"type": "string", "description": "Short identifier"},
            "fully_qualified_name": {"type": "string", "description": "Fully qualified name (e.g., rem.schemas.resources)"},
            "properties": {"type": "object", "description": "JSON Schema properties"},
            "required": {"type": "array", "items": {"type": "string"}, "description": "Required field names"},
            "json_schema_extra": {"type": "object", "description": "Additional metadata (tools, resources, etc.)"},
            "indexed_fields": {"type": "array", "items": {"type": "string"}, "description": "Fields to index for fast lookups"},
            "embedding_fields": {"type": "array", "items": {"type": "string"}, "description": "Fields to generate embeddings for"}
        },
        "required": ["fully_qualified_name", "properties"]
    });

    db.register_schema(
        "schema".to_string(),
        schema_schema,
        vec!["fully_qualified_name".to_string()],
        vec!["description".to_string()],
    )?;

    println!("  {} Registered schema: schema (meta-schema)", "✓".green());

    // 2. Resources schema (URI-based chunked documents)
    let resources_schema = json!({
        "title": "Resource",
        "description": "Schema for URI-based chunked documents with embeddings",
        "version": "1.0.0",
        "short_name": "resources",
        "fully_qualified_name": "rem.schemas.resources",
        "properties": {
            "uri": {
                "type": "string",
                "description": "Resource URI (file path, URL, etc.)"
            },
            "chunk_ordinal": {
                "type": "integer",
                "description": "Chunk index for this resource (0-based)",
                "default": 0
            },
            "content": {
                "type": "string",
                "description": "Text content of this chunk"
            },
            "description": {
                "type": "string",
                "description": "Optional description or summary of the resource"
            },
            "category": {
                "type": "string",
                "description": "Resource category (e.g., 'documentation', 'code', 'article')"
            },
            "metadata": {
                "type": "object",
                "description": "Additional metadata (author, created_at, etc.)"
            }
        },
        "required": ["uri", "content"]
    });

    db.register_schema(
        "resources".to_string(),
        resources_schema,
        vec!["uri".to_string(), "category".to_string()],
        vec!["content".to_string(), "description".to_string()],
    )?;

    println!("  {} Registered schema: resources", "✓".green());

    Ok(())
}

/// Insert system entities with descriptions.
async fn insert_system_entities(db: &Database) -> Result<(), Box<dyn std::error::Error>> {
    let resource = json!({
        "uri": "system://schemas/resources",
        "chunk_ordinal": 0,
        "content": "The Resource schema stores chunked, embedded content from documents. \
                    It supports semantic search via vector embeddings and flexible metadata storage.",
        "description": "Built-in schema for URI-based document chunks with embeddings",
        "category": "system"
    });

    let id = db
        .insert_entity_with_embedding("resources", resource)
        .await?;

    println!("  {} Created resource: {}", "✓".green(), id);

    Ok(())
}
