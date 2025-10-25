# Multi-Peer Replication Testing Guide

This document explains how to test the gRPC-based replication system with multiple peers.

## Architecture

```
Primary (Port 50051)          Replica 1 (Port 50052)       Replica 2 (Port 50053)
      |                              |                             |
      | <-- subscribe(seq=0) -------|                             |
      | ---- stream entries -------> |                             |
      |                              | <-- subscribe(seq=0) -------|
      |                              | ---- stream entries -------> |
      |                                                             |
```

## Components

### 1. WAL (Write-Ahead Log)
- **Purpose**: Durable log of all write operations for replication
- **Storage**: RocksDB `CF_WAL` column family
- **Key format**: `wal:{seq:020}` (zero-padded sequence numbers)
- **Operations**: `Insert`, `Update`, `Delete` with tenant isolation

**Implementation**: `src/replication/wal.rs` (456 lines)

### 2. gRPC Protocol
- **Service**: `ReplicationService` (bidirectional streaming)
- **Methods**:
  - `Subscribe(stream SubscribeRequest) → stream WalEntryProto`: Stream WAL entries
  - `GetStatus(StatusRequest) → StatusResponse`: Query WAL status
- **Protobuf**: `proto/replication.proto`

### 3. PrimaryNode (gRPC Server)
- **Purpose**: Expose WAL entries to replicas via gRPC
- **Streaming**: Sends all entries after replica's `from_seq`
- **Heartbeats**: Supports client heartbeats (not yet implemented)
- **Flow control**: 100-entry buffer per stream

**Implementation**: `src/replication/primary.rs` (210 lines)

### 4. ReplicaNode (gRPC Client)
- **Purpose**: Connect to primary and apply WAL entries locally
- **State machine**: Uses `SyncStateMachine` for connection lifecycle
- **Catchup**: Automatically starts from local sequence number
- **Continuous sync**: Blocks in `follow()` until disconnected

**Implementation**: `src/replication/replica.rs` (216 lines)

### 5. SyncStateMachine
- **States**: `Disconnected → Connecting → Syncing → Synced`
- **Retry logic**: Exponential backoff (1s → 2s → 4s → 8s → max 60s)
- **Error handling**: Max 10 retries before giving up

**Implementation**: `src/replication/sync.rs` (441 lines)

## Test Scenarios

The integration tests (`tests/rust/test_replication.rs`) cover:

### 1. Basic Replication (Primary → Replica)
```rust
// Primary inserts 2 entries
// Replica connects and syncs
// Verifies replica has 2 entries
```

### 2. Multi-Replica (Primary → Replica1 + Replica2)
```rust
// Primary inserts 10 entries
// Both replicas connect concurrently
// Verifies both have all 10 entries
```

### 3. Replica Catchup
```rust
// Primary inserts 5 entries BEFORE replica connects
// Replica connects (from seq=0)
// Verifies replica catches up to seq=5
```

### 4. Concurrent Writes
```rust
// 3 threads write 5 entries each (15 total)
// Replica syncs concurrently
// Verifies replica has all 15 entries
```

## Running Tests

### Prerequisites

1. **Enable python feature** (includes gRPC):
   ```bash
   # In Cargo.toml
   [features]
   default = ["python"]
   python = ["pyo3", "tonic", "prost"]
   ```

2. **Install dependencies**:
   ```bash
   # Add to Cargo.toml [dependencies]
   tonic = "0.11"
   prost = "0.12"
   tokio-stream = "0.1"

   # Add to [build-dependencies]
   tonic-build = "0.11"
   ```

### Run Integration Tests

```bash
# All replication tests
cargo test --features python --test test_replication

# Specific test
cargo test --features python test_basic_replication

# With output
cargo test --features python test_multi_replica -- --nocapture
```

### Manual Testing with Multiple Processes

**Terminal 1 - Start Primary**:
```rust
use percolate_rocks::replication::{PrimaryNode, WriteAheadLog, WalOperation};
use percolate_rocks::storage::Storage;

#[tokio::main]
async fn main() {
    let storage = Storage::open("./data/primary").unwrap();
    let mut wal = WriteAheadLog::new(storage).unwrap();

    // Insert some test data
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

**Terminal 2 - Start Replica 1**:
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

**Terminal 3 - Start Replica 2**:
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

**Terminal 4 - Monitor Status**:
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

## Verification

### Check Replica Caught Up

```rust
// In replica code
let status = replica.status().await;
println!("Replica status:");
println!("  Connected: {}", status.connected);
println!("  Local seq: {}", status.local_seq);
println!("  Primary seq: {}", status.primary_seq);
println!("  Lag: {} entries", status.primary_seq - status.local_seq);
```

### Inspect WAL Entries

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

### Monitor Network Traffic

```bash
# Use tcpdump to see gRPC traffic
sudo tcpdump -i lo0 -A 'port 50051'

# Use grpcurl to inspect service
grpcurl -plaintext localhost:50051 list
grpcurl -plaintext localhost:50051 replication.ReplicationService/GetStatus
```

## Performance Benchmarks

Expected performance (local network):

| Metric | Target | Measured |
|--------|--------|----------|
| Replication lag | < 10ms | TBD |
| Catchup speed | > 1000 ops/sec | TBD |
| Concurrent replicas | 10+ | TBD |
| Network overhead | < 2x data size | TBD |

## Troubleshooting

### Replica Not Connecting

```
Error: Connection failed: Connection refused
```

**Solution**: Ensure primary is running and listening on correct port:
```bash
lsof -i :50051  # Check if port is in use
```

### Replication Lag Growing

```
Primary seq: 1000
Replica seq: 100
Lag: 900 entries
```

**Possible causes**:
1. Network bandwidth saturated
2. Replica disk I/O bottleneck
3. gRPC buffer size too small

**Solution**: Increase batch size in `get_entries_after(from_seq, limit)`:
```rust
// In primary.rs:167
let entries = wal_read.get_entries_after(from_seq, 1000)?;  // Increase from 100 to 1000
```

### Sync State Stuck in "Connecting"

```
State: Connecting
Retry count: 5
```

**Solution**: Check network connectivity and primary status:
```rust
let state = replica.sync_state.read().await;
println!("State: {:?}", state.state());
println!("Time in state: {:?}", state.time_in_state());
println!("Retry count: {}", state.retry_count());
```

## TODO: Future Improvements

- [ ] **Compression**: Compress WAL entries before transmission (zstd)
- [ ] **Authentication**: Add mTLS or JWT authentication
- [ ] **Heartbeats**: Implement periodic heartbeats to detect stale connections
- [ ] **Flow control**: Add ack_seq handling for backpressure
- [ ] **Metrics**: Expose Prometheus metrics (lag, throughput, errors)
- [ ] **Automatic retry**: Implement retry with backoff in ReplicaNode
- [ ] **Conflict resolution**: Apply LWW or CRDT merge for concurrent writes
- [ ] **Snapshot transfer**: Send full snapshot for large catchup (> 10k entries)
- [ ] **Partial replication**: Allow filtering by tenant_id or entity_type

## References

- **gRPC streaming**: https://grpc.io/docs/languages/rust/basics/
- **Tonic**: https://github.com/hyperium/tonic
- **Prost**: https://github.com/tokio-rs/prost
- **RocksDB replication**: Similar to Kafka's log-based replication
- **WAL design**: PostgreSQL write-ahead log architecture
