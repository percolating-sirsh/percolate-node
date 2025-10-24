# Analytics export strategy: Cached snapshots → DuckDB

## Core insight

For a **personal database** (< 1M rows), we don't need real-time analytics. Instead:
- Export database snapshots periodically (hourly, daily)
- Store as Parquet files or DuckDB database
- Query with DuckDB for analytics (aggregations, joins, window functions)
- Accept latency (minutes to hours) for analytical queries

**Why this works**:
- Personal use = small data (< 1M rows, often < 100K)
- Analytics are occasional (dashboards, reports, exploration)
- Don't need real-time aggregations (hourly/daily refresh is fine)
- Delegate all complex SQL to DuckDB (battle-tested)
- Zero maintenance burden (no sync logic, no dual storage)

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  REM Database (RocksDB)                  │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Operational queries (real-time)                   │ │
│  │  - Entity CRUD                                     │ │
│  │  - Vector search (semantic)                        │ │
│  │  - Graph traversal                                 │ │
│  │  - Simple filters (WHERE, ORDER BY)                │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                          │
                          │ Export (scheduled)
                          │ - Every hour / day / on-demand
                          ▼
┌─────────────────────────────────────────────────────────┐
│              Analytics Snapshot (Parquet)                │
│  ┌────────────────────────────────────────────────────┐ │
│  │  .fs/analytics/{tenant}/                           │ │
│  │    ├── resources.parquet                           │ │
│  │    ├── agents.parquet                              │ │
│  │    ├── sessions.parquet                            │ │
│  │    ├── messages.parquet                            │ │
│  │    └── export_metadata.json                        │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                          │
                          │ Query
                          ▼
┌─────────────────────────────────────────────────────────┐
│                   DuckDB Analytics                       │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Analytical queries (cached)                       │ │
│  │  - Aggregations (GROUP BY, COUNT, SUM, AVG)        │ │
│  │  - Multi-table joins                               │ │
│  │  - Window functions (RANK, LAG, LEAD)              │ │
│  │  - Complex SQL (CTEs, subqueries)                  │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## Implementation

### 1. Export database to Parquet

```python
# src/rem_db/analytics.py

from pathlib import Path
from datetime import datetime
import pyarrow as pa
import pyarrow.parquet as pq
import orjson
from typing import Optional

class AnalyticsExporter:
    """Export REM database to Parquet for analytics."""

    def __init__(self, db: REMDatabase, export_path: Path):
        self.db = db
        self.export_path = export_path
        self.export_path.mkdir(parents=True, exist_ok=True)

    def export_table(self, table_name: str) -> Path:
        """Export a single table to Parquet.

        Args:
            table_name: Name of table/schema to export

        Returns:
            Path to exported Parquet file
        """
        # Get schema
        schema = self.db.get_schema(table_name)
        if not schema:
            raise ValueError(f"Schema not found: {table_name}")

        # Scan all entities of this type
        entities = self.db.sql(f"SELECT * FROM {table_name}")

        if not entities:
            print(f"No data for table: {table_name}")
            return None

        # Convert to records (flatten properties)
        records = []
        for entity in entities:
            record = {
                "id": str(entity.id),
                "created_at": entity.created_at.isoformat(),
                "modified_at": entity.modified_at.isoformat(),
                "deleted_at": entity.deleted_at.isoformat() if entity.deleted_at else None,
            }

            # Add all properties as top-level fields
            if entity.properties:
                for key, value in entity.properties.items():
                    # Skip large fields (content, embedding)
                    if key in ["content", "embedding", "embedding_alt"]:
                        continue

                    # Handle nested dicts (flatten or serialize)
                    if isinstance(value, dict):
                        record[key] = orjson.dumps(value).decode()
                    elif isinstance(value, list) and value and isinstance(value[0], dict):
                        record[key] = orjson.dumps(value).decode()
                    else:
                        record[key] = value

            records.append(record)

        # Convert to Arrow table
        arrow_table = pa.Table.from_pylist(records)

        # Write to Parquet
        output_path = self.export_path / f"{table_name}.parquet"
        pq.write_table(
            arrow_table,
            output_path,
            compression='zstd',  # Good compression ratio
            use_dictionary=True,  # Efficient for categorical fields
        )

        print(f"✓ Exported {len(records)} rows to {output_path}")
        return output_path

    def export_all(self, tables: Optional[list[str]] = None) -> dict[str, Path]:
        """Export all tables to Parquet.

        Args:
            tables: List of table names to export (None = all)

        Returns:
            Dict of table_name -> parquet_path
        """
        if tables is None:
            tables = self.db.list_schemas()

        exported = {}
        start_time = datetime.now()

        print(f"Exporting {len(tables)} tables to {self.export_path}")

        for table in tables:
            try:
                path = self.export_table(table)
                if path:
                    exported[table] = path
            except Exception as e:
                print(f"✗ Failed to export {table}: {e}")

        # Write export metadata
        metadata = {
            "exported_at": datetime.now().isoformat(),
            "duration_seconds": (datetime.now() - start_time).total_seconds(),
            "tables": list(exported.keys()),
            "row_counts": {
                table: len(self.db.sql(f"SELECT id FROM {table}"))
                for table in exported.keys()
            },
            "tenant_id": self.db.tenant_id,
        }

        metadata_path = self.export_path / "export_metadata.json"
        metadata_path.write_bytes(orjson.dumps(metadata, option=orjson.OPT_INDENT_2))

        print(f"\n✓ Export complete: {len(exported)} tables in {metadata['duration_seconds']:.1f}s")
        print(f"  Metadata: {metadata_path}")

        return exported
```

### 2. DuckDB analytics interface

```python
# src/rem_db/analytics.py (continued)

import duckdb
import pandas as pd

class AnalyticsEngine:
    """DuckDB-based analytics over exported Parquet snapshots."""

    def __init__(self, export_path: Path):
        self.export_path = export_path
        self.metadata = self._load_metadata()

        # Connect to DuckDB (in-memory)
        self.duckdb = duckdb.connect(':memory:')

        # Register all Parquet files as tables
        self._register_tables()

    def _load_metadata(self) -> dict:
        """Load export metadata."""
        metadata_path = self.export_path / "export_metadata.json"
        if not metadata_path.exists():
            raise FileNotFoundError(
                f"No export metadata found at {metadata_path}. "
                "Run export_all() first."
            )
        return orjson.loads(metadata_path.read_bytes())

    def _register_tables(self):
        """Register all Parquet files as DuckDB tables."""
        for table in self.metadata["tables"]:
            parquet_path = self.export_path / f"{table}.parquet"
            if parquet_path.exists():
                # Register Parquet file as table
                self.duckdb.execute(
                    f"CREATE OR REPLACE VIEW {table} AS "
                    f"SELECT * FROM read_parquet('{parquet_path}')"
                )
                print(f"✓ Registered table: {table}")

    def query(self, sql: str) -> pd.DataFrame:
        """Execute analytics query and return DataFrame.

        Args:
            sql: SQL query string

        Returns:
            Pandas DataFrame with results

        Example:
            >>> analytics = AnalyticsEngine(Path('.fs/analytics/tenant-123'))
            >>> df = analytics.query('''
            ...     SELECT category, COUNT(*) as count
            ...     FROM resources
            ...     WHERE created_at >= '2024-01-01'
            ...     GROUP BY category
            ...     ORDER BY count DESC
            ... ''')
        """
        return self.duckdb.execute(sql).fetchdf()

    def export_age(self) -> float:
        """Return age of export in hours."""
        from datetime import datetime, timezone

        exported_at = datetime.fromisoformat(self.metadata["exported_at"])
        age = datetime.now(timezone.utc) - exported_at.replace(tzinfo=timezone.utc)
        return age.total_seconds() / 3600

    def info(self) -> dict:
        """Return information about loaded analytics snapshot."""
        return {
            "exported_at": self.metadata["exported_at"],
            "age_hours": self.export_age(),
            "tables": self.metadata["tables"],
            "row_counts": self.metadata["row_counts"],
            "total_rows": sum(self.metadata["row_counts"].values()),
        }
```

### 3. Unified database interface with analytics

```python
# src/rem_db/database.py (additions)

class REMDatabase:
    """REM Database with analytics export capabilities."""

    def __init__(self, tenant_id: str, path: str | Path, ...):
        # ... existing init ...

        # Analytics paths
        self.analytics_path = Path(path).parent / "analytics" / tenant_id
        self._analytics_engine: Optional[AnalyticsEngine] = None

    def export_analytics(
        self,
        tables: Optional[list[str]] = None,
        force: bool = False
    ) -> dict[str, Path]:
        """Export database to Parquet for analytics.

        Args:
            tables: Tables to export (None = all)
            force: Force export even if recent export exists

        Returns:
            Dict of table_name -> parquet_path
        """
        # Check if recent export exists
        metadata_path = self.analytics_path / "export_metadata.json"
        if metadata_path.exists() and not force:
            metadata = orjson.loads(metadata_path.read_bytes())
            from datetime import datetime, timezone
            exported_at = datetime.fromisoformat(metadata["exported_at"])
            age_hours = (datetime.now(timezone.utc) - exported_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600

            if age_hours < 1:  # Less than 1 hour old
                print(f"Recent export exists ({age_hours:.1f}h old). Use force=True to re-export.")
                return {table: self.analytics_path / f"{table}.parquet" for table in metadata["tables"]}

        # Perform export
        exporter = AnalyticsExporter(self, self.analytics_path)
        return exporter.export_all(tables)

    @property
    def analytics(self) -> AnalyticsEngine:
        """Get analytics engine (lazy load).

        Returns:
            AnalyticsEngine for querying exported snapshots

        Raises:
            FileNotFoundError: If no export exists

        Example:
            >>> df = db.analytics.query("SELECT category, COUNT(*) FROM resources GROUP BY category")
        """
        if self._analytics_engine is None:
            self._analytics_engine = AnalyticsEngine(self.analytics_path)
        return self._analytics_engine

    def analytics_query(self, sql: str, max_age_hours: float = 24) -> pd.DataFrame:
        """Execute analytics query with automatic export refresh.

        Args:
            sql: SQL query string
            max_age_hours: Maximum age of export before auto-refresh

        Returns:
            Pandas DataFrame with results

        Example:
            >>> df = db.analytics_query('''
            ...     SELECT u.name, COUNT(i.id) as issue_count
            ...     FROM users u
            ...     LEFT JOIN issues i ON u.id = i.created_by
            ...     GROUP BY u.name
            ...     ORDER BY issue_count DESC
            ... ''')
        """
        # Check if export exists and is recent
        try:
            analytics = self.analytics
            if analytics.export_age() > max_age_hours:
                print(f"Export is {analytics.export_age():.1f}h old, refreshing...")
                self.export_analytics()
                # Reload analytics engine
                self._analytics_engine = AnalyticsEngine(self.analytics_path)
        except FileNotFoundError:
            print("No export found, creating initial export...")
            self.export_analytics()
            self._analytics_engine = AnalyticsEngine(self.analytics_path)

        return self.analytics.query(sql)
```

### 4. CLI commands

```python
# src/rem_db/cli.py (additions)

@app.command()
def export_analytics(
    db: Annotated[str, typer.Option("--db")] = "default",
    tables: Annotated[Optional[str], typer.Option("--tables")] = None,
    force: Annotated[bool, typer.Option("--force")] = False,
):
    """Export database to Parquet for analytics.

    Examples:
        rem-db export-analytics --db mydb
        rem-db export-analytics --db mydb --tables resources,agents
        rem-db export-analytics --db mydb --force
    """
    database = _get_db(db)

    table_list = tables.split(",") if tables else None

    exported = database.export_analytics(tables=table_list, force=force)

    rprint(f"\n✓ Exported {len(exported)} tables")
    for table, path in exported.items():
        size_mb = path.stat().st_size / 1024 / 1024
        rprint(f"  • {table}: {size_mb:.2f} MB")

    database.close()


@app.command()
def analytics(
    query: Annotated[str, typer.Argument(help="SQL query")],
    db: Annotated[str, typer.Option("--db")] = "default",
    output: Annotated[str, typer.Option("--output")] = "table",
    max_age: Annotated[float, typer.Option("--max-age-hours")] = 24,
):
    """Execute analytics query over exported snapshots.

    Examples:
        rem-db analytics "SELECT category, COUNT(*) FROM resources GROUP BY category"
        rem-db analytics "SELECT * FROM users LEFT JOIN issues ON users.id = issues.created_by"
        rem-db analytics "SELECT category, RANK() OVER (ORDER BY COUNT(*) DESC) FROM resources GROUP BY category"
    """
    database = _get_db(db)

    # Execute query with auto-refresh
    df = database.analytics_query(query, max_age_hours=max_age)

    # Display results
    if output == "json":
        rprint(df.to_json(orient="records", indent=2))
    else:
        # Rich table
        from rich.table import Table
        table = Table(show_header=True, header_style="bold cyan")

        for col in df.columns:
            table.add_column(col)

        for _, row in df.iterrows():
            table.add_row(*[str(v) for v in row])

        rprint(table)
        rprint(f"\n{len(df)} row(s) returned")

    # Show export info
    info = database.analytics.info()
    rprint(f"\n[dim]Export age: {info['age_hours']:.1f} hours[/dim]")

    database.close()


@app.command()
def analytics_info(
    db: Annotated[str, typer.Option("--db")] = "default",
):
    """Show analytics export information.

    Example:
        rem-db analytics-info --db mydb
    """
    database = _get_db(db)

    try:
        info = database.analytics.info()

        rprint("\n[bold]Analytics Export Info[/bold]")
        rprint(f"  Exported at: {info['exported_at']}")
        rprint(f"  Age: {info['age_hours']:.1f} hours")
        rprint(f"  Tables: {len(info['tables'])}")
        rprint(f"  Total rows: {info['total_rows']:,}")

        rprint("\n[bold]Table Details[/bold]")
        for table, count in info['row_counts'].items():
            rprint(f"  • {table}: {count:,} rows")

    except FileNotFoundError:
        rprint("[yellow]No analytics export found. Run 'rem-db export-analytics' first.[/yellow]")

    database.close()
```

### 5. Scheduled exports (optional)

```python
# src/rem_db/scheduler.py

import schedule
import time
from pathlib import Path
from typing import Callable

class AnalyticsScheduler:
    """Schedule periodic analytics exports."""

    def __init__(self, db: REMDatabase, interval_hours: int = 24):
        self.db = db
        self.interval_hours = interval_hours

    def start(self):
        """Start scheduled exports."""
        # Schedule export
        schedule.every(self.interval_hours).hours.do(self._export)

        print(f"Scheduled analytics export every {self.interval_hours} hours")

        # Run initial export
        self._export()

        # Run scheduler loop
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute

    def _export(self):
        """Perform export."""
        try:
            print(f"Running scheduled export...")
            self.db.export_analytics(force=True)
            print(f"✓ Scheduled export complete")
        except Exception as e:
            print(f"✗ Scheduled export failed: {e}")

# Usage (background process or systemd service)
# scheduler = AnalyticsScheduler(db, interval_hours=24)
# scheduler.start()
```

---

## Usage examples

### 1. Basic export and query

```python
from rem_db import REMDatabase

# Open database
db = REMDatabase(tenant_id="alice", path="./data")

# Export to Parquet (first time or when needed)
db.export_analytics()
# ✓ Exported 4 tables in 2.3s

# Query with DuckDB
df = db.analytics.query("""
    SELECT category, COUNT(*) as count, AVG(priority) as avg_priority
    FROM resources
    WHERE status = 'active'
    GROUP BY category
    ORDER BY count DESC
""")

print(df)
#     category  count  avg_priority
# 0  tutorial     25          4.2
# 1  guide        18          3.8
# 2  reference    12          3.1
```

### 2. Auto-refresh on query

```python
# Query with automatic export refresh if > 24h old
df = db.analytics_query("""
    SELECT
        DATE_TRUNC('month', created_at) as month,
        COUNT(*) as resources,
        COUNT(DISTINCT category) as categories
    FROM resources
    GROUP BY month
    ORDER BY month DESC
""", max_age_hours=24)
```

### 3. Complex joins

```python
# Multi-table join with aggregations
df = db.analytics_query("""
    SELECT
        u.name,
        COUNT(DISTINCT i.id) as issues,
        COUNT(DISTINCT p.id) as prs,
        AVG(i.priority) as avg_issue_priority
    FROM users u
    LEFT JOIN issues i ON u.id = i.created_by
    LEFT JOIN pull_requests p ON u.id = p.author_id
    WHERE u.status = 'active'
    GROUP BY u.name
    HAVING COUNT(DISTINCT i.id) > 5
    ORDER BY issues DESC
""")
```

### 4. Window functions

```python
# Ranking and lag
df = db.analytics_query("""
    SELECT
        category,
        COUNT(*) as total,
        RANK() OVER (ORDER BY COUNT(*) DESC) as rank,
        LAG(COUNT(*)) OVER (ORDER BY category) as prev_count
    FROM resources
    GROUP BY category
""")
```

### 5. CLI usage

```bash
# Export database
rem-db export-analytics --db mydb
# ✓ Exported 4 tables
#   • resources: 2.4 MB
#   • agents: 0.3 MB
#   • sessions: 1.2 MB
#   • messages: 3.8 MB

# Query analytics
rem-db analytics "SELECT category, COUNT(*) FROM resources GROUP BY category" --db mydb
# ┌──────────┬───────┐
# │ category │ count │
# ├──────────┼───────┤
# │ tutorial │    25 │
# │ guide    │    18 │
# └──────────┴───────┘
# 2 row(s) returned
# Export age: 0.5 hours

# Check export status
rem-db analytics-info --db mydb
# Analytics Export Info
#   Exported at: 2024-10-24T16:30:00
#   Age: 2.3 hours
#   Tables: 4
#   Total rows: 1,234
```

### 6. Scheduled exports

```bash
# Run as background service
python -c "
from rem_db import REMDatabase
from rem_db.scheduler import AnalyticsScheduler

db = REMDatabase(tenant_id='alice', path='./data')
scheduler = AnalyticsScheduler(db, interval_hours=6)  # Every 6 hours
scheduler.start()
"
```

Or with systemd:

```ini
# /etc/systemd/system/rem-analytics.service
[Unit]
Description=REM Database Analytics Export
After=network.target

[Service]
Type=simple
User=alice
WorkingDirectory=/home/alice/data
ExecStart=/usr/bin/python3 -m rem_db.scheduler --db mydb --interval 6
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## Performance expectations

### Export performance

**Small database** (< 10K entities):
- Export time: 1-5 seconds
- Parquet size: 1-10 MB
- Suitable for: On-demand exports

**Medium database** (10K-100K entities):
- Export time: 5-30 seconds
- Parquet size: 10-100 MB
- Suitable for: Hourly exports

**Large database** (100K-1M entities):
- Export time: 30-300 seconds (5 minutes)
- Parquet size: 100MB-1GB
- Suitable for: Daily exports

**Very large database** (> 1M entities):
- Export time: 5-30 minutes
- Parquet size: 1-10 GB
- Suitable for: Weekly exports or incremental updates

### Query performance (DuckDB)

**Aggregations**:
- Simple GROUP BY: 10-100ms
- Complex aggregations: 50-500ms
- Window functions: 100ms-1s

**Joins**:
- 2-table join: 20-200ms
- 3-table join: 50-500ms
- Complex multi-table: 100ms-2s

**Full table scans**:
- 10K rows: 10-50ms
- 100K rows: 50-200ms
- 1M rows: 200ms-1s

All queries are **much faster** than building aggregations ourselves in Python.

---

## Storage overhead

**Parquet compression**: ~30-50% of JSON size

Example:
- RocksDB (JSON): 100 MB
- Parquet (zstd): 30-50 MB
- **Overhead**: 30-50 MB additional disk space

For a personal database:
- 100K entities ≈ 50-100 MB Parquet
- Totally acceptable overhead

---

## Advantages of this approach

### 1. Zero maintenance
- No sync logic (just export + read)
- No consistency issues (snapshot is consistent)
- No dual storage complexity (Parquet is cache)

### 2. Delegate complexity to DuckDB
- Don't build aggregations ourselves
- Don't build joins ourselves
- Don't build window functions
- Get full SQL support for free

### 3. Acceptable latency for personal use
- Analytics are occasional (dashboards, reports)
- Don't need real-time (hourly/daily is fine)
- Export is fast (< 1 minute for typical personal DB)

### 4. Simple mental model
- RocksDB = operational (real-time)
- Parquet = analytical (cached)
- Clear separation of concerns

### 5. Portable analytics
- Parquet files can be queried by other tools
- Can share snapshots for collaboration
- Can load into Jupyter, BI tools, etc.

### 6. Incremental cost
- Export only when needed
- No continuous sync overhead
- Storage is cheap (30-50 MB for typical DB)

---

## Limitations and mitigations

### 1. Stale data (by design)
**Issue**: Analytics queries return cached data, not real-time.

**Mitigation**:
- Show export age in UI: `"Export age: 2.3 hours"`
- Auto-refresh if too old: `max_age_hours=24`
- On-demand export: `db.export_analytics(force=True)`

**Acceptable because**: Personal use = analytics are exploratory, not operational.

### 2. Export takes time
**Issue**: Large databases (> 1M rows) take minutes to export.

**Mitigation**:
- Schedule during off-hours
- Incremental exports (only changed data) - TODO
- Run as background job

**Acceptable because**: 1M rows is rare for personal use; most users < 100K.

### 3. Disk space overhead
**Issue**: Parquet files duplicate data (30-50% of RocksDB size).

**Mitigation**:
- Parquet compression (zstd)
- Skip large fields (content, embeddings)
- Periodic cleanup of old exports

**Acceptable because**: Storage is cheap, overhead is small (50-100 MB typical).

### 4. No real-time aggregations
**Issue**: Can't do `SELECT COUNT(*) FROM resources` in real-time.

**Mitigation**:
- Use cached export for analytics
- If real-time needed, build simple aggregations (COUNT only)
- Most analytics don't need real-time

**Acceptable because**: Personal databases rarely need real-time analytics.

---

## Incremental exports (future enhancement)

For very large databases, support incremental exports:

```python
def export_incremental(self, since: datetime) -> dict[str, Path]:
    """Export only entities modified since timestamp.

    Strategy:
    1. Load previous export metadata
    2. Scan RocksDB for entities with modified_at > since
    3. Append to existing Parquet (or create new partition)
    4. Update metadata
    """
    # TODO: Implement incremental export
    # Parquet supports append mode
    # Track last_exported_at in metadata
    pass
```

---

## Comparison with alternatives

### vs. Real-time DuckDB sync
**Export approach**:
- ✅ No sync complexity
- ✅ No consistency issues
- ✅ Simpler code
- ❌ Stale data (minutes to hours)

**Real-time sync**:
- ✅ Always current
- ❌ Complex sync logic
- ❌ Consistency challenges
- ❌ Continuous overhead

**Winner**: Export for personal use (simplicity >> real-time)

### vs. Building aggregations ourselves
**Export approach**:
- ✅ Full SQL support (window functions, CTEs, complex joins)
- ✅ Battle-tested engine
- ✅ No maintenance burden
- ❌ Requires export step

**Custom aggregations**:
- ✅ Real-time results
- ❌ Limited SQL support
- ❌ Need to build/maintain
- ❌ Bugs and edge cases

**Winner**: Export (delegate to DuckDB >> build ourselves)

### vs. DataFusion TableProvider
**Export approach**:
- ✅ Simple (just export + query)
- ✅ Python-only (no Rust)
- ✅ Full SQL support
- ❌ Not real-time

**DataFusion**:
- ✅ Real-time
- ✅ Rust-native
- ❌ 4-6 weeks implementation
- ❌ RocksDB key-value mismatch

**Winner**: Export for short-term (fast to implement), DataFusion for long-term Rust migration

---

## Recommendation

**Implement the cached export → DuckDB analytics pattern.**

**Why**:
1. ✅ **Simple**: ~200 lines of code, no complex logic
2. ✅ **Fast to implement**: 1-2 days
3. ✅ **Zero maintenance**: No sync, no consistency issues
4. ✅ **Full SQL**: Get aggregations, joins, window functions for free
5. ✅ **Acceptable latency**: Personal use doesn't need real-time analytics
6. ✅ **Low overhead**: 30-50 MB for typical database

**Don't**:
1. ❌ Build aggregations ourselves (SQLGlot approach)
2. ❌ Real-time DuckDB sync (too complex)
3. ❌ DataFusion TableProvider (save for Rust migration)

**Implementation order**:
1. **Export to Parquet** (1 day)
   - AnalyticsExporter class
   - export_analytics() method
   - CLI command

2. **DuckDB query interface** (1 day)
   - AnalyticsEngine class
   - analytics_query() method
   - CLI analytics command

3. **Auto-refresh logic** (half day)
   - Check export age
   - Auto-export if stale
   - Show age in UI

4. **Optional: Scheduler** (half day)
   - Background export service
   - Systemd integration

**Total**: 2-3 days of work for full analytics support.

This is the pragmatic choice for a personal database. We delegate all analytics complexity to DuckDB and accept latency (which is fine for personal use).
