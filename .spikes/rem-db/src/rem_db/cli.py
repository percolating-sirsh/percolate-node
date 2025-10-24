"""Command-line interface for REM Database."""

import json
import os
import sys
from pathlib import Path
from typing import Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from .database import REMDatabase
from .models import Agent, Resource, Session

app = typer.Typer(
    name="rem-db",
    help="REM Database - RocksDB + Vectors + SQL",
    add_completion=False
)

console = Console()


def get_db_path(name: str, custom_path: Optional[str] = None) -> Path:
    """Get database path."""
    if custom_path:
        return Path(custom_path)
    return Path.home() / ".p8" / "node" / "db" / name


@app.command()
def new(
    name: str = typer.Argument(..., help="Database name"),
    path: Optional[str] = typer.Option(None, help="Custom database path"),
    tenant: str = typer.Option("default", help="Tenant ID"),
):
    """Create a new REM database."""
    db_path = get_db_path(name, path)

    if db_path.exists():
        rprint(f"[red]Error: Database already exists at {db_path}[/red]")
        raise typer.Exit(1)

    # Create database
    db = REMDatabase(tenant_id=tenant, path=str(db_path))

    rprint(f"[green]✓[/green] Created database: {name}")
    rprint(f"  Location: {db_path}")
    rprint(f"  Tenant: {tenant}")
    rprint(f"\nNext step: rem-db init --db {name}")


@app.command()
def init(
    db_name: str = typer.Option("default", "--db", help="Database name"),
    path: Optional[str] = typer.Option(None, help="Custom database path"),
    tenant: str = typer.Option("default", help="Tenant ID"),
):
    """Initialize database with system schemas and entities."""
    db_path = get_db_path(db_name, path)

    if not db_path.exists():
        rprint(f"[red]Error: Database not found at {db_path}[/red]")
        rprint(f"Create it first with: rem-db new {db_name}")
        raise typer.Exit(1)

    # Open database
    db = REMDatabase(tenant_id=tenant, path=str(db_path))

    rprint("[cyan]Initializing database...[/cyan]")

    # Built-in schemas are auto-registered in __init__
    schemas = db.list_schemas()
    rprint(f"[green]✓[/green] Registered {len(schemas)} system schemas:")
    for schema_name in schemas:
        schema = db.get_schema(schema_name)
        rprint(f"  • {schema_name} ({schema.category})")

    # Insert system entities with descriptions
    rprint("\n[cyan]Creating system entities with embedded descriptions...[/cyan]")

    system_entities = [
        ("resources", Resource, {
            "name": "Resource Schema",
            "content": """The Resource schema stores chunked, embedded content from documents.
            It supports semantic search via vector embeddings and flexible metadata storage.
            Resources can represent documents, notes, code snippets, or any text-based content
            that needs to be searchable and retrievable.""",
            "category": "system",
            "metadata": {"type": "schema-definition", "version": "1.0.0"}
        }),
        ("agents", Agent, {
            "name": "Agent Schema",
            "description": """The Agent schema defines agent-lets with output schemas and MCP tools.
            Agent-lets are trainable AI skills with structured outputs defined via JSON schemas.
            They can reference MCP tools for capabilities and are versioned for reproducibility.
            Agents can be system-defined, user-created, or publicly shared.""",
            "category": "system",
            "metadata": {"type": "schema-definition", "version": "1.0.0"}
        }),
        ("sessions", Session, {
            "name": "Session Schema",
            "query": """The Session schema tracks conversation sessions and agent interactions.
            Sessions group related messages and link to cases or projects for context.
            They support nested conversations via parent_session_id and track completion status.""",
            "agent": "system",
            "session_type": "documentation",
            "metadata": {"type": "schema-definition", "version": "1.0.0"}
        }),
    ]

    for table_name, model_class, data in system_entities:
        try:
            entity_id = db.insert(table_name, data)
            rprint(f"[green]✓[/green] Created {table_name}: {data.get('name', data.get('query', 'entity'))}")
        except Exception as e:
            rprint(f"[yellow]⚠[/yellow] {table_name}: {str(e)}")

    rprint(f"\n[green]✓[/green] Database initialized successfully!")
    rprint(f"\nTry these commands:")
    rprint(f"  rem-db schemas --db {db_name}")
    rprint(f"  rem-db sql \"SELECT * FROM agents\"")
    rprint(f"  rem-db query \"what schemas are available?\"")


@app.command()
def schemas(
    db_name: str = typer.Option("default", "--db", help="Database name"),
    path: Optional[str] = typer.Option(None, help="Custom database path"),
    tenant: str = typer.Option("default", help="Tenant ID"),
    category: Optional[str] = typer.Option(None, help="Filter by category"),
):
    """List registered schemas."""
    db_path = get_db_path(db_name, path)

    if not db_path.exists():
        rprint(f"[red]Error: Database not found at {db_path}[/red]")
        raise typer.Exit(1)

    db = REMDatabase(tenant_id=tenant, path=str(db_path))

    # Get schemas
    if category:
        schema_names = db.list_schemas_by_category(category)
        rprint(f"[cyan]Schemas in category '{category}':[/cyan]")
    else:
        schema_names = db.list_schemas()
        rprint(f"[cyan]All schemas:[/cyan]")

    # Display as table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Name", style="cyan")
    table.add_column("Category", style="yellow")
    table.add_column("Version", style="green")
    table.add_column("Fields", style="white")

    for name in schema_names:
        schema = db.get_schema(name)
        if schema:
            field_count = len(schema.properties)
            table.add_row(
                name,
                schema.category,
                schema.version or "1.0.0",
                str(field_count)
            )

    console.print(table)
    rprint(f"\nTotal: {len(schema_names)} schema(s)")


@app.command()
def sql(
    query: str = typer.Argument(..., help="SQL query"),
    db_name: str = typer.Option("default", "--db", help="Database name"),
    path: Optional[str] = typer.Option(None, help="Custom database path"),
    tenant: str = typer.Option("default", help="Tenant ID"),
    output: str = typer.Option("table", help="Output format (table, json)"),
):
    """Execute SQL query."""
    db_path = get_db_path(db_name, path)

    if not db_path.exists():
        rprint(f"[red]Error: Database not found at {db_path}[/red]")
        raise typer.Exit(1)

    db = REMDatabase(tenant_id=tenant, path=str(db_path))

    try:
        results = db.sql(query)

        if output == "json":
            rprint(json.dumps(results, indent=2, default=str))
        else:
            # Table output
            if not results:
                rprint("[yellow]No results[/yellow]")
                return

            table = Table(show_header=True, header_style="bold magenta")

            # Add columns
            for key in results[0].keys():
                table.add_column(key, style="cyan")

            # Add rows
            for row in results:
                table.add_row(*[str(v) for v in row.values()])

            console.print(table)
            rprint(f"\n[green]{len(results)} row(s) returned[/green]")

    except Exception as e:
        rprint(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command()
def query(
    query_text: str = typer.Argument(..., help="Natural language query"),
    db_name: str = typer.Option("default", "--db", help="Database name"),
    path: Optional[str] = typer.Option(None, help="Custom database path"),
    tenant: str = typer.Option("default", help="Tenant ID"),
    top_k: int = typer.Option(10, help="Number of results"),
    min_score: float = typer.Option(0.7, help="Minimum similarity score"),
):
    """Execute natural language query (semantic search)."""
    db_path = get_db_path(db_name, path)

    if not db_path.exists():
        rprint(f"[red]Error: Database not found at {db_path}[/red]")
        raise typer.Exit(1)

    db = REMDatabase(tenant_id=tenant, path=str(db_path))

    # Check if embedding model is available
    if not db._embedding_model:
        rprint("[red]Error: Embedding model not available[/red]")
        rprint("Install sentence-transformers: uv pip install sentence-transformers")
        raise typer.Exit(1)

    try:
        # Generate query embedding
        rprint(f"[cyan]Searching for:[/cyan] {query_text}")
        query_embedding = db._generate_embedding(query_text)

        if not query_embedding:
            rprint("[red]Error: Failed to generate query embedding[/red]")
            raise typer.Exit(1)

        # Perform vector search
        results = db.search_similar(query_embedding, top_k=top_k, min_score=min_score)

        if not results:
            rprint("[yellow]No results found[/yellow]")
            rprint(f"Try lowering --min-score (currently {min_score})")
            return

        # Display results
        rprint(f"\n[green]Found {len(results)} result(s):[/green]\n")

        for i, (item, score) in enumerate(results, 1):
            rprint(f"[bold cyan]{i}. {item.name}[/bold cyan] [dim](score: {score:.3f})[/dim]")

            # Get content from item (Resource has .content, Entity has .properties['content'])
            content = None
            if hasattr(item, 'content'):
                content = item.content
            elif hasattr(item, 'properties') and 'content' in item.properties:
                content = item.properties['content']
            elif hasattr(item, 'properties') and 'description' in item.properties:
                content = item.properties['description']

            # Show content preview (first 200 chars)
            if content:
                content_preview = content[:200] if len(content) > 200 else content
                if len(content) > 200:
                    content_preview += "..."
                rprint(f"   {content_preview}")

            # Show metadata if present
            metadata = getattr(item, 'metadata', None) or (item.properties.get('metadata') if hasattr(item, 'properties') else None)
            if metadata:
                rprint(f"   [dim]Metadata: {metadata}[/dim]")

            rprint()  # Empty line between results

    except Exception as e:
        rprint(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command()
def info(
    db_name: str = typer.Option("default", "--db", help="Database name"),
    path: Optional[str] = typer.Option(None, help="Custom database path"),
    tenant: str = typer.Option("default", help="Tenant ID"),
):
    """Show database information."""
    db_path = get_db_path(db_name, path)

    if not db_path.exists():
        rprint(f"[red]Error: Database not found at {db_path}[/red]")
        raise typer.Exit(1)

    db = REMDatabase(tenant_id=tenant, path=str(db_path))

    rprint(f"[cyan]Database Information[/cyan]")
    rprint(f"  Name: {db_name}")
    rprint(f"  Location: {db_path}")
    rprint(f"  Tenant: {tenant}")
    rprint(f"  Embedding dim: {db.embedding_dim} (default)")

    # Schemas
    schemas = db.list_schemas()
    rprint(f"\n[cyan]Schemas:[/cyan] {len(schemas)}")
    for category in db.get_categories():
        cat_schemas = db.list_schemas_by_category(category)
        if cat_schemas:
            rprint(f"  {category}: {len(cat_schemas)}")

    # TODO: Add entity counts, storage size, etc.


@app.command()
def insert(
    schema: str = typer.Argument(..., help="Schema name"),
    data: str = typer.Option(..., help="JSON data to insert"),
    db_name: str = typer.Option("default", "--db", help="Database name"),
    path: Optional[str] = typer.Option(None, help="Custom database path"),
    tenant: str = typer.Option("default", help="Tenant ID"),
):
    """Insert entity into schema."""
    db_path = get_db_path(db_name, path)

    if not db_path.exists():
        rprint(f"[red]Error: Database not found at {db_path}[/red]")
        raise typer.Exit(1)

    db = REMDatabase(tenant_id=tenant, path=str(db_path))

    try:
        data_dict = json.loads(data)
        entity_id = db.insert(schema, data_dict)
        rprint(f"[green]✓[/green] Inserted entity: {entity_id}")
    except json.JSONDecodeError as e:
        rprint(f"[red]Error: Invalid JSON - {str(e)}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        rprint(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command()
def ask(
    query: str = typer.Argument(..., help="Natural language query"),
    table: str = typer.Option("resources", help="Table to query"),
    db_name: str = typer.Option("default", "--db", help="Database name"),
    path: Optional[str] = typer.Option(None, help="Custom database path"),
    tenant: str = typer.Option("default", help="Tenant ID"),
    max_stages: int = typer.Option(3, help="Maximum retrieval stages"),
    show_metadata: bool = typer.Option(False, "--metadata", help="Show query metadata"),
):
    """Ask a natural language question and get results.

    Examples:
        rem-db ask "find resources about programming"
        rem-db ask "get resource with name Python" --table resources
        rem-db ask "resources about web development" --metadata
    """
    db_path = get_db_path(db_name, path)

    if not db_path.exists():
        rprint(f"[red]Error: Database not found at {db_path}[/red]")
        raise typer.Exit(1)

    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        rprint("[red]Error: OPENAI_API_KEY environment variable not set[/red]")
        rprint("Set your OpenAI API key to use natural language queries:")
        rprint("  export OPENAI_API_KEY='your-key-here'")
        raise typer.Exit(1)

    db = REMDatabase(tenant_id=tenant, path=str(db_path))

    try:
        rprint(f"\n[cyan]Query:[/cyan] {query}")
        rprint(f"[dim]Table: {table}[/dim]\n")

        # Execute natural language query
        result = db.query_natural_language(query, table, max_stages=max_stages)

        # Show generated query
        rprint(f"[green]Generated {result['query_type']} query:[/green]")
        rprint(f"  {result['query']}\n")

        # Show confidence
        confidence_color = "green" if result['confidence'] >= 0.8 else "yellow"
        rprint(f"[{confidence_color}]Confidence: {result['confidence']:.2f}[/{confidence_color}]")

        # Show explanation if present
        if result['explanation']:
            rprint(f"\n[yellow]Explanation:[/yellow]")
            rprint(f"  {result['explanation']}")

        # Show results
        results = result['results']
        if not results:
            rprint("\n[yellow]No results found[/yellow]")
            if result.get('fallback_query'):
                rprint(f"[dim]Fallback query available: {result['fallback_query']}[/dim]")
        else:
            rprint(f"\n[green]Found {len(results)} result(s):[/green]\n")

            for i, row in enumerate(results, 1):
                # Display based on available fields
                name = row.get('name', row.get('id', f'Result {i}'))
                rprint(f"[bold cyan]{i}. {name}[/bold cyan]")

                # Show score if present (from vector search)
                if '_score' in row:
                    rprint(f"   [dim]Similarity: {row['_score']:.4f}[/dim]")

                # Show content preview
                content = row.get('content') or row.get('description')
                if content:
                    preview = content[:200] if len(content) > 200 else content
                    if len(content) > 200:
                        preview += "..."
                    rprint(f"   {preview}")

                rprint()

        # Show metadata if requested
        if show_metadata:
            rprint("\n[cyan]Query Metadata:[/cyan]")
            rprint(f"  Query type: {result['query_type']}")
            rprint(f"  Stages: {result['stages']}")
            if result.get('fallback_query'):
                rprint(f"  Fallback: {result['fallback_query']}")

    except Exception as e:
        rprint(f"[red]Error: {str(e)}[/red]")
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)
    finally:
        db.close()


def main():
    """CLI entry point."""
    app()


if __name__ == "__main__":
    main()
