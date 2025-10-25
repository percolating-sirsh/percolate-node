# Percolate

**Personal AI Node for Privacy-First Agentic Intelligence**

Percolate is a run-anywhere personal AI node designed for individuals who want full control over their AI assistants and data. It combines bio-inspired memory systems, privacy-first architecture, and trainable agent-lets into a unified platform that runs on desktop, mobile, or cloud infrastructure with complete tenant isolation.

## Overview

Percolate is a **three-layer system**:

1. **Percolate-Rocks** (Foundation): High-performance Rust database with REM (Resources-Entities-Moments) model
2. **Percolate** (Core): Python API server for chat, agents, search, and authentication
3. **Percolate-Reader** (Processing): Optional multimedia processing service (PDF, audio, OCR)

**Current status:**
- ✅ **Percolate-Rocks**: Published on PyPI, production-ready
- 🔨 **Percolate**: Planned (API server, agents, MCP)
- 🔨 **Percolate-Reader**: Planned (document processing)

**Key capabilities:**
- **Own your AI memory**: Store years of personal context in embedded database with semantic search
- **Train personal assistants**: Create agent-lets (JSON Schema-defined AI skills) with evaluation loops
- **Run anywhere**: Local desktop, mobile, or cloud with complete tenant isolation
- **Control privacy**: End-to-end encryption with mobile-first key management (Ed25519, ChaCha20)
- **Interoperate seamlessly**: OpenAI-compatible chat API and Model Context Protocol (MCP) support
- **REM Dreaming**: Background intelligence that generates moments, summaries, and graph connections

## Quick Start (Percolate-Rocks)

The REM database is available now for standalone use:

```bash
# Install from PyPI
pip install percolate-rocks

# Initialize database
rem init

# Register a schema (from Pydantic model or JSON)
rem schema add schema.json

# Insert data with auto-embeddings
echo '{"title": "Hello", "content": "World"}' | rem insert articles

# Semantic search (HNSW)
rem search "greeting examples" --schema=articles

# SQL queries
rem query "SELECT * FROM articles WHERE title LIKE 'Hello%'"

# Natural language queries
rem ask "show recent articles"

# REM Dreaming (background intelligence)
rem dream --lookback-hours 24
```

See [`.spikes/percolate-rocks/README.md`](.spikes/percolate-rocks/README.md) for full documentation.

## System Overview

```mermaid
graph TB
    subgraph "Layer 3: Processing (Planned)"
        Reader[Percolate-Reader<br/>PDF, Excel, Audio, OCR<br/>Heavy Embeddings]
    end

    subgraph "Layer 2: Core (Planned)"
        API[Percolate API<br/>Chat, Upload, Auth, MCP]
        Agents[Agent-let Runtime<br/>Pydantic AI + JSON Schema]
        Search[Search Interface<br/>ask, lookup, traverse]
        Sessions[Session/Message History]
        Moments[Moment Tracking]
    end

    subgraph "Layer 1: Foundation (Available Now)"
        REM[(Percolate-Rocks<br/>REM Database)]
        HNSW[HNSW Vector Index]
        SQL[SQL Query Engine]
        Graph[Graph Engine]
        Crypto[Encryption at Rest]
        Repl[Peer Replication]
    end

    Reader -->|Parsed content| API
    API --> Agents
    API --> Search
    API --> Sessions
    Agents --> REM
    Search --> HNSW
    Search --> SQL
    Search --> Graph
    Sessions --> REM
    Moments --> REM

    style REM fill:#e1f5ff
    style Agents fill:#fff4e1
    style Reader fill:#ffe1e1
    style API fill:#f0e1ff
```

**Key points:**

- **Percolate-Rocks** is the foundation - a standalone REM database you can use today
- **Percolate** will wrap it with an API server, agents, and MCP tools
- **Percolate-Reader** will handle heavy processing (optional, shared service in cloud)
- All three export OpenTelemetry traces (excluding eval/LLM internals)

## System Architecture

Percolate is a **three-layer system** built around the REM database foundation:

### Layer 1: Foundation - Percolate-Rocks (REM Database)

**High-performance embedded database** providing semantic search, graph queries, and structured data storage:

- **Core**: Rust implementation with PyO3 bindings
- **Storage**: RocksDB with column families for performance
- **Vectors**: HNSW index for semantic search (200x faster than naive scan)
- **Graph**: Bidirectional edges with fast traversal
- **Encryption**: ChaCha20-Poly1305 AEAD with Ed25519 keys
- **Replication**: Primary/replica peer replication via gRPC

**Published as:** `percolate-rocks` on PyPI

### Layer 2: Core - Percolate (REM Node)

**Python API server and orchestration** sitting on top of percolate-rocks:

```mermaid
graph TB
    subgraph "Percolate API Layer"
        Chat["/v1/chat/completions<br/>OpenAI-compatible"]
        Upload["/v1/ingest/upload<br/>Document upload"]
        Auth["/oauth/*<br/>OAuth 2.1 flows"]
        MCP["/mcp<br/>Model Context Protocol"]
    end

    subgraph "Percolate Services"
        Agents[Agent-let Runtime<br/>Pydantic AI + JSON Schema]
        Search[Search Interface<br/>Semantic + SQL + Graph]
        Moments[Moment Tracking<br/>REM Dreaming]
        Sessions[Session History<br/>Message storage]
    end

    subgraph "Percolate-Rocks Foundation"
        DB[(REM Database<br/>Resources-Entities-Moments)]
        HNSW[HNSW Vector Index<br/>Rust]
        Graph[Graph Engine<br/>Bidirectional edges]
        SQL[SQL Query Engine<br/>Predicate evaluation]
    end

    Chat --> Agents
    Upload --> Search
    MCP --> Search
    MCP --> Agents

    Agents --> DB
    Search --> HNSW
    Search --> SQL
    Search --> Graph
    Moments --> DB
    Sessions --> DB

    style DB fill:#e1f5ff
    style Agents fill:#fff4e1
    style Search fill:#c8e6c9
```

**Uses percolate-rocks for:**
- Memory storage and retrieval (resources, entities, moments)
- Semantic search via HNSW
- SQL queries with predicates
- Graph traversal
- Session and message history
- REM Dreaming (background intelligence)

**Exposes:**
- Chat API (OpenAI-compatible streaming)
- Upload API (document ingestion)
- OAuth 2.1 endpoints
- MCP server with tools:
  - `search_knowledge_base`: Unified search across REM
  - `lookup_entity`: Entity graph navigation
  - `parse_document`: Document processing (via reader)
  - `create_agent`: Dynamic agent-let instantiation
  - `ask_agent`: Agent execution
  - `list_moments`: Temporal classifications

### Layer 3: Processing - Percolate-Reader

**Heavy multimedia processing service** (optional, deployed separately):

- **Document parsing**: PDF, Excel, DOCX, audio → structured content
- **Heavy embeddings**: Large embedding models (GPU-accelerated)
- **OCR**: Tesseract + LLM vision for complex layouts
- **Transcription**: Whisper for audio

**Protocol:** HTTP API consumed by Percolate

**Deployment:**
- Local: Runs alongside Percolate on same machine
- Cloud: Shared service across multiple tenant nodes (GPU instances)

```mermaid
graph LR
    subgraph "Percolate Nodes"
        P1[Percolate A<br/>Tenant-specific]
        P2[Percolate B<br/>Tenant-specific]
        P3[Percolate C<br/>Tenant-specific]
    end

    subgraph "Shared Reader Service"
        Reader[Percolate-Reader<br/>Stateless, GPU]
    end

    P1 -->|Parse PDF| Reader
    P2 -->|Embed batch| Reader
    P3 -->|Transcribe audio| Reader

    style P1 fill:#f0e1ff
    style P2 fill:#f0e1ff
    style P3 fill:#f0e1ff
    style Reader fill:#ffe1e1
```

**Why separate?**
- Cost-effective: Don't need GPU per tenant
- Scales independently: Add reader capacity based on demand
- Stateless: Easy horizontal scaling
- Optional: Percolate works without it (local models only)

### Complete System Flow

```mermaid
graph TB
    User[User/Client]

    subgraph "Percolate (REM Node)"
        API[FastAPI Server<br/>Chat/Upload/Auth/MCP]
        AgentRuntime[Agent-let Runtime<br/>Pydantic AI]
        SearchLayer[Search Interface<br/>ask/lookup/traverse]
    end

    subgraph "Percolate-Rocks (Foundation)"
        RemDB[(REM Database<br/>RocksDB)]
        HNSW[Vector Index]
        GraphEngine[Graph Engine]
    end

    subgraph "Percolate-Reader (Optional)"
        Parser[Document Parser]
        Embedder[Heavy Embeddings]
        OCR[OCR/Transcription]
    end

    subgraph "External Services"
        LLM[LLM API<br/>OpenAI/Anthropic]
        OTEL[OpenTelemetry<br/>Phoenix]
    end

    User -->|HTTP/SSE| API
    API --> AgentRuntime
    API --> SearchLayer
    AgentRuntime --> RemDB
    SearchLayer --> HNSW
    SearchLayer --> GraphEngine

    API -->|Parse request| Parser
    Parser --> Embedder
    Parser --> OCR
    Parser -->|Structured content| RemDB

    AgentRuntime -.->|LLM calls| LLM
    AgentRuntime -.->|Traces| OTEL
    SearchLayer --> RemDB

    style RemDB fill:#e1f5ff
    style AgentRuntime fill:#fff4e1
    style API fill:#f0e1ff
    style Parser fill:#ffe1e1
```

## Core Components

### 1. REM Memory System (Percolate-Rocks)

**Resources-Entities-Moments** is the foundation database layer providing:

**Three conceptual abstractions** (all stored as entities in RocksDB):

| Abstraction | What It Stores | Query Type | Use Case |
|------------|----------------|------------|----------|
| **Resources** | Chunked documents with embeddings | Semantic search (HNSW) | Documents, files, uploaded content |
| **Entities** | Structured data with properties | SQL queries, key lookups | People, concepts, domain knowledge |
| **Moments** | Temporal classifications | Time-range queries | Events, conversations, workflow history |

```mermaid
graph LR
    subgraph "REM Database (Percolate-Rocks)"
        R[Resources<br/>Chunked + Embedded]
        E[Entities<br/>Graph + Fuzzy Search]
        M[Moments<br/>Temporal Index]
    end

    R -->|references| E
    M -->|classifies| R
    M -->|contextualizes| E
    E -->|edges| E

    style R fill:#b3e5fc
    style E fill:#c8e6c9
    style M fill:#fff9c4
```

**Implementation features:**
- **Pydantic-first**: Schemas defined via Pydantic models with `json_schema_extra`
- **Deterministic UUIDs**: Idempotent inserts via content-based keys (blake3)
- **Auto-embeddings**: Configured fields embedded automatically on insert
- **Graph edges**: Bidirectional column families for O(1) traversal
- **Hybrid search**: Semantic (HNSW) + SQL predicates + graph navigation
- **Encryption at rest**: ChaCha20-Poly1305 with Ed25519 keys
- **Peer replication**: Primary/replica via WAL and gRPC

**Published separately** as `percolate-rocks` for standalone use.

### 2. Agent-let Framework (Percolate)

**Agent-lets are JSON Schema-defined AI skills** stored as entities in REM:

```mermaid
graph TD
    Schema[Agent-let Schema<br/>JSON Schema + Tools]
    Registry[REM Database<br/>Stored as entities]
    Factory[Agent Factory<br/>Pydantic AI internally]
    Runtime[Runtime Execution<br/>LLM + MCP Tools]
    Eval[Evaluation<br/>Metrics + Feedback]

    Schema --> Registry
    Registry --> Factory
    Factory --> Runtime
    Runtime --> Eval
    Eval -.->|Iterate| Schema

    style Schema fill:#e1bee7
    style Registry fill:#e1f5ff
    style Runtime fill:#90caf9
    style Eval fill:#ffcc80
```

**Key characteristics:**
- **Pure JSON Schema**: System prompts, tools, outputs defined in JSON (not code)
- **Stored in REM**: Agent-lets are entities with embeddings for similarity search
- **MCP tool integration**: Reference external tools via MCP server names
- **Pydantic AI runtime**: Factory uses Pydantic AI internally for execution
- **Versioned**: Semantic versioning for schema evolution
- **Observable**: OpenTelemetry traces exported (excludes eval/LLM internals)
- **Evaluable**: Built-in evaluation framework with cost/quality metrics

**Agent-let schema pattern:**
```python
class MyAgent(BaseModel):
    """Agent description becomes system prompt."""
    input_field: str
    output_field: dict

    model_config = ConfigDict(
        json_schema_extra={
            "description": "You are an expert...",  # System prompt
            "tools": [{"mcp_server": "carrier", "tool_name": "search"}],
            "resources": [{"uri": "cda://field-definitions"}],
            "embedding_fields": ["description"]  # For agent similarity search
        }
    )
```

### 3. Document Processing (Percolate-Reader)

**Percolate-Reader** handles heavy multimedia processing via HTTP API:

| Format | Capability | Output |
|--------|-----------|--------|
| **PDF** | Semantic + OCR + visual verification | Markdown + tables + images |
| **Excel** | Multi-sheet analysis + structure detection | Structured data + metadata |
| **Audio** | Speech-to-text + speaker diarization | Transcripts + timestamps |
| **Office** | Document extraction | Clean markdown |

**Processing strategy:**
1. Fast semantic extraction (primary path)
2. Quality flags for uncertain content
3. On-demand visual verification (LLM vision models)
4. Structured artifacts (tables, images, metadata)
5. Return structured content to Percolate for REM storage

**Protocol:** Percolate calls reader via HTTP (`/parse/pdf`, `/embed/batch`, `/ocr/extract`)

### 4. Privacy-First Authentication

```mermaid
sequenceDiagram
    participant Mobile
    participant Node
    participant Cloud

    Mobile->>Mobile: Generate Ed25519 keypair
    Mobile->>Node: Register device + public key
    Node->>Mobile: Email verification
    Mobile->>Node: Sign verification
    Node->>Mobile: Issue OAuth tokens

    Desktop->>Node: Request device code (QR)
    Mobile->>Node: Scan QR + approve
    Node->>Desktop: Issue tokens

    Note over Mobile,Cloud: All keys stored on device
    Note over Node: Per-tenant encryption
```

**Security Features:**
- **Mobile as keychain**: Private keys never leave device
- **OAuth 2.1 compliance**: PKCE mandatory, no implicit flow
- **Ed25519 signatures**: Device authentication
- **Per-tenant encryption**: RocksDB encrypted at rest
- **S3 credential derivation**: HKDF-based scoped credentials

## Supported Protocols

Percolate implements several standard and custom protocols for interoperability:

### Model Context Protocol (MCP)

**Full MCP server implementation** for tool integration and resource access:

**Built-in MCP Tools:**
- `search_knowledge_base`: Unified REM search (semantic + SQL + graph)
- `lookup_entity`: Entity graph navigation with fuzzy matching
- `parse_document`: Document processing (delegates to percolate-reading)
- `create_agent`: Dynamic agent-let instantiation
- `ask_agent`: Execute agent with prompt
- `add_case_comment`: Add comment to case/project
- `submit_feedback`: Evaluation feedback (Phoenix integration)
- `list_moments`: Query temporal classifications
- `read_resource`: Access MCP resources

**Built-in MCP Resources:**
- `sessions://list`: List all sessions
- `moments://list`: List moments (temporal classifications)
- `messages://{session_id}`: Messages for session
- Custom resources can be registered dynamically

See [MCP Documentation](https://modelcontextprotocol.io) for protocol details.

### OpenAI Chat Completions API

**OpenAI-compatible streaming chat** with custom content headers:

**Standard OpenAI Headers:**
- `Authorization: Bearer <token>` - Authentication (required)
- `Content-Type: application/json` - Request format
- `Accept: text/event-stream` - Streaming responses (SSE)

**Custom Content Headers** (see [docs/protocols/content-headers.md](docs/protocols/content-headers.md) for full reference):

| Header | Description | Example |
|--------|-------------|---------|
| `X-User-Source-ID` | User identifier | `user-550e8400-e29b-41d4-a716-446655440000` |
| `X-Device-ID` | Device identifier | `device-abc123def456` |
| `X-Tenant-ID` | Tenant scope | `tenant_12345678` |
| `X-Session-ID` | Session identifier | `session_abc123def456` |
| `X-Chat-Is-Audio` | Audio input flag | `true`, `false` |
| `X-Content-Source-Provider` | Source service | `GOOGLE_DRIVE`, `ICLOUD`, `DROPBOX` |
| `X-Processing-Priority` | Processing priority | `high`, `medium`, `low` |

Example request:
```http
POST /v1/chat/completions
Content-Type: application/json
Authorization: Bearer p8fs_at_eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9...
X-Tenant-ID: tenant_12345678
X-Session-ID: session_abc123def456

{
  "model": "gpt-4",
  "messages": [{"role": "user", "content": "Hello"}],
  "stream": true
}
```

See [p8fs-api content headers](https://github.com/p8fs-modules/p8fs-api/blob/main/docs/content_headers.md) for complete header reference.

### OAuth 2.1 & OIDC

**Modern OAuth 2.1 compliance** with mobile-first device flow:

**Endpoints:**
- `/.well-known/openid-configuration` - OIDC discovery
- `/oauth/authorize` - Authorization endpoint
- `/oauth/token` - Token endpoint
- `/oauth/device/code` - Device authorization (QR code flow)
- `/oauth/device/token` - Device token exchange

**Features:**
- PKCE mandatory for all flows
- No implicit grant (OAuth 2.1)
- Ed25519 device signatures
- Mobile as keychain (private keys never leave device)

See [OAuth 2.1 specification](https://oauth.net/2.1/) for protocol details.

### S3 Protocol

**S3-compatible object storage** for tenant data and backups:

**Tenant isolation:**
- S3 home: `s3://<bucket>/tenants/<tenant_id>/`
- Context blob: `s3://<bucket>/tenants/<tenant_id>/context.yaml`
- Backups: `s3://<bucket>/tenants/<tenant_id>/backups/`
- Archives: `s3://<bucket>/tenants/<tenant_id>/archives/`

**Credential derivation:**
- HKDF-based scoped credentials per tenant
- Ed25519 key derivation from mobile device
- Time-limited STS tokens for S3 access

### gRPC Protocol

**Peer replication and cluster coordination:**

**Services:**
- WAL replication (primary/replica)
- Cluster node discovery
- Tenant context synchronization
- Health checks and heartbeats

**Tenant deletion protocol:**
1. Remove from tenant context (`/tenants/<tenant_id>/context.yaml`)
2. Delete RocksDB from each REM node
3. Remove S3 tenant folder (backups, archives)
4. Audit log entry for compliance

### Parse Job Protocol

**Document processing workflow** between Percolate and Percolate-Reader:

**Pydantic model:**
```python
from percolate.schemas import ParseJob

job = ParseJob(
    job_id="parse-job-xyz789",
    tenant_id="tenant_12345678",
    file_name="contract.pdf",
    file_type="application/pdf",
    status="completed",  # pending | processing | completed | failed
    result=ParseJobResult(
        content="Extracted text...",
        tables=[...],
        metadata={...}
    )
)
```

**Flow:**
1. Percolate receives document upload (`/v1/ingest/upload`)
2. Percolate creates `ParseJob` and submits to Reader
3. Reader processes document and returns `ParseJobResult`
4. Percolate stores content in REM database
5. Gateway tracks parse job in tenant context

See [docs/protocols/README.md](docs/protocols/README.md#parse-job-protocol) for full model definition.

### JSON Schema Standard

**All schemas use JSON Schema** with Pydantic extensions:

**Pydantic definition with inline comments:**
```python
from percolate.schemas import (
    PercolateSchemaExtensions,
    MCPTool,
    MCPResource,
)

class ResearchAgent(BaseModel):
    """Agent for research and analysis tasks."""
    agent_id: str
    description: str
    system_prompt: str

    model_config = ConfigDict(
        json_schema_extra=PercolateSchemaExtensions(
            # Fully qualified name - must be unique across all schemas
            name="percolate.agents.ResearchAgent",

            # Short name for CLI/API (rem insert research-agent)
            short_name="research-agent",

            # MCP tools this agent can call
            tools=[
                MCPTool(mcp_server="percolate", tool_name="search_knowledge_base"),
                MCPTool(mcp_server="percolate", tool_name="lookup_entity"),
            ],

            # MCP resources this agent can access (read-only)
            resources=[
                MCPResource(mcp_server="percolate", resource_uri="sessions://list"),
                MCPResource(mcp_server="percolate", resource_uri="moments://list"),
            ],

            # Auto-embed description for agent similarity search
            embedding_fields=["description"],

            # Primary key field for lookups
            key_field="agent_id",
        ).model_dump()
    )
```

**Extension fields:**
- `name`: Fully qualified unique name (e.g., `"percolate.agents.ResearchAgent"`)
- `short_name`: CLI/API identifier (e.g., `"research-agent"`)
- `tools`: MCP tool references (callable functions)
- `resources`: MCP resource references (read-only data)
- `embedding_fields`: Auto-embed on insert
- `indexed_columns`: SQL predicate columns
- `key_field`: Primary identifier
- `default_embedding_provider`: Provider override

See [docs/protocols/json-schema-extensions.md](docs/protocols/json-schema-extensions.md) for full documentation.

### Tenant Context Protocol

**Gateway-stored context** for fast tenant operations:

**Stored at:** `s3://<bucket>/tenants/<tenant_id>/context.yaml`

**Contains:**
- Peer list: Distributed REM node addresses
- Recent conversations: Last N session IDs
- Recent parse jobs: Parse job IDs and status
- Tenant details: Tier, account status (slim, no PII)
- Resource quotas: Storage, API limits

**Example:**
```yaml
tenant_id: tenant_12345678
tier: premium  # premium, standard, free
account_status: active
peer_nodes:
  - node-1.percolationlabs.ai:9000
  - node-2.percolationlabs.ai:9000
recent_sessions:
  - session_abc123
  - session_def456
recent_parse_jobs:
  - parse-job-xyz789: completed
quotas:
  storage_gb: 100
  api_calls_per_day: 10000
```

**Tenant deletion:** Remove context entry + delete REM data from each node + remove S3 tenant folder.

## API Endpoints

### Percolate API (REM Node)

| Endpoint | Purpose | Protocol |
|----------|---------|----------|
| `/v1/chat/completions` | OpenAI-compatible chat | HTTP/SSE streaming |
| `/v1/ingest/upload` | Document upload | HTTP multipart |
| `/mcp` | Model Context Protocol | SSE |
| `/oauth/*` | OAuth 2.1 flows | HTTP |
| `/.well-known/openid-configuration` | OIDC discovery | HTTP |

**MCP Tools (Built-in Server):**
- `search_knowledge_base`: Unified search (semantic + SQL + graph)
- `lookup_entity`: Entity graph navigation with fuzzy matching
- `parse_document`: Document processing (delegates to reader)
- `create_agent`: Dynamic agent-let instantiation
- `ask_agent`: Execute agent with prompt
- `add_case_comment`: Add comment to case/project
- `submit_feedback`: Evaluation feedback (Phoenix integration)
- `list_moments`: Query temporal classifications
- `read_resource`: Access MCP resources (field definitions, carriers, etc.)

**MCP Resources (Built-in):**
- `sessions://list`: List all sessions
- `moments://list`: List moments (temporal classifications)
- `messages://{session_id}`: Messages for session
- Custom resources can be registered dynamically

### Percolate-Reader API (Processing Node)

| Endpoint | Purpose | Protocol |
|----------|---------|----------|
| `/parse/pdf` | PDF parsing | HTTP multipart |
| `/parse/excel` | Excel parsing | HTTP multipart |
| `/parse/audio` | Audio transcription | HTTP multipart |
| `/embed/batch` | Batch embedding generation | HTTP JSON |
| `/ocr/extract` | OCR from images | HTTP multipart |
| `/health` | Health check | HTTP |
| `/metrics` | Prometheus metrics | HTTP |

## Deployment Models

### Local (Desktop/Mobile)

```
percolate run --local
```

- Embedded RocksDB database
- Local file storage
- Optional cloud LLM API calls
- Full offline operation (with local models)

### Cloud (Multi-tenant)

```
tenant.percolationlabs.ai
```

- Isolated RocksDB per tenant
- Encrypted S3 storage
- Gateway routing to tenant nodes
- Shared embedding/LLM services
- Cold archival for old data

### Hybrid

- Primary node on device
- Cloud sync for backup
- Shared agent-lets across devices
- Gateway for mobile app API

## Technology Stack

### Percolate-Rocks (Foundation)
| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Core** | Rust (PyO3) | Memory engine, embeddings, crypto |
| **Database** | RocksDB | Embedded KV store with column families |
| **Vectors** | HNSW (Rust) | Semantic search index |
| **Graph** | Bidirectional CFs | Fast edge traversal |
| **Crypto** | ChaCha20-Poly1305, Ed25519 | Encryption at rest, signatures |
| **Replication** | gRPC + WAL | Primary/replica sync |

### Percolate (REM Node)
| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Runtime** | Python (uv) | API server, orchestration |
| **API** | FastAPI | HTTP/SSE server |
| **Auth** | OAuth 2.1 + JWT + OIDC | Authentication |
| **Agents** | Pydantic AI | Agent factory (internal) |
| **MCP** | FastMCP | Tool protocol server |
| **Observability** | OpenTelemetry + Phoenix | Tracing (excludes eval/LLM) |
| **Memory** | percolate-rocks | REM database (PyO3 bindings) |

### Percolate-Reader (Processing Node)
| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Runtime** | Python (uv) | Processing API server |
| **API** | FastAPI | HTTP server |
| **PDF Parsing** | PyMuPDF, pdfplumber | Document extraction |
| **Embeddings** | fastembed, sentence-transformers | Vector generation |
| **OCR** | Tesseract, LLM vision | Text extraction from images |
| **Transcription** | Whisper | Audio to text |
| **Observability** | OpenTelemetry | Tracing |

## Project Structure

```
percolation/
├── .spikes/                # Experimental implementations
│   ├── percolate-rocks/    # REM Database (Rust + PyO3)
│   │   ├── src/            # Rust implementation
│   │   │   ├── storage/        # RocksDB wrapper
│   │   │   ├── index/          # HNSW vector index
│   │   │   ├── query/          # SQL execution
│   │   │   ├── graph/          # Graph traversal
│   │   │   ├── embeddings/     # Embedding providers
│   │   │   ├── replication/    # WAL + gRPC
│   │   │   └── bindings/       # PyO3 Python bindings
│   │   ├── python/rem_db/  # Python CLI wrapper
│   │   ├── schema/         # Built-in schemas (core, templates)
│   │   ├── Cargo.toml
│   │   └── pyproject.toml
│   │
│   └── rem-db/             # Python spike (reference)
│
├── percolate/              # REM Node (Python package) - PLANNED
│   ├── src/percolate/
│   │   ├── api/            # FastAPI server
│   │   │   ├── main.py         # Application entry
│   │   │   └── routers/
│   │   │       ├── chat.py     # /v1/chat/completions
│   │   │       ├── ingest.py   # /v1/ingest/upload
│   │   │       ├── oauth.py    # /oauth/*
│   │   │       └── mcp.py      # /mcp
│   │   ├── agents/         # Agent-let runtime
│   │   │   ├── factory.py      # Pydantic AI factory
│   │   │   ├── registry.py     # Agent discovery (from REM)
│   │   │   └── executor.py     # Execution with MCP tools
│   │   ├── memory/         # REM interface (wraps percolate-rocks)
│   │   │   ├── search.py       # Unified search (ask)
│   │   │   ├── entities.py     # Entity operations (lookup)
│   │   │   ├── moments.py      # Moment queries (list)
│   │   │   └── sessions.py     # Session/message history
│   │   ├── auth/           # OAuth 2.1 + OIDC
│   │   ├── mcp/            # MCP server implementation
│   │   │   ├── server.py       # FastMCP setup
│   │   │   └── tools/          # MCP tool implementations
│   │   ├── cli/            # CLI (percolate serve, etc.)
│   │   └── settings.py     # Pydantic Settings
│   └── pyproject.toml
│
├── percolate-reading/      # Reader Node (Python package) - PLANNED
│   ├── src/percolate_reading/
│   │   ├── api/            # FastAPI server
│   │   │   └── routers/
│   │   │       ├── parse.py    # /parse/{pdf,excel,audio}
│   │   │       ├── embed.py    # /embed/batch
│   │   │       └── ocr.py      # /ocr/extract
│   │   ├── parsers/        # Document parsing
│   │   ├── embeddings/     # Heavy models
│   │   ├── ocr/            # OCR services
│   │   ├── transcription/  # Whisper
│   │   ├── cli/            # CLI (percolate-reading serve)
│   │   └── settings.py     # Pydantic Settings
│   └── pyproject.toml
│
├── docs/                   # Architecture documentation
├── CLAUDE.md               # Coding standards (project-level)
└── README.md               # This file
```

### Package Responsibilities

**1. percolate-rocks** (Foundation - Rust + PyO3)

- **Status**: Published on PyPI, production-ready
- REM database implementation (RocksDB)
- HNSW vector search (200x faster than Python)
- SQL query execution with predicates
- Graph operations (bidirectional edges)
- Encryption at rest (ChaCha20-Poly1305)
- Peer replication (WAL + gRPC)
- **CLI**: `rem` command for database operations
- **Published as**: `percolate-rocks` package

**2. percolate** (REM Node - Python)

- **Status**: Planned, not yet implemented
- FastAPI server (chat, upload, auth, MCP)
- Agent-let runtime (Pydantic AI + JSON Schema)
- Memory interface (wraps percolate-rocks)
- Search interface (ask/lookup/traverse)
- Session and message tracking
- Moment listing (REM Dreaming integration)
- MCP server with built-in tools
- OAuth 2.1 authentication
- **Uses**: percolate-rocks for all memory operations
- **Optional**: Can use percolate-reading for processing

**3. percolate-reading** (Reader Node - Python)

- **Status**: Planned, not yet implemented
- FastAPI server for processing endpoints
- Document parsing (PDF, Excel, audio)
- Heavy embedding models (GPU-accelerated)
- OCR (Tesseract + LLM vision)
- Audio transcription (Whisper)
- Stateless design for horizontal scaling
- **Uses**: percolate-rocks for fast parsing (future optimization)
- **Called by**: percolate via HTTP API

## Design Principles

### From Carrier Project

- **Conciseness**: Minimal, precise code
- **No hacks**: Fail fast, explicit errors
- **Separation of concerns**: Single responsibility per module
- **Modularity**: Functions 5-15 lines, modules <200 lines
- **Type safety**: Full type hints everywhere
- **Observable**: OpenTelemetry instrumentation built-in

### From P8FS Research

- **No agents, only state**: Agents are data, not objects
- **Context engineering**: Sophisticated retrieval per LLM call
- **Hybrid storage**: Graph + relational + vector
- **Mobile-first security**: Device as root of trust
- **Tenant isolation**: Complete data separation

## Challenges & Solutions

| Challenge | Solution |
|-----------|----------|
| **Multi-tenant isolation** | Encrypted RocksDB per tenant, gateway routing |
| **Years of metadata** | Efficient embedded DB with cold archival |
| **Document parsing** | Rust-based fast path with Python orchestration |
| **Agent training** | Evaluation framework with Phoenix observability |
| **Mobile encryption** | Ed25519 keys in secure enclave, OAuth device flow |
| **Run anywhere** | Embedded DB, optional cloud services |

## Comparison to Related Projects

| Feature | Percolate | Carrier | P8FS-Modules |
|---------|-----------|---------|--------------|
| **Purpose** | Personal AI node | Domain agents | Research platform |
| **Memory** | REM (bio-inspired) | Session-based | Cortex-mode (aspirational) |
| **Agents** | Trainable agent-lets | JSON schema agents | Stateless LLM + state |
| **Deployment** | Anywhere | Cloud API | Cloud multi-tenant |
| **Auth** | Mobile-first OAuth 2.1 | OIDC optional | Mobile + cryptographic |
| **Target** | Individuals | Enterprises | Research |

## Documentation

### Percolate-Rocks (Available Now)

- [REM Database README](.spikes/percolate-rocks/README.md) - Complete REM database documentation
- [Implementation Guide](.spikes/percolate-rocks/CLAUDE.md) - Coding standards and patterns
- [Replication](.spikes/percolate-rocks/docs/replication.md) - Primary/replica setup
- [REM Dreaming](.spikes/percolate-rocks/docs/rem-dreaming.md) - Background intelligence
- [Encryption](.spikes/percolate-rocks/docs/encryption-architecture.md) - Encryption at rest
- [SQL Dialect](.spikes/percolate-rocks/docs/sql-dialect.md) - Query language reference
- [Schema Design](.spikes/percolate-rocks/docs/schema.md) - Pydantic schema patterns

### Percolate (Planned)

- System overview (planned)
- Agent-let patterns (planned)
- MCP protocol implementation (planned)
- OAuth 2.1 flows (planned)

### Development

- [Coding Standards](CLAUDE.md) - Project-level coding standards

## Status

**Current State:**

- ✅ **Percolate-Rocks (v0.1.0)**: Published on PyPI, production-ready
  - Full REM database implementation
  - HNSW vector search
  - SQL query engine
  - Graph operations
  - Encryption at rest
  - Peer replication
  - REM Dreaming
  - CLI (`rem` command)

- 🔨 **Percolate**: Planned (API server layer)
  - FastAPI server for chat, upload, auth
  - Agent-let runtime (Pydantic AI)
  - MCP server with built-in tools
  - OAuth 2.1 authentication
  - Session/message tracking

- 🔨 **Percolate-Reader**: Planned (processing service)
  - Document parsing (PDF, Excel, audio)
  - Heavy embeddings (GPU)
  - OCR and transcription

## Cloud Deployment

Percolate supports **tiered multi-tenant deployment** with independent horizontal scaling:

**Tenant Tiers:**

- **Tier A (Premium)**: Keep-warm, 6 tenants/pod, 99.9% SLA
- **Tier B (Standard)**: 5min idle, 12 tenants/pod, 99% SLA
- **Tier C (Free)**: 1min idle, 20 tenants/pod, best effort

**Architecture:**

```text
Gateway → Tier A Deployment (2-50 pods)
       → Tier B Deployment (1-100 pods)
       → Tier C Deployment (1-200 pods)
```

**Key Features:**

- Independent HPA per tier
- Context blob caching for instant cold-start response
- Tier-aware routing with consistent hashing
- Cost optimization: 74% margin at 1,000+ tenants

See cloud deployment docs for complete specification.

## References

- **Pydantic AI**: https://ai.pydantic.dev - Agent framework
- **FastMCP**: https://github.com/jlowin/fastmcp - MCP implementation
- **OAuth 2.1**: https://oauth.net/2.1/ - Modern OAuth standard
- **RocksDB**: https://rocksdb.org - Embedded database
- **PyO3**: https://pyo3.rs - Python/Rust bindings
