# Building And Publishing

## Building

This project is a **PyO3 extension module** that can be built in two modes.

### Python extension (default)

```bash
# Build and install into current Python environment
maturin develop

# Syntax check only (faster iteration)
maturin develop --skip-install

# Release build
maturin develop --release
```

**Important:** Do NOT use `cargo check` or `cargo build` directly. They will fail with Python linker errors because the `extension-module` feature configures the library to link against Python at runtime.

### Standalone Rust library

To use this library in other Rust projects without Python:

```bash
# Build without Python bindings
cargo check --lib --no-default-features
cargo build --lib --no-default-features --release

# Run tests
cargo test --lib --no-default-features
```

**In other Rust projects:**
```toml
[dependencies]
percolate-rocks = { version = "0.1", default-features = false }
```

This excludes PyO3 and pyo3-asyncio, making it a pure Rust library.

### Development workflow

```bash
# 1. Make changes to Rust code
# 2. Check compilation
maturin develop --skip-install

# 3. Run tests
cargo test --lib

# 4. Build and install Python extension
maturin develop

# 5. Test Python integration
pytest
```

### Common issues

**Issue:** "Symbol not found for architecture arm64"
**Cause:** Using `cargo check` or `cargo build` directly
**Fix:** Use `maturin develop --skip-install` instead

**Issue:** "No module named 'rem_db'"
**Cause:** Haven't run `maturin develop` yet
**Fix:** Run `maturin develop` to build and install

**Issue:** Warning spam (285 warnings)
**Cause:** Unused fields in stubs (expected during implementation)
**Fix:** Ignore until implementation phase, or use `#[allow(dead_code)]`

## Publishing To PyPI

### Prerequisites

1. PyPI account (https://pypi.org/account/register/)
2. API token from PyPI account settings
3. Maturin installed: `pip install maturin`

### Environment setup

Add your PyPI token to bash profile:

```bash
# In ~/.bash_profile or ~/.zshrc
export PYPI_TOKEN="pypi-..."
```

Or configure in `~/.pypirc`:

```ini
[distutils]
index-servers = pypi

[pypi]
repository = https://upload.pypi.org/legacy/
username = __token__
password = pypi-...
```

### Build wheels

```bash
# Activate venv
source .venv/bin/activate

# Build for current platform
maturin build --release

# Build for multiple platforms (requires Docker or cross-compilation)
maturin build --release --target universal2-apple-darwin  # macOS universal
maturin build --release --target x86_64-unknown-linux-gnu  # Linux x86_64
maturin build --release --target aarch64-unknown-linux-gnu  # Linux ARM64
```

Wheels are created in `target/wheels/`.

### Test package locally

```bash
# Install the wheel
pip install target/wheels/percolate_rocks-*.whl

# Test import
python3 -c "from rem_db import Database; print('✓ Package works')"
```

### Publish to test PyPI (optional)

```bash
# Build
maturin build --release

# Upload to Test PyPI
maturin publish --repository testpypi

# Or with explicit token
maturin publish --repository testpypi --token $TESTPYPI_TOKEN
```

Test installation:
```bash
pip install --index-url https://test.pypi.org/simple/ percolate-rocks
```

### Publish to PyPI

```bash
# Build release wheels
maturin build --release

# Publish
source ~/.bash_profile  # Load PYPI_TOKEN
maturin publish

# Or with explicit token
maturin publish --token $PYPI_TOKEN

# Or use twine (alternative)
pip install twine
twine upload target/wheels/*.whl
```

### Version management

Update version in:
1. `Cargo.toml` - `version = "0.2.0"`
2. `pyproject.toml` - `version = "0.2.0"`
3. `python/rem_db/__init__.py` - `__version__ = "0.2.0"`

### Manual publishing steps

```bash
# 1. Clean build
cargo clean
rm -rf target/wheels/

# 2. Update version numbers (see above)

# 3. Build wheels
source .venv/bin/activate
maturin build --release

# 4. Verify wheel
ls -lh target/wheels/
unzip -l target/wheels/*.whl | head -20

# 5. Test locally
pip install target/wheels/*.whl --force-reinstall
python3 -c "from rem_db import Database; print(Database)"

# 6. Publish
source ~/.bash_profile
maturin publish

# Or if you have .pypirc configured:
twine upload target/wheels/*.whl
```

### Post-publishing checklist

1. Test installation: `pip install percolate-rocks`
2. Verify on PyPI: https://pypi.org/project/percolate-rocks/
3. Update README with new version
4. Create release notes in `.release-notes/`
5. Update `status.md` with new completion percentages
6. Create GitHub release with changelog (if using GitHub)

## Troubleshooting

### "Invalid distribution file"
- Ensure wheel is built for correct platform
- Check wheel filename matches PyPI conventions

### "File already exists"
- Version already published
- Increment version number in Cargo.toml and pyproject.toml

### "Authentication failed"
- Check PYPI_TOKEN is set correctly: `echo $PYPI_TOKEN`
- Ensure token has upload permissions
- Try using `twine upload` instead of `maturin publish`
- Load environment: `source ~/.bash_profile`

### Build errors
- Ensure maturin is installed: `pip install maturin`
- Check Rust is installed: `rustc --version`
- Clean build directory: `cargo clean && rm -rf target/wheels/`

## CI/CD with GitHub Actions

Create `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [created]

jobs:
  build:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest]
        python-version: ['3.8', '3.9', '3.10', '3.11', '3.12']

    steps:
    - uses: actions/checkout@v3

    - uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install Rust
      uses: actions-rs/toolchain@v1
      with:
        toolchain: stable

    - name: Install maturin
      run: pip install maturin

    - name: Build wheels
      run: maturin build --release

    - name: Upload wheels
      uses: actions/upload-artifact@v3
      with:
        name: wheels
        path: target/wheels/

  publish:
    needs: build
    runs-on: ubuntu-latest

    steps:
    - uses: actions/download-artifact@v3
      with:
        name: wheels
        path: wheels/

    - name: Publish to PyPI
      env:
        MATURIN_PYPI_TOKEN: ${{ secrets.PYPI_TOKEN }}
      run: |
        pip install maturin
        maturin publish --skip-existing
```

## Package metadata checklist

- [ ] README.md (shows on PyPI)
- [ ] LICENSE file
- [ ] Classifiers in pyproject.toml
- [ ] Keywords for searchability
- [ ] Project URLs (homepage, repository, documentation)
- [ ] Supported Python versions
- [ ] Dependencies listed correctly
