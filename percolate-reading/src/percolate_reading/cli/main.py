"""CLI entry point for percolate-reading."""

import asyncio
from pathlib import Path

import typer
import uvicorn
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from percolate_reading.settings import settings

app = typer.Typer(name="percolate-reading", help="Percolate reading node CLI")
console = Console()


@app.command()
def serve(
    host: str = typer.Option(settings.host, help="API server host"),
    port: int = typer.Option(settings.port, help="API server port"),
    reload: bool = typer.Option(settings.reload, help="Auto-reload on code changes"),
    workers: int = typer.Option(settings.workers, help="Number of workers"),
) -> None:
    """Start the Percolate-Reading API server.

    Example:
        percolate-reading serve --port 8001 --workers 4
    """
    typer.echo(f"Starting Percolate-Reading on {host}:{port}")
    typer.echo(f"Workers: {workers}")
    typer.echo(f"Storage: {settings.storage_path}")
    typer.echo(f"Device: {settings.device}")
    typer.echo(f"Gateway mode: {settings.gateway_mode}")

    if settings.gateway_mode:
        typer.echo("\nGateway Configuration:")
        if settings.s3_enabled:
            typer.echo(f"  S3: {settings.s3_endpoint}/{settings.s3_bucket}")
        if settings.nats_enabled:
            typer.echo(f"  NATS: {settings.nats_url}")

    uvicorn.run(
        "percolate_reading.api.app:create_app",
        host=host,
        port=port,
        reload=reload,
        workers=1 if reload else workers,  # Can't use workers with reload
        factory=True,
    )


@app.command()
def info() -> None:
    """Show configuration information."""
    typer.echo("Percolate-Reading Configuration:")
    typer.echo(f"  Host: {settings.host}:{settings.port}")
    typer.echo(f"  Storage: {settings.storage_path}")
    typer.echo(f"  Database: {settings.db_path}")
    typer.echo(f"  Workers: {settings.workers}")
    typer.echo(f"  Embedding Model: {settings.embedding_model}")
    typer.echo(f"  Whisper Model: {settings.whisper_model}")
    typer.echo(f"  Device: {settings.device}")
    typer.echo(f"  Auth Enabled: {settings.auth_enabled}")
    typer.echo(f"  Gateway Mode: {settings.gateway_mode}")

    if settings.gateway_mode:
        typer.echo("\nGateway Configuration:")
        typer.echo(f"  S3 Enabled: {settings.s3_enabled}")
        if settings.s3_enabled:
            typer.echo(f"  S3 Endpoint: {settings.s3_endpoint}")
            typer.echo(f"  S3 Bucket: {settings.s3_bucket}")
        typer.echo(f"  NATS Enabled: {settings.nats_enabled}")
        if settings.nats_enabled:
            typer.echo(f"  NATS URL: {settings.nats_url}")


@app.command()
def worker() -> None:
    """Start worker mode (listen to NATS queue).

    Example:
        percolate-reading worker
    """
    import asyncio

    typer.echo("Starting Percolate-Reading Worker")
    typer.echo(f"NATS URL: {settings.nats_url}")
    typer.echo(f"Queue Group: {settings.nats_queue_group}")
    typer.echo(f"Storage: {settings.storage_path}")
    typer.echo(f"Device: {settings.device}")

    if not settings.nats_enabled:
        typer.echo("ERROR: NATS not enabled. Set PERCOLATE_READING_NATS_ENABLED=true")
        raise typer.Exit(1)

    # TODO: Implement NATS worker
    # from percolate_reading.worker import run_worker
    # asyncio.run(run_worker())

    typer.echo("\n⚠️  Worker mode not yet implemented")
    typer.echo("TODO: Implement NATS consumer for job processing")
    typer.echo("\nExpected behavior:")
    typer.echo("  1. Connect to NATS JetStream")
    typer.echo("  2. Subscribe to queue: percolate.jobs")
    typer.echo("  3. Process jobs from queue")
    typer.echo("  4. Download files from S3")
    typer.echo("  5. Parse with appropriate provider")
    typer.echo("  6. Upload results to S3")
    typer.echo("  7. Send webhook callback")
    typer.echo("  8. Acknowledge NATS message")


@app.command()
def parse(
    path: Path = typer.Argument(..., help="File or folder to parse"),
    ingest: bool = typer.Option(False, "--ingest", help="Chunk and embed as resources"),
    storage_strategy: str = typer.Option("dated", help="Storage strategy (dated/tenant/system)"),
    tenant_id: str | None = typer.Option(None, help="Tenant ID (for tenant strategy)"),
) -> None:
    """Parse files or folders with appropriate providers.

    Examples:
        # Parse single file
        percolate-reading parse document.pdf

        # Parse folder
        percolate-reading parse ./documents/

        # Parse and ingest as resources
        percolate-reading parse document.pdf --ingest
    """
    asyncio.run(_parse_files(path, ingest, storage_strategy, tenant_id))


async def _parse_files(
    path: Path,
    ingest: bool,
    storage_strategy: str,
    tenant_id: str | None,
) -> None:
    """Parse files async implementation."""
    import mimetypes
    import uuid
    from datetime import datetime

    from percolate_reading.models.parse import ParseJob, ParseStatus, StorageStrategy
    from percolate_reading.providers.audio import AudioProvider
    from percolate_reading.providers.base import ProviderRegistry
    from percolate_reading.providers.excel import ExcelProvider
    from percolate_reading.providers.image import ImageProvider
    from percolate_reading.providers.pdf import PDFProvider
    from percolate_reading.storage.manager import StorageManager

    # Validate path
    if not path.exists():
        console.print(f"[red]Error: Path not found: {path}[/red]")
        raise typer.Exit(1)

    # Initialize storage and registry
    storage = StorageManager(base_dir=Path(settings.storage_path))
    registry = ProviderRegistry(storage)
    registry.register(PDFProvider(storage))
    registry.register(ExcelProvider(storage))
    registry.register(AudioProvider(storage))
    registry.register(ImageProvider(storage))

    # Collect files to parse
    files: list[Path] = []
    if path.is_file():
        files.append(path)
    else:
        for ext in [".pdf", ".xlsx", ".xls", ".mp3", ".wav", ".m4a", ".png", ".jpg", ".jpeg"]:
            files.extend(path.rglob(f"*{ext}"))

    if not files:
        console.print(f"[yellow]No supported files found in: {path}[/yellow]")
        return

    console.print(f"[cyan]Found {len(files)} file(s) to parse[/cyan]")

    # Parse each file
    for file_path in files:
        # Detect MIME type
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            console.print(f"[yellow]Skipping {file_path.name}: Unknown MIME type[/yellow]")
            continue

        # Get provider
        try:
            provider = registry.get_provider(mime_type)
        except ValueError:
            console.print(f"[yellow]Skipping {file_path.name}: No provider for {mime_type}[/yellow]")
            continue

        # Create job
        job_id = uuid.uuid4()
        job = ParseJob(
            job_id=job_id,
            file_name=file_path.name,
            file_type=mime_type,
            file_size_bytes=file_path.stat().st_size,
            status=ParseStatus.PROCESSING,
            progress=0.0,
            storage_strategy=StorageStrategy(storage_strategy),
            tenant_id=tenant_id,
            created_at=datetime.now(),
        )

        # Parse with progress
        console.print(f"\n[cyan]Parsing: {file_path.name}[/cyan]")
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Processing...", total=None)

            def update_progress(pct: float, msg: str) -> None:
                progress.update(task, description=msg)

            try:
                result = await provider.parse(file_path, job, progress_callback=update_progress)

                console.print(f"[green]✓ Parsed successfully[/green]")
                console.print(f"  Job ID: {job_id}")
                console.print(f"  Duration: {result.parse_duration_ms}ms")
                console.print(f"  Pages: {result.content.num_pages}")
                console.print(f"  Tables: {result.content.num_tables}")
                console.print(f"  Quality: {result.quality.overall_score:.2f}")
                console.print(f"  Storage: {result.storage.base_path}")

                if ingest:
                    console.print("[yellow]  Note: --ingest flag not yet implemented[/yellow]")

            except Exception as e:
                console.print(f"[red]✗ Parse failed: {e}[/red]")


@app.command()
def version() -> None:
    """Show version information."""
    from percolate_reading import __version__

    typer.echo(f"Percolate-Reading v{__version__}")


if __name__ == "__main__":
    app()
