# Percolate Project Summary

## What Has Been Created

A comprehensive foundation for Percolate - a privacy-first personal AI node with a clean **3-package architecture**.

## Three-Package Architecture

### 1. percolate (REM Node - Python)
**Location:** `percolate/`  
**Purpose:** Memory, agents, and API server  
**Language:** Python with Rust extensions via percolate-rust  

**Responsibilities:**
- REM memory storage and retrieval
- Agent-let runtime
- Chat API and MCP server
- OAuth 2.1 authentication
- Orchestration and user-facing API

### 2. percolate-reading (Reader Node - Python)
**Location:** `percolate-reading/`  
**Purpose:** Heavy multimedia processing services  
**Language:** Python (with optional Rust components in future)  

**Responsibilities:**
- Document parsing (PDF, Excel, Audio)
- Heavy embedding models
- OCR services
- Audio transcription (Whisper)
- Visual verification
- Can use percolate-rust for fast parsing in future

### 3. percolate-rust (Shared Components - Rust + PyO3)
**Location:** `percolate-rust/`  
**Purpose:** Performance-critical shared components  
**Language:** Rust with Python bindings  

**Provides:**
- REM storage providers (RocksDB, PostgreSQL)
- Cryptographic primitives (Ed25519, ChaCha20, HKDF)
- Lightweight embeddings (HNSW)
- Fast document parsing (future)
- **Used by:** Both percolate and percolate-reading

## Why This Structure?

**Clean separation:**
- Python packages stay pure Python (easy to develop)
- Rust code is shared where it makes sense
- Each package can import percolate-rust independently

**Flexibility:**
- Reading node can add Rust components later (fast PDF parsing)
- REM node gets Rust for memory and crypto
- Both benefit from shared Rust code

**No confusion:**
- 2 deployable services (percolate, percolate-reading)
- 1 shared library (percolate-rust)

## Cloud Architecture Optimization

**Key Innovation:** In cloud deployments, percolate-reading is a **shared service**:

```
Tenant A Node (REM) ──┐
Tenant B Node (REM) ──┼──> Shared Reading Service (GPU)
Tenant C Node (REM) ──┘
```

All nodes use percolate-rust for performance-critical operations.

**Benefits:**
- 98.6% cost reduction vs dedicated GPU per tenant
- Scales independently
- Efficient resource utilization
- ~$3.54/tenant/month vs $250/month

## Documentation Structure

### Root Level
- **README.md** - Project overview with architecture diagrams
- **Claude.md** - Coding standards (based on Carrier)
- **.gitignore** - Comprehensive ignore patterns
- **PROJECT_SUMMARY.md** - This file
- **.spikes/** - Experimental code and prototypes (see below)

### Architecture Docs (`docs/`)
1. **01-architecture.md** - System architecture and design philosophy
2. **02-rem-memory.md** - REM memory system details
3. **03-agent-lets.md** - Agent-let framework specification
4. **04-sync-replication.md** - Multi-node sync with vector clocks
5. **05-sharing-collaboration.md** - Data sharing and team workspaces
6. **06-cloud-deployment.md** - Cloud architecture and cost optimization
7. **07-multi-tenant-allocation.md** - Tiered multi-tenancy with K8s HPA and context blob caching

### Component Designs (`docs/components/`)
- **memory-engine.md** - Rust memory engine implementation
- **auth-flow.md** - OAuth 2.1 authentication flows (includes key management models)
- **parsing-pipeline.md** - Document processing pipeline
- **storage-provider.md** - Pluggable storage abstraction
- **query-layer.md** - SQL-like predicate queries over RocksDB

### Experimental Spikes (`.spikes/`)

The `.spikes/` directory contains experimental prototypes for testing concepts:

**Purpose:**
- Iterate rapidly without polluting main codebase
- Test architectural decisions with working code
- Find cleanest solution through experimentation
- Document learnings before main implementation

**Active Spikes:**

1. **`.spikes/rem-db/`** - REM Database Implementation
   - Goal: Build RocksDB-based REM with vector search and SQL predicates
   - Approach: Python prototype first for speed, then port to Rust
   - Tests: Performance, API ergonomics, tenant isolation
   - Status: Ready to begin implementation

2. **`.spikes/platform/`** - Multi-Tenant Platform Layer
   - Goal: Design cloud platform infrastructure
   - Components: Argo/K8s manifests, gateway, management DB, archival
   - Tests: Tier routing, HPA scaling, tenant migrations
   - Status: Architecture defined, ready for prototyping

**Guidelines:**
- Spikes can be messy and contain dead ends
- Document learnings in spike README
- Extract clean patterns to main codebase once proven
- Archive completed spikes (not deleted)

## Project Structure

```
percolation/
├── percolate/              # REM Node (Python)
│   ├── src/percolate/
│   │   ├── api/            # FastAPI server + MCP
│   │   ├── agents/         # Agent-let runtime
│   │   ├── memory/         # REM interface (wraps Rust)
│   │   ├── auth/           # OAuth 2.1
│   │   ├── client/         # Reading client
│   │   ├── cli/            # CLI
│   │   └── settings.py     # Pydantic Settings
│   ├── schema/             # Agent-let JSON schemas
│   │   ├── agentlets/
│   │   └── evaluators/
│   └── pyproject.toml
│
├── percolate-reading/      # Reader Node (Python)
│   ├── src/percolate_reading/
│   │   ├── api/            # Processing API
│   │   ├── parsers/        # PDF/Excel/Audio
│   │   ├── embeddings/     # Heavy models
│   │   ├── ocr/            # OCR services
│   │   ├── transcription/  # Whisper
│   │   ├── cli/            # CLI
│   │   └── settings.py     # Pydantic Settings
│   └── pyproject.toml
│
├── percolate-rust/         # Shared Rust (PyO3)
│   ├── src/
│   │   ├── lib.rs          # Python bindings
│   │   ├── memory/         # REM engine
│   │   ├── crypto/         # Ed25519, ChaCha20
│   │   ├── embeddings/     # Lightweight HNSW
│   │   └── parsers/        # Fast parsers
│   ├── Cargo.toml
│   └── README.md
│
├── docs/                   # Architecture docs
└── Claude.md               # Coding standards
```

## Key Design Decisions

1. **Three-package structure**: Clean separation of concerns
2. **Shared Rust library**: percolate-rust used by both Python packages
3. **Schema in percolate**: Agent-let definitions with REM node
4. **Storage providers**: Pluggable (RocksDB default, PostgreSQL enterprise)
5. **Both use Pydantic Settings**: Consistent configuration
6. **Mobile-first auth**: Ed25519 keys in secure enclave
7. **Multi-node sync**: Vector clocks and CRDTs
8. **Team workspaces**: Shared memory with encryption

## Storage Provider Abstraction

**Key Feature:** Pluggable storage backend via provider interface

### Providers

1. **RocksDB** (Default)
   - Use case: Desktop, mobile, per-tenant cloud pods
   - Isolation: Separate database files per tenant

2. **PostgreSQL** (Enterprise)
   - Use case: Enterprise with shared database
   - Isolation: Schema-level + row-level security

### Configuration

```python
# RocksDB (default)
from percolate_rust import MemoryEngine

memory = MemoryEngine(
    provider="rocksdb",
    path="./data/percolate.db",
    tenant_id="tenant-123"
)

# PostgreSQL (enterprise)
memory = MemoryEngine(
    provider="postgres",
    connection_string="postgresql://localhost/percolate",
    tenant_id="tenant-123"
)
```

## API Boundaries

### Percolate → Percolate-Reading
**Protocol:** HTTP  
**Client:** `percolate.client.ReadingClient`  
**Endpoints:**
- `POST /parse/pdf` - Parse PDF
- `POST /parse/excel` - Parse Excel
- `POST /parse/audio` - Transcribe audio
- `POST /embed/batch` - Generate embeddings
- `POST /ocr/extract` - OCR extraction

### Clients → Percolate
**Protocol:** HTTP/WebSocket/MCP  
**Endpoints:**
- `POST /v1/chat/completions` - OpenAI-compatible
- `POST /v1/ingest/upload` - Document upload
- `/mcp` - Model Context Protocol
- `/oauth/*` - OAuth 2.1 flows

### Python → Rust
**Protocol:** PyO3 bindings  
**Module:** `percolate_rust`  
**Used by:** percolate (now), percolate-reading (future)

## Next Steps

### Phase 1: Core Implementation
1. Implement REM memory engine (Rust)
2. Create basic API server (Python)
3. Implement authentication (OAuth 2.1)
4. Build reading client integration

### Phase 2: Processing
1. Implement document parsers (percolate-reading)
2. Add lightweight embeddings (Rust)
3. Create reading node API
4. Integrate heavy models

### Phase 3: Agents
1. Implement agent-let runtime
2. Create MCP server
3. Add evaluation framework
4. Build feedback loops

### Phase 4: Sync & Collaboration
1. Implement multi-node sync
2. Add sharing capabilities
3. Create team workspaces
4. Deploy to cloud

## Development Commands

### Percolate (REM Node)
```bash
cd percolate
uv venv && source .venv/bin/activate

# Build Rust extension
cd ../percolate-rust
maturin develop
cd ../percolate

# Install Python deps
uv pip install -e ".[dev]"
uv run percolate serve
```

### Percolate-Reading (Reader Node)
```bash
cd percolate-reading
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
uv run percolate-reading serve --port 8001
```

### Percolate-Rust (Shared Components)
```bash
cd percolate-rust

# Build Rust library
cargo build --release

# Build Python extension
maturin develop

# Test
cargo test

# Benchmark
cargo bench
```

## Design Principles

From Carrier:
- Conciseness: Minimal, precise code
- No hacks: Fail fast, explicit errors
- Separation of concerns: Single responsibility
- Modularity: Functions 5-15 lines, modules <200 lines

From P8FS Research:
- No agents, only state: Agents are data
- Context engineering: Sophisticated retrieval
- Hybrid storage: Graph + relational + vector
- Mobile-first security: Device as root of trust

## References

- Carrier: `/Users/sirsh/code/tribe/carrier`
- P8FS-Modules: `/Users/sirsh/code/p8fs-modules`
- Pydantic AI: https://ai.pydantic.dev
- FastMCP: https://github.com/jlowin/fastmcp
- OAuth 2.1: https://oauth.net/2.1/
- PyO3: https://pyo3.rs
- Maturin: https://www.maturin.rs

---

**Status:** Foundation complete with clean 3-package structure  
**Documentation:** High-level, objective, comprehensive  
**Code:** Placeholder structure with clear interfaces  
**Schema:** Lives in percolate package  
**Rust:** Shared components in percolate-rust
