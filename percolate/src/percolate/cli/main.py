"""CLI entry point."""

import asyncio
import json
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(name="percolate", help="Personal AI node CLI")
console = Console()


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
    from percolate.mcp.tools.agent import ask_agent

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


if __name__ == "__main__":
    app()
