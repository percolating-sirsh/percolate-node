# Publishing to PyPI

## Prerequisites

1. PyPI account (https://pypi.org/account/register/)
2. API token from PyPI account settings
3. Maturin installed: `pip install maturin`

## Environment Setup

Add your PyPI token to bash profile:

```bash
# In ~/.bashrc or ~/.zshrc
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

## Build Process

### 1. Build Wheels

```bash
# Activate venv
source .venv/bin/activate

# Build for current platform (macOS ARM64)
maturin build --release

# Build for multiple platforms (requires Docker or cross-compilation)
maturin build --release --target universal2-apple-darwin  # macOS universal
maturin build --release --target x86_64-unknown-linux-gnu  # Linux x86_64
maturin build --release --target aarch64-unknown-linux-gnu  # Linux ARM64
```

Wheels are created in `target/wheels/`.

### 2. Test Package Locally

```bash
# Install the wheel
pip install target/wheels/percolate_rocks-0.1.0-*.whl

# Test import
python3 -c "from rem_db import Database; print('✓ Package works')"
```

### 3. Publish to Test PyPI (Optional)

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

### 4. Publish to PyPI

```bash
# Build release wheels
maturin build --release

# Publish
maturin publish

# Or with explicit token
maturin publish --token $PYPI_TOKEN

# Or use twine (alternative)
pip install twine
twine upload target/wheels/*.whl
```

## Version Management

Update version in:
1. `Cargo.toml` - `version = "0.1.0"`
2. `pyproject.toml` - `version = "0.1.0"`
3. `python/rem_db/__init__.py` - `__version__ = "0.1.0"`

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

## Manual Publishing Steps

```bash
# 1. Clean build
cargo clean
rm -rf target/wheels/

# 2. Build wheels
source .venv/bin/activate
maturin build --release

# 3. Verify wheel
ls -lh target/wheels/
unzip -l target/wheels/*.whl | head -20

# 4. Test locally
pip install target/wheels/*.whl --force-reinstall
python3 -c "from rem_db import Database; print(Database)"

# 5. Publish
maturin publish

# Or if you have .pypirc configured:
twine upload target/wheels/*.whl
```

## Troubleshooting

### "Invalid distribution file"
- Ensure wheel is built for correct platform
- Check wheel filename matches PyPI conventions

### "File already exists"
- Version already published
- Increment version number in Cargo.toml and pyproject.toml

### "Authentication failed"
- Check PYPI_TOKEN is set correctly
- Ensure token has upload permissions
- Try using `twine upload` instead of `maturin publish`

## Post-Publishing

1. Test installation: `pip install percolate-rocks`
2. Verify on PyPI: https://pypi.org/project/percolate-rocks/
3. Update README with installation instructions
4. Create GitHub release with changelog
5. Announce on social media / mailing lists

## Package Metadata Checklist

- [ ] README.md (shows on PyPI)
- [ ] LICENSE file
- [ ] Classifiers in pyproject.toml
- [ ] Keywords for searchability
- [ ] Project URLs (homepage, repository, documentation)
- [ ] Supported Python versions
- [ ] Dependencies listed correctly
