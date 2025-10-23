#!/bin/bash
# Bump major version (e.g., 0.1.0 -> 1.0.0)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

python3 "$SCRIPT_DIR/bump_version.py" major
