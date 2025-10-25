# Protocol documentation

Percolate implements several standard and custom protocols for interoperability.

## Supported protocols

### Standard protocols

| Protocol | Purpose | Documentation |
|----------|---------|---------------|
| **MCP** | Model Context Protocol for tool integration | [MCP Docs](https://modelcontextprotocol.io) |
| **OpenAI** | Chat completions API (streaming) | [OpenAI API](https://platform.openai.com/docs/api-reference) |
| **OAuth 2.1** | Modern authentication with PKCE | [OAuth 2.1](https://oauth.net/2.1/) |
| **OIDC** | OpenID Connect discovery | [OIDC Spec](https://openid.net/specs/openid-connect-core-1_0.html) |
| **S3** | Object storage protocol | [S3 API](https://docs.aws.amazon.com/s3/) |
| **gRPC** | Peer replication and clustering | [gRPC Docs](https://grpc.io) |
| **JSON Schema** | Schema validation standard | [JSON Schema](https://json-schema.org) |

### Custom protocols

| Protocol | Purpose | Documentation |
|----------|---------|---------------|
| **Content Headers** | User/device/content context | [content-headers.md](content-headers.md) |
| **Parse Job Protocol** | Document processing workflow | See below |
| **Tenant Context Protocol** | Gateway coordination | See below |
| **JSON Schema Extensions** | REM database configuration | [json-schema-extensions.md](json-schema-extensions.md) |

## Quick reference

### MCP server (Built-in tools)

```python
# Search REM database
mcp_tool("search_knowledge_base", query="...", tenant_id="...")

# Entity lookup
mcp_tool("lookup_entity", entity_type="carrier", query="DHL")

# Parse document
mcp_tool("parse_document", file_path="doc.pdf", tenant_id="...")

# Agent execution
mcp_tool("ask_agent", agent_uri="carrier-mapper", prompt="...")
```

### OpenAI chat completions

```http
POST /v1/chat/completions
Authorization: Bearer <token>
X-Tenant-ID: tenant_12345678
X-Session-ID: session_abc123

{
  "model": "gpt-4",
  "messages": [{"role": "user", "content": "Hello"}],
  "stream": true
}
```

### OAuth 2.1 device flow

```http
# Step 1: Request device code
POST /oauth/device/code
Content-Type: application/x-www-form-urlencoded

client_id=p8-node&scope=read+write

# Step 2: Display QR code to user
# (user scans and approves on mobile)

# Step 3: Poll for token
POST /oauth/device/token
Content-Type: application/x-www-form-urlencoded

client_id=p8-node&device_code=<code>&grant_type=urn:ietf:params:oauth:grant-type:device_code
```

### S3 tenant storage

```
s3://<bucket>/tenants/<tenant_id>/
├── context.yaml           # Tenant context blob
├── backups/               # Database backups
│   └── 2024-01-15.tar.gz
└── archives/              # Cold storage
    └── 2023/
```

### gRPC replication

```protobuf
service ReplicationService {
  rpc StreamWAL(WALRequest) returns (stream WALEntry);
  rpc GetTenantContext(TenantRequest) returns (TenantContext);
  rpc DeleteTenant(TenantRequest) returns (DeleteResponse);
}
```

### JSON Schema extensions

```python
from percolate.schemas import PercolateSchemaExtensions

class Article(BaseModel):
    title: str
    content: str

    model_config = ConfigDict(
        json_schema_extra=PercolateSchemaExtensions(
            name="Article",
            short_name="article",
            embedding_fields=["title", "content"],
            indexed_columns=["category"],
            key_field="title"
        ).model_dump()
    )
```

## Parse job protocol

Document processing workflow between Percolate and Percolate-Reader.

### Pydantic model

```python
from percolate.schemas import ParseJob, ParseJobResult

# Parse job tracking
job = ParseJob(
    job_id="parse-job-abc123def456",
    tenant_id="tenant_12345678",
    file_name="contract.pdf",
    file_type="application/pdf",
    file_size_bytes=524288,
    processing_options={
        "extract_text": True,
        "extract_tables": True,
        "generate_thumbnail": True,
    },
    priority="high",  # "high" | "medium" | "low"
    status="pending",  # "pending" | "processing" | "completed" | "failed"
)

# Parse result
result = ParseJobResult(
    content="This agreement is made...",
    tables=[
        {
            "page": 2,
            "rows": [
                ["Item", "Quantity", "Price"],
                ["Widget A", "100", "$50.00"],
            ],
        }
    ],
    images=[],
    metadata={
        "pages": 5,
        "author": "Legal Team",
        "created_date": "2024-01-15",
    },
)
```

### Flow

1. **Upload**: Client uploads document to Percolate (`/v1/ingest/upload`)
2. **Submit**: Percolate creates `ParseJob` and submits to Reader
3. **Process**: Reader extracts content and returns `ParseJobResult`
4. **Store**: Percolate stores content in REM database
5. **Track**: Gateway stores parse job in tenant context

### Parse job states

| State | Description |
|-------|-------------|
| `pending` | Job queued, not started |
| `processing` | Currently processing |
| `completed` | Successfully completed (result populated) |
| `failed` | Processing failed (error_message populated) |

### HTTP API example

```http
# Client uploads PDF
POST /v1/ingest/upload
Content-Type: multipart/form-data
X-Tenant-ID: tenant_12345678
X-Processing-Priority: high

[PDF file data]

# Response (ParseJob as JSON)
{
  "job_id": "parse-job-xyz789",
  "tenant_id": "tenant_12345678",
  "file_name": "contract.pdf",
  "file_type": "application/pdf",
  "status": "pending",
  "created_at": "2024-01-15T10:30:00Z"
}

# Check status
GET /v1/parse-jobs/parse-job-xyz789
X-Tenant-ID: tenant_12345678

# Response (ParseJob with result)
{
  "job_id": "parse-job-xyz789",
  "status": "completed",
  "result": {
    "content": "This agreement is made...",
    "tables": [
      {
        "page": 2,
        "rows": [
          ["Item", "Quantity", "Price"],
          ["Widget A", "100", "$50.00"]
        ]
      }
    ],
    "metadata": {
      "pages": 5,
      "author": "Legal Team"
    }
  },
  "completed_at": "2024-01-15T10:31:00Z",
  "resource_id": "resource-xyz789"
}
```

## Tenant context protocol

Gateway-stored context for fast tenant operations.

### Storage location

`s3://<bucket>/tenants/<tenant_id>/context.yaml`

### Contents

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

### Tenant deletion protocol

When deleting a tenant, the gateway performs:

1. **Remove context**: Delete `context.yaml` from S3
2. **Delete REM data**: Remove RocksDB from each peer node
3. **Remove S3 folder**: Delete entire tenant folder (backups, archives)
4. **Audit log**: Record deletion for compliance

**GDPR compliance:**
- No PII stored in context (no email, name, phone)
- Only stable tenant_id and tier/status
- Personal details stored in encrypted REM database only
- Deletion removes all data across all nodes

### Usage

```python
from percolate.schemas import TenantContext

# Load context
context = await gateway.load_tenant_context(tenant_id)

# Route to peer node
node_address = context.peer_nodes[0]
response = await grpc_client.call(node_address, request)

# Update recent sessions
context.recent_sessions.append(session_id)
await gateway.save_tenant_context(context)
```

## See also

- [Main README](../../Readme.md) - System overview
- [MCP Protocol](../08-mcp-protocol.md) - Detailed MCP implementation
- [OAuth 2.1 Flows](../03-auth.md) - Authentication flows
- [Replication Protocol](../../.spikes/percolate-rocks/docs/replication.md) - gRPC replication
