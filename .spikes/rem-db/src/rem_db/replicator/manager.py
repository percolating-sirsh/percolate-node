"""Replication manager orchestrating server and clients.

Coordinates replication lifecycle across all configured peers.
"""

import asyncio
import logging
from typing import Optional

from rem_db.replicator.peer import PeerConfig, PeerDiscovery
from rem_db.replicator.server import ReplicationServer, WALEntry
from rem_db.replicator.client import ReplicationClient

logger = logging.getLogger(__name__)


class ReplicationManager:
    """Orchestrates replication across server and multiple clients.

    Responsibilities:
    - Start/stop replication server
    - Discover peers via configuration
    - Connect to all peers as clients
    - Broadcast local writes to all peers
    - Monitor peer health and reconnect
    - Coordinate graceful shutdown

    Architecture:
        Each database instance runs:
        - 1 ReplicationServer (listens for incoming streams)
        - N ReplicationClients (connect to N peers)

        When a local write occurs:
        1. Database writes to local RocksDB + WAL
        2. Manager broadcasts entry to server
        3. Server forwards to all connected peers
        4. Clients receive from peers and apply locally

    Usage:
        manager = ReplicationManager(
            db=rem_database,
            peer_id="instance-a",
            config_path="./config.json"
        )
        await manager.start()

        # On local write
        entry = WALEntry(...)
        await manager.on_local_write(entry)

        # Shutdown
        await manager.stop()
    """

    def __init__(
        self,
        db,  # REMDatabase instance
        peer_id: str,
        config_path: Optional[str] = None,
        server_address: str = "0.0.0.0:9000",
        encryption_enabled: bool = False,
    ):
        """Initialize replication manager.

        Args:
            db: REMDatabase instance
            peer_id: This instance's peer ID
            config_path: Path to peer configuration file
            server_address: Address for replication server
            encryption_enabled: Whether to enable encryption
        """
        self.db = db
        self.peer_id = peer_id
        self.config_path = config_path
        self.server_address = server_address
        self.encryption_enabled = encryption_enabled

        # Components
        self.server: Optional[ReplicationServer] = None
        self.clients: dict[str, ReplicationClient] = {}
        self.discovery = PeerDiscovery(
            config_path=config_path,
            tenant_id=db.tenant_id if hasattr(db, "tenant_id") else None
        )

        # State
        self.running = False

    async def start(self):
        """Start replication server and connect to all peers.

        Workflow:
        1. Discover peers from configuration
        2. Start replication server
        3. Connect to each peer as client
        4. Begin bidirectional replication
        """
        logger.info(f"Starting replication manager for peer {self.peer_id}")

        # Discover peers (discovery already initialized in __init__)
        peers = await self.discovery.discover_peers()
        logger.info(f"Discovered {len(peers)} peers: {[p.peer_id for p in peers]}")

        # Start server
        self.server = ReplicationServer(
            db=self.db,
            peer_id=self.peer_id,
            bind_address=self.server_address,
            encryption_enabled=self.encryption_enabled,
        )
        await self.server.start()

        # Connect to each peer
        for peer_config in peers:
            await self._connect_to_peer(peer_config)

        self.running = True
        logger.info("Replication manager started")

    async def stop(self):
        """Stop replication server and disconnect all peers.

        Performs graceful shutdown:
        1. Stop accepting new connections
        2. Flush pending entries to peers
        3. Disconnect all clients
        4. Stop server
        """
        logger.info("Stopping replication manager")
        self.running = False

        # Disconnect all clients
        disconnect_tasks = [
            client.disconnect() for client in self.clients.values()
        ]
        await asyncio.gather(*disconnect_tasks, return_exceptions=True)

        # Stop server
        if self.server:
            await self.server.stop()

        logger.info("Replication manager stopped")

    async def on_local_write(self, entry: WALEntry):
        """Handle local database write.

        Broadcasts entry to all connected peers for replication.

        Args:
            entry: WAL entry for local write
        """
        if not self.running or not self.server:
            return

        # Broadcast to all peers via server
        await self.server.broadcast_entry(entry)

    async def _connect_to_peer(self, peer_config: PeerConfig):
        """Connect to a single peer as client.

        Args:
            peer_config: Configuration for peer to connect to
        """
        logger.info(
            f"Connecting to peer {peer_config.peer_id} at {peer_config.address}"
        )

        client = ReplicationClient(
            db=self.db,
            peer_id=self.peer_id,
            peer_config=peer_config,
            encryption_enabled=self.encryption_enabled,
        )

        # Store client
        self.clients[peer_config.peer_id] = client

        # Start subscription in background (don't await)
        async def subscribe_with_logging():
            try:
                logger.info(f"Starting subscription to {peer_config.peer_id}")
                await client.subscribe()
            except Exception as e:
                logger.error(f"Failed to subscribe to {peer_config.peer_id}: {e}", exc_info=True)

        asyncio.create_task(subscribe_with_logging())

    async def get_status(self) -> dict:
        """Get replication status for all peers.

        Returns:
            Dictionary with server and client status
        """
        server_status = await self.server.health_check() if self.server else {}

        client_status = {
            peer_id: {
                "connected": client.connected,
                "watermark": client.watermark,
                "address": client.peer_config.address,
            }
            for peer_id, client in self.clients.items()
        }

        return {
            "running": self.running,
            "peer_id": self.peer_id,
            "server": server_status,
            "clients": client_status,
        }
