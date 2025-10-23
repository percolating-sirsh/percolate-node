# Sync and Replication Architecture

## Overview

Percolate supports **multi-node deployment** where each user can have:
- **Multiple cloud nodes** (2+ for redundancy)
- **Desktop node** (local primary)
- **Mobile app** (client only, or lightweight node)

Data synchronizes between nodes for:
- **Failure recovery**: Cloud node redundancy
- **Offline operation**: Desktop works independently
- **Multi-device access**: Same memory across devices

## Node Types

### 1. Desktop Node (Primary)

**Characteristics:**
- Full REM memory engine (RocksDB)
- Complete agent-let runtime
- Can operate fully offline
- Syncs to cloud nodes periodically

**Storage:**
- Local RocksDB: `~/.percolate/data/`
- Agent-lets: `~/.percolate/schema/`
- API server runs locally (optional)

### 2. Cloud Node (Replica)

**Characteristics:**
- Hosted in Kubernetes cluster
- Per-tenant isolated RocksDB
- Continuous sync from desktop and other cloud nodes
- High availability (2+ replicas per tenant)

**Storage:**
- Persistent volume: `/var/lib/percolate/{tenant_id}/`
- S3 backup: Cold archive for old data

### 3. Mobile App (Client)

**Characteristics:**
- Lightweight client (mostly UI)
- Optional embedded node for offline
- Connects to nearest node (desktop or cloud)
- Key management (Ed25519 in secure enclave)

**Storage:**
- Minimal local cache
- Keys in secure enclave
- Recent conversations cached

## Sync Protocol

### Conflict-Free Replicated Data Types (CRDTs)

REM uses **last-write-wins (LWW)** with vector clocks for conflict resolution:

```rust
pub struct Resource {
    pub id: ResourceId,
    pub content: String,
    pub metadata: Metadata,
    pub version: VectorClock,  // Node ID → sequence number
    pub updated_at: Timestamp,
}

pub struct VectorClock {
    pub clocks: HashMap<NodeId, u64>,
}

impl VectorClock {
    pub fn happens_before(&self, other: &VectorClock) -> bool {
        // Lamport happens-before relation
    }

    pub fn merge(&mut self, other: &VectorClock) {
        // Take max of each clock
        for (node_id, seq) in &other.clocks {
            self.clocks
                .entry(*node_id)
                .and_modify(|e| *e = (*e).max(*seq))
                .or_insert(*seq);
        }
    }
}
```

### Sync Flow

```
Desktop Node
  ↓ (periodic sync every 5 minutes)
  → Compute delta since last sync
    → Upload changed resources/entities/moments
      → Cloud Node 1 receives delta
        ↓
        → Apply delta with vector clock merge
          → Resolve conflicts (LWW)
            → Replicate to Cloud Node 2
              ↓
              → Cloud Node 2 applies delta
                → Both cloud nodes consistent
```

### Delta Computation

```rust
pub struct SyncDelta {
    pub resources_added: Vec<Resource>,
    pub resources_updated: Vec<Resource>,
    pub resources_deleted: Vec<ResourceId>,
    pub entities_added: Vec<Entity>,
    pub entities_updated: Vec<Entity>,
    pub entities_deleted: Vec<EntityId>,
    pub moments_added: Vec<Moment>,
    pub from_version: VectorClock,
    pub to_version: VectorClock,
}

impl MemoryEngine {
    pub fn compute_delta(&self, from_version: &VectorClock) -> Result<SyncDelta> {
        // 1. Query all items with version > from_version
        // 2. Group into added/updated/deleted
        // 3. Return delta
    }

    pub fn apply_delta(&mut self, delta: SyncDelta) -> Result<VectorClock> {
        // 1. For each item in delta
        // 2. Merge vector clocks
        // 3. Resolve conflicts (LWW by timestamp)
        // 4. Apply changes
        // 5. Return new version
    }
}
```

## Conflict Resolution

### Last-Write-Wins (LWW)

When concurrent updates occur:

```rust
pub fn resolve_conflict(local: &Resource, remote: &Resource) -> Resource {
    // Compare vector clocks
    match local.version.partial_cmp(&remote.version) {
        Some(Ordering::Less) => remote.clone(),     // Remote is newer
        Some(Ordering::Greater) => local.clone(),   // Local is newer
        _ => {
            // Concurrent writes - use timestamp
            if remote.updated_at > local.updated_at {
                remote.clone()
            } else {
                local.clone()
            }
        }
    }
}
```

### Merge Semantics by Type

| Type | Conflict Strategy |
|------|-------------------|
| **Resource** | LWW by timestamp (immutable after creation) |
| **Entity** | Field-level merge (properties merged, LWW for conflicts) |
| **Edge** | LWW by timestamp (relationships are atomic) |
| **Moment** | Immutable (no conflicts, append-only) |

### Entity Field Merge

Entities support field-level merging:

```rust
pub fn merge_entities(local: &Entity, remote: &Entity) -> Entity {
    let mut merged = local.clone();

    // Merge properties field by field
    for (key, remote_value) in &remote.properties {
        match local.properties.get(key) {
            None => {
                // Field only in remote
                merged.properties.insert(key.clone(), remote_value.clone());
            }
            Some(local_value) => {
                // Field in both - compare vector clocks
                let local_clock = local.version.clocks.get(&local.node_id).unwrap_or(&0);
                let remote_clock = remote.version.clocks.get(&remote.node_id).unwrap_or(&0);

                if remote_clock > local_clock {
                    merged.properties.insert(key.clone(), remote_value.clone());
                }
            }
        }
    }

    // Merge vector clocks
    merged.version.merge(&remote.version);
    merged
}
```

## Node Discovery

### Cloud Gateway

Gateway maintains registry of active nodes per tenant:

```python
# Gateway service
class NodeRegistry:
    def __init__(self):
        self.nodes: dict[str, list[NodeInfo]] = {}

    def register_node(self, tenant_id: str, node: NodeInfo):
        """Register node for tenant."""
        if tenant_id not in self.nodes:
            self.nodes[tenant_id] = []
        self.nodes[tenant_id].append(node)

    def get_nodes(self, tenant_id: str) -> list[NodeInfo]:
        """Get all nodes for tenant."""
        return self.nodes.get(tenant_id, [])

    def get_primary_node(self, tenant_id: str) -> NodeInfo:
        """Get primary (lowest latency) node."""
        nodes = self.get_nodes(tenant_id)
        return min(nodes, key=lambda n: n.latency_ms)

@dataclass
class NodeInfo:
    node_id: str
    type: str  # "desktop", "cloud", "mobile"
    endpoint: str
    latency_ms: float
    last_seen: datetime
    is_healthy: bool
```

### Desktop → Cloud Registration

Desktop nodes register with gateway on startup:

```python
# Desktop node
async def register_with_gateway():
    response = await httpx.post(
        "https://gateway.percolationlabs.ai/api/v1/nodes/register",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "node_id": socket.gethostname(),
            "type": "desktop",
            "endpoint": "https://desktop.local:8000",
            "capabilities": ["full_node", "api_server", "mcp_server"]
        }
    )

    # Gateway returns list of other nodes for sync
    other_nodes = response.json()["nodes"]
    return other_nodes
```

## Sync Schedule

### Desktop → Cloud

- **Periodic sync**: Every 5 minutes (configurable)
- **On-demand sync**: When user explicitly triggers
- **Event-driven sync**: After significant operations (document ingestion)

```python
import asyncio

async def sync_loop(memory: MemoryEngine, cloud_nodes: list[str]):
    while True:
        try:
            # Compute delta
            delta = memory.compute_delta(from_version=last_synced_version)

            # Upload to all cloud nodes
            for node in cloud_nodes:
                await upload_delta(node, delta)

            # Update last synced version
            last_synced_version = delta.to_version

        except Exception as e:
            logger.error(f"Sync failed: {e}")

        await asyncio.sleep(300)  # 5 minutes
```

### Cloud → Cloud (Replication)

- **Real-time replication**: Changes replicated immediately between cloud nodes
- **Consensus**: Leader election for write coordination (Raft/Paxos)

```
Cloud Node 1 (Leader)
  ↓ (receives delta from desktop)
  → Apply delta locally
    ↓
    → Replicate to Cloud Node 2
      ↓
      → Cloud Node 2 applies delta
        ↓
        → Ack to Cloud Node 1
          ↓
          → Cloud Node 1 confirms sync to desktop
```

## Failure Recovery

### Cloud Node Failure

If Cloud Node 1 fails:
1. Gateway detects failure (health check timeout)
2. Gateway routes traffic to Cloud Node 2
3. Desktop syncs to Cloud Node 2 only
4. Cloud Node 1 recovers and catches up via delta from Cloud Node 2

### Desktop Node Offline

If desktop goes offline:
1. Cloud nodes continue serving (mobile app connects to cloud)
2. Desktop accumulates local changes
3. Desktop reconnects and syncs delta to cloud
4. Cloud nodes merge delta with vector clocks

### Split-Brain Scenario

If desktop and cloud nodes diverge significantly:
1. Desktop reconnects after long offline period
2. Compute delta (may be large)
3. Upload delta to cloud
4. Cloud merges with LWW conflict resolution
5. Desktop pulls cloud changes
6. Desktop applies cloud delta with merge

## Bandwidth Optimization

### Incremental Sync

Only sync changes, not full database:

```rust
pub struct SyncStats {
    pub resources_added: usize,
    pub resources_updated: usize,
    pub bytes_transferred: usize,
    pub duration_ms: u64,
}

// Only send IDs for deleted items (not full content)
pub struct DeletedResource {
    pub id: ResourceId,
    pub deleted_at: Timestamp,
}
```

### Compression

Compress deltas before transmission:

```rust
use zstd::stream::encode_all;

pub fn compress_delta(delta: &SyncDelta) -> Result<Vec<u8>> {
    let json = serde_json::to_vec(delta)?;
    Ok(encode_all(&json[..], 3)?)  // Compression level 3
}
```

### Batching

Batch small changes before sync:

```python
# Wait for batch window before syncing
async def batch_sync(memory: MemoryEngine, batch_window: int = 60):
    changes = []

    async for change in memory.watch_changes():
        changes.append(change)

        # Sync if batch window elapsed or batch is large
        if len(changes) >= 100 or time_since_last_sync() > batch_window:
            await sync_changes(changes)
            changes.clear()
```

## Security

### Encrypted Sync

All sync traffic encrypted with TLS 1.3:

```python
# Upload delta to cloud
async def upload_delta(node_url: str, delta: SyncDelta):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{node_url}/api/v1/sync/delta",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            json=delta.to_dict(),
            timeout=30.0
        )
        return response.json()
```

### Per-Node Authentication

Each node authenticates with JWT tokens:

```python
# Node-to-node authentication
async def authenticate_node(node_id: str) -> str:
    # Exchange device credentials for node token
    response = await client.post(
        "https://gateway.percolationlabs.ai/oauth/token",
        data={
            "grant_type": "client_credentials",
            "client_id": node_id,
            "client_secret": node_secret
        }
    )
    return response.json()["access_token"]
```

## Future Enhancements

### Phase 1 (Current)
- Desktop → Cloud sync (periodic)
- Cloud → Cloud replication (leader-follower)
- LWW conflict resolution

### Phase 2
- Mobile as lightweight node (optional)
- Optimistic UI updates (sync in background)
- Selective sync (sync only recent data)

### Phase 3
- CRDTs for entities (field-level convergence)
- Conflict detection UI (show conflicts to user)
- Peer-to-peer sync (desktop ↔ desktop)

### Phase 4
- Edge computing (regional cloud nodes)
- CDN for static content
- Global sync with geo-replication

## References

- Vector Clocks: Lamport (1978)
- CRDTs: Shapiro et al. (2011)
- Last-Write-Wins: Dynamo paper (Amazon, 2007)
- Raft Consensus: Ongaro & Ousterhout (2014)
