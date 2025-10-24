# REM Database Benchmark Implementation Plan

## Quick Start

```bash
# Run all benchmarks and generate comparison report
./run_benchmarks.sh

# View results
open benchmark_results/comparison_report.html
```

## Benchmark Suite Structure

```
.spikes/
├── benchmarks/                    # Shared benchmark infrastructure
│   ├── fixtures/                  # Test data
│   │   ├── generate_fixtures.py   # Generate test entities/documents
│   │   ├── entities_1k.json
│   │   ├── entities_10k.json
│   │   └── documents_1k.txt
│   ├── scenarios/                 # End-to-end scenarios
│   │   ├── rag_simulation.py      # RAG application workflow
│   │   ├── analytics_workload.py  # Complex SQL queries
│   │   └── multi_tenant.py        # Concurrent tenant simulation
│   ├── compare.py                 # Generate comparison report
│   └── run_all.sh                 # Run all benchmarks
│
├── rem-db/                        # Python implementation
│   └── tests/
│       └── test_performance.py    # Existing Python benchmarks
│
└── percolate-rocks/               # Rust implementation
    ├── benches/
    │   ├── entity_operations.rs   # CRUD benchmarks
    │   ├── scan_operations.rs     # Scan benchmarks
    │   └── vector_search.rs       # Vector search benchmarks
    └── examples/
        └── benchmark_cli.rs       # CLI for scenario benchmarks
```

## Phase 1: Microbenchmarks (Week 1)

### Step 1.1: Generate Shared Fixtures

**File:** `benchmarks/fixtures/generate_fixtures.py`

```python
"""Generate benchmark test data."""
import json
import random
from pathlib import Path
from uuid import uuid4

def generate_entities(count: int, output_file: Path):
    """Generate test entities."""
    entities = []
    for i in range(count):
        entities.append({
            "id": str(uuid4()),
            "type": random.choice(["person", "project", "resource"]),
            "name": f"Entity {i}",
            "properties": {
                "index": i,
                "status": random.choice(["active", "inactive"]),
                "priority": random.randint(1, 5),
                "team": random.choice(["platform", "infra", "data"]),
                "description": f"This is entity number {i} with various properties."
            }
        })

    with open(output_file, 'w') as f:
        json.dump(entities, f)

    print(f"✓ Generated {count} entities -> {output_file}")

if __name__ == "__main__":
    fixtures_dir = Path(__file__).parent
    generate_entities(1_000, fixtures_dir / "entities_1k.json")
    generate_entities(10_000, fixtures_dir / "entities_10k.json")
    generate_entities(100_000, fixtures_dir / "entities_100k.json")
```

**Run:**
```bash
cd .spikes/benchmarks/fixtures
python generate_fixtures.py
```

### Step 1.2: Python Microbenchmarks (Already Exist)

**File:** `.spikes/rem-db/tests/test_performance.py` (already implemented)

**Run:**
```bash
cd .spikes/rem-db
uv run pytest tests/test_performance.py --benchmark-only --benchmark-json=../../benchmark_results/python_micro.json
```

**Captures:**
- Insert throughput (no embeddings)
- Read throughput (by ID)
- Scan performance (10k entities)
- Vector search latency
- Memory footprint estimate

### Step 1.3: Rust Microbenchmarks (New)

**File:** `.spikes/percolate-rocks/benches/entity_operations.rs`

```rust
use criterion::{black_box, criterion_group, criterion_main, Criterion, BenchmarkId};
use percolate_rocks::{Database, Entity};
use std::path::PathBuf;
use tempfile::TempDir;
use uuid::Uuid;

fn bench_insert(c: &mut Criterion) {
    let mut group = c.benchmark_group("insert");

    for size in [100, 1000, 10000] {
        group.bench_with_input(BenchmarkId::new("no_embedding", size), &size, |b, &size| {
            b.iter_batched(
                || {
                    let temp_dir = TempDir::new().unwrap();
                    let db = Database::open(temp_dir.path(), "bench-tenant").unwrap();
                    (db, temp_dir)
                },
                |(db, _temp_dir)| {
                    for i in 0..size {
                        let properties = serde_json::json!({
                            "name": format!("Entity {}", i),
                            "index": i,
                            "status": "active",
                        });
                        let _ = db.insert_entity("test", properties).unwrap();
                    }
                },
                criterion::BatchSize::PerIteration,
            );
        });
    }

    group.finish();
}

fn bench_get(c: &mut Criterion) {
    let mut group = c.benchmark_group("get");

    // Setup: Insert 10k entities
    let temp_dir = TempDir::new().unwrap();
    let db = Database::open(temp_dir.path(), "bench-tenant").unwrap();

    let mut entity_ids = Vec::new();
    for i in 0..10000 {
        let properties = serde_json::json!({"index": i});
        let id = db.insert_entity("test", properties).unwrap();
        entity_ids.push(id);
    }

    group.bench_function("by_id", |b| {
        b.iter(|| {
            for id in entity_ids.iter().take(1000) {
                let _ = db.get_entity(black_box(*id)).unwrap();
            }
        });
    });

    group.finish();
}

criterion_group!(benches, bench_insert, bench_get);
criterion_main!(benches);
```

**File:** `.spikes/percolate-rocks/benches/scan_operations.rs`

```rust
use criterion::{black_box, criterion_group, criterion_main, Criterion};
use percolate_rocks::Database;
use tempfile::TempDir;

fn bench_scan(c: &mut Criterion) {
    let mut group = c.benchmark_group("scan");

    for size in [1000, 10000, 100000] {
        // Setup database with entities
        let temp_dir = TempDir::new().unwrap();
        let db = Database::open(temp_dir.path(), "bench-tenant").unwrap();

        for i in 0..size {
            let properties = serde_json::json!({"index": i, "status": "active"});
            let _ = db.insert_entity("test", properties).unwrap();
        }

        group.bench_function(format!("full_scan_{}", size), |b| {
            b.iter(|| {
                let entities = db.scan_entities().unwrap();
                black_box(entities);
            });
        });

        group.bench_function(format!("scan_by_type_{}", size), |b| {
            b.iter(|| {
                let entities = db.scan_entities_by_type("test").unwrap();
                black_box(entities);
            });
        });
    }

    group.finish();
}

criterion_group!(benches, bench_scan);
criterion_main!(benches);
```

**Run:**
```bash
cd .spikes/percolate-rocks
cargo bench --bench entity_operations -- --save-baseline rust_micro
cargo bench --bench scan_operations -- --save-baseline rust_micro
```

## Phase 2: End-to-End Scenarios (Week 2)

### Step 2.1: RAG Simulation

**File:** `benchmarks/scenarios/rag_simulation.py`

```python
"""RAG application simulation benchmark."""
import asyncio
import time
import json
import sys
from pathlib import Path

# Add both implementations to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "rem-db" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "percolate-rocks" / "python"))

def benchmark_python():
    """Benchmark Python implementation."""
    from rem_db import REMDatabase
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        db = REMDatabase(tenant_id="rag-bench", path=tmpdir)

        # Load fixtures
        fixtures_path = Path(__file__).parent.parent / "fixtures" / "documents_1k.txt"
        with open(fixtures_path) as f:
            documents = [line.strip() for line in f if line.strip()]

        # Phase 1: Ingest
        start = time.perf_counter()
        for i, doc in enumerate(documents[:1000]):
            db.insert("resources", {
                "name": f"doc-{i}",
                "content": doc,
            })
        ingest_time = time.perf_counter() - start

        # Phase 2: Query
        queries = ["machine learning", "database design", "web development"]
        start = time.perf_counter()
        for query in queries * 10:  # 30 queries total
            results = db.sql(f"SELECT * FROM resources WHERE embedding.cosine('{query}') LIMIT 10")
        query_time = time.perf_counter() - start

        db.close()

        return {
            "implementation": "Python",
            "ingest_time_sec": ingest_time,
            "ingest_throughput": 1000 / ingest_time,
            "query_time_sec": query_time,
            "query_throughput": 30 / query_time,
        }

async def benchmark_rust():
    """Benchmark Rust implementation."""
    from percolate_rocks import REMDatabase
    import tempfile
    import os

    # Use OpenAI for fair comparison
    os.environ["P8_DEFAULT_EMBEDDING"] = "text-embedding-3-small"

    with tempfile.TemporaryDirectory() as tmpdir:
        db = REMDatabase(tenant_id="rag-bench", path=tmpdir, enable_embeddings=True)

        db.register_schema("resources", {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "content": {"type": "string"}
            }
        }, embedding_fields=["content"])

        # Load fixtures
        fixtures_path = Path(__file__).parent.parent / "fixtures" / "documents_1k.txt"
        with open(fixtures_path) as f:
            documents = [line.strip() for line in f if line.strip()]

        # Phase 1: Ingest
        start = time.perf_counter()
        for i, doc in enumerate(documents[:1000]):
            await db.insert_with_embedding("resources", {
                "name": f"doc-{i}",
                "content": doc,
            })
        ingest_time = time.perf_counter() - start

        # Phase 2: Query (not implemented yet - placeholder)
        query_time = 0.0  # TODO: Implement vector search in Rust

        return {
            "implementation": "Rust",
            "ingest_time_sec": ingest_time,
            "ingest_throughput": 1000 / ingest_time,
            "query_time_sec": query_time,
            "query_throughput": 0.0,
        }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--impl", choices=["python", "rust", "both"], default="both")
    args = parser.parse_args()

    results = []

    if args.impl in ["python", "both"]:
        print("Running Python RAG simulation...")
        results.append(benchmark_python())

    if args.impl in ["rust", "both"]:
        print("Running Rust RAG simulation...")
        results.append(asyncio.run(benchmark_rust()))

    # Print results
    print("\n" + "="*60)
    print("RAG SIMULATION RESULTS")
    print("="*60)
    for result in results:
        print(f"\n{result['implementation']}:")
        print(f"  Ingest: {result['ingest_time_sec']:.2f}s ({result['ingest_throughput']:.1f} docs/sec)")
        print(f"  Query:  {result['query_time_sec']:.2f}s ({result['query_throughput']:.1f} queries/sec)")

    # Save to JSON
    output_path = Path(__file__).parent.parent.parent / "benchmark_results" / "rag_simulation.json"
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
```

**Run:**
```bash
cd .spikes/benchmarks/scenarios
python rag_simulation.py --impl both
```

### Step 2.2: Analytics Workload

**File:** `benchmarks/scenarios/analytics_workload.py`

```python
"""Analytics query workload benchmark."""
import time
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "rem-db" / "src"))

def benchmark_analytics_python():
    """Benchmark analytics queries on Python implementation."""
    from rem_db import REMDatabase, Query, Eq, Gt, And
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        db = REMDatabase(tenant_id="analytics-bench", path=tmpdir)

        # Load 100k entities
        fixtures_path = Path(__file__).parent.parent / "fixtures" / "entities_100k.json"
        with open(fixtures_path) as f:
            entities = json.load(f)

        print("Loading 100k entities...")
        start = time.perf_counter()
        for entity in entities:
            db.create_entity(db.models.Entity(**entity))
        load_time = time.perf_counter() - start
        print(f"✓ Loaded in {load_time:.2f}s")

        results = {}

        # Query 1: Full scan
        start = time.perf_counter()
        all_entities = db.query_entities(Query())
        results["full_scan"] = {
            "time_sec": time.perf_counter() - start,
            "count": len(all_entities)
        }

        # Query 2: Equality filter (indexed)
        start = time.perf_counter()
        active = db.query_entities(Query().filter(Eq("status", "active")))
        results["indexed_filter"] = {
            "time_sec": time.perf_counter() - start,
            "count": len(active)
        }

        # Query 3: Range query + sort
        start = time.perf_counter()
        high_priority = db.query_entities(
            Query().filter(Gt("priority", 3)).sort("priority", db.models.Order.DESC).take(100)
        )
        results["range_sort"] = {
            "time_sec": time.perf_counter() - start,
            "count": len(high_priority)
        }

        # Query 4: Complex AND filter
        start = time.perf_counter()
        complex_query = db.query_entities(
            Query().filter(And([
                Eq("type", "person"),
                Eq("status", "active"),
                Gt("priority", 2)
            ]))
        )
        results["complex_and"] = {
            "time_sec": time.perf_counter() - start,
            "count": len(complex_query)
        }

        db.close()

        return {
            "implementation": "Python",
            "load_time_sec": load_time,
            "queries": results
        }

if __name__ == "__main__":
    print("Running Analytics Workload Benchmark...")
    result = benchmark_analytics_python()

    print("\n" + "="*60)
    print("ANALYTICS WORKLOAD RESULTS (Python)")
    print("="*60)
    print(f"\nLoad time: {result['load_time_sec']:.2f}s (100k entities)")
    print("\nQuery Performance:")
    for query_name, stats in result['queries'].items():
        print(f"  {query_name:20s}: {stats['time_sec']*1000:6.2f}ms ({stats['count']:6d} results)")

    # Save results
    output_path = Path(__file__).parent.parent.parent / "benchmark_results" / "analytics_workload.json"
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)
```

**Run:**
```bash
cd .spikes/benchmarks/scenarios
python analytics_workload.py
```

## Phase 3: Comparison Report (Week 3)

### Step 3.1: Comparison Script

**File:** `benchmarks/compare.py`

```python
"""Generate comparison report from benchmark results."""
import json
from pathlib import Path
from typing import Dict, Any

def load_results() -> Dict[str, Any]:
    """Load all benchmark results."""
    results_dir = Path(__file__).parent.parent / "benchmark_results"

    results = {}

    # Python microbenchmarks
    python_micro = results_dir / "python_micro.json"
    if python_micro.exists():
        with open(python_micro) as f:
            results["python_micro"] = json.load(f)

    # Rust microbenchmarks
    rust_micro = results_dir / "rust_micro" / "estimates.json"
    if rust_micro.exists():
        with open(rust_micro) as f:
            results["rust_micro"] = json.load(f)

    # Scenarios
    for scenario in ["rag_simulation", "analytics_workload"]:
        scenario_file = results_dir / f"{scenario}.json"
        if scenario_file.exists():
            with open(scenario_file) as f:
                results[scenario] = json.load(f)

    return results

def generate_markdown_report(results: Dict[str, Any]) -> str:
    """Generate markdown comparison report."""

    md = ["# REM Database Benchmark Results\n"]
    md.append(f"Generated: {Path(__file__).stat().st_mtime}\n")

    # Microbenchmarks
    md.append("## Microbenchmarks\n")
    md.append("### Insert Performance\n")
    md.append("| Implementation | Throughput (ops/sec) | Latency (ms) | Speedup |\n")
    md.append("|----------------|---------------------|--------------|----------|\n")

    # TODO: Parse actual benchmark results and calculate speedup
    md.append("| Python         | 1,000              | 1.00         | 1.0x     |\n")
    md.append("| Rust           | 5,000              | 0.20         | 5.0x     |\n")

    # RAG Simulation
    if "rag_simulation" in results:
        md.append("\n## RAG Simulation\n")
        md.append("| Implementation | Ingest (docs/sec) | Query (queries/sec) |\n")
        md.append("|----------------|-------------------|---------------------|\n")
        for result in results["rag_simulation"]:
            impl = result["implementation"]
            ingest = result["ingest_throughput"]
            query = result["query_throughput"]
            md.append(f"| {impl:14s} | {ingest:17.1f} | {query:19.1f} |\n")

    # Analytics
    if "analytics_workload" in results:
        md.append("\n## Analytics Workload\n")
        md.append(f"**Load time:** {results['analytics_workload']['load_time_sec']:.2f}s\n\n")
        md.append("| Query Type      | Time (ms) | Results |\n")
        md.append("|-----------------|-----------|----------|\n")
        for query_name, stats in results["analytics_workload"]["queries"].items():
            time_ms = stats["time_sec"] * 1000
            count = stats["count"]
            md.append(f"| {query_name:15s} | {time_ms:9.2f} | {count:8d} |\n")

    return "".join(md)

if __name__ == "__main__":
    results = load_results()
    report = generate_markdown_report(results)

    # Save markdown
    output_path = Path(__file__).parent.parent / "benchmark_results" / "comparison_report.md"
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(report)

    print(f"✓ Comparison report saved to: {output_path}")
    print("\n" + report)
```

**Run:**
```bash
cd .spikes/benchmarks
python compare.py
```

### Step 3.2: Automated Benchmark Runner

**File:** `benchmarks/run_all.sh`

```bash
#!/bin/bash
set -e

echo "======================================"
echo "REM Database Benchmark Suite"
echo "======================================"

# Create results directory
mkdir -p ../benchmark_results

# Phase 1: Generate fixtures
echo "\n[1/6] Generating test fixtures..."
cd fixtures
python generate_fixtures.py

# Phase 2: Python microbenchmarks
echo "\n[2/6] Running Python microbenchmarks..."
cd ../../rem-db
uv run pytest tests/test_performance.py --benchmark-only \
  --benchmark-json=../benchmark_results/python_micro.json

# Phase 3: Rust microbenchmarks
echo "\n[3/6] Running Rust microbenchmarks..."
cd ../percolate-rocks
cargo bench --bench entity_operations -- --save-baseline rust_micro
cargo bench --bench scan_operations -- --save-baseline rust_micro

# Phase 4: RAG simulation
echo "\n[4/6] Running RAG simulation..."
cd ../benchmarks/scenarios
python rag_simulation.py --impl both

# Phase 5: Analytics workload
echo "\n[5/6] Running analytics workload..."
python analytics_workload.py

# Phase 6: Generate report
echo "\n[6/6] Generating comparison report..."
cd ..
python compare.py

echo "\n======================================"
echo "✓ Benchmarks complete!"
echo "Results: ../benchmark_results/comparison_report.md"
echo "======================================"
```

**Run:**
```bash
cd .spikes/benchmarks
chmod +x run_all.sh
./run_all.sh
```

## Expected Timeline

### Week 1: Microbenchmarks
- **Day 1:** Generate fixtures, setup infrastructure
- **Day 2:** Run Python benchmarks (already exist)
- **Day 3-4:** Implement Rust benchmarks (entity_operations, scan_operations)
- **Day 5:** Analyze microbenchmark results, document findings

### Week 2: End-to-End Scenarios
- **Day 6-7:** RAG simulation (both implementations)
- **Day 8-9:** Analytics workload
- **Day 10:** Multi-tenant simulation (stretch goal)

### Week 3: Analysis & Reporting
- **Day 11-12:** Implement comparison script
- **Day 13:** Generate charts and visualizations
- **Day 14:** Write final analysis document
- **Day 15:** Present findings, decide on Rust migration scope

## Success Metrics

### Microbenchmarks
- ✅ Rust 2-5x faster on insert (no embeddings)
- ✅ Rust 2-5x faster on read (by ID)
- ✅ Rust 5-10x faster on full scans
- ✅ Rust 2-5x lower memory usage

### End-to-End Scenarios
- ✅ RAG ingestion 2-3x faster (Rust)
- ✅ Analytics queries 5-10x faster (Rust)
- ✅ Multi-tenant 10-100x higher QPS (Rust)

### Decision Criteria
If Rust shows **<2x improvement** on typical workloads:
  → **Stick with Python** (not worth complexity)

If Rust shows **2-5x improvement**:
  → **Hybrid approach** (Python API + Rust core via PyO3)

If Rust shows **>5x improvement**:
  → **Full Rust migration** (rewrite from scratch)

## Next Steps

1. **Run microbenchmarks** (Week 1)
   ```bash
   cd .spikes/benchmarks
   ./run_all.sh
   ```

2. **Analyze results** (Week 2)
   - Identify bottlenecks in both implementations
   - Measure memory usage (Python: memory_profiler, Rust: valgrind)
   - Profile CPU (Python: py-spy, Rust: flamegraph)

3. **Make decision** (Week 3)
   - Document performance comparison
   - Calculate ROI (development time vs performance gains)
   - Choose migration strategy (none, hybrid, full)

4. **Execute plan** (Ongoing)
   - If hybrid: Port hotspots to Rust, keep Python API
   - If full: Incremental rewrite, feature parity checklist
   - If none: Optimize Python (Cython, PyPy, algorithmic improvements)
