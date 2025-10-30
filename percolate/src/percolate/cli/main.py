"""CLI entry point."""

import asyncio
import json
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
def agent_run(
    yaml_file: Path = typer.Argument(..., help="Path to YAML agent definition"),
    prompt: str = typer.Argument(..., help="Prompt to evaluate agent with"),
    tenant_id: str = typer.Option("default", help="Tenant ID"),
    model: str = typer.Option(None, help="Model override"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed execution info"),
) -> None:
    """Run an agent from a YAML definition file.

    The YAML file should contain:
    - description: System prompt for the agent
    - properties: Output schema definition
    - required: List of required output fields
    - tools: Optional list of MCP tools (for future)

    Examples:
        percolate agent-run test-agent.yaml "What is 2+2?"
        percolate agent-run my-agent.yaml "Analyze this" --verbose
        percolate agent-run agent.yaml "Question" --model claude-opus-4
    """
    from percolate.agents import AgentContext, create_agent

    # Load YAML file
    if not yaml_file.exists():
        console.print(f"[red]Error:[/red] File not found: {yaml_file}")
        raise typer.Exit(code=1)

    with open(yaml_file) as f:
        agent_schema = yaml.safe_load(f)

    if verbose:
        console.print(Panel("[bold]Agent Schema[/bold]", style="blue"))
        console.print(JSON(json.dumps(agent_schema, indent=2)))
        console.print()

    async def run():
        # Create context
        ctx = AgentContext(
            tenant_id=tenant_id,
            default_model=model or "claude-sonnet-4-20250514",
        )

        if verbose:
            console.print(f"[dim]Creating agent with model: {ctx.default_model}[/dim]")
            console.print(f"[dim]Tenant: {ctx.tenant_id}[/dim]")
            console.print()

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
