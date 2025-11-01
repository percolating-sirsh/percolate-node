"""CLI entry point."""

import asyncio
import json
import uuid
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(name="percolate", help="Personal AI node CLI")
console = Console()

# Register subcommands
from percolate.cli.test_topology import app as test_topology_app
app.add_typer(test_topology_app, name="test-topology")

# Import REM database CLI
try:
    from rem_db.cli import app as rem_app
    app.add_typer(rem_app, name="rem", help="REM database commands")
except ImportError:
    pass  # rem_db not installed, skip


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="API server host"),
    port: int = typer.Option(8000, help="API server port"),
    reload: bool = typer.Option(False, help="Auto-reload on code changes"),
) -> None:
    """Start the Percolate API server with integrated MCP endpoint.

    The server provides:
    - REST API at /v1/agents/eval
    - MCP endpoint at /mcp (SSE transport)
    - Health check at /health
    - OpenAPI docs at /docs

    Examples:
        percolate serve
        percolate serve --reload
        percolate serve --host 127.0.0.1 --port 8080
    """
    import uvicorn

    console.print(f"[green]Starting Percolate API server on {host}:{port}[/green]")
    console.print(f"[dim]API endpoint:[/dim] http://{host}:{port}/v1/agents/eval")
    console.print(f"[dim]MCP endpoint:[/dim] http://{host}:{port}/mcp")
    console.print(f"[dim]Docs:[/dim] http://{host}:{port}/docs")

    uvicorn.run(
        "percolate.api.main:app",
        host=host,
        port=port,
        reload=reload,
    )


@app.command()
def mcp() -> None:
    """Run MCP server in stdio mode for Claude Desktop.

    This command starts the MCP server using stdio transport,
    which is required for Claude Desktop integration.

    The server provides tools for:
    - Knowledge base search (search_knowledge_base)
    - Entity lookup (lookup_entity)
    - Document parsing (parse_document)
    - Agent creation and execution (create_agent, ask_agent)

    Example:
        percolate mcp

    For Claude Desktop configuration, add to claude_desktop_config.json:
        {
          "mcpServers": {
            "percolate": {
              "command": "uv",
              "args": ["run", "--directory", "/path/to/percolate", "percolate", "mcp"],
              "env": {
                "P8_DB_PATH": "/path/to/database",
                "P8_TENANT_ID": "your-tenant-id"
              }
            }
          }
        }
    """
    from percolate.mcplib.server import create_mcp_server

    mcp_server = create_mcp_server()
    mcp_server.run()  # Runs in stdio mode by default


@app.command()
def version() -> None:
    """Show version information."""
    from percolate import __version__

    typer.echo(f"Percolate v{__version__}")


@app.command()
def agent_eval(
    agent_uri: str = typer.Argument(..., help="Agent URI (e.g., 'test-agent')"),
    prompt: str = typer.Argument(..., help="Prompt to evaluate agent with"),
    tenant_id: str = typer.Option("default", help="Tenant ID"),
    model: str = typer.Option(None, help="Model override (e.g., 'claude-sonnet-4.5')"),
    output_json: bool = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """Evaluate an agent-let with a prompt.

    This command loads an agent-let, runs it with the provided prompt,
    and displays the structured output and usage statistics.

    Examples:
        percolate agent-eval test-agent "What is 2+2?"
        percolate agent-eval test-agent "Explain percolate" --json
    """
    from percolate.mcplib.tools.agent import ask_agent

    async def run():
        result = await ask_agent(
            ctx=None,
            agent_uri=agent_uri,
            tenant_id=tenant_id,
            prompt=prompt,
            model=model,
        )
        return result

    # Run async function
    result = asyncio.run(run())

    if output_json:
        # Output raw JSON
        console.print_json(data=result)
    else:
        # Pretty-print result
        if result["status"] == "error":
            console.print(f"[red]Error:[/red] {result['error']}")
            raise typer.Exit(code=1)

        console.print(f"[green]✓[/green] Agent: {result['agent_uri']}")
        console.print(f"[blue]Model:[/blue] {result['model']}")
        console.print()

        # Show response
        console.print("[bold]Response:[/bold]")
        response = result["response"]
        if isinstance(response, dict):
            # Pretty-print structured output
            table = Table(show_header=False, box=None)
            table.add_column("Key", style="cyan")
            table.add_column("Value")

            for key, value in response.items():
                if isinstance(value, list):
                    value_str = ", ".join(str(v) for v in value)
                else:
                    value_str = str(value)
                table.add_row(key, value_str)

            console.print(table)
        else:
            console.print(response)

        console.print()

        # Show usage
        usage = result["usage"]
        console.print(f"[dim]Tokens: {usage['input_tokens']} in / {usage['output_tokens']} out[/dim]")


@app.command()
def parse(
    file_path: Path = typer.Argument(..., help="Path to document to parse and analyze"),
    agent_file: Path = typer.Option(None, "--agent", help="Path to agent YAML definition"),
    tenant_id: str = typer.Option("default", help="Tenant ID"),
    model: str = typer.Option(None, help="Model override"),
    project: str = typer.Option(None, "--project", help="Project name for session grouping"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed execution info"),
) -> None:
    """Parse a document and analyze with an agent.

    PARSING ARCHITECTURE
    ====================

    This command uses a two-tier parsing strategy depending on file type and
    embedding requirements:

    1. DEFAULT PARSER (Built-in, No External Service Required)
    -----------------------------------------------------------
    Used for: Text files (.txt, .md, .markdown)
    Dependencies: None (Python stdlib only)
    Embeddings: OpenAI API (text-embedding-3-small via API call)
    Chunking: Semantic chunking (paragraph-based with overlap)

    The default parser handles simple text extraction without heavy dependencies.
    It can optionally chunk and embed content using OpenAI's embedding API if
    the --embed flag is provided. This is lightweight and works without any
    local ML models or percolate-reading service.

    Benefits:
    - Zero infrastructure dependencies for basic text parsing
    - Fast startup (no model loading)
    - OpenAI embeddings via API (no local ML dependencies)
    - Simple semantic chunking (paragraph boundaries, overlap)

    Limitations:
    - Text files only (no PDF, Excel, audio, images)
    - OpenAI embeddings only (no local/custom models)
    - Basic chunking (no advanced layout analysis)

    2. PERCOLATE-READING SERVICE (Advanced Parsing)
    ------------------------------------------------
    Used for:
    - Complex formats: PDF, DOCX, Excel, audio, images
    - Special embeddings: Local models (sentence-transformers, all-MiniLM-L6-v2)
    - Advanced chunking: Layout-aware, table extraction, OCR

    Dependencies: percolate-reading service (Docker container or process)
    Embeddings: Local models via sentence-transformers (requires heavy ML deps)
    Chunking: Advanced (layout-aware, table detection, multi-column)

    The percolate-reading service is a separate microservice that handles:
    - PDF parsing (pypdf, pdfplumber, OCR)
    - Excel parsing (openpyxl, structured table extraction)
    - Audio transcription (whisper, speech-to-text)
    - Image OCR (tesseract, vision models)
    - Local embedding models (sentence-transformers, ~500MB models)
    - Advanced chunking strategies (layout analysis, semantic boundaries)

    Benefits:
    - Handles all document types (PDF, Excel, audio, images)
    - Local embedding models (privacy, no API costs)
    - Advanced layout analysis (tables, multi-column, headers)
    - Optimized for batch processing

    When to use:
    - Parsing PDFs, Excel files, or other binary formats
    - Using local/custom embedding models (not OpenAI)
    - Need advanced chunking (layout-aware, table detection)
    - Processing sensitive documents (local-only, no API calls)

    WORKFLOW
    ========

    1. Determine parsing strategy:
       - .txt/.md files → Default parser (built-in)
       - All other files → percolate-reading service (POST /v1/parse)

    2. Parse document:
       - Default: Read file, semantic chunk (optional), embed via OpenAI API (optional)
       - Service: POST to percolate-reading, receive structured content

    3. Load agent schema with MCP tools

    4. Execute agent with document content as context

    5. Return structured analysis

    CONFIGURATION
    =============

    Default parser (OpenAI embeddings):
    - OPENAI_API_KEY: Required if --embed flag is used
    - P8_DEFAULT_EMBEDDING: "openai:text-embedding-3-small" (default)

    percolate-reading service:
    - PERCOLATE_READING_URL: http://localhost:8001 (default)
    - P8_DEFAULT_EMBEDDING: "local:all-MiniLM-L6-v2" (uses service models)

    EXAMPLES
    ========

    # Text file with default parser (no embeddings)
    percolate parse notes.md --agent summarizer.yaml

    # Text file with OpenAI embeddings (no service needed)
    percolate parse notes.md --agent rag-agent.yaml --embed

    # PDF with percolate-reading service (requires service running)
    percolate parse deal.pdf --agent alpha-extraction.yaml

    # Excel with local embeddings (uses service for both parsing and embeddings)
    percolate parse financials.xlsx --agent analyzer.yaml --embed

    # Audio transcription (requires service)
    percolate parse meeting.mp3 --agent transcribe.yaml

    TROUBLESHOOTING
    ===============

    Error: "percolate-reading service unavailable"
    - For PDF/Excel/audio: Start service with `docker run -p 8001:8000 percolate-reading`
    - For .txt/.md: Should work without service (check file permissions)

    Error: "Embedding generation failed"
    - Using OpenAI: Check OPENAI_API_KEY environment variable
    - Using local models: Ensure percolate-reading service is running

    Error: "File not found"
    - Use absolute paths or verify current working directory
    - Check file permissions (readable by current user)
    """
    from percolate.agents import AgentContext, create_agent
    from percolate.mcplib.tools.parse import parse_document
    from percolate.memory.session_store import SessionStore
    from percolate.settings import settings

    # Validate file exists
    if not file_path.exists():
        console.print(f"[red]Error:[/red] File not found: {file_path}")
        raise typer.Exit(code=1)

    # Validate agent file exists
    if agent_file and not agent_file.exists():
        console.print(f"[red]Error:[/red] Agent file not found: {agent_file}")
        raise typer.Exit(code=1)

    # Generate session ID
    session_id = str(uuid.uuid4())

    async def run():
        console.print(f"[cyan]→[/cyan] Parsing document: {file_path.name}")

        # Handle text files directly, use parse service for others
        if file_path.suffix in ['.txt', '.md']:
            # Read text file directly
            with open(file_path, 'r') as f:
                content = f.read()
            metadata = {"page_count": 1, "file_type": "text"}
        else:
            # Parse document via service
            try:
                parse_result = await parse_document(
                    file_path=str(file_path),
                    tenant_id=tenant_id
                )

                if parse_result.get("status") != "completed":
                    console.print(f"[red]Error:[/red] Parse failed: {parse_result.get('error')}")
                    return None

                # Extract content
                content = parse_result.get("result", {}).get("content", "")
                metadata = parse_result.get("result", {}).get("metadata", {})
            except Exception as e:
                console.print(f"[red]Error:[/red] Parse service unavailable: {e}")
                console.print("[yellow]Tip:[/yellow] Make sure percolate-reading service is running")
                return None

        if verbose:
            console.print(f"[dim]Parsed {metadata.get('page_count', 'N/A')} pages[/dim]")
            console.print(f"[dim]Content length: {len(content)} characters[/dim]")
            console.print()

        # Load agent schema
        if not agent_file:
            console.print("[red]Error:[/red] --agent parameter required")
            return None

        with open(agent_file) as f:
            agent_schema = yaml.safe_load(f)

        if verbose:
            console.print("[dim]Creating agent with MCP tools...[/dim]")

        # Create context with session and project tracking
        ctx = AgentContext(
            tenant_id=tenant_id,
            session_id=session_id,
            default_model=model or "claude-sonnet-4-20250514",
            agent_schema_uri=str(agent_file) if agent_file else None,
            project_name=project,
            metadata={"source": "cli", "file": str(file_path)},
        )

        # Initialize session store
        session_store = SessionStore() if settings.session_logging_enabled else None

        # Save user message to session
        if session_store:
            # Build the prompt that will be sent to the agent
            user_prompt = f"""Analyze the following investment document:

**Document:** {file_path.name}

**Content:**
{content[:50000]}

Provide your forensic analysis identifying alpha signals and risks."""

            session_store.save_message(
                session_id=session_id,
                tenant_id=tenant_id,
                role="user",
                content=user_prompt,
                agent_uri=str(agent_file) if agent_file else None,
                metadata=ctx.get_session_metadata(),
            )

        # Create agent from schema
        agent = await create_agent(
            context=ctx,
            agent_schema_override=agent_schema,
            model_override=model,
        )

        if verbose:
            console.print(f"[green]✓[/green] Agent created with {len(agent._function_tools or [])} tools")
            console.print()

        # Build prompt with document content
        prompt = f"""Analyze the following investment document:

**Document:** {file_path.name}

**Content:**
{content[:50000]}

Provide your forensic analysis identifying alpha signals and risks."""

        console.print(f"[bold cyan]→[/bold cyan] Running analysis...")
        console.print()

        # Execute agent
        result = await agent.run(prompt)

        # Save assistant response to session
        if session_store:
            # Extract content from result
            if hasattr(result, 'output') and hasattr(result.output, 'model_dump'):
                assistant_content = json.dumps(result.output.model_dump(), indent=2)
            else:
                assistant_content = str(result)

            # Extract usage if available
            usage_dict = None
            if hasattr(result, 'usage'):
                usage = result.usage()
                usage_dict = {
                    "input_tokens": getattr(usage, 'input_tokens', 0),
                    "output_tokens": getattr(usage, 'output_tokens', 0),
                }

            session_store.save_message(
                session_id=session_id,
                tenant_id=tenant_id,
                role="assistant",
                content=assistant_content,
                agent_uri=str(agent_file) if agent_file else None,
                model=ctx.default_model,
                usage=usage_dict,
                metadata=ctx.get_session_metadata(),
            )

        return result

    # Run async function
    result = asyncio.run(run())

    if result is None:
        raise typer.Exit(code=1)

    # Display structured output
    if hasattr(result, 'output') and hasattr(result.output, 'model_dump'):
        console.print(Panel("[bold]Analysis Results[/bold]", style="green"))

        data_dict = result.output.model_dump()

        # Display document classification
        if "document_classification" in data_dict:
            console.print("\n[bold cyan]Document Classification[/bold cyan]")
            doc_class = data_dict["document_classification"]
            console.print(f"  Type: {doc_class.get('document_type')}")
            console.print(f"  Asset Class: {doc_class.get('asset_class')}")
            console.print(f"  Transaction: {doc_class.get('transaction_type')}")
            console.print(f"  Deal: {doc_class.get('deal_name')}")

        # Display alpha score and quality
        if "alpha_score" in data_dict:
            score = data_dict["alpha_score"]
            color = "green" if score > 0 else "red" if score < 0 else "yellow"
            console.print(f"\n[bold]Alpha Score:[/bold] [{color}]{score}/10[/{color}]")

        if "quality_rating" in data_dict:
            console.print(f"[bold]Quality:[/bold] {data_dict['quality_rating']}")

        # Display alpha signals
        if "alpha_signals" in data_dict:
            signals = data_dict["alpha_signals"]

            if signals.get("positive_signals"):
                console.print("\n[bold green]Positive Alpha Signals:[/bold green]")
                for sig in signals["positive_signals"]:
                    impact_color = "green" if sig.get("impact") == "major" else "dim"
                    console.print(f"  [{impact_color}]• {sig.get('signal_type')}[/{impact_color}]")
                    console.print(f"    {sig.get('description')[:200]}...")

            if signals.get("negative_signals"):
                console.print("\n[bold red]Negative Alpha Signals:[/bold red]")
                for sig in signals["negative_signals"]:
                    impact_color = "red" if sig.get("impact") == "major" else "dim"
                    console.print(f"  [{impact_color}]• {sig.get('signal_type')}[/{impact_color}]")
                    console.print(f"    {sig.get('description')[:200]}...")

        # Display judgment
        if "investment_judgment" in data_dict:
            console.print("\n[bold]Investment Judgment:[/bold]")
            console.print(f"  {data_dict['investment_judgment'][:500]}...")

        console.print()
    else:
        console.print(Panel(str(result), title="[bold]Response[/bold]", style="green"))

    # Show usage metrics
    if hasattr(result, 'usage'):
        usage = result.usage()
        input_tokens = usage.input_tokens if hasattr(usage, 'input_tokens') else 0
        output_tokens = usage.output_tokens if hasattr(usage, 'output_tokens') else 0
        console.print(f"[dim]Tokens: {input_tokens} in / {output_tokens} out[/dim]")


@app.command()
def ask(
    yaml_file: Path = typer.Argument(..., help="Path to YAML agent definition"),
    prompt: str = typer.Argument(..., help="Prompt to evaluate agent with"),
    tenant_id: str = typer.Option("default", help="Tenant ID"),
    model: str = typer.Option(None, help="Model override"),
    project: str = typer.Option(None, "--project", help="Project name for session grouping"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed execution info"),
) -> None:
    """Ask an agent a question using a YAML definition file.

    The YAML file should contain:
    - description: System prompt for the agent
    - properties: Output schema definition
    - required: List of required output fields
    - tools: Optional list of MCP tools (for future)

    Examples:
        percolate ask test-agent.yaml "What is 2+2?"
        percolate ask my-agent.yaml "Analyze this" --verbose
        percolate ask agent.yaml "Question" --model claude-opus-4
    """
    from percolate.agents import AgentContext, create_agent
    from percolate.memory.session_store import SessionStore
    from percolate.settings import settings

    # Load YAML file
    if not yaml_file.exists():
        console.print(f"[red]Error:[/red] File not found: {yaml_file}")
        raise typer.Exit(code=1)

    with open(yaml_file) as f:
        agent_schema = yaml.safe_load(f)

    # Generate session ID
    session_id = str(uuid.uuid4())

    if verbose:
        console.print(Panel("[bold]Agent Schema[/bold]", style="blue"))
        console.print(JSON(json.dumps(agent_schema, indent=2)))
        console.print()

    async def run():
        # Create context with session and project tracking
        ctx = AgentContext(
            tenant_id=tenant_id,
            session_id=session_id,
            default_model=model or "claude-sonnet-4-20250514",
            agent_schema_uri=str(yaml_file),
            project_name=project,
            metadata={"source": "cli"},
        )

        if verbose:
            console.print(f"[dim]Creating agent with model: {ctx.default_model}[/dim]")
            console.print(f"[dim]Tenant: {ctx.tenant_id}[/dim]")
            if project:
                console.print(f"[dim]Project: {project}[/dim]")
            console.print()

        # Initialize session store
        session_store = SessionStore() if settings.session_logging_enabled else None

        # Save user message to session
        if session_store:
            session_store.save_message(
                session_id=session_id,
                tenant_id=tenant_id,
                role="user",
                content=prompt,
                agent_uri=str(yaml_file),
                metadata=ctx.get_session_metadata(),
            )

        # Create agent from schema
        agent = await create_agent(
            context=ctx,
            agent_schema_override=agent_schema,
            model_override=model,
        )

        if verbose:
            console.print(f"[green]✓[/green] Agent created")
            console.print(f"[dim]System prompt: {agent.system_prompt[:100]}...[/dim]")
            console.print()

        # Execute agent
        console.print(f"[bold cyan]→[/bold cyan] Prompt: {prompt}")
        console.print()

        result = await agent.run(prompt)

        # Save assistant response to session
        if session_store:
            # Extract content from result
            if hasattr(result, 'output') and hasattr(result.output, 'model_dump'):
                assistant_content = json.dumps(result.output.model_dump(), indent=2)
            else:
                assistant_content = str(result)

            # Extract usage if available
            usage_dict = None
            if hasattr(result, 'usage'):
                usage = result.usage()
                usage_dict = {
                    "input_tokens": getattr(usage, 'input_tokens', 0),
                    "output_tokens": getattr(usage, 'output_tokens', 0),
                }

            session_store.save_message(
                session_id=session_id,
                tenant_id=tenant_id,
                role="assistant",
                content=assistant_content,
                agent_uri=str(yaml_file),
                model=ctx.default_model,
                usage=usage_dict,
                metadata=ctx.get_session_metadata(),
            )

        return result

    # Run async function
    result = asyncio.run(run())

    # Display structured output
    if hasattr(result, 'output') and hasattr(result.output, 'model_dump'):
        console.print(Panel("[bold]Structured Output[/bold]", style="green"))

        # Pretty-print structured output
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Field", style="cyan bold")
        table.add_column("Value")

        data_dict = result.output.model_dump()
        for key, value in data_dict.items():
            if isinstance(value, list):
                value_str = "\n".join(f"• {v}" for v in value)
            elif isinstance(value, dict):
                value_str = json.dumps(value, indent=2)
            else:
                value_str = str(value)
            table.add_row(key, value_str)

        console.print(table)
        console.print()
    else:
        console.print(Panel(str(result), title="[bold]Response[/bold]", style="green"))
        console.print()

    # Show usage metrics
    if hasattr(result, 'usage'):
        usage = result.usage()
        input_tokens = usage.input_tokens if hasattr(usage, 'input_tokens') else 0
        output_tokens = usage.output_tokens if hasattr(usage, 'output_tokens') else 0
        console.print(f"[dim]Tokens: {input_tokens} in / {output_tokens} out[/dim]")

        if verbose and hasattr(usage, 'requests'):
            console.print(f"[dim]Requests: {usage.requests}[/dim]")


if __name__ == "__main__":
    app()
