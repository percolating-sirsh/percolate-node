# Replication: gRPC Peer Subscription Sync

## Overview

REM database supports **primary/replica replication** via gRPC streaming and Write-Ahead Log (WAL). Replicas subscribe to primary node changes and sync in real-time.

**Key characteristics:**
- **gRPC streaming**: Bi-directional streams for real-time sync
- **WAL-based**: Write-Ahead Log ensures durability and replay
- **Async catchup**: Replicas automatically catchup after disconnection
- **Read-only replicas**: Replicas serve reads, primary handles writes
- **Peer subscription**: Pull model (replicas subscribe to primary)

## Architecture

```
┌─────────────┐
│   Primary   │
│  (writes)   │
│             │
│  WAL: seq 1 │◄──┐
│  WAL: seq 2 │   │
│  WAL: seq 3 │   │ gRPC stream
└─────────────┘   │ (replication log)
                  │
       ┌──────────┴──────────┐
       │                     │
       ▼                     ▼
┌─────────────┐       ┌─────────────┐
│  Replica 1  │       │  Replica 2  │
│  (reads)    │       │  (reads)    │
│             │       │             │
│  Seq: 3     │       │  Seq: 3     │
│  Lag: 2ms   │       │  Lag: 5ms   │
└─────────────┘       └─────────────┘
```

## CLI Usage

### Terminal 1: Start Primary

```bash
export P8_REPLICATION_MODE=primary
export P8_REPLICATION_PORT=50051
export P8_WAL_ENABLED=true
export P8_DB_PATH=./data/primary

rem init
rem schema add schema.json

# Start gRPC replication server
rem serve --host 0.0.0.0 --port 50051

# Insert data (writes to WAL)
rem insert articles '{"title": "Doc 1", "content": "Test"}'

# Check WAL
rem replication wal-status
# Output:
# WAL sequence: 1
# Entries: 1
# Pending replicas: 2
```

### Terminal 2: Start Replica

```bash
export P8_REPLICATION_MODE=replica
export P8_PRIMARY_HOST=localhost:50051
export P8_DB_PATH=./data/replica1

rem init

# Subscribe to primary (blocks, streams changes)
rem replicate --primary=localhost:50051 --follow

# In another terminal, check status
rem replication status
# Output:
# Mode: replica
# Primary: localhost:50051
# WAL position: 1
# Lag: 2ms
# Status: synced
```

### Querying Replicas

```bash
# Replicas are read-only
rem query "SELECT * FROM articles"
# ✅ Works - reads local copy

rem insert articles '{"title": "Doc 2"}'
# ❌ Error: Replica is read-only
```

## Python API

### Primary Node

```python
from rem_db import Database

# Enable WAL and replication
db = Database(
    path="./data/primary",
    replication_mode="primary",
    replication_port=50051,
    wal_enabled=True
)

# Start gRPC server (non-blocking)
db.start_replication_server()

# Normal operations
db.insert("articles", {"title": "Doc 1", "content": "..."})

# Check WAL status
status = db.get_wal_status()
print(f"WAL sequence: {status['sequence']}")
print(f"Connected replicas: {status['replica_count']}")
```

### Replica Node

```python
from rem_db import Database

# Connect as replica
db = Database(
    path="./data/replica",
    replication_mode="replica",
    primary_host="localhost:50051"
)

# Subscribe to primary (blocking call)
# Streams changes and applies them locally
db.replicate(follow=True)

# In separate thread/process, query replica
results = db.query("SELECT * FROM articles")
```

### Async Catchup Example

```python
import asyncio
from rem_db import Database

async def replica_with_catchup():
    db = Database(
        path="./data/replica",
        replication_mode="replica",
        primary_host="localhost:50051"
    )

    # Initial sync from last known position
    await db.sync_from_primary()

    # Subscribe for real-time updates
    async for entry in db.stream_replication():
        print(f"Received WAL entry: seq={entry.sequence}")
        # Entry already applied to local DB

        # Check lag
        lag = await db.get_replication_lag()
        if lag > 1000:  # 1 second
            print(f"WARNING: Replica lag {lag}ms")

asyncio.run(replica_with_catchup())
```

## Rust Implementation

### Core Components

```
src/replication/
├── mod.rs              # Public API
├── wal.rs              # Write-Ahead Log
├── primary.rs          # gRPC server (primary node)
├── replica.rs          # gRPC client (replica node)
├── protocol.rs         # Protobuf definitions
└── sync.rs             # Sync state machine
```

### WAL Design (wal.rs)

```rust
// src/replication/wal.rs

/// Write-Ahead Log entry
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WalEntry {
    pub sequence: u64,
    pub timestamp: SystemTime,
    pub operation: WalOperation,
    pub entity_id: Uuid,
    pub entity_type: String,
    pub data: Vec<u8>,  // Serialized entity
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum WalOperation {
    Insert,
    Update,
    Delete,
}

pub struct Wal {
    storage: Arc<RocksDB>,
    sequence: AtomicU64,
}

impl Wal {
    /// Append entry to WAL (atomic)
    pub fn append(&self, operation: WalOperation, entity: &Entity) -> Result<u64> {
        let seq = self.sequence.fetch_add(1, Ordering::SeqCst);
        let entry = WalEntry {
            sequence: seq,
            timestamp: SystemTime::now(),
            operation,
            entity_id: entity.id,
            entity_type: entity.entity_type.clone(),
            data: bincode::serialize(entity)?,
        };

        // Write to WAL CF
        let key = encode_wal_key(seq);
        let value = bincode::serialize(&entry)?;
        self.storage.put(CF_WAL, &key, &value)?;

        Ok(seq)
    }

    /// Read WAL entries from sequence
    pub fn read_from(&self, start_seq: u64) -> Result<Vec<WalEntry>> {
        let prefix = b"wal:";
        let mut entries = Vec::new();

        let iter = self.storage.prefix_iterator(CF_WAL, prefix);
        for (key, value) in iter {
            let entry: WalEntry = bincode::deserialize(&value)?;
            if entry.sequence >= start_seq {
                entries.push(entry);
            }
        }

        Ok(entries)
    }

    /// Compact WAL (remove old entries)
    pub fn compact(&self, keep_from_seq: u64) -> Result<()> {
        // Delete entries < keep_from_seq
        let prefix = b"wal:";
        let iter = self.storage.prefix_iterator(CF_WAL, prefix);

        for (key, _) in iter {
            let seq = decode_wal_key(&key)?;
            if seq < keep_from_seq {
                self.storage.delete(CF_WAL, &key)?;
            }
        }

        Ok(())
    }
}
```

**Design considerations:**
- **Atomic sequence**: `AtomicU64` for lock-free sequence generation
- **Bincode serialization**: Faster than JSON, smaller size
- **Separate CF**: WAL in dedicated column family for isolation
- **Compaction**: Periodic cleanup of old entries (configurable retention)

### Primary Node (primary.rs)

```rust
// src/replication/primary.rs
use tonic::{transport::Server, Request, Response, Status};
use tokio::sync::broadcast;

pub struct ReplicationServer {
    wal: Arc<Wal>,
    broadcast_tx: broadcast::Sender<WalEntry>,
}

#[tonic::async_trait]
impl ReplicationService for ReplicationServer {
    type StreamReplicationStream = ReceiverStream<Result<WalEntry, Status>>;

    /// Stream WAL entries to replica
    async fn stream_replication(
        &self,
        request: Request<ReplicationRequest>,
    ) -> Result<Response<Self::StreamReplicationStream>, Status> {
        let req = request.into_inner();
        let start_seq = req.last_sequence + 1;

        // 1. Send historical entries (catchup)
        let historical = self.wal.read_from(start_seq)
            .map_err(|e| Status::internal(e.to_string()))?;

        // 2. Subscribe to live updates
        let mut rx = self.broadcast_tx.subscribe();

        let (tx, rx_stream) = mpsc::channel(100);

        tokio::spawn(async move {
            // Send historical entries first
            for entry in historical {
                if tx.send(Ok(entry)).await.is_err() {
                    return; // Client disconnected
                }
            }

            // Stream live entries
            while let Ok(entry) = rx.recv().await {
                if tx.send(Ok(entry)).await.is_err() {
                    return; // Client disconnected
                }
            }
        });

        Ok(Response::new(ReceiverStream::new(rx_stream)))
    }
}

impl ReplicationServer {
    /// Broadcast new WAL entry to all connected replicas
    pub fn broadcast_entry(&self, entry: WalEntry) {
        let _ = self.broadcast_tx.send(entry);
        // Ignore errors (no subscribers = OK)
    }
}
```

**Design considerations:**
- **Tokio broadcast channel**: Fan-out to multiple replicas
- **Two-phase stream**: Historical catchup + live streaming
- **Backpressure**: Channel with bounded capacity (100 entries)
- **Graceful disconnect**: Detect client disconnection via send error

### Replica Node (replica.rs)

```rust
// src/replication/replica.rs
use tonic::transport::Channel;

pub struct ReplicaClient {
    client: ReplicationServiceClient<Channel>,
    storage: Arc<RocksDB>,
    last_sequence: AtomicU64,
}

impl ReplicaClient {
    /// Subscribe to primary and sync
    pub async fn replicate(&self, follow: bool) -> Result<()> {
        loop {
            let last_seq = self.last_sequence.load(Ordering::SeqCst);

            let request = ReplicationRequest {
                last_sequence: last_seq,
            };

            let mut stream = self.client
                .stream_replication(request)
                .await?
                .into_inner();

            // Process entries
            while let Some(entry) = stream.message().await? {
                self.apply_entry(&entry).await?;
                self.last_sequence.store(entry.sequence, Ordering::SeqCst);
            }

            // Stream ended
            if !follow {
                break; // One-shot sync
            }

            // Reconnect after delay
            tokio::time::sleep(Duration::from_secs(5)).await;
        }

        Ok(())
    }

    /// Apply WAL entry to local database
    async fn apply_entry(&self, entry: &WalEntry) -> Result<()> {
        let entity: Entity = bincode::deserialize(&entry.data)?;

        match entry.operation {
            WalOperation::Insert | WalOperation::Update => {
                self.storage.insert_entity(&entity)?;
            }
            WalOperation::Delete => {
                self.storage.delete_entity(entry.entity_id)?;
            }
        }

        Ok(())
    }

    /// Get replication lag in milliseconds
    pub async fn get_lag(&self) -> Result<u64> {
        let status: ReplicationStatus = self.client
            .get_status(Empty {})
            .await?
            .into_inner();

        let replica_seq = self.last_sequence.load(Ordering::SeqCst);
        let primary_seq = status.current_sequence;

        let lag_entries = primary_seq.saturating_sub(replica_seq);

        // Estimate lag (assuming 1ms per entry avg)
        Ok(lag_entries)
    }
}
```

**Design considerations:**
- **Automatic reconnect**: Retry connection after disconnect (exponential backoff)
- **Idempotent apply**: Same sequence can be applied multiple times (upsert semantics)
- **Lag calculation**: Primary sequence - replica sequence
- **One-shot or follow**: Support both catchup and streaming modes

### Protobuf Protocol (protocol.rs)

```protobuf
// protocol.proto
syntax = "proto3";

package replication;

service ReplicationService {
  rpc StreamReplication(ReplicationRequest) returns (stream WalEntry);
  rpc GetStatus(Empty) returns (ReplicationStatus);
}

message ReplicationRequest {
  uint64 last_sequence = 1;
}

message WalEntry {
  uint64 sequence = 1;
  int64 timestamp = 2;
  string operation = 3;  // "insert", "update", "delete"
  bytes entity_id = 4;   // UUID bytes
  string entity_type = 5;
  bytes data = 6;        // Serialized entity
}

message ReplicationStatus {
  uint64 current_sequence = 1;
  uint32 replica_count = 2;
}

message Empty {}
```

### Sync State Machine (sync.rs)

```rust
// src/replication/sync.rs

pub enum SyncState {
    Disconnected,
    Connecting,
    Syncing { from_seq: u64 },
    Streaming,
    Error { reason: String },
}

pub struct SyncStateMachine {
    state: Arc<RwLock<SyncState>>,
}

impl SyncStateMachine {
    pub async fn transition(&self, new_state: SyncState) {
        let mut state = self.state.write().await;

        // Log state transitions
        tracing::info!("Replication state: {:?} → {:?}", *state, new_state);

        *state = new_state;
    }

    pub async fn is_synced(&self) -> bool {
        matches!(*self.state.read().await, SyncState::Streaming)
    }
}
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `P8_REPLICATION_MODE` | `none` | `none`, `primary`, `replica` |
| `P8_PRIMARY_HOST` | - | Primary address (replica only) |
| `P8_REPLICATION_PORT` | `50051` | gRPC server port |
| `P8_WAL_ENABLED` | `true` | Enable Write-Ahead Log |
| `P8_WAL_SYNC_INTERVAL_MS` | `1000` | WAL flush interval |
| `P8_WAL_MAX_SIZE_MB` | `100` | WAL compaction threshold |
| `P8_WAL_RETENTION_HOURS` | `24` | Keep WAL entries for 24h |

### TOML Configuration

```toml
[replication]
mode = "primary"  # or "replica"
port = 50051

[replication.primary]
# Primary-specific config
wal_enabled = true
wal_sync_interval_ms = 1000
wal_max_size_mb = 100

[replication.replica]
# Replica-specific config
primary_host = "primary.example.com:50051"
reconnect_delay_ms = 5000
max_lag_ms = 10000  # Alert if lag > 10s
```

## Performance Characteristics

| Metric | Target | Notes |
|--------|--------|-------|
| Replication lag | < 10ms | P50 latency (local network) |
| Throughput | 10K ops/sec | Primary write throughput |
| Catchup speed | 50K entries/sec | Replay speed during sync |
| WAL overhead | +5-10% | Write latency increase |
| Network bandwidth | ~1KB per entry | Depends on entity size |

## Failure Scenarios

### Primary Failure

```bash
# Primary crashes
# → Replicas detect disconnect
# → Enter SyncState::Disconnected
# → Continue serving reads from local copy

# Primary restarts
# → Replicas auto-reconnect
# → Catchup from last known sequence
# → Resume streaming
```

### Replica Failure

```bash
# Replica crashes
# → Primary continues serving writes
# → WAL accumulates entries

# Replica restarts
# → Subscribes with last_sequence
# → Primary sends historical entries (catchup)
# → Replica applies and catches up
# → Resumes streaming
```

### Network Partition

```bash
# Network split
# → Replicas retry connection (exponential backoff)
# → Primary continues, WAL grows
# → Alert if WAL > max_size

# Network heals
# → Replicas reconnect
# → Catchup from accumulated WAL
# → Resume streaming
```

## Monitoring

### Metrics to Track

```rust
// Prometheus metrics
replication_lag_ms          // Replica lag in milliseconds
replication_wal_sequence    // Current WAL sequence (primary)
replication_replica_count   // Connected replicas (primary)
replication_catchup_entries // Entries replayed during catchup
replication_stream_errors   // gRPC stream errors
```

### Health Checks

```bash
# Check primary
rem replication status
# Output:
# Mode: primary
# WAL sequence: 12345
# Connected replicas: 2
# WAL size: 45MB

# Check replica
rem replication status
# Output:
# Mode: replica
# Primary: localhost:50051
# Last sequence: 12340
# Lag: 15ms
# Status: streaming
```

## Best Practices

1. **Use local network**: Replication works best with low-latency connections (<10ms)
2. **Monitor lag**: Alert if lag > 1 second (indicates network or performance issues)
3. **WAL compaction**: Run periodic compaction to prevent unbounded growth
4. **Read-only replicas**: Never write to replicas (enforce in code)
5. **Graceful failover**: Promote replica to primary only after confirming catchup complete
6. **Connection pooling**: Reuse gRPC channels, avoid reconnect storms
7. **Backpressure**: Slow replicas don't block primary (use bounded channels)

## Testing Guide

### Test Scenarios

The integration tests (`tests/rust/test_replication.rs`) cover:

#### Basic Replication (Primary → Replica)
```rust
// Primary inserts 2 entries
// Replica connects and syncs
// Verifies replica has 2 entries
```

#### Multi-Replica (Primary → Replica1 + Replica2)
```rust
// Primary inserts 10 entries
// Both replicas connect concurrently
// Verifies both have all 10 entries
```

#### Replica Catchup
```rust
// Primary inserts 5 entries BEFORE replica connects
// Replica connects (from seq=0)
// Verifies replica catches up to seq=5
```

#### Concurrent Writes
```rust
// 3 threads write 5 entries each (15 total)
// Replica syncs concurrently
// Verifies replica has all 15 entries
```

### Running Tests

#### Prerequisites

Enable python feature (includes gRPC):
```bash
# In Cargo.toml
[features]
default = ["python"]
python = ["pyo3", "tonic", "prost"]
```

Dependencies:
```toml
[dependencies]
tonic = "0.11"
prost = "0.12"
tokio-stream = "0.1"

[build-dependencies]
tonic-build = "0.11"
```

#### Run Integration Tests

```bash
# All replication tests
cargo test --features python --test test_replication

# Specific test
cargo test --features python test_basic_replication

# With output
cargo test --features python test_multi_replica -- --nocapture
```

### Manual Testing with Multiple Processes

#### Terminal 1: Start Primary
```rust
use percolate_rocks::replication::{PrimaryNode, WriteAheadLog, WalOperation};
use percolate_rocks::storage::Storage;

#[tokio::main]
async fn main() {
    let storage = Storage::open("./data/primary").unwrap();
    let mut wal = WriteAheadLog::new(storage).unwrap();

    // Insert test data
    for i in 0..10 {
        let op = WalOperation::Insert {
            tenant_id: "tenant-1".to_string(),
            entity: serde_json::json!({"id": i, "message": format!("Entry {}", i)}),
        };
        wal.append(op).unwrap();
    }

    // Start server
    let primary = PrimaryNode::new(wal, 50051);
    println!("Primary started on port 50051");
    primary.serve().await.unwrap();
}
```

#### Terminal 2: Start Replica 1
```rust
use percolate_rocks::replication::{ReplicaNode, WriteAheadLog};
use percolate_rocks::storage::Storage;

#[tokio::main]
async fn main() {
    let storage = Storage::open("./data/replica1").unwrap();
    let wal = WriteAheadLog::new(storage).unwrap();

    let mut replica = ReplicaNode::new(wal, "http://localhost:50051".to_string());

    replica.connect().await.unwrap();
    println!("Replica 1 connected");

    replica.follow().await.unwrap();  // Blocks until disconnected
}
```

#### Terminal 3: Start Replica 2
```rust
use percolate_rocks::replication::{ReplicaNode, WriteAheadLog};
use percolate_rocks::storage::Storage;

#[tokio::main]
async fn main() {
    let storage = Storage::open("./data/replica2").unwrap();
    let wal = WriteAheadLog::new(storage).unwrap();

    let mut replica = ReplicaNode::new(wal, "http://localhost:50051".to_string());

    replica.connect().await.unwrap();
    println!("Replica 2 connected");

    replica.follow().await.unwrap();
}
```

#### Terminal 4: Monitor Status
```rust
use percolate_rocks::replication::protocol::pb;
use tonic::Request;

#[tokio::main]
async fn main() {
    let mut client = pb::replication_service_client::ReplicationServiceClient::connect(
        "http://localhost:50051"
    ).await.unwrap();

    loop {
        let status = client.get_status(Request::new(pb::StatusRequest {}))
            .await.unwrap()
            .into_inner();

        println!("Primary WAL: seq={}, healthy={}", status.current_seq, status.healthy);

        tokio::time::sleep(std::time::Duration::from_secs(5)).await;
    }
}
```

### Verification

#### Check Replica Caught Up
```rust
// In replica code
let status = replica.status().await;
println!("Replica status:");
println!("  Connected: {}", status.connected);
println!("  Local seq: {}", status.local_seq);
println!("  Primary seq: {}", status.primary_seq);
println!("  Lag: {} entries", status.primary_seq - status.local_seq);
```

#### Inspect WAL Entries
```rust
let storage = Storage::open("./data/replica1").unwrap();
let wal = WriteAheadLog::new(storage).unwrap();

// Get all entries
let entries = wal.get_entries_after(0, 1000).unwrap();
println!("Replica has {} entries", entries.len());

for entry in entries {
    println!("Seq {}: {:?}", entry.seq, entry.op);
}
```

#### Monitor Network Traffic
```bash
# Use tcpdump to see gRPC traffic
sudo tcpdump -i lo0 -A 'port 50051'

# Use grpcurl to inspect service
grpcurl -plaintext localhost:50051 list
grpcurl -plaintext localhost:50051 replication.ReplicationService/GetStatus
```

## Troubleshooting

### Replica Not Connecting

**Error:**
```
Error: Connection failed: Connection refused
```

**Solution:** Ensure primary is running and listening on correct port:
```bash
lsof -i :50051  # Check if port is in use
```

### Replication Lag Growing

**Symptoms:**
```
Primary seq: 1000
Replica seq: 100
Lag: 900 entries
```

**Possible causes:**
1. Network bandwidth saturated
2. Replica disk I/O bottleneck
3. gRPC buffer size too small

**Solution:** Increase batch size in `get_entries_after(from_seq, limit)`:
```rust
// In primary.rs:167
let entries = wal_read.get_entries_after(from_seq, 1000)?;  // Increase from 100 to 1000
```

### Sync State Stuck in "Connecting"

**Symptoms:**
```
State: Connecting
Retry count: 5
```

**Solution:** Check network connectivity and primary status:
```rust
let state = replica.sync_state.read().await;
println!("State: {:?}", state.state());
println!("Time in state: {:?}", state.time_in_state());
println!("Retry count: {}", state.retry_count());
```

## Implementation Details

### Component Overview

| Component | Purpose | Implementation | Lines |
|-----------|---------|----------------|-------|
| **WAL** | Durable log of write operations | `src/replication/wal.rs` | 456 |
| **gRPC Protocol** | Service definition (bidirectional streaming) | `proto/replication.proto` | - |
| **PrimaryNode** | Expose WAL via gRPC server | `src/replication/primary.rs` | 210 |
| **ReplicaNode** | Connect and apply WAL entries | `src/replication/replica.rs` | 216 |
| **SyncStateMachine** | Connection lifecycle and retry logic | `src/replication/sync.rs` | 441 |

### WAL Details

- **Storage**: RocksDB `CF_WAL` column family
- **Key format**: `wal:{seq:020}` (zero-padded sequence numbers)
- **Operations**: `Insert`, `Update`, `Delete` with tenant isolation

### gRPC Service

**Methods:**
- `Subscribe(stream SubscribeRequest) → stream WalEntryProto`: Stream WAL entries
- `GetStatus(StatusRequest) → StatusResponse`: Query WAL status

**Features:**
- Bidirectional streaming
- 100-entry buffer per stream
- Heartbeat support (planned)

### SyncStateMachine States

| State | Description | Next State |
|-------|-------------|------------|
| `Disconnected` | No connection | `Connecting` |
| `Connecting` | Attempting connection | `Syncing` or retry |
| `Syncing` | Catching up from seq | `Synced` |
| `Synced` | Real-time streaming | `Disconnected` on error |

**Retry logic:** Exponential backoff (1s → 2s → 4s → 8s → max 60s), max 10 retries

## Performance Benchmarks

Expected performance (local network):

| Metric | Target | Notes |
|--------|--------|-------|
| Replication lag | < 10ms | P50 latency |
| Catchup speed | > 1000 ops/sec | Historical replay |
| Concurrent replicas | 10+ | Tested with 2 |
| Network overhead | < 2x data size | Bincode + gRPC |

## Security Considerations

### Encryption at Rest (High Priority)

Each tenant has Ed25519 key pair:
- All data encrypted with ChaCha20-Poly1305
- Private keys encrypted with master password (Argon2 key derivation)
- Public keys stored plaintext for sharing

See `docs/encryption-architecture.md` for complete design.

### Encrypted WAL

- WAL entries encrypted before storage and replication
- Defense in depth: mTLS (transport) + encrypted entries (application)
- Replica nodes must have same tenant key pair to decrypt

### Tenant Data Sharing

- Encrypt with recipient's public key (X25519 ECDH)
- End-to-end encryption - even database admin cannot read
- Cross-tenant secure sharing

### Authentication (Planned)

- [ ] Add mTLS for primary-replica connections
- [ ] Client certificates for replica authentication
- [ ] Mutual authentication prevents unauthorized replication

## Future Enhancements

### Performance
- [ ] **Compression**: Compress WAL entries before transmission (zstd)
- [ ] **Heartbeats**: Implement periodic heartbeats to detect stale connections
- [ ] **Flow control**: Add ack_seq handling for backpressure
- [ ] **Metrics**: Expose Prometheus metrics (lag, throughput, errors)

### Reliability
- [ ] **Automatic retry**: Enhanced retry with backoff in ReplicaNode
- [ ] **Conflict resolution**: Apply LWW or CRDT merge for concurrent writes
- [ ] **Snapshot transfer**: Send full snapshot for large catchup (> 10k entries)
- [ ] **Partial replication**: Allow filtering by tenant_id or entity_type

### Advanced Features
- [ ] **Multi-primary**: Conflict-free replicated data types (CRDTs)
- [ ] **Quorum writes**: Wait for N replicas before ack
- [ ] **Compressed WAL**: Reduce network bandwidth
- [ ] **Delta sync**: Send only changed fields (not full entity)
- [ ] **Snapshot transfer**: Initial sync from snapshot instead of WAL replay

## References

- **gRPC streaming**: https://grpc.io/docs/languages/rust/basics/
- **Tonic**: https://github.com/hyperium/tonic
- **Prost**: https://github.com/tokio-rs/prost
- **RocksDB replication**: Similar to Kafka's log-based replication
- **WAL design**: PostgreSQL write-ahead log architecture
