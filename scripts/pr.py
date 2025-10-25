#!/usr/bin/env python3
"""Create PR with version bumps and release notes."""
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt

app = typer.Typer()
console = Console()


def get_repo_root() -> Path:
    """Get repository root."""
    script_path = Path(__file__).resolve()
    return script_path.parent.parent


def get_current_version(project: str) -> str:
    """Get current version for project."""
    root = get_repo_root()
    if project == "percolate":
        version_file = root / "percolate" / "src" / "percolate" / "version.py"
        match = re.search(r'__version__\s*=\s*"([^"]+)"', version_file.read_text())
        if not match:
            raise ValueError("Could not parse version from version.py")
        return match.group(1)
    elif project == "percolate-reading":
        pyproject = root / "percolate-reading" / "pyproject.toml"
        match = re.search(r'version\s*=\s*"([^"]+)"', pyproject.read_text())
        if not match:
            raise ValueError("Could not parse version from pyproject.toml")
        return match.group(1)
    elif project == "percolate-rocks":
        cargo_toml = root / "percolate-rocks" / "Cargo.toml"
        match = re.search(r'version\s*=\s*"([^"]+)"', cargo_toml.read_text())
        if not match:
            raise ValueError("Could not parse version from Cargo.toml")
        return match.group(1)
    else:
        raise ValueError(f"Unknown project: {project}")


def run_cmd(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run shell command."""
    console.print(f"[dim]$ {' '.join(cmd)}[/dim]")
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def has_changes(project_dir: str) -> bool:
    """Check if project directory has uncommitted changes."""
    result = run_cmd(["git", "status", "--porcelain", project_dir], check=False)
    return bool(result.stdout.strip())


def collect_release_notes(project: str, version: str) -> Optional[str]:
    """Collect release notes from .release/vX.Y.Z/ if exists."""
    root = get_repo_root()
    release_dir = root / project / ".release" / f"v{version}"

    if not release_dir.exists():
        return None

    notes = []
    for note_file in sorted(release_dir.glob("*.md")):
        content = note_file.read_text().strip()
        if content:
            notes.append(f"## {note_file.stem}\n\n{content}")

    return "\n\n".join(notes) if notes else None


def create_commit_message(changes: dict[str, str]) -> str:
    """Create commit message with version changes and release notes."""
    lines = ["Release version bumps"]
    lines.append("")

    for project, version in changes.items():
        lines.append(f"- {project}: v{version}")

    lines.append("")

    for project, version in changes.items():
        release_notes = collect_release_notes(project, version)
        if release_notes:
            lines.append(f"## {project} v{version}")
            lines.append("")
            lines.append(release_notes)
            lines.append("")

    return "\n".join(lines)


@app.command()
def create(
    message: Optional[str] = typer.Option(None, "--message", "-m", help="Commit message"),
    push: bool = typer.Option(False, "--push", help="Push to remote after commit"),
    build: bool = typer.Option(True, "--build/--no-build", help="Trigger builds"),
) -> None:
    """Create PR with version changes and release notes."""
    root = get_repo_root()

    # Check which projects have changes
    projects = ["percolate", "percolate-reading", "percolate-rocks"]
    changed_projects = {}

    console.print("\n🔍 Checking for changes...")
    for project in projects:
        if has_changes(project):
            version = get_current_version(project)
            changed_projects[project] = version
            console.print(f"  ✓ {project}: v{version}")
        else:
            console.print(f"  - {project}: no changes")

    if not changed_projects:
        console.print("\n[yellow]No changes detected[/yellow]")
        return

    # Generate commit message
    if not message:
        message = create_commit_message(changed_projects)

    console.print("\n📝 Commit message:")
    console.print("[dim]" + "─" * 60 + "[/dim]")
    console.print(message)
    console.print("[dim]" + "─" * 60 + "[/dim]")

    if not Confirm.ask("\nProceed with commit?"):
        console.print("[yellow]Aborted[/yellow]")
        return

    # Stage all changes
    console.print("\n📦 Staging changes...")
    run_cmd(["git", "add", "."])

    # Commit
    console.print("\n💾 Creating commit...")
    run_cmd(["git", "commit", "-m", message])

    # Create tags if building
    if build:
        console.print("\n🏷️  Creating version tags...")
        for project, version in changed_projects.items():
            tag = f"{project}-v{version}"
            console.print(f"  Creating tag: {tag}")
            run_cmd(["git", "tag", tag])

    # Push if requested
    if push:
        console.print("\n⬆️  Pushing to remote...")
        run_cmd(["git", "push"])

        if build:
            console.print("\n⬆️  Pushing tags...")
            run_cmd(["git", "push", "--tags"])

    console.print("\n✅ Done!")

    if build and not push:
        console.print(
            "\n[yellow]Note: Tags created but not pushed. "
            "Run 'git push --tags' to trigger builds.[/yellow]"
        )


@app.command()
def status() -> None:
    """Show version status for all projects."""
    projects = ["percolate", "percolate-reading", "percolate-rocks"]

    console.print("\n📦 Version Status\n")

    for project in projects:
        version = get_current_version(project)
        has_uncommitted = has_changes(project)
        status = "[yellow]uncommitted changes[/yellow]" if has_uncommitted else "[green]clean[/green]"
        console.print(f"  {project:20} v{version:10} {status}")


if __name__ == "__main__":
    app()
