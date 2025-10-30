"""Test topology CLI commands for Kubernetes deployment testing."""

import asyncio
import time
from typing import Optional

import httpx
import typer
from rich.console import Console
from rich.live import Live
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

app = typer.Typer(
    name="test-topology",
    help="Test Kubernetes topology: tenant affinity, scaling, replication",
)
console = Console()


@app.command()
def simulate_tenant(
    tenant_id: str = typer.Argument(..., help="Tenant ID to simulate"),
    duration: int = typer.Option(120, help="Duration in seconds"),
    rate: int = typer.Option(10, help="Requests per second"),
    api_url: str = typer.Option("http://localhost:8000", help="API base URL"),
) -> None:
    """Simulate traffic for a single tenant.

    Sends requests at specified rate for duration, tracking tenant affinity
    and database pod assignment.

    Examples:
        percolate test-topology simulate-tenant tenant-a --duration 120 --rate 10
        percolate test-topology simulate-tenant tenant-b --rate 5
    """
    asyncio.run(_simulate_tenant(tenant_id, duration, rate, api_url))


async def _simulate_tenant(
    tenant_id: str, duration: int, rate: int, api_url: str
) -> None:
    """Async implementation of simulate-tenant."""
    console.print(f"[cyan]Simulating tenant:[/cyan] {tenant_id}")
    console.print(f"[dim]Duration: {duration}s, Rate: {rate} req/s[/dim]")
    console.print()

    requests_sent = 0
    pod_assignments: dict[str, int] = {}
    errors = 0

    start_time = time.time()
    interval = 1.0 / rate

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Sending requests to {tenant_id}...", total=None)

        async with httpx.AsyncClient(timeout=10.0) as client:
            while time.time() - start_time < duration:
                try:
                    # Send request with X-Tenant-ID header
                    response = await client.get(
                        f"{api_url}/api/v1/resources",
                        headers={"X-Tenant-ID": tenant_id},
                        params={"query": "test"},
                    )

                    if response.status_code == 200:
                        data = response.json()
                        pod_name = data.get("pod", "unknown")
                        pod_assignments[pod_name] = pod_assignments.get(pod_name, 0) + 1
                        requests_sent += 1
                    else:
                        errors += 1
                        console.print(
                            f"[yellow]Warning:[/yellow] Status {response.status_code}"
                        )

                except Exception as e:
                    errors += 1
                    console.print(f"[red]Error:[/red] {e}")

                # Wait for next request
                await asyncio.sleep(interval)

                # Update progress
                progress.update(
                    task,
                    description=f"Sent {requests_sent} requests, {errors} errors",
                )

    # Display results
    console.print()
    console.print(f"[green]✓[/green] Simulation complete")
    console.print(f"[dim]Total requests: {requests_sent}[/dim]")
    console.print(f"[dim]Total errors: {errors}[/dim]")
    console.print()

    # Show pod affinity
    if pod_assignments:
        console.print("[bold]Pod Assignments:[/bold]")
        table = Table(show_header=True)
        table.add_column("Pod", style="cyan")
        table.add_column("Requests", justify="right")
        table.add_column("Percentage", justify="right")

        for pod, count in sorted(
            pod_assignments.items(), key=lambda x: x[1], reverse=True
        ):
            percentage = (count / requests_sent) * 100
            table.add_row(pod, str(count), f"{percentage:.1f}%")

        console.print(table)

        # Check affinity
        max_count = max(pod_assignments.values())
        affinity_rate = (max_count / requests_sent) * 100
        if affinity_rate > 95:
            console.print(
                f"[green]✓[/green] Tenant affinity: {affinity_rate:.1f}% (excellent)"
            )
        elif affinity_rate > 80:
            console.print(
                f"[yellow]⚠[/yellow] Tenant affinity: {affinity_rate:.1f}% (acceptable)"
            )
        else:
            console.print(
                f"[red]✗[/red] Tenant affinity: {affinity_rate:.1f}% (poor)"
            )


@app.command()
def simulate_tenants(
    tenants: int = typer.Option(5, help="Number of tenants to simulate"),
    duration: int = typer.Option(300, help="Duration in seconds"),
    rate: int = typer.Option(5, help="Requests per second per tenant"),
    api_url: str = typer.Option("http://localhost:8000", help="API base URL"),
) -> None:
    """Simulate traffic for multiple tenants concurrently.

    Creates concurrent tasks for each tenant, useful for testing multi-tenant
    scaling behavior.

    Examples:
        percolate test-topology simulate-tenants --tenants 5 --duration 300
        percolate test-topology simulate-tenants --tenants 10 --rate 2
    """
    asyncio.run(_simulate_tenants(tenants, duration, rate, api_url))


async def _simulate_tenants(
    tenants: int, duration: int, rate: int, api_url: str
) -> None:
    """Async implementation of simulate-tenants."""
    console.print(f"[cyan]Simulating {tenants} tenants concurrently[/cyan]")
    console.print(f"[dim]Duration: {duration}s, Rate: {rate} req/s per tenant[/dim]")
    console.print()

    # Create tasks for each tenant
    tasks = []
    for i in range(tenants):
        tenant_id = f"tenant-{chr(65 + i)}"  # tenant-A, tenant-B, etc.
        task = _simulate_tenant_background(tenant_id, duration, rate, api_url)
        tasks.append(task)

    # Run all tasks concurrently
    await asyncio.gather(*tasks)


async def _simulate_tenant_background(
    tenant_id: str, duration: int, rate: int, api_url: str
) -> None:
    """Background tenant simulation (no console output)."""
    start_time = time.time()
    interval = 1.0 / rate

    async with httpx.AsyncClient(timeout=10.0) as client:
        while time.time() - start_time < duration:
            try:
                await client.get(
                    f"{api_url}/api/v1/resources",
                    headers={"X-Tenant-ID": tenant_id},
                    params={"query": "test"},
                )
            except Exception:
                pass  # Silent failure for background tasks

            await asyncio.sleep(interval)


@app.command()
def submit_jobs(
    count: int = typer.Option(10, help="Number of jobs to submit"),
    tenant_id: str = typer.Option("tenant-a", help="Tenant ID"),
    nats_url: str = typer.Option("http://localhost:4222", help="NATS server URL"),
) -> None:
    """Submit background jobs to NATS queue.

    Publishes job messages to NATS JetStream, triggering worker pod scaling.

    Examples:
        percolate test-topology submit-jobs --count 20 --tenant tenant-a
        percolate test-topology submit-jobs --count 5
    """
    console.print(f"[cyan]Submitting {count} jobs for tenant {tenant_id}[/cyan]")
    console.print(f"[dim]NATS URL: {nats_url}[/dim]")
    console.print()

    console.print("[yellow]⚠[/yellow] Not yet implemented - requires NATS client")
    console.print("[dim]Use kubectl to create test jobs directly[/dim]")


@app.command()
def verify_affinity(
    tenant_id: str = typer.Argument(..., help="Tenant ID to verify"),
    requests: int = typer.Option(100, help="Number of test requests"),
    api_url: str = typer.Option("http://localhost:8000", help="API base URL"),
) -> None:
    """Verify tenant affinity by sending test requests.

    Measures what percentage of requests for a tenant go to the same pod.

    Examples:
        percolate test-topology verify-affinity tenant-a --requests 100
        percolate test-topology verify-affinity tenant-b --requests 50
    """
    asyncio.run(_verify_affinity(tenant_id, requests, api_url))


async def _verify_affinity(tenant_id: str, requests: int, api_url: str) -> None:
    """Async implementation of verify-affinity."""
    console.print(f"[cyan]Verifying tenant affinity for {tenant_id}[/cyan]")
    console.print(f"[dim]Sending {requests} test requests...[/dim]")
    console.print()

    pod_assignments: dict[str, int] = {}
    errors = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Sending requests...", total=requests)

        async with httpx.AsyncClient(timeout=10.0) as client:
            for i in range(requests):
                try:
                    response = await client.get(
                        f"{api_url}/api/v1/resources",
                        headers={"X-Tenant-ID": tenant_id},
                        params={"query": "test"},
                    )

                    if response.status_code == 200:
                        data = response.json()
                        pod_name = data.get("pod", "unknown")
                        pod_assignments[pod_name] = pod_assignments.get(pod_name, 0) + 1
                    else:
                        errors += 1

                except Exception:
                    errors += 1

                progress.update(task, advance=1)

    # Display results
    console.print()
    if errors > 0:
        console.print(f"[yellow]⚠[/yellow] {errors} errors occurred")
        console.print()

    if not pod_assignments:
        console.print("[red]✗[/red] No successful requests")
        raise typer.Exit(code=1)

    # Show pod distribution
    table = Table(show_header=True)
    table.add_column("Pod", style="cyan")
    table.add_column("Requests", justify="right")
    table.add_column("Percentage", justify="right")

    total_successful = sum(pod_assignments.values())
    for pod, count in sorted(pod_assignments.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / total_successful) * 100
        table.add_row(pod, str(count), f"{percentage:.1f}%")

    console.print(table)
    console.print()

    # Verdict
    max_count = max(pod_assignments.values())
    affinity_rate = (max_count / total_successful) * 100

    if affinity_rate > 95:
        console.print(
            f"[green]✓[/green] Affinity: {affinity_rate:.1f}% - Excellent (>95%)"
        )
        raise typer.Exit(code=0)
    elif affinity_rate > 80:
        console.print(
            f"[yellow]⚠[/yellow] Affinity: {affinity_rate:.1f}% - Acceptable (>80%)"
        )
        raise typer.Exit(code=0)
    else:
        console.print(
            f"[red]✗[/red] Affinity: {affinity_rate:.1f}% - Poor (<80%)"
        )
        raise typer.Exit(code=1)


@app.command()
def check_replication(
    tenant_id: str = typer.Argument(..., help="Tenant ID to check"),
    api_url: str = typer.Option("http://localhost:8000", help="API base URL"),
) -> None:
    """Check database replication lag for a tenant.

    Writes a test value to primary database node and measures time until
    it appears on replica nodes.

    Examples:
        percolate test-topology check-replication tenant-a
        percolate test-topology check-replication tenant-b
    """
    console.print(f"[cyan]Checking replication for {tenant_id}[/cyan]")
    console.print()

    console.print("[yellow]⚠[/yellow] Not yet implemented - requires direct DB access")
    console.print("[dim]Use kubectl to inspect database pod logs[/dim]")


@app.command()
def observe_scaling(
    duration: int = typer.Option(600, help="Duration in seconds"),
    namespace: str = typer.Option("percolate-test", help="Kubernetes namespace"),
) -> None:
    """Observe pod scaling behavior in real-time.

    Watches Kubernetes pods and displays scaling events as they occur.

    Examples:
        percolate test-topology observe-scaling --duration 600
        percolate test-topology observe-scaling --duration 300 --namespace percolate
    """
    console.print(f"[cyan]Observing scaling behavior for {duration}s[/cyan]")
    console.print(f"[dim]Namespace: {namespace}[/dim]")
    console.print()

    console.print("[yellow]⚠[/yellow] Not yet implemented - requires kubectl")
    console.print(
        "[dim]Use: watch kubectl get pods -n percolate-test[/dim]"
    )


if __name__ == "__main__":
    app()
