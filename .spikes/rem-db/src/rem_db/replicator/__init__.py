"""gRPC-based peer replication for REM database.

This module implements distributed replication between REM database instances
using gRPC streaming. Supports:

- Peer discovery via configuration
- WAL-based change streaming
- Same-tenant and cross-tenant replication
- Encryption for data in transit (optional)
- Multi-instance synchronization

Architecture:
    Each database instance can act as both client and server:
    - Server: Accepts replication streams from peers
    - Client: Subscribes to peer streams for updates

    Replication is bidirectional and eventually consistent.
"""

from rem_db.replicator.peer import PeerConfig, PeerDiscovery
from rem_db.replicator.server import ReplicationServer
from rem_db.replicator.client import ReplicationClient
from rem_db.replicator.manager import ReplicationManager

__all__ = [
    "PeerConfig",
    "PeerDiscovery",
    "ReplicationServer",
    "ReplicationClient",
    "ReplicationManager",
]
