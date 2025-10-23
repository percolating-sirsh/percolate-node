#!/bin/bash
# Publish package to PyPI or TestPyPI
#
# Usage:
#   ./scripts/publish.sh         # Publish to PyPI
#   ./scripts/publish.sh test    # Publish to TestPyPI
#   ./scripts/publish.sh build   # Build only, don't publish
#   ./scripts/publish.sh check   # Run checks only

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "${1:-}" in
  test)
    python3 "$SCRIPT_DIR/publish.py" --test
    ;;
  build)
    python3 "$SCRIPT_DIR/publish.py" --build-only
    ;;
  check)
    python3 "$SCRIPT_DIR/publish.py" --check
    ;;
  "")
    python3 "$SCRIPT_DIR/publish.py"
    ;;
  *)
    echo "Usage: $0 [test|build|check]"
    exit 1
    ;;
esac
