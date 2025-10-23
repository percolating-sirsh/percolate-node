# Architecture Overview

## Vision

Percolate is a **personal AI node** that runs anywhere - desktop, mobile, or cloud - providing individuals with:
- Complete ownership of their AI memory and data
- Trainable agent-lets (AI skills) defined as portable JSON schemas
- Privacy-first design with mobile key management and tenant isolation
- OpenAI-compatible API and Model Context Protocol (MCP) support

## Design Philosophy

### Run Anywhere
- **Embedded**: RocksDB for local storage, no external dependencies
- **Lightweight**: Rust core for performance, small memory footprint
- **Offline-capable**: Core functionality works without internet
- **Cloud-optional**: Can sync to cloud for backup and multi-device access

### Privacy First
- **Mobile as keychain**: Private keys never leave device
- **Per-tenant encryption**: Separate encrypted database per user
- **OAuth 2.1**: Modern authentication with PKCE
- **No cross-tenant access**: Complete data isolation

### Data as Infrastructure
- **Agent-lets are data**: JSON schemas, not code
- **Memory as foundation**: REM (Resources-Entities-Moments) system
- **Portable intelligence**: Share and evolve agent-lets across instances

## High-Level Architecture

### Two-Node Architecture

Percolate uses a **specialized node separation** for optimal resource usage:

**Percolate (REM Node)**: Lightweight, runs everywhere
**Percolate-Reading (Reader Node)**: Heavy processing, scales independently

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Layer                             │
│  (Desktop CLI, Mobile App, Web Interface, MCP Clients)          │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ HTTP/WebSocket/MCP
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                Percolate Node (REM) - Python                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ FastAPI      │  │ OAuth 2.1    │  │ MCP Server   │         │
│  │ Chat API     │  │ Auth         │  │ Tools        │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│  ┌──────────────┐  ┌──────────────────────────────────┐       │
│  │ Agent-let    │  │ Reading Client                   │       │
│  │ Runtime      │  │ (HTTP client to reading node)    │       │
│  └──────────────┘  └──────────────────────────────────┘       │
└────────────────────────┬────────────────────────────────────────┘
                         │ PyO3 Bindings
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│             Percolate-Core (Rust) - Lightweight                  │
│  ┌──────────────┐  ┌──────────────────────────────┐            │
│  │ REM Memory   │  │ Lightweight Embeddings       │            │
│  │ Engine       │  │ (Small HNSW, fast inference) │            │
│  └──────────────┘  └──────────────────────────────┘            │
│  ┌──────────────┐                                               │
│  │ Crypto       │                                               │
│  │ Primitives   │                                               │
│  └──────────────┘                                               │
└────────────────────────┬────────────────────────────────────────┘
                         │ RocksDB API
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Storage Layer                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ RocksDB      │  │ File Storage │  │ S3 (optional)│         │
│  │ (Encrypted)  │  │ (Local/S3)   │  │ Cold Archive │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘

                         │ HTTP API
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│          Percolate-Reading Node (Heavy Processing)               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ Document     │  │ Heavy        │  │ OCR Services │         │
│  │ Parsers      │  │ Embeddings   │  │ Tesseract    │         │
│  │ (PDF/Excel)  │  │ (Large)      │  │ Vision LLM   │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│  ┌──────────────┐  ┌──────────────┐                            │
│  │ Transcription│  │ Processing   │                            │
│  │ (Whisper)    │  │ API          │                            │
│  └──────────────┘  └──────────────┘                            │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### Percolate Node (REM)

#### 1. REM Memory System (Rust Core)

**Resources-Entities-Moments** - A bio-inspired memory architecture with **pluggable storage providers**:

**Storage Providers:**
- **RocksDB** (default): Embedded, per-tenant isolation, high performance
- **PostgreSQL** (enterprise): Shared database, multi-tenant with schemas, advanced SQL

**REM Components:**

- **Resources**: Chunked, embedded documents
  - Semantic search via lightweight vector embeddings (Rust)
  - Efficient storage with deduplication
  - Metadata: source, timestamp, tenant, hash

- **Entities**: Domain knowledge graph
  - Key-value properties
  - Graph edges (relationships)
  - Fuzzy search on names/aliases
  - Entity types: person, concept, agent-let, etc.

- **Moments**: Temporal classifications
  - Time-indexed events
  - References to resources and entities
  - Enable chronological memory retrieval

**Provider Interface:**
All REM operations go through a `StorageProvider` trait, making the database backend transparent to higher-level code. Choose backend via configuration.

#### 2. Agent-let Runtime (Python)

Trainable AI skills defined as JSON schemas:

- **Schema-driven**: System prompts, outputs, tools in JSON
- **Factory pattern**: Pydantic AI creates agents from schemas
- **MCP tools**: Agents call tools via Model Context Protocol
- **Observable**: OpenTelemetry instrumentation built-in
- **Evaluable**: Feedback loops for continuous improvement

#### 3. Authentication System (Python + Rust Crypto)

Mobile-first OAuth 2.1 with cryptographic key management:

- **Device registration**: Ed25519 keypair on mobile
- **OAuth flows**: Device code flow for desktop pairing
- **Token management**: JWT access tokens (ES256), opaque refresh tokens
- **Encryption**: Per-tenant database encryption (ChaCha20-Poly1305)
- **S3 credentials**: HKDF-based credential derivation

#### 4. API Layer (Python)

Standard interfaces for interoperability:

- **OpenAI-compatible chat**: `/v1/chat/completions` with streaming
- **Document ingestion**: `/v1/ingest/upload` (delegates to reading node)
- **MCP server**: `/mcp` with SSE transport
- **OAuth endpoints**: `/oauth/*` for device and refresh flows
- **Health checks**: `/health`, `/version`

#### 5. Reading Client (Python)

HTTP client to communicate with percolate-reading node:

- **Document parsing**: POST `/parse/pdf`, `/parse/excel`, `/parse/audio`
- **Heavy embeddings**: POST `/embed/batch` for large models
- **OCR**: POST `/ocr/extract` for visual text extraction
- **Transcription**: POST `/transcribe` for audio to text

### Percolate-Reading Node

#### 1. Document Processing Pipeline (Python + Rust)

Fast document parsing with structured extraction:

- **PDF**: Semantic extraction, table detection, OCR fallback
- **Excel**: Multi-sheet analysis, structure detection
- **Audio**: Speech-to-text with speaker diarization (Whisper)
- **Office**: DOCX/PPTX to markdown conversion

Strategy: Rust parsing for fast path, LLM-based verification for quality flags.

#### 2. Heavy Embedding Models (Python)

Large embedding models for semantic search:

- **Models**: `nomic-embed-text-v1.5`, `text-embedding-3-large`
- **Batch processing**: Efficient batch inference
- **GPU support**: CUDA for acceleration (optional)
- **Caching**: Embedding cache for repeated content

#### 3. OCR Services (Python)

Visual text extraction:

- **Tesseract**: Fast OCR for scanned documents
- **Vision LLM**: Claude/GPT-4V for complex layouts
- **Table extraction**: Specialized table detection
- **Quality assessment**: Confidence scoring

#### 4. Transcription Services (Python)

Audio to text conversion:

- **Whisper**: State-of-the-art speech recognition
- **Speaker diarization**: Identify different speakers
- **Timestamps**: Word-level timing information
- **Language detection**: Automatic language identification

#### 5. Processing API (FastAPI)

HTTP API for REM node to consume:

- **POST /parse/pdf**: Parse PDF document
- **POST /parse/excel**: Parse Excel workbook
- **POST /parse/audio**: Transcribe audio file
- **POST /embed/batch**: Generate embeddings for text batch
- **POST /ocr/extract**: Extract text from image
- **GET /health**: Health check

## Data Flow

### Ingestion Flow

```
User uploads file
  → API validates file
    → Parser extracts content (Rust)
      → Chunker splits into resources
        → Embedder generates vectors (Rust)
          → REM stores resources + embeddings (RocksDB)
            → Entity extractor identifies entities (LLM)
              → REM stores entities + edges (RocksDB)
```

### Query Flow

```
User asks question
  → API creates agent context
    → Agent-let factory loads schema
      → Agent executes with MCP tools
        → Tool calls REM search (hybrid)
          → REM returns ranked results
            → Agent synthesizes response
              → API streams to user
                → OTEL logs trace
```

### Authentication Flow

```
Mobile registers
  → Generate Ed25519 keypair (secure enclave)
    → Send public key to API
      → API sends verification email
        → Mobile signs verification
          → API creates tenant + issues tokens
            → Mobile stores tokens securely

Desktop requests device code
  → API returns code + QR
    → Mobile scans QR
      → Mobile approves on API
        → Desktop polls for tokens
          → API issues tokens to desktop
```

## Deployment Models

### Local (Embedded)

- Single-user, runs on user device
- RocksDB in user home directory
- Local file storage
- Optional cloud LLM APIs
- No authentication required (single user)

### Cloud (Multi-tenant)

- Kubernetes deployment
- Gateway routes to tenant-specific nodes
- Each tenant has isolated RocksDB instance
- S3 for file storage and cold archive
- Shared services: embeddings, LLMs
- Full OAuth 2.1 authentication

### Hybrid

- Primary node on device (local)
- Cloud backup node for sync
- Gateway for mobile app access
- Agent-lets shared across devices
- Conflict resolution via last-write-wins

## Security Architecture

### Threat Model

**Protected Assets:**
- User memory (REM data)
- Private keys (Ed25519)
- API credentials (JWT tokens)
- Agent-let definitions

**Threats:**
- Unauthorized access to user data
- Cross-tenant data leakage
- Key compromise
- Token theft
- Supply chain attacks

**Mitigations:**
- Per-tenant encryption at rest (RocksDB)
- Private keys in secure enclave (mobile)
- JWT tokens with short expiration
- Tenant ID validation on all operations
- Dependency scanning and pinning

### Encryption Layers

1. **Transport**: TLS 1.3 for all network communication
2. **Storage**: ChaCha20-Poly1305 for RocksDB encryption
3. **Tokens**: ES256 signatures for JWT (ECDSA P-256)
4. **Device**: Secure enclave for Ed25519 keys

### Tenant Isolation

- Separate RocksDB database per tenant
- Tenant ID extracted from JWT claims
- Validated on every operation
- No shared indexes or caches
- Gateway enforces routing to correct node

## Observability

### OpenTelemetry Integration

- **Traces**: Agent execution, tool calls, REM operations
- **Metrics**: Request counts, latencies, error rates
- **Logs**: Structured logs with trace context
- **Spans**: Annotated with tenant, agent, tool metadata

### Key Metrics

- Agent execution time
- REM search latency
- Embedding generation throughput
- Document parsing duration
- Token usage per agent
- Cache hit rates

### Evaluation Framework

- Phoenix Arize for trace analysis
- Custom evaluators for agent quality
- Cost vs. accuracy tracking
- Feedback collection from users

## Technology Choices

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Core** | Rust | Performance, memory safety, small footprint |
| **API** | Python + FastAPI | Rapid development, rich ecosystem |
| **Storage** | Pluggable providers | RocksDB (default), PostgreSQL (enterprise) |
| **Database** | RocksDB / PostgreSQL | Embedded / shared multi-tenant |
| **Vectors** | HNSW (Rust) / pgvector | Fast approximate nearest neighbor |
| **Auth** | OAuth 2.1 + JWT | Standard, mobile-friendly |
| **Agents** | Pydantic AI | Structured outputs, type safety |
| **MCP** | FastMCP | Standard protocol, growing ecosystem |
| **OTEL** | OpenTelemetry | Industry standard observability |

## Design Decisions

### Why Rust + Python?

- **Rust**: Performance-critical operations (memory, embeddings, parsing)
- **Python**: Orchestration, API, agent runtime (flexibility)
- **Boundary**: High-level APIs in Rust, not low-level primitives
- **Benefit**: Best of both worlds - performance and productivity

### Why Pluggable Storage Providers?

**Design:** Provider interface abstracts database backend

**RocksDB (Default):**
- Embedded (no separate database process)
- High performance (LSM tree)
- Proven at scale (used by Facebook, LinkedIn)
- Per-tenant isolation (separate DB files)
- Encryption support built-in
- Best for: Desktop, mobile, per-tenant cloud pods

**PostgreSQL (Enterprise):**
- Client-server architecture
- Multi-tenant via schemas + row-level security
- Advanced querying (SQL, joins, aggregations)
- Mature ecosystem (replication, backup, monitoring)
- pgvector for efficient vector operations
- Best for: Enterprise with centralized database infrastructure

**Benefits:**
- Flexibility: Choose backend based on deployment
- Testing: Easy to swap providers for tests
- Future-proofing: Add TiDB, FoundationDB, etc.
- Migration: Export/import between providers

### Why Mobile-First Auth?

- Mobile devices have secure enclaves
- Biometric authentication built-in
- Users always have phone with them
- Enables secure device pairing
- Better UX than username/password

### Why Agent-lets as JSON?

- Data-driven (not code)
- Versionable and shareable
- Evaluable against test suites
- Platform-independent
- Can be generated by LLMs

### Why OAuth 2.1?

- Industry standard
- Mobile-friendly (device code flow)
- PKCE prevents auth code interception
- Refresh token rotation improves security
- Well-understood security properties

## Future Considerations

### Phase 1 (Foundation)
- REM memory engine (Rust)
- Basic agent-let runtime (Python)
- OAuth 2.1 authentication
- Local deployment only

### Phase 2 (Orchestration)
- Document parsing pipeline
- MCP server implementation
- OpenAI-compatible API
- CLI for local management

### Phase 3 (Cloud)
- Multi-tenant gateway
- S3 storage backend
- Shared embedding services
- Mobile app integration

### Phase 4 (Intelligence)
- Evaluation framework
- Agent-let marketplace
- Automatic entity extraction
- Advanced hybrid search

## References

- RocksDB: https://rocksdb.org
- OAuth 2.1: https://oauth.net/2.1/
- Model Context Protocol: https://modelcontextprotocol.io
- Pydantic AI: https://ai.pydantic.dev
- OpenTelemetry: https://opentelemetry.io
