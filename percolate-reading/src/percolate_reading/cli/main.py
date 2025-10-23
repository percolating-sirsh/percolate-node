"""CLI entry point for percolate-reading."""

import typer

app = typer.Typer(name="percolate-reading", help="Percolate reading node CLI")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="API server host"),
    port: int = typer.Option(8001, help="API server port"),
    reload: bool = typer.Option(False, help="Auto-reload on code changes"),
    device: str = typer.Option("cpu", help="Compute device (cpu/cuda)"),
) -> None:
    """Start the Percolate-Reading API server."""
    import uvicorn

    typer.echo(f"Starting Percolate-Reading API server on {host}:{port}")
    typer.echo(f"Device: {device}")

    uvicorn.run(
        "percolate_reading.api.main:app",
        host=host,
        port=port,
        reload=reload,
    )


@app.command()
def version() -> None:
    """Show version information."""
    from percolate_reading import __version__

    typer.echo(f"Percolate-Reading v{__version__}")


if __name__ == "__main__":
    app()
