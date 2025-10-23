"""CLI entry point."""

import typer

app = typer.Typer(name="percolate", help="Personal AI node CLI")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="API server host"),
    port: int = typer.Option(8000, help="API server port"),
    reload: bool = typer.Option(False, help="Auto-reload on code changes"),
) -> None:
    """Start the Percolate API server."""
    import uvicorn

    typer.echo(f"Starting Percolate API server on {host}:{port}")
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


if __name__ == "__main__":
    app()
