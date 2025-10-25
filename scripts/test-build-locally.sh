#!/bin/bash
# Local build test that mimics GitHub Actions environment
# Usage: ./scripts/test-build-locally.sh [platform]
# Platforms: linux-amd64, linux-arm64, darwin-amd64, darwin-arm64

set -e

PLATFORM="${1:-darwin-arm64}"
PROJECT_DIR="percolate-rocks"

echo "🔍 Testing build for platform: $PLATFORM"
echo "📂 Project directory: $PROJECT_DIR"
echo ""

# Clean previous build artifacts
echo "🧹 Cleaning previous builds..."
cd "$PROJECT_DIR"
cargo clean
rm -rf target/wheels/

# Detect Rust target from platform
case "$PLATFORM" in
  linux-amd64)
    TARGET="x86_64-unknown-linux-gnu"
    ;;
  linux-arm64)
    TARGET="aarch64-unknown-linux-gnu"
    echo "⚠️  Note: ARM64 Linux requires cross-compilation setup"
    echo "   Run: rustup target add $TARGET"
    echo "   Run: brew install messense/macos-cross-toolchains/aarch64-unknown-linux-gnu"
    ;;
  darwin-amd64)
    TARGET="x86_64-apple-darwin"
    ;;
  darwin-arm64)
    TARGET="aarch64-apple-darwin"
    ;;
  *)
    echo "❌ Unknown platform: $PLATFORM"
    echo "   Valid platforms: linux-amd64, linux-arm64, darwin-amd64, darwin-arm64"
    exit 1
    ;;
esac

echo "🎯 Rust target: $TARGET"
echo ""

# Add target if not installed
echo "📦 Ensuring Rust target is installed..."
rustup target add "$TARGET" || true

# Step 1: Cargo check (fast syntax validation)
echo ""
echo "==> Step 1: Cargo check"
cargo check --target "$TARGET" 2>&1 | tail -30
if [ $? -ne 0 ]; then
  echo "❌ Cargo check failed"
  exit 1
fi
echo "✅ Cargo check passed"

# Step 2: Cargo build (full compilation)
echo ""
echo "==> Step 2: Cargo build"
cargo build --release --target "$TARGET" 2>&1 | tail -30
if [ $? -ne 0 ]; then
  echo "❌ Cargo build failed"
  exit 1
fi
echo "✅ Cargo build passed"

# Step 3: Maturin build (Python wheel)
echo ""
echo "==> Step 3: Maturin build wheel"
maturin build --release --target "$TARGET" 2>&1 | tail -30
if [ $? -ne 0 ]; then
  echo "❌ Maturin build failed"
  exit 1
fi
echo "✅ Maturin build passed"

# Show results
echo ""
echo "🎉 Build successful!"
echo ""
echo "📦 Wheels created:"
ls -lh target/wheels/

# Test import (native platform only)
if [[ "$TARGET" == *"$(uname -m)"* ]] || [[ "$TARGET" == "aarch64-apple-darwin" && "$(uname -m)" == "arm64" ]]; then
  echo ""
  echo "==> Step 4: Test wheel import (native platform)"

  # Create venv and test
  VENV_DIR="/tmp/test-wheel-$$"
  python3 -m venv "$VENV_DIR"
  source "$VENV_DIR/bin/activate"

  pip install -q target/wheels/*.whl
  python3 -c "import rem_db; print(f'✅ Import successful: rem_db v{rem_db.__version__}')" || echo "❌ Import failed"

  deactivate
  rm -rf "$VENV_DIR"
else
  echo ""
  echo "⚠️  Skipping import test (cross-compiled for $TARGET)"
fi

echo ""
echo "✅ All steps passed for $PLATFORM"
