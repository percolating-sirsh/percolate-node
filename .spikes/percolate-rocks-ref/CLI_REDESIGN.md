# CLI redesign summary

## What changed

We redesigned the rem-db CLI to use database names instead of paths, with sensible defaults and centralized configuration.

### Before (old pattern)

```bash
rem-db init --path ./my-database --tenant my-app
rem-db query "SELECT * FROM resources" --path ./my-database --tenant my-app
rem-db search "query" --path ./my-database --tenant my-app
```

**Problems:**
- Users had to specify `--path` and `--tenant` for every command
- No centralized config - easy to forget where databases are
- Verbose and repetitive
- Path-centric instead of name-centric

### After (new pattern)

```bash
rem-db init my-database
rem-db query -d my-database "SELECT * FROM resources"
rem-db search -d my-database "query"
rem-db list  # See all databases
```

**Benefits:**
- Database names instead of paths
- Default storage at `~/.p8/db/<name>`
- Centralized config at `~/.p8/config.json`
- Much cleaner and more intuitive
- Still supports custom paths via `--path` override

## Implementation details

### New files

**`src/config.rs`** (172 lines)
- `Config` struct for managing database registry
- `DatabaseConfig` for individual database metadata
- JSON config file at `~/.p8/config.json`
- Helper functions for default paths (`~/.p8/db/`, `~/.p8/models/`)

**Key functions:**
- `Config::load()` - Load config from `~/.p8/config.json`
- `Config::save()` - Save config to file
- `Config::register(name, path, tenant)` - Register a database
- `Config::resolve_path(name)` - Resolve name to (path, tenant)
- `Config::list()` - List all databases
- `Config::default_db_dir()` - Returns `~/.p8/db/`

### Modified files

**`src/types/error.rs`**
- Added `ConfigError` variant for configuration errors

**`src/lib.rs`**
- Added `pub mod config;` export

**`src/bin/cli.rs`** (completely rewritten)
- Changed `Init` command: `init <name> [--path]`
- Changed all commands to use `-d, --db <name>` instead of `--path` and `--tenant`
- Added `List` command to show all databases
- Added `resolve_database()` helper to look up database by name

### Command changes

| Command | Old | New |
|---------|-----|-----|
| Init | `init --path ./db --tenant demo` | `init demo [--path ./db]` |
| Query | `query "..." --path ./db --tenant demo` | `query -d demo "..."` |
| Search | `search "..." --path ./db --tenant demo` | `search -d demo "..."` |
| Schemas | `schemas --path ./db --tenant demo` | `schemas -d demo` |
| Export | `export table --output file --path ./db --tenant demo` | `export -d demo table --output file` |
| List | N/A | `list` (NEW) |

## Testing

### Manual testing

```bash
# Test init with default path
rm -rf ~/.p8/db/demo ~/.p8/config.json
./target/release/rem-db init demo

# Test list
./target/release/rem-db list

# Test query
./target/release/rem-db query -d demo "SELECT * FROM resources"

# Test search
./target/release/rem-db search -d demo "vector embeddings database" --min-score 0.3

# Test schemas
./target/release/rem-db schemas -d demo
```

### Automated testing

Updated `.spikes/test-openai-embeddings/test_complete_flow.sh` to use new CLI pattern.

## Configuration file format

**`~/.p8/config.json`:**
```json
{
  "databases": {
    "demo": {
      "name": "demo",
      "path": "/Users/sirsh/.p8/db/demo",
      "tenant": "demo"
    },
    "my-app": {
      "name": "my-app",
      "path": "/custom/path/to/db",
      "tenant": "my-app"
    }
  }
}
```

## Documentation updates

- **`USER_FLOW.md`** - Complete rewrite with new CLI pattern
- **`test_complete_flow.sh`** - Updated test script
- **`CLI_REDESIGN.md`** - This file (summary)

## Python bindings

**Python bindings remain unchanged** - they use paths directly:

```python
from percolate_rocks import REMDatabase

# Python users specify path directly
db = REMDatabase("tenant-id", "./path/to/db", enable_embeddings=True)
```

The Python bindings are lightweight wrappers around the Rust core, and don't need the CLI config management.

## Migration guide

For users with existing scripts using the old CLI:

### Old script
```bash
rem-db init --path ./my-db --tenant my-app
rem-db query "SELECT *" --path ./my-db --tenant my-app
```

### New script
```bash
rem-db init my-app --path ./my-db
rem-db query -d my-app "SELECT *"
```

Or use default path:
```bash
rem-db init my-app
rem-db query -d my-app "SELECT *"
```

## Future improvements

- [ ] `rem-db rename <old-name> <new-name>` - Rename a database
- [ ] `rem-db remove <name>` - Remove database from config
- [ ] `rem-db status <name>` - Show database info (size, schema count, etc.)
- [ ] `rem-db clone <source> <target>` - Clone a database
- [ ] Tab completion for database names
