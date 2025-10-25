# Claude.md - Coding Standards for Percolate

## Project Philosophy

**Percolate is a privacy-first personal AI node that runs anywhere.**

This is **not** a cloud-only SaaS platform. Instead, it's infrastructure for:

1. **Personal memory systems** (REM: Resources-Entities-Moments)
2. **Trainable agent-lets** (JSON schema-defined AI skills)
3. **Privacy-preserving architecture** (mobile-first cryptography, tenant isolation)
4. **Run-anywhere deployment** (embedded, desktop, mobile, cloud)

The focus is on **individual empowerment** through personal AI infrastructure. Key tenets:
- **Data ownership**: Users control their data and where it lives
- **Privacy by design**: Encryption, tenant isolation, mobile key management
- **Portable intelligence**: Agent-lets as data artifacts that can be shared and evolved
- **Offline-capable**: Core functionality works without cloud dependencies
- **Rust core, Python orchestration**: Performance-critical paths in Rust, flexibility in Python

Think of Percolate as **personal AI infrastructure** rather than an AI assistant product. The value is in the platform for owning, training, and deploying your own AI systems.

## Core Principles

### Conciseness
- Write minimal, precise code
- No redundant logic or unnecessary abstractions
- Every line serves a clear purpose
- Prefer clarity over cleverness

### No Hacks or Fallbacks
- No workarounds or temporary solutions
- No fallback logic that masks problems
- Fail fast and explicitly when assumptions break
- Use proper error handling, not try-except-pass
- Explicit errors better than silent degradation

### Separation of Concerns
- Each module has a single, well-defined responsibility
- Business logic separate from infrastructure
- Agent definitions separate from execution
- Memory layer separate from API layer
- Rust core separate from Python orchestration

### Modularity
- Small, focused functions (typically 5-15 lines)
- Clear function signatures with type hints
- Pure functions where possible
- Modules under 200 lines
- One primary concern per file

## Project Structure

### Dual-Language Architecture

Percolate uses **Rust for performance-critical core** and **Python for orchestration**:

```
percolation/
├── percolate/              # Python package (uv project)
│   ├── src/percolate/
│   │   ├── api/            # FastAPI server
│   │   │   ├── main.py         # Application entry point
│   │   │   └── routers/        # API route handlers
│   │   │       ├── chat.py     # Chat completions (OpenAI-compatible)
│   │   │       ├── ingest.py   # Document upload
│   │   │       ├── oauth.py    # OAuth 2.1 endpoints
│   │   │       └── mcp.py      # MCP endpoints
│   │   ├── auth/           # Authentication & authorization
│   │   │   ├── middleware.py   # Auth middleware
│   │   │   ├── oauth.py        # OAuth 2.1 flows
│   │   │   ├── device.py       # Mobile device registration
│   │   │   ├── crypto.py       # Ed25519 signatures, PKCE
│   │   │   └── models.py       # Auth data models
│   │   ├── agents/         # Agent-let runtime
│   │   │   ├── factory.py      # Agent factory (Pydantic AI)
│   │   │   ├── context.py      # Execution context
│   │   │   └── registry.py     # Agent-let discovery
│   │   ├── memory/         # REM database interface (wraps Rust)
│   │   │   ├── resources.py    # Resource operations
│   │   │   ├── entities.py     # Entity graph operations
│   │   │   ├── moments.py      # Temporal classifications
│   │   │   └── search.py       # Unified search interface
│   │   ├── parsers/        # Document parsing (orchestration)
│   │   │   ├── pdf.py          # PDF parsing
│   │   │   ├── excel.py        # Excel parsing
│   │   │   ├── audio.py        # Audio transcription
│   │   │   └── models.py       # Parse job models
│   │   ├── mcp/            # Model Context Protocol
│   │   │   ├── server.py       # MCP server setup
│   │   │   └── tools/          # MCP tool implementations
│   │   │       ├── search.py   # Knowledge base search
│   │   │       ├── entity.py   # Entity lookups
│   │   │       ├── agent.py    # Agent management
│   │   │       └── parse.py    # Document parsing
│   │   ├── cli/            # Command-line interface
│   │   │   ├── main.py         # CLI entry point
│   │   │   └── commands/       # Command modules
│   │   ├── otel/           # OpenTelemetry instrumentation
│   │   ├── settings.py     # Pydantic settings
│   │   └── version.py      # Version management
│   ├── tests/
│   │   ├── fixtures/          # Shared test fixtures and data
│   │   ├── unit/              # Unit tests (no external services)
│   │   │   ├── agents/        # Agent factory and context tests
│   │   │   ├── mcp/           # MCP tool logic tests
│   │   │   ├── auth/          # Auth model and crypto tests
│   │   │   ├── test_imports.py
│   │   │   └── __init__.py
│   │   └── integration/       # Integration tests (real connections)
│   │       ├── agents/        # Full agent execution tests
│   │       ├── mcp/           # MCP server protocol tests
│   │       ├── auth/          # OAuth flow tests
│   │       └── __init__.py
│   └── pyproject.toml      # UV project configuration
├── percolate-rocks/        # REM database (Rust + PyO3)
│   ├── src/
│   │   ├── lib.rs          # Python bindings
│   │   ├── memory/         # REM engine implementation
│   │   │   ├── mod.rs          # Memory module interface
│   │   │   ├── resources.rs    # Resource storage & chunking
│   │   │   ├── entities.rs     # Entity graph (KV-based)
│   │   │   ├── moments.rs      # Temporal indexing
│   │   │   ├── rocksdb.rs      # RocksDB backend
│   │   │   └── search.rs       # Hybrid search implementation
│   │   ├── embeddings/     # Vector operations
│   │   │   ├── mod.rs          # Embedding module interface
│   │   │   ├── models.rs       # Embedding model inference
│   │   │   └── index.rs        # Vector index (HNSW)
│   │   ├── parsers/        # Fast document parsing
│   │   │   ├── mod.rs          # Parser module interface
│   │   │   ├── pdf.rs          # PDF extraction
│   │   │   └── excel.rs        # Excel parsing
│   │   └── crypto/         # Cryptographic primitives
│   │       ├── mod.rs          # Crypto module interface
│   │       ├── keys.rs         # Ed25519 key operations
│   │       ├── encryption.rs   # ChaCha20-Poly1305 AEAD
│   │       └── kdf.rs          # HKDF key derivation
│   ├── Cargo.toml          # Rust project manifest
│   ├── pyproject.toml      # Python package metadata
│   └── tests/              # Rust unit tests
├── schema/                 # Agent-let definitions (JSON schemas)
│   ├── agentlets/
│   └── evaluators/
├── percolate/docs/         # Implementation documentation
│   ├── 00-overview.md      # System architecture
│   ├── 01-testing.md       # Test organization
│   ├── 02-agentlets.md     # Agent-let patterns
│   ├── 03-auth.md          # Authentication
│   ├── 04-mcp.md           # MCP protocol
│   └── 05-evals.md         # Evaluation framework
├── docs/                   # Planning documentation
│   ├── 01-architecture.md
│   ├── 02-rem-memory.md
│   ├── 03-agentlets.md
│   ├── 04-sync-replication.md
│   ├── 05-sharing-collaboration.md
│   ├── 06-cloud-deployment.md
│   ├── 07-multi-tenant-allocation.md
│   ├── 08-mcp-protocol.md
│   ├── 09-cluster-nodes.md # Kubernetes deployment
│   └── components/
│       ├── memory-engine.md
│       ├── storage-provider.md
│       ├── parsing-pipeline.md
│       ├── query-layer.md
│       └── auth-flow.md
├── scripts/                # Build and release automation
│   ├── bump_version.py     # Version management
│   └── pr.py               # Release PR creation
└── .github/workflows/      # CI/CD workflows
    ├── build-all.yml       # Build orchestrator (DAG)
    ├── build-rocks.yml     # PyPI wheel builds
    ├── build-percolate.yml # Docker builds (main API)
    ├── build-reading.yml   # Docker builds (reading service)
    └── release-*.yml       # Production release workflows
```

### Design Rationale

**Python Layer (percolate/):**
- FastAPI for HTTP/WebSocket API
- Pydantic AI for agent orchestration
- Rich CLI for user interaction
- OpenTelemetry for observability
- Flexible integration with external services

**Rust Layer (percolate-core/):**
- RocksDB for embedded database
- HNSW for vector indexing
- Fast document parsing
- Cryptographic operations (Ed25519, ChaCha20-Poly1305)
- Zero-copy operations where possible

**Boundary:**
- Python calls Rust via PyO3 bindings
- Rust exposes high-level APIs (not low-level primitives)
- Rust handles performance-critical operations
- Python handles orchestration and external integrations

## Code Standards

### Type Hints (Python)
- All function signatures must have type hints
- Use Protocol for abstract interfaces
- Use TypedDict or Pydantic models for complex types
- Use `typing.Optional` explicitly (not bare `| None`)

### Type Safety (Rust)
- Leverage Rust's type system aggressively
- Use `Result<T, E>` for fallible operations
- Avoid `unwrap()` in library code (only in examples/tests)
- Use `thiserror` for custom error types
- Document panic conditions in docstrings

### Function Design
- Single responsibility per function
- Maximum 3-4 parameters (use structs/models for more)
- Avoid side effects where possible
- Name functions by what they do, not how
- Python: 5-15 lines typical
- Rust: 10-30 lines typical (more complex operations)

### Error Handling

**Python:**
- Use explicit error types (custom exceptions)
- Raise errors, don't return None or empty values
- No silent failures
- Log errors with loguru
- Catch specific exceptions, not bare `except:`

**Rust:**
- Use `Result<T, E>` for recoverable errors
- Use `panic!` only for unrecoverable programmer errors
- Define custom error types with `thiserror`
- Propagate errors with `?` operator
- Document error conditions in function docstrings

### Memory Safety & Performance (Rust)
- Prefer zero-copy operations (slices over owned data)
- Use `&str` over `String` in function signatures where possible
- Use `Cow<'_, str>` for conditional ownership
- Profile before optimizing (use `criterion` for benchmarks)
- Document performance characteristics in docstrings

### Testing

**Important: All tests must be in the `tests/` directory with proper organization.**

**Python Tests (pytest):**
```
percolate/tests/
├── fixtures/             # Shared test fixtures and data
│   ├── agentlets/        # Sample agent schemas
│   └── documents/        # Test documents
├── unit/                 # Unit tests - no external services
│   ├── agents/           # Agent factory, context tests
│   ├── mcp/              # MCP tool logic tests
│   │   └── test_tools.py
│   ├── auth/             # Auth model and crypto tests
│   ├── test_imports.py   # Dependency verification
│   └── __init__.py
└── integration/          # Integration tests - real connections
    ├── agents/           # Full agent execution tests
    │   └── test_agent_eval.py
    ├── mcp/              # MCP server protocol tests
    │   └── test_mcp_server.py
    ├── auth/             # OAuth flow tests
    └── __init__.py
```

**Rust Tests (cargo test):**
```
percolate-core/
├── src/
│   └── memory/
│       ├── mod.rs
│       └── tests.rs   # Unit tests alongside implementation
└── tests/
    └── integration/   # Integration tests
        └── memory_test.rs
```

**Test Organization Rules:**
1. **Never put test files in project root** - always in `tests/` directory
2. **Unit tests** (`tests/unit/`):
   - No external services (no HTTP, no database)
   - Fast execution (< 1s per test)
   - Mock external dependencies minimally
   - Test pure logic and data transformations
3. **Integration tests** (`tests/integration/`):
   - Real external connections (HTTP server, database)
   - May be slower (acceptable up to 10s per test)
   - Require services to be running
   - Test end-to-end workflows
4. **Naming conventions**:
   - Test files: `test_*.py` or `*_test.py`
   - Test functions: `test_*`
   - Test classes: `Test*`
5. **Running tests**:
   ```bash
   # Unit tests only (fast, no server needed)
   uv run pytest tests/unit/

   # Integration tests (requires running server)
   uv run percolate serve &
   uv run pytest tests/integration/

   # All tests
   uv run pytest
   ```

**Principles:**
- Unit tests: no external services, fast execution
- Integration tests: real connections, may be slower
- Python: Mock only when absolutely necessary
- Rust: Use test doubles for external I/O
- Test error paths explicitly
- Use property-based testing for complex logic (proptest in Rust)
- Each test should be independent and idempotent

## CLI Design

- Flat command structure (avoid deep nesting)
- Clear, action-oriented command names
- Rich output for human readability (`rich` library)
- `--json` flag for machine parsing
- Progress indicators for long operations
- Structured logs to stderr, results to stdout

See [Schema Patterns](docs/10-schema-patterns.md#cli-command-schema) for detailed examples.

## Agent-let Patterns

Agent-lets are JSON schema-defined AI skills that can be trained, shared, and evolved.

**Key principles:**
- Pure JSON Schema definition (no executable code)
- MCP tool references only (not inline functions)
- Semantic versioning for compatibility
- Single factory function per target (Pydantic AI)
- OpenTelemetry instrumentation built in

See [Agent-lets Architecture](docs/03-agentlets.md) and [Schema Patterns](docs/10-schema-patterns.md#agent-let-schema) for detailed examples.

## Authentication & Security

### Cryptographic Standards
- **Device Auth**: Ed25519 (digital signatures)
- **Key Exchange**: X25519 (ECDH)
- **JWT Signing**: ES256 (ECDSA P-256)
- **Key Derivation**: HKDF-SHA256
- **Encryption**: ChaCha20-Poly1305 AEAD
- **Session Tokens**: Opaque random (32 bytes)

### Security Principles
- Private keys never leave device (secure enclave)
- Per-tenant encryption at rest (RocksDB)
- PKCE mandatory for all OAuth flows
- No implicit grant (OAuth 2.1 compliance)
- Rate limiting on auth endpoints
- Audit logging for security events

### Tenant Isolation
- Separate RocksDB database per tenant
- Tenant ID validated in authentication layer
- Tenant ID propagated through all operations
- S3 buckets scoped to tenant
- No cross-tenant data access

## REM Memory Design

**Storage model:**
- **Resources**: Chunked documents with embeddings
- **Entities**: Graph nodes with KV properties
- **Moments**: Temporal classifications with timestamps

**Key conventions:**
- All keys scoped by `tenant_id` for isolation
- Resources: `resource:{tenant_id}:{resource_id}`
- Entities: `entity:{tenant_id}:{entity_id}`
- Edges: `edge:{tenant_id}:{src_id}:{dst_id}:{type}`
- Moments: `moment:{tenant_id}:{timestamp}:{moment_id}`

**Search strategy:**
- Vector search for semantic similarity (HNSW)
- Trigram index for fuzzy entity matching
- Graph traversal for relationship navigation
- Hybrid search with score fusion

See [REM Memory](docs/02-rem-memory.md) and [Schema Patterns](docs/10-schema-patterns.md#rem-memory-schema) for detailed design and examples.

## Documentation Guidelines

### Writing Style

**General Principles:**
- **Clear and concise** - Every word should add value
- **Sentence case for headings** - Not Title Case or UPPER CASE
- **No uppercase acronyms in headings** - Use "MCP protocol" not "MCP Protocol"
- **Technical accuracy** - Verify claims and examples
- **Active voice** - Prefer "The function returns X" over "X is returned"
- **Present tense** - Use "returns" not "will return"

**Avoid:**
- ❌ Uppercase in headings: `## MCP PROTOCOL` or `## IMPORTANT NOTICE`
- ❌ Marketing language: "amazing", "powerful", "revolutionary"
- ❌ Unnecessary emphasis: Multiple exclamation marks!!
- ❌ Vague descriptions: "handles various things", "works with data"

**Prefer:**
- ✅ Sentence case: `## MCP protocol` or `## Important notice`
- ✅ Precise language: "concise", "efficient", "novel"
- ✅ Measured tone: Single punctuation only
- ✅ Specific descriptions: "parses PDF documents", "validates JSON schemas"

### README Structure

```markdown
# Project Name

Brief description (one sentence).

## Overview

What this project does and why it exists (2-3 paragraphs max).

## Installation

```bash
uv sync
```

## Usage

Basic usage examples with code.

## Architecture

Key design decisions (link to detailed docs).

## Contributing

How to contribute (link to CONTRIBUTING.md if complex).

## License

License information.
```

### Code Documentation

**Docstrings (Python):**
```python
def parse_document(file_path: str, tenant_id: str) -> ParseResult:
    """Parse a document and extract structured information.

    Args:
        file_path: Path to the document file
        tenant_id: Tenant scope for the operation

    Returns:
        ParseResult with extracted content and metadata

    Raises:
        FileNotFoundError: If file_path does not exist
        ValueError: If file format is unsupported

    Example:
        >>> result = parse_document("doc.pdf", "tenant-123")
        >>> print(result.content)
    """
```

**Documentation Comments (Rust):**
```rust
/// Parse a document and extract structured information.
///
/// # Arguments
///
/// * `file_path` - Path to the document file
/// * `tenant_id` - Tenant scope for the operation
///
/// # Returns
///
/// `Result<ParseResult, ParseError>` with extracted content
///
/// # Errors
///
/// Returns `ParseError::FileNotFound` if file doesn't exist.
///
/// # Example
///
/// ```
/// let result = parse_document("doc.pdf", "tenant-123")?;
/// println!("{}", result.content);
/// ```
pub fn parse_document(file_path: &str, tenant_id: &str) -> Result<ParseResult, ParseError> {
    // Implementation
}
```

### Markdown Conventions

**Headings:**
- Use sentence case: `## Test organization` not `## Test Organization`
- No trailing punctuation
- Maximum 3 levels deep in README files

**Code blocks:**
- Always specify language: ` ```python `, not ` ``` `
- Include comments for clarity
- Keep examples runnable

**Lists:**
- Use `-` for unordered lists (not `*` or `+`)
- Use `1.` for ordered lists
- Keep items parallel in structure

**Emphasis:**
- `**bold**` for important terms (first use)
- `*italic*` for emphasis (sparingly)
- `` `code` `` for inline code, filenames, commands

### Technical Documentation

**Architecture docs** (`docs/` directory):
- Explain the "why" not just the "what"
- Include diagrams (ASCII art acceptable)
- Link to related code files
- Update when implementation changes

**API documentation:**
- Describe every parameter
- Specify return types
- List possible errors
- Provide runnable examples

## Anti-Patterns to Avoid

### Code Anti-Patterns
- Magic values (use constants or configuration)
- God classes or modules (keep focused)
- Deep inheritance hierarchies (prefer composition)
- Circular dependencies (enforce DAG)
- Mutable global state (use context objects)
- String-based type checking (use isinstance/match)
- Premature optimization (measure first)
- Overly clever code (clarity over cleverness)
- Panic in library code (Rust - use Result)
- Unwrap without justification (Rust)

### Documentation Anti-Patterns
- Uppercase headings (except proper acronyms like NASA, HTTP)
- Outdated examples that don't run
- Missing parameter descriptions
- Vague "TODO" comments without context
- Copy-pasted documentation from other projects
- Marketing language instead of technical precision

## New LLM models (2025)

This section documents NEW models released in 2025 that may not be in Claude's training data. For a complete list of supported models, see Pydantic AI documentation.

### Anthropic Claude (new 2025 releases)

- **Claude Opus 4**: `claude-opus-4-20250514`
- **Claude Sonnet 4**: `claude-sonnet-4-20250514`
- **Claude Sonnet 4.5**: `claude-sonnet-4-5-20250929`
- **Claude Haiku 4.5**: `claude-haiku-4-5-20251001` (verified working)

### OpenAI GPT (new 2025 releases)

- **GPT-5**: `gpt-5`
- **GPT-4.1**: `gpt-4.1`

### Google Gemini (new 2025 releases)

- **Gemini 3 Ultra**: `gemini-3-ultra`
- **Gemini 3 Pro**: `gemini-3-pro`
- **Gemini 3 Flash**: `gemini-3-flash`

### Model selection

Model selection follows this priority:

1. **Explicit override**: `model` parameter in function call
2. **Context**: `AgentContext.default_model`
3. **Settings**: Global `settings.default_model` (env: `PERCOLATE_DEFAULT_MODEL`)

Example configuration:

```bash
# Environment variable
export PERCOLATE_DEFAULT_MODEL=claude-sonnet-4-20250514

# Or in .env file
PERCOLATE_DEFAULT_MODEL=gpt-5
```

Example usage:

```bash
# Use default model
percolate agent-run my-agent.yaml "Your prompt"

# Override with specific model
percolate agent-run my-agent.yaml "Your prompt" --model claude-opus-4-20250514
```

## Dependencies

### Python - Use
- **FastAPI**: HTTP server
- **Pydantic AI**: Agent framework
- **Typer**: CLI
- **loguru**: Logging
- **pytest**: Testing
- **OpenTelemetry**: Observability
- **FastMCP**: MCP implementation
- **PyO3**: Rust bindings

### Python - Avoid
- Custom validation logic (use Pydantic)
- Custom CLI parsing (use Typer)
- Custom logging (use loguru)
- Custom observability (use OpenTelemetry)
- Heavy computation (move to Rust)

### Rust - Use
- **rocksdb**: Embedded database
- **pyo3**: Python bindings
- **tokio**: Async runtime
- **serde**: Serialization
- **thiserror**: Error handling
- **tracing**: Structured logging
- **criterion**: Benchmarking

### Rust - Avoid
- `unsafe` without documented justification
- `unwrap()` in library code
- Blocking operations in async contexts
- Manual memory management (use RAII)

## Performance Considerations

### Python Layer
- Async/await for I/O-bound operations
- Minimize data copying across Python/Rust boundary
- Use generators for large result sets
- Profile with `py-spy` or `scalene`

### Rust Layer
- Zero-copy where possible (slices, `Cow`)
- Batch operations to amortize overhead
- Use arena allocation for temporary data
- Profile with `cargo flamegraph`
- Benchmark with `criterion` before optimizing

### Database
- Batch writes to RocksDB (write batches)
- Use column families for logical separation
- Tune bloom filters for query patterns
- Monitor compaction performance

## Git Workflow

### Commit Messages
- Keep concise (1-3 lines maximum)
- Use imperative mood ("Add feature" not "Added feature")
- No attribution or metadata in message body
- Focus on what and why, not how

Examples:
```
Add vector search to REM memory

Fix entity normalization for multi-word names

Refactor agent factory to support custom tools
```

### Branching
- Feature branches: `feature/description`
- Bug fixes: `fix/description`
- Keep branches short-lived
- Rebase on main before PR

## Review Checklist

### Python
- [ ] Function under 15 lines
- [ ] All parameters type-hinted
- [ ] Single responsibility
- [ ] No fallback logic
- [ ] Clear error handling
- [ ] Proper module placement
- [ ] No magic values
- [ ] Tests written
- [ ] Docstring with examples

### Rust
- [ ] Function under 30 lines
- [ ] All types explicit
- [ ] Error types with `thiserror`
- [ ] No `unwrap()` without justification
- [ ] Docstring with examples
- [ ] Tests written (unit + integration)
- [ ] Benchmarks for hot paths
- [ ] No `unsafe` without documented safety invariants

## References

- **Carrier**: Agent-let framework patterns
- **P8FS-Modules**: Authentication and memory research
- **Pydantic AI**: https://ai.pydantic.dev
- **FastMCP**: https://github.com/jlowin/fastmcp
- **OAuth 2.1**: https://oauth.net/2.1/
- **RocksDB**: https://rocksdb.org
- **PyO3**: https://pyo3.rs
