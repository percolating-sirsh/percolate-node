#!/usr/bin/env python3
"""Build and publish percolate-rem to PyPI.

Usage:
    python scripts/publish.py              # Publish to PyPI
    python scripts/publish.py --test       # Publish to TestPyPI
    python scripts/publish.py --build-only # Build without publishing
    python scripts/publish.py --check      # Run pre-publish checks
"""

import subprocess
import sys
from pathlib import Path
from typing import NoReturn

PROJECT_ROOT = Path(__file__).parent.parent


class PublishError(Exception):
    """Publishing operation failed."""


def run_command(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run shell command and return result."""
    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            check=check,
            capture_output=True,
            text=True,
        )
        return result
    except subprocess.CalledProcessError as e:
        raise PublishError(f"Command failed: {' '.join(cmd)}\n{e.stderr}") from e


def check_git_status() -> None:
    """Verify git working directory is clean."""
    result = run_command(["git", "status", "--porcelain"], check=False)

    if result.returncode != 0:
        print("⚠ Warning: Not in a git repository")
        return

    if result.stdout.strip():
        raise PublishError(
            "Working directory has uncommitted changes. "
            "Commit or stash changes before publishing."
        )

    print("✓ Git working directory is clean")


def check_version_tagged() -> None:
    """Verify current version is tagged in git."""
    # Read current version
    version_file = PROJECT_ROOT / "src" / "percolate" / "version.py"
    content = version_file.read_text()

    import re
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
    if not match:
        raise PublishError("Could not parse version from version.py")

    version = match.group(1)
    tag = f"v{version}"

    # Check if tag exists
    result = run_command(["git", "tag", "-l", tag], check=False)

    if not result.stdout.strip():
        print(f"⚠ Warning: Version {version} is not tagged (expected tag: {tag})")
        response = input("Continue anyway? [y/N]: ")
        if response.lower() != "y":
            raise PublishError("Aborted: Version not tagged")
    else:
        print(f"✓ Version {version} is tagged as {tag}")


def clean_build_artifacts() -> None:
    """Remove old build artifacts."""
    dist_dir = PROJECT_ROOT / "dist"
    if dist_dir.exists():
        import shutil
        shutil.rmtree(dist_dir)
        print("✓ Cleaned old build artifacts")


def build_package() -> None:
    """Build package using uv."""
    print("\nBuilding package...")
    run_command(["uv", "build"])
    print("✓ Package built successfully")


def publish_package(test: bool = False) -> None:
    """Publish package to PyPI or TestPyPI."""
    target = "TestPyPI" if test else "PyPI"
    print(f"\nPublishing to {target}...")

    cmd = ["uv", "publish"]

    if test:
        cmd.extend([
            "--publish-url", "https://test.pypi.org/legacy/",
        ])

    run_command(cmd)
    print(f"✓ Published to {target} successfully")


def show_next_steps(test: bool) -> None:
    """Show post-publish instructions."""
    if test:
        print("\n📦 Package published to TestPyPI!")
        print("\nTest installation:")
        print("  uv pip install --index-url https://test.pypi.org/simple/ percolate-rem")
    else:
        print("\n📦 Package published to PyPI!")
        print("\nInstall with:")
        print("  uv pip install percolate-rem")


def fail(message: str) -> NoReturn:
    """Print error and exit."""
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    """Main entry point."""
    # Parse arguments
    test_pypi = "--test" in sys.argv
    build_only = "--build-only" in sys.argv
    check_only = "--check" in sys.argv

    try:
        # Pre-publish checks
        print("Running pre-publish checks...")
        check_git_status()

        if not build_only:
            check_version_tagged()

        if check_only:
            print("\n✓ All checks passed!")
            return

        # Build
        clean_build_artifacts()
        build_package()

        if build_only:
            print("\n✓ Build complete! Artifacts in dist/")
            return

        # Publish
        publish_package(test=test_pypi)
        show_next_steps(test=test_pypi)

    except PublishError as e:
        fail(str(e))
    except KeyboardInterrupt:
        fail("Aborted by user")


if __name__ == "__main__":
    main()
