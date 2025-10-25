#!/usr/bin/env python3
"""Version bump script for all percolate projects."""
import re
import sys
from enum import Enum
from pathlib import Path
from typing import Literal

import typer
from rich.console import Console

app = typer.Typer()
console = Console()

VersionPart = Literal["major", "minor", "patch"]


class Project(str, Enum):
    """Supported projects."""

    PERCOLATE = "percolate"
    PERCOLATE_READING = "percolate-reading"
    PERCOLATE_ROCKS = "percolate-rocks"


def parse_version(version_str: str) -> tuple[int, int, int]:
    """Parse semantic version string."""
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version_str.strip())
    if not match:
        raise ValueError(f"Invalid version format: {version_str}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def bump_version(
    version: tuple[int, int, int], part: VersionPart
) -> tuple[int, int, int]:
    """Bump version component."""
    major, minor, patch = version
    if part == "major":
        return (major + 1, 0, 0)
    elif part == "minor":
        return (major, minor + 1, 0)
    else:
        return (major, minor, patch + 1)


def get_project_root() -> Path:
    """Get repository root."""
    script_path = Path(__file__).resolve()
    return script_path.parent.parent


def update_percolate_version(new_version: str) -> None:
    """Update percolate version.py."""
    version_file = get_project_root() / "percolate" / "src" / "percolate" / "version.py"
    content = version_file.read_text()
    updated = re.sub(
        r'__version__\s*=\s*"[^"]+"',
        f'__version__ = "{new_version}"',
        content,
    )
    version_file.write_text(updated)
    console.print(f"✅ Updated {version_file}")


def update_percolate_reading_version(new_version: str) -> None:
    """Update percolate-reading pyproject.toml."""
    pyproject = get_project_root() / "percolate-reading" / "pyproject.toml"
    content = pyproject.read_text()
    updated = re.sub(
        r'version\s*=\s*"[^"]+"',
        f'version = "{new_version}"',
        content,
        count=1,
    )
    pyproject.write_text(updated)
    console.print(f"✅ Updated {pyproject}")


def update_percolate_rocks_version(new_version: str) -> None:
    """Update percolate-rocks Cargo.toml."""
    cargo_toml = get_project_root() / "percolate-rocks" / "Cargo.toml"
    content = cargo_toml.read_text()
    updated = re.sub(
        r'version\s*=\s*"[^"]+"',
        f'version = "{new_version}"',
        content,
        count=1,
    )
    cargo_toml.write_text(updated)
    console.print(f"✅ Updated {cargo_toml}")


def get_current_version(project: Project) -> str:
    """Get current version for project."""
    root = get_project_root()
    if project == Project.PERCOLATE:
        version_file = root / "percolate" / "src" / "percolate" / "version.py"
        match = re.search(r'__version__\s*=\s*"([^"]+)"', version_file.read_text())
        if not match:
            raise ValueError("Could not parse version from version.py")
        return match.group(1)
    elif project == Project.PERCOLATE_READING:
        pyproject = root / "percolate-reading" / "pyproject.toml"
        match = re.search(r'version\s*=\s*"([^"]+)"', pyproject.read_text())
        if not match:
            raise ValueError("Could not parse version from pyproject.toml")
        return match.group(1)
    else:
        cargo_toml = root / "percolate-rocks" / "Cargo.toml"
        match = re.search(r'version\s*=\s*"([^"]+)"', cargo_toml.read_text())
        if not match:
            raise ValueError("Could not parse version from Cargo.toml")
        return match.group(1)


@app.command()
def bump(
    project: Project = typer.Argument(..., help="Project to bump version for"),
    part: VersionPart = typer.Option("patch", help="Version part to bump"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show changes without applying"),
) -> None:
    """Bump version for a project."""
    current = get_current_version(project)
    version_tuple = parse_version(current)
    new_tuple = bump_version(version_tuple, part)
    new_version = f"{new_tuple[0]}.{new_tuple[1]}.{new_tuple[2]}"

    console.print(f"\n📦 Project: [bold]{project.value}[/bold]")
    console.print(f"🔢 Current: {current}")
    console.print(f"🆕 New:     {new_version}")
    console.print(f"📝 Part:    {part}")

    if dry_run:
        console.print("\n[yellow]Dry run - no changes made[/yellow]")
        return

    confirm = typer.confirm("\nProceed with version bump?")
    if not confirm:
        console.print("[yellow]Aborted[/yellow]")
        sys.exit(1)

    if project == Project.PERCOLATE:
        update_percolate_version(new_version)
    elif project == Project.PERCOLATE_READING:
        update_percolate_reading_version(new_version)
    else:
        update_percolate_rocks_version(new_version)

    console.print(f"\n✅ Bumped {project.value} to {new_version}")


@app.command()
def show(
    project: Project = typer.Argument(..., help="Project to show version for"),
) -> None:
    """Show current version for a project."""
    current = get_current_version(project)
    console.print(f"{project.value}: {current}")


if __name__ == "__main__":
    app()
