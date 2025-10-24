# Build Instructions

## TL;DR

```bash
# Check syntax (with warnings)
maturin develop --skip-install

# Build and install locally
maturin develop

# Run tests
cargo test --lib
```

## Why Not `cargo check`?

This is a **PyO3 extension module**, not a standalone Rust binary. The `extension-module` feature in Cargo.toml means it links against Python at runtime, not build time.

**Don't use:**
- ❌ `cargo check` - Will fail with Python linker errors
- ❌ `cargo build` - Will fail with Python linker errors
- ❌ `cargo run` - Not applicable (no binary)

**Use instead:**
- ✅ `maturin develop` - Build and install into current venv
- ✅ `maturin develop --skip-install` - Build only (syntax check)
- ✅ `cargo test --lib` - Run Rust unit tests
- ✅ `cargo clippy` - Linting (may show Python linker errors but lints still work)

## Development Workflow

### 1. Install Development Dependencies

```bash
# Install maturin (if not already installed)
pip install maturin

# Or with uv
uv pip install maturin
```

### 2. Build and Install

```bash
# Build and install into current Python environment
maturin develop

# This creates a wheel and installs rem_db module
# You can now import it:
python -c "import rem_db"
```

### 3. Run Tests

```bash
# Rust unit tests (no Python required)
cargo test --lib

# Python tests (after maturin develop)
pytest python/tests/
```

### 4. Quick Syntax Check

```bash
# Build but don't install (faster iteration)
maturin develop --skip-install
```

## Common Issues

### Issue: "Symbol not found for architecture arm64"
**Cause:** Using `cargo check` or `cargo build` directly
**Fix:** Use `maturin develop --skip-install` instead

### Issue: "No module named 'rem_db'"
**Cause:** Haven't run `maturin develop` yet
**Fix:** Run `maturin develop` to build and install

### Issue: Warning spam (310 warnings)
**Cause:** Unused fields in stubs (expected)
**Fix:** Ignore until implementation phase, or use `#[allow(dead_code)]`

## CI/CD

For automated testing:

```bash
# Install maturin
pip install maturin

# Build
maturin build --release

# Install wheel
pip install target/wheels/*.whl

# Test
pytest
```

## Editor Integration

**VS Code:**
- rust-analyzer may show linker errors - ignore them
- Tests and clippy work fine
- Use maturin for actual builds

**IntelliJ/CLion:**
- Same as VS Code
- Configure to use maturin for builds
