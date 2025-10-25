# percolate-rocks v0.2.1-dev - Known Issues

**Status**: Development version (fixing v0.2.0 issues)
**Last updated**: 2025-10-25

## Summary

Version 0.2.0 successfully builds and publishes to PyPI, with wheels for Linux AMD64 and macOS ARM64. However, **all CLI commands are not yet implemented** - the Rust core library exists but PyO3 bindings are incomplete.

**Recent fixes (v0.2.1-dev)**:
- ✅ Removed all mock JSON data that caused JSONDecodeError
- ✅ All unimplemented commands now show clear error messages instead of crashing
- ✅ Commands exit with status code 1 and point to relevant Rust implementation files

## Installation & Import

### ✅ WORKING

1. **Package installation**
   ```bash
   pip install percolate-rocks
   # Successfully installs v0.2.0 from PyPI
   ```

2. **Python import**
   ```python
   import rem_db
   from rem_db import Database
   # Both imports succeed
   print(rem_db.__version__)  # 0.2.0
   ```

3. **CLI availability**
   ```bash
   rem --help
   # CLI is properly installed and shows all commands
   ```

## CLI Commands Status

### ❌ ALL COMMANDS NOT IMPLEMENTED

**Root cause**: Rust core library exists, but PyO3 bindings in `src/bindings/database.rs` are all `todo!()` placeholders.

All commands now fail gracefully with:
```
✗ Not implemented - Rust bindings need to be completed
Help wanted: See src/bindings/database.rs::<method_name>()
```

| Command | Status | Rust Binding Location |
|---------|--------|----------------------|
| `rem init` | ❌ Not implemented | `src/database` module |
| `rem schema-add` | ❌ Not implemented | `src/bindings/database.rs::register_schema()` |
| `rem schema-list` | ❌ Not implemented | `src/schema` module |
| `rem insert` | ❌ Not implemented | `src/bindings/database.rs::insert()` |
| `rem insert --batch` | ❌ Not implemented | `src/bindings/database.rs::insert_batch()` |
| `rem get` | ❌ Not implemented | `src/bindings/database.rs::get()` |
| `rem lookup` | ❌ Not implemented | `src/bindings/database.rs::lookup()` |
| `rem search` | ❌ Not implemented | `src/bindings/database.rs::search()` |
| `rem query` | ❌ Not implemented | `src/bindings/database.rs::query()` |
| `rem ask` | ❌ Not implemented | `src/bindings/database.rs::ask()` |
| `rem traverse` | ❌ Not implemented | `src/bindings/database.rs::traverse()` |
| `rem export` | ❌ Not implemented | `src/bindings/database.rs::export()` |
| `rem ingest` | ❌ Not implemented | `src/bindings/database.rs::ingest()` |
| `rem serve` | ❌ Not implemented | `src/replication` module |
| `rem replicate` | ❌ Not implemented | `src/replication` module |
| `rem replication-wal-status` | ❌ Not implemented | `src/replication` module |
| `rem replication-status` | ❌ Not implemented | `src/replication` module |

**What changed in v0.2.1-dev**:
- ❌ Before: Commands crashed with `JSONDecodeError` on invalid mock JSON
- ✅ After: Commands exit cleanly with exit code 1 and point to implementation location

## Detailed Issues

### Issue #1: All CLI commands not implemented (CRITICAL)

**Severity**: Critical (blocks all usage)
**Status**: 🔧 Partially fixed in v0.2.1-dev

**Root cause**:
- Rust core library modules exist (`src/database`, `src/storage`, `src/index`, etc.)
- PyO3 bindings in `src/bindings/database.rs` are all `todo!()` placeholders
- CLI commands delegate to these unimplemented bindings

**What was fixed**:
- ✅ Removed all mock JSON data that caused `JSONDecodeError` crashes
- ✅ Commands now exit gracefully with helpful error messages
- ✅ Error messages point to exact Rust file/function needing implementation

**What still needs work**:
- ❌ Implement PyO3 bindings in `src/bindings/database.rs`
- ❌ Connect bindings to Rust core library (storage, index, query modules)
- ❌ Add integration tests for CLI → Python → Rust flow

**Old behavior (v0.2.0)**:
```bash
$ rem get 550e8400-...
JSONDecodeError: Expecting property name enclosed in double quotes: line 1 column 31
```

**New behavior (v0.2.1-dev)**:
```bash
$ rem get 550e8400-...
✗ Not implemented - Rust bindings need to be completed
Help wanted: See src/bindings/database.rs::get()
```

### Issue #2: No data verification workflow

**Severity**: Medium
**Status**: Blocked by Issue #1

Once CLI commands are implemented, users will need verification tools. Currently there's no way to:
- Count records in a table
- View sample records
- Verify schema registration
- Check database statistics

**Recommendation**: After implementing core commands, add:
- `rem count <schema>` - Quick record count
- `rem sample <schema> --limit=5` - Show sample records
- `rem stats` - Database statistics (size, record counts, index status)

### Issue #3: Version published to PyPI sets wrong expectations

**Severity**: Medium (user experience)
**Status**: Will fix in v0.2.1

**Problem**: Version 0.2.0 was published to PyPI but no commands work.

**Current state**:
- ✅ Package builds and installs correctly
- ✅ CLI is accessible
- ❌ ALL commands are unimplemented (exit with error)
- ❌ No working functionality at all

**Version semantics**:
- `0.1.0-alpha` - Early development, core features incomplete ← **This is where we are**
- `0.2.0-beta` - Major features working, some gaps
- `0.2.0` - Production-ready for basic use

**Recommendation**:
- Publish v0.2.1 with improved error messages (current state)
- Add "alpha" badge to README
- Add "Implementation Status" section showing what works
- Set expectations that this is pre-alpha quality

## Test Results Summary

**Test environment:**
- OS: macOS 14.4 (ARM64)
- Python: 3.11.11
- Installation: `pip install percolate-rocks==0.2.0`

**v0.2.0 test results (all commands failed):**
```bash
rem init                                                 # ❌ Mock success (no DB created)
rem schema-add article.json                              # ❌ Mock success (no schema registered)
rem insert Article --batch                               # ❌ Mock success (no data inserted)
rem get 550e8400-...                                     # ❌ JSONDecodeError (invalid mock JSON)
rem lookup "title"                                       # ❌ JSONDecodeError (invalid mock JSON)
rem search "query"                                       # ❌ JSONDecodeError (invalid mock JSON)
rem query "SELECT * FROM Article"                        # ❌ JSONDecodeError (invalid mock JSON)
rem ask "show articles"                                  # ❌ JSONDecodeError (invalid mock JSON)
rem traverse 550e8400-...                                # ❌ JSONDecodeError (invalid mock JSON)
rem export Article --output test.parquet                 # ❌ Mock success (no export)
```

**Success rate**: 0/10 commands (0%)

**v0.2.1-dev test results (graceful failures):**
```bash
rem init                                                 # ❌ Clear error message
rem schema-add article.json                              # ❌ Clear error message
# ... all commands exit with helpful error pointing to Rust implementation
```

**Success rate**: Still 0/10, but no crashes and clear error messages ✅

## Priority Recommendations

### P0 - Critical (Foundation)

**Goal**: Make basic insert/query workflow functional

1. **Implement PyO3 Database wrapper**
   - Complete `src/bindings/database.rs::PyDatabase::new()`
   - Connect to Rust `Database` from `src/database` module
   - Add proper error type conversions (`src/bindings/errors.rs`)

2. **Implement schema registration**
   - Complete `PyDatabase::register_schema()`
   - Wire to `src/schema/registry.rs`
   - Add persistence to RocksDB schema column family

3. **Implement basic insert**
   - Complete `PyDatabase::insert()` and `insert_batch()`
   - Wire to `src/database` insert methods
   - Return actual UUIDs, not mock data

4. **Implement get by ID**
   - Complete `PyDatabase::get()`
   - Wire to `src/storage` entity retrieval
   - Proper None handling for missing entities

### P1 - High (Core Queries)

5. **Implement SQL query execution**
   - Complete `PyDatabase::query()`
   - Wire to `src/query/executor.rs`
   - Return real query results

6. **Implement key lookup**
   - Complete `PyDatabase::lookup()`
   - Wire to `src/index/keys.rs` reverse index
   - Support global key searches

7. **Implement schema listing**
   - Add method to retrieve registered schemas
   - Show schema metadata (version, fields, indexes)
   - Fix `rem schema-list` command

### P2 - Medium (Advanced Features)

8. **Implement vector search**
   - Complete `PyDatabase::search()`
   - Wire to `src/index/hnsw.rs`
   - Require embedding configuration

9. **Implement graph traversal**
   - Complete `PyDatabase::traverse()`
   - Wire to `src/graph/traversal.rs`
   - Support depth and direction options

10. **Implement data export**
    - Complete `PyDatabase::export()`
    - Wire to `src/export` module
    - Support Parquet/CSV/JSONL formats

### P3 - Low (Nice to Have)

11. **Add verification commands**
    - `rem count <schema>`
    - `rem sample <schema> --limit=N`
    - `rem stats`

12. **Implement natural language queries**
    - Complete `PyDatabase::ask()`
    - Wire to `src/llm` query builder
    - Require LLM API configuration

## Documentation Gaps

### README.md needs updates for v0.2.1:

1. **Add implementation status badge** - Make it clear this is pre-alpha
2. **Add "Current Status" section** - All commands are unimplemented
3. **Remove/comment examples** - Don't show examples that don't work
4. **Add roadmap** - Show what's planned vs. what's done

### Recommendations:

```markdown
# percolate-rocks

⚠️  **Status: Pre-Alpha** - All CLI commands are currently unimplemented.
PyO3 bindings are in progress. See [ISSUES.md](ISSUES.md) for details.

## Current Status (v0.2.1)

- ✅ Package builds and installs from PyPI
- ✅ Rust core library structure complete
- ❌ PyO3 bindings not implemented (all `todo!()`)
- ❌ No CLI commands work yet

**Help wanted**: See `src/bindings/database.rs` to contribute.
```

## Next Release Checklist (v0.2.1)

**v0.2.1 - Better error messages (current state)**
- [x] Remove all mock JSON data
- [x] Add clear error messages for unimplemented commands
- [x] Update ISSUES.md with current status
- [ ] Update README.md with status badge
- [ ] Publish to PyPI (replaces confusing v0.2.0)

**v0.3.0 - Basic functionality**
- [ ] Implement P0 commands (init, schema-add, insert, get, query)
- [ ] Add integration tests
- [ ] Test on Linux AMD64 and macOS ARM64
- [ ] Document working getting-started workflow

**v0.4.0 - Search and indexing**
- [ ] Implement vector search
- [ ] Implement key lookup
- [ ] Add schema listing
- [ ] Add verification commands (count, sample, stats)

## Contact

For bug reports and feature requests:
- GitHub Issues: [percolating-sirsh/percolate-node](https://github.com/percolating-sirsh/percolate-node/issues)
- Project: `percolate-rocks/` subdirectory

---

_Last updated: 2025-10-25 (v0.2.0 release testing)_
