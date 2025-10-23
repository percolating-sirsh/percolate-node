#!/bin/bash
# Full release workflow: bump version, commit, tag, and publish
#
# Usage:
#   ./scripts/release.sh patch   # Patch release (0.1.0 -> 0.1.1)
#   ./scripts/release.sh minor   # Minor release (0.1.0 -> 0.2.0)
#   ./scripts/release.sh major   # Major release (0.1.0 -> 1.0.0)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Validate argument
if [[ ! "${1:-}" =~ ^(patch|minor|major)$ ]]; then
  echo "Usage: $0 <patch|minor|major>"
  exit 1
fi

BUMP_TYPE="$1"

# Get current version
CURRENT_VERSION=$(python3 "$SCRIPT_DIR/bump_version.py" --current)
echo "Current version: $CURRENT_VERSION"

# Bump version
echo "Bumping $BUMP_TYPE version..."
python3 "$SCRIPT_DIR/bump_version.py" "$BUMP_TYPE"

# Get new version
NEW_VERSION=$(python3 "$SCRIPT_DIR/bump_version.py" --current)
echo "New version: $NEW_VERSION"

# Commit version change
echo "Committing version change..."
cd "$PROJECT_ROOT"
git add src/percolate/version.py
git commit -m "Bump version to $NEW_VERSION"

# Create git tag
echo "Creating tag v$NEW_VERSION..."
git tag "v$NEW_VERSION"

# Confirm before publishing
echo ""
echo "Ready to publish v$NEW_VERSION to PyPI"
read -p "Continue? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Aborted. To undo:"
  echo "  git reset --hard HEAD~1"
  echo "  git tag -d v$NEW_VERSION"
  exit 1
fi

# Publish
python3 "$SCRIPT_DIR/publish.py"

# Push to remote
echo ""
echo "Push to remote? This will push the commit and tag."
read -p "Push to remote? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  git push
  git push --tags
  echo "✓ Pushed to remote"
fi

echo ""
echo "🎉 Release v$NEW_VERSION complete!"
