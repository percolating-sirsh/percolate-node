"""Peer discovery and configuration management.

This module handles:
- Peer configuration loading (file, database, environment)
- Peer health checking
- Peer registry updates
"""

from dataclasses import dataclass
from typing import Optional
import json
import os
from pathlib import Path


@dataclass
class PeerConfig:
    """Configuration for a replication peer.

    Attributes:
        peer_id: Unique identifier for the peer instance
        address: Network address (host:port) for gRPC connection
        tenant_id: Tenant scope for replication
        tablespaces: List of tablespaces to replicate (["*"] for all)
        mode: Replication mode ("bidirectional", "pull", "push")
        encryption_enabled: Whether to use encryption (cross-tenant only)
    """

    peer_id: str
    address: str
    tenant_id: str
    tablespaces: list[str] = None
    mode: str = "bidirectional"
    encryption_enabled: bool = False

    def __post_init__(self):
        if self.tablespaces is None:
            self.tablespaces = ["*"]  # All tablespaces by default

    @classmethod
    def from_dict(cls, data: dict) -> "PeerConfig":
        """Create PeerConfig from dictionary."""
        return cls(
            peer_id=data["peer_id"],
            address=data["address"],
            tenant_id=data["tenant_id"],
            tablespaces=data.get("tablespaces", ["*"]),
            mode=data.get("mode", "bidirectional"),
            encryption_enabled=data.get("encryption_enabled", False),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "peer_id": self.peer_id,
            "address": self.address,
            "tenant_id": self.tenant_id,
            "tablespaces": self.tablespaces,
            "mode": self.mode,
            "encryption_enabled": self.encryption_enabled,
        }


class PeerDiscovery:
    """Discover and manage peer connections.

    Supports multiple discovery methods:
    1. Config file (static peer list)
    2. Database state (dynamic peer registry)
    3. Environment variables (for testing)

    Usage:
        discovery = PeerDiscovery(
            config_path="./config.json",
            tenant_id="tenant-1"
        )
        peers = await discovery.discover_peers()
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        tenant_id: Optional[str] = None,
        db_path: Optional[str] = None,
    ):
        """Initialize peer discovery.

        Args:
            config_path: Path to JSON config file
            tenant_id: Tenant ID for filtering peers
            db_path: Path to database for peer registry
        """
        self.config_path = config_path
        self.tenant_id = tenant_id
        self.db_path = db_path
        self._peers: list[PeerConfig] = []

    async def discover_peers(self) -> list[PeerConfig]:
        """Discover peers from all sources.

        Returns:
            List of PeerConfig objects for active peers

        Priority order:
        1. Manually added peers (via add_peer)
        2. Environment variables
        3. Config file
        4. Database registry
        """
        # Start with manually added peers
        peers = list(self._peers)

        # 1. Load from environment
        env_peers = self._load_from_env()
        if env_peers:
            peers.extend(env_peers)

        # 2. Load from config file
        if self.config_path and not env_peers:
            file_peers = self._load_from_file()
            peers.extend(file_peers)

        # 3. Load from database (future)
        # if self.db_path and not peers:
        #     db_peers = await self._load_from_db()
        #     peers.extend(db_peers)

        # Filter by tenant if specified
        if self.tenant_id:
            peers = [p for p in peers if p.tenant_id == self.tenant_id]

        self._peers = peers
        return peers

    def _load_from_env(self) -> list[PeerConfig]:
        """Load peers from environment variables.

        Format:
            REM_REPLICATION_PEERS=peer1@host1:port1,peer2@host2:port2
            REM_REPLICATION_TENANT_ID=tenant-1
        """
        peers_str = os.getenv("REM_REPLICATION_PEERS")
        if not peers_str:
            return []

        tenant_id = os.getenv("REM_REPLICATION_TENANT_ID", self.tenant_id or "default")

        peers = []
        for peer_def in peers_str.split(","):
            peer_def = peer_def.strip()
            if "@" not in peer_def:
                continue

            peer_id, address = peer_def.split("@", 1)
            peers.append(
                PeerConfig(
                    peer_id=peer_id,
                    address=address,
                    tenant_id=tenant_id,
                    tablespaces=["*"],
                    mode="bidirectional",
                )
            )

        return peers

    def _load_from_file(self) -> list[PeerConfig]:
        """Load peers from JSON config file.

        Expected format:
        {
          "replication": {
            "peers": [
              {
                "peer_id": "instance-a",
                "address": "localhost:9000",
                "tenant_id": "tenant-1",
                "tablespaces": ["*"],
                "mode": "bidirectional"
              }
            ]
          }
        }
        """
        if not self.config_path:
            return []

        config_file = Path(self.config_path)
        if not config_file.exists():
            return []

        with open(config_file) as f:
            config = json.load(f)

        replication_config = config.get("replication", {})
        peers_data = replication_config.get("peers", [])

        return [PeerConfig.from_dict(p) for p in peers_data]

    def get_peers(self) -> list[PeerConfig]:
        """Get cached list of peers."""
        return self._peers

    def add_peer(self, peer: PeerConfig):
        """Add a peer to the discovery list."""
        if peer not in self._peers:
            self._peers.append(peer)

    def remove_peer(self, peer_id: str):
        """Remove a peer from the discovery list."""
        self._peers = [p for p in self._peers if p.peer_id != peer_id]
