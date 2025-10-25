"""Command-line interface for REM database.

All CLI commands delegate to Rust implementation for performance.
"""

import typer
from typing import Optional
from typing_extensions import Annotated
from pathlib import Path
from rich.console import Console
from rich.table import Table
import json
import os
import sys

app = typer.Typer(help="REM Database CLI")
console = Console()


def get_db_path() -> Path:
    """Get database path from environment or default."""
    path_str = os.environ.get("P8_DB_PATH", "./data")
    return Path(path_str).expanduser()


def get_database():
    """Get database instance with default tenant."""
    from rem_db import Database
    path = get_db_path()
    tenant_id = os.environ.get("P8_TENANT_ID", "default")
    return Database(str(path), tenant_id)


@app.command()
def init(
    path: Annotated[Optional[Path], typer.Option("--path", help="Database directory path")] = None,
):
    """Initialize database.

    Creates database directory and column families.

    Example:
        rem init --path ./data
    """
    try:
        if path:
            os.environ["P8_DB_PATH"] = str(path)

        db_path = get_db_path()
        db_path.mkdir(parents=True, exist_ok=True)

        # Opening the database will initialize it
        db = get_database()

        console.print(f"[green]✓[/green] Initialized database at {db_path}")
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to initialize database: {e}")
        raise typer.Exit(1)


@app.command("schema")
def schema_cmd():
    """Schema management commands."""
    pass


@app.command("schema-add")
def schema_add(
    schema_path: Annotated[Path, typer.Argument(help="Path to schema file (JSON/YAML)")],
):
    """Register schema from JSON or YAML file.

    Example:
        rem schema-add article_schema.json
        rem schema-add article_schema.yaml
    """
    try:
        if not schema_path.exists():
            console.print(f"[red]✗[/red] Schema file not found: {schema_path}")
            raise typer.Exit(1)

        # Read schema file
        with open(schema_path) as f:
            if schema_path.suffix in [".yaml", ".yml"]:
                import yaml
                schema_data = yaml.safe_load(f)
            else:
                schema_data = json.load(f)

        # Get schema name from file or data
        schema_name = schema_data.get("name") or schema_data.get("short_name") or schema_path.stem

        db = get_database()
        db.register_schema(schema_name, json.dumps(schema_data))

        console.print(f"[green]✓[/green] Registered schema: {schema_name}")
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to register schema: {e}")
        raise typer.Exit(1)


@app.command("schema-list")
def schema_list():
    """List registered schemas.

    Example:
        rem schema-list
    """
    try:
        db = get_database()
        schemas = db.list_schemas()

        if schemas:
            table = Table(title="Registered Schemas")
            table.add_column("Name", style="cyan")

            for schema_name in schemas:
                table.add_row(schema_name)

            console.print(table)
        else:
            console.print("[yellow]No schemas registered[/yellow]")
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to list schemas: {e}")
        raise typer.Exit(1)


@app.command()
def insert(
    table: Annotated[str, typer.Argument(help="Table name")],
    data: Annotated[Optional[str], typer.Argument(help="JSON data")] = None,
    batch: Annotated[bool, typer.Option("--batch", help="Batch insert from stdin")] = False,
):
    """Insert entity or batch insert from stdin.

    Examples:
        rem insert articles '{"title": "...", "content": "..."}'
        cat data.jsonl | rem insert articles --batch
    """
    try:
        db = get_database()

        if batch:
            # Read JSONL from stdin
            uuids = []
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue
                entity_data = json.loads(line)
                uuid_str = db.insert(table, entity_data)
                uuids.append(uuid_str)

            console.print(f"[green]✓[/green] Batch insert complete: {len(uuids)} records inserted")
            if uuids and len(uuids) <= 5:
                for uuid_str in uuids:
                    console.print(f"  - {uuid_str}")
        else:
            if not data:
                console.print("[red]✗[/red] No data provided. Use --batch for stdin or provide JSON string.")
                raise typer.Exit(1)

            entity_data = json.loads(data)
            uuid_str = db.insert(table, entity_data)
            console.print(f"[green]✓[/green] Inserted entity with ID: {uuid_str}")
    except Exception as e:
        console.print(f"[red]✗[/red] Insert failed: {e}")
        raise typer.Exit(1)


@app.command()
def ingest(
    file_path: Annotated[Path, typer.Argument(help="Document file path")],
    schema: Annotated[str, typer.Option("--schema", help="Target schema name")] = "resources",
):
    """Upload and chunk document file.

    Example:
        rem ingest tutorial.txt --schema=articles
        rem ingest document.txt --schema=resources
    """
    try:
        if not file_path.exists():
            console.print(f"[red]✗[/red] File not found: {file_path}")
            raise typer.Exit(1)

        db = get_database()
        uuids = db.ingest(str(file_path), schema)

        console.print(f"[green]✓[/green] Ingested {file_path}: {len(uuids)} chunks created")
        if uuids and len(uuids) <= 5:
            for uuid_str in uuids:
                console.print(f"  - {uuid_str}")
        elif uuids:
            console.print(f"  - {uuids[0]} ... and {len(uuids) - 1} more")
    except Exception as e:
        console.print(f"[red]✗[/red] Ingest failed: {e}")
        raise typer.Exit(1)


@app.command()
def get(
    entity_id: Annotated[str, typer.Argument(help="Entity UUID")],
):
    """Get entity by ID.

    Example:
        rem get 550e8400-e29b-41d4-a716-446655440000
    """
    try:
        db = get_database()
        entity = db.get(entity_id)

        if entity:
            console.print_json(json.dumps(entity, indent=2))
        else:
            console.print(f"[yellow]No entity found with ID: {entity_id}[/yellow]")
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] Get failed: {e}")
        raise typer.Exit(1)


@app.command()
def lookup(
    table: Annotated[str, typer.Argument(help="Table name")],
    key_value: Annotated[str, typer.Argument(help="Key field value")],
):
    """Lookup by key field value.

    Example:
        rem lookup articles "Python Guide"
    """
    try:
        db = get_database()
        entities = db.lookup(table, key_value)

        if entities:
            console.print_json(json.dumps(entities, indent=2))
        else:
            console.print(f"[yellow]No entities found with key: {key_value}[/yellow]")
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] Lookup failed: {e}")
        raise typer.Exit(1)


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Search query")],
    schema: Annotated[str, typer.Option("--schema", help="Schema name")] = "resources",
    top_k: Annotated[int, typer.Option("--top-k", help="Number of results")] = 10,
):
    """Semantic search using vector embeddings.

    Example:
        rem search "async programming" --schema=articles --top-k=5
    """
    try:
        db = get_database()
        results = db.search(query, schema, top_k)

        if results:
            for entity, score in results:
                console.print(f"\n[bold cyan]Score: {score:.4f}[/bold cyan]")
                console.print_json(json.dumps(entity, indent=2))
        else:
            console.print("[yellow]No results found[/yellow]")
    except Exception as e:
        console.print(f"[red]✗[/red] Search failed: {e}")
        raise typer.Exit(1)


@app.command()
def query(
    sql: Annotated[str, typer.Argument(help="SQL query")],
):
    """Execute SQL query.

    Example:
        rem query "SELECT * FROM articles WHERE category = 'programming'"
    """
    try:
        db = get_database()
        results = db.query(sql)

        if results:
            console.print_json(json.dumps(results, indent=2))
        else:
            console.print("[yellow]No results[/yellow]")
    except Exception as e:
        console.print(f"[red]✗[/red] Query failed: {e}")
        raise typer.Exit(1)


@app.command()
def ask(
    question: Annotated[str, typer.Argument(help="Natural language question")],
    plan: Annotated[bool, typer.Option("--plan", help="Show query plan without executing")] = False,
    schema: Annotated[Optional[str], typer.Option("--schema", help="Schema hint")] = None,
    model: Annotated[Optional[str], typer.Option("--model", help="LLM model override")] = None,
):
    """Natural language query using LLM.

    Requires OPENAI_API_KEY or ANTHROPIC_API_KEY environment variable.

    Examples:
        rem ask "show recent programming articles"
        rem ask "show recent articles" --plan
        rem ask "find articles about rust" --schema=articles
    """
    try:
        # Set model if provided
        if model:
            os.environ["P8_DEFAULT_LLM"] = model

        db = get_database()
        result = db.ask(question, not plan, schema)

        if plan:
            # Show query plan
            console.print("[bold]Query Plan:[/bold]")
            console.print_json(json.dumps(result, indent=2))
        else:
            # Show results
            console.print_json(json.dumps(result, indent=2))
    except Exception as e:
        console.print(f"[red]✗[/red] Ask failed: {e}")
        if "API key" in str(e):
            console.print("[yellow]Hint:[/yellow] Set OPENAI_API_KEY or ANTHROPIC_API_KEY environment variable")
        raise typer.Exit(1)


@app.command()
def traverse(
    entity_id: Annotated[str, typer.Argument(help="Starting entity UUID")],
    depth: Annotated[int, typer.Option("--depth", help="Traversal depth")] = 2,
    direction: Annotated[str, typer.Option("--direction", help="Direction (out/in/both)")] = "out",
):
    """Graph traversal from entity.

    Example:
        rem traverse 550e8400-... --depth=2 --direction=out
    """
    try:
        db = get_database()
        uuids = db.traverse(entity_id, direction, depth)

        if uuids:
            console.print(f"[green]Found {len(uuids)} entities:[/green]")
            for uuid in uuids:
                console.print(f"  - {uuid}")
        else:
            console.print("[yellow]No connected entities found[/yellow]")
    except Exception as e:
        console.print(f"[red]✗[/red] Traversal failed: {e}")
        raise typer.Exit(1)


@app.command()
def export(
    table: Annotated[str, typer.Argument(help="Table name")],
    output: Annotated[Path, typer.Option("--output", help="Output file path")] = Path("./export.parquet"),
    format: Annotated[str, typer.Option("--format", help="Export format (parquet/csv/jsonl)")] = "parquet",
):
    """Export entities to Parquet/CSV/JSONL.

    Examples:
        rem export articles --output ./data.parquet
        rem export articles --output ./data.csv --format=csv
    """
    try:
        # Infer format from file extension if not specified
        if output.suffix:
            ext_format = output.suffix[1:]  # Remove the dot
            if ext_format in ["parquet", "csv", "jsonl"]:
                format = ext_format

        db = get_database()
        db.export(table, str(output), format)

        console.print(f"[green]✓[/green] Exported to {output}")
    except Exception as e:
        console.print(f"[red]✗[/red] Export failed: {e}")
        raise typer.Exit(1)


@app.command()
def serve(
    host: Annotated[str, typer.Option("--host", help="gRPC server host")] = "0.0.0.0",
    port: Annotated[int, typer.Option("--port", help="gRPC server port")] = 50051,
):
    """Start replication server (primary mode).

    Example:
        rem serve --host 0.0.0.0 --port 50051
    """
    console.print("[red]✗[/red] Not implemented - Rust bindings need to be completed")
    console.print("[yellow]Help wanted:[/yellow] See src/replication module")
    raise typer.Exit(1)


@app.command()
def replicate(
    primary: Annotated[str, typer.Option("--primary", help="Primary host:port")] = "localhost:50051",
    follow: Annotated[bool, typer.Option("--follow", help="Follow primary in real-time")] = False,
):
    """Connect to primary and replicate (replica mode).

    Examples:
        rem replicate --primary=localhost:50051 --follow
    """
    console.print("[red]✗[/red] Not implemented - Rust bindings need to be completed")
    console.print("[yellow]Help wanted:[/yellow] See src/replication module")
    raise typer.Exit(1)


@app.command("replication")
def replication_cmd():
    """Replication status commands."""
    pass


@app.command("replication-wal-status")
def replication_wal_status():
    """Show WAL status.

    Example:
        rem replication wal-status
    """
    console.print("[red]✗[/red] Not implemented - Rust bindings need to be completed")
    console.print("[yellow]Help wanted:[/yellow] See src/replication module")
    raise typer.Exit(1)


@app.command("replication-status")
def replication_status():
    """Show replication status.

    Example:
        rem replication status
    """
    console.print("[red]✗[/red] Not implemented - Rust bindings need to be completed")
    console.print("[yellow]Help wanted:[/yellow] See src/replication module")
    raise typer.Exit(1)


if __name__ == "__main__":
    app()
