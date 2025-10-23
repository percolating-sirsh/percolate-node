#!/usr/bin/env python3
"""Bump semantic version for percolate-rem package.

Usage:
    python scripts/bump_version.py patch  # 0.1.0 -> 0.1.1
    python scripts/bump_version.py minor  # 0.1.0 -> 0.2.0
    python scripts/bump_version.py major  # 0.1.0 -> 1.0.0
    python scripts/bump_version.py --current  # Show current version
"""

import re
import sys
from pathlib import Path
from typing import Literal

VersionPart = Literal["major", "minor", "patch"]

VERSION_FILE = Path(__file__).parent.parent / "src" / "percolate" / "version.py"


class VersionError(Exception):
    """Version operation failed."""


def read_version() -> str:
    """Read current version from version.py."""
    if not VERSION_FILE.exists():
        raise VersionError(f"Version file not found: {VERSION_FILE}")

    content = VERSION_FILE.read_text()
    match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)

    if not match:
        raise VersionError("Could not parse version from version.py")

    return match.group(1)


def parse_version(version: str) -> tuple[int, int, int]:
    """Parse semantic version string into (major, minor, patch)."""
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version)

    if not match:
        raise VersionError(f"Invalid semantic version: {version}")

    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def format_version(major: int, minor: int, patch: int) -> str:
    """Format version tuple as string."""
    return f"{major}.{minor}.{patch}"


def bump_version(version: str, part: VersionPart) -> str:
    """Bump version according to semantic versioning rules."""
    major, minor, patch = parse_version(version)

    if part == "major":
        return format_version(major + 1, 0, 0)
    elif part == "minor":
        return format_version(major, minor + 1, 0)
    elif part == "patch":
        return format_version(major, minor, patch + 1)
    else:
        raise VersionError(f"Invalid version part: {part}")


def write_version(version: str) -> None:
    """Write new version to version.py."""
    content = f'"""Version information for percolate-rem."""\n\n__version__ = "{version}"\n'
    VERSION_FILE.write_text(content)


def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    arg = sys.argv[1].lower()

    try:
        current = read_version()

        if arg in ("--current", "-c"):
            print(current)
            return

        if arg not in ("major", "minor", "patch"):
            raise VersionError(f"Invalid argument: {arg}")

        new_version = bump_version(current, arg)  # type: ignore
        write_version(new_version)

        print(f"✓ Bumped version: {current} → {new_version}")
        print(f"\nNext steps:")
        print(f"  1. Review changes: git diff {VERSION_FILE.relative_to(Path.cwd())}")
        print(f"  2. Commit: git add {VERSION_FILE.relative_to(Path.cwd())} && git commit -m 'Bump version to {new_version}'")
        print(f"  3. Tag: git tag v{new_version}")
        print(f"  4. Publish: python scripts/publish.py")

    except VersionError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
