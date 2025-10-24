"""gRPC replication client implementation.

Subscribes to peer WAL streams for replication.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

import grpc
from . import replication_pb2, replication_pb2_grpc
from .peer import PeerConfig
from .server import WALEntry

logger = logging.getLogger(__name__)


class ReplicationClient:
    """gRPC client for subscribing to peer replication streams.

    Responsibilities:
    - Connect to configured peers
    - Subscribe to peer WAL streams
    - Apply incoming WAL entries to local database
    - Push local entries to peer (bidirectional)
    - Track and persist watermarks for resumption

    Usage:
        client = ReplicationClient(
            db=rem_database,
            peer_id="instance-b",
            peer_config=peer_config
        )
        await client.subscribe()
    """

    def __init__(
        self,
        db,  # REMDatabase instance
        peer_id: str,
        peer_config: PeerConfig,
        encryption_enabled: bool = False,
    ):
        """Initialize replication client.

        Args:
            db: REMDatabase instance for applying entries
            peer_id: This client's peer ID
            peer_config: Configuration for the peer to connect to
            encryption_enabled: Whether encryption is enabled
        """
        self.db = db
        self.peer_id = peer_id
        self.peer_config = peer_config
        self.encryption_enabled = encryption_enabled

        # Connection state
        self.connected = False
        self.channel = None
        self.stub = None

        # Watermark tracking
        self.watermark = 0  # Last processed seq_num
        self.watermark_file = Path(f"./.watermarks/{peer_config.peer_id}")

    async def subscribe(self):
        """Subscribe to peer's WAL stream.

        Establishes connection, requests historical catchup from watermark,
        and streams real-time updates. Runs until stopped or disconnected.
        """
        try:
            # Load last watermark from disk
            self.watermark = await self._load_watermark()

            # Create gRPC channel
            self.channel = grpc.aio.insecure_channel(self.peer_config.address)
            self.stub = replication_pb2_grpc.ReplicationServiceStub(self.channel)

            # Create bidirectional stream
            async def request_generator():
                # Send initial subscribe request
                yield replication_pb2.WALRequest(
                    subscribe=replication_pb2.SubscribeRequest(
                        peer_id=self.peer_id,
                        tenant_id=self.peer_config.tenant_id,
                        tablespaces=self.peer_config.tablespaces,
                        watermark=self.watermark,
                        encryption_enabled=self.encryption_enabled,
                        auth_token=b""
                    )
                )

                # Keep connection alive with heartbeats
                while self.connected:
                    await asyncio.sleep(30)
                    # Send ACK
                    yield replication_pb2.WALRequest(
                        ack=replication_pb2.AckRequest(seq_num=self.watermark)
                    )

            response_stream = self.stub.StreamWAL(request_generator())

            self.connected = True
            logger.info(
                f"Connected to peer {self.peer_config.peer_id} at {self.peer_config.address}"
            )

            # Process responses
            async for response in response_stream:
                if response.HasField("connected"):
                    await self._handle_connected(response.connected)
                elif response.HasField("historical"):
                    await self._handle_historical_batch(response.historical)
                elif response.HasField("entry"):
                    await self._handle_entry(response.entry)
                elif response.HasField("error"):
                    await self._handle_error(response.error)

        except Exception as e:
            logger.error(f"Error subscribing to peer {self.peer_config.peer_id}: {e}", exc_info=True)
            self.connected = False
            # Retry with exponential backoff
            await self._reconnect_with_backoff()

    async def disconnect(self):
        """Disconnect from peer and cleanup resources."""
        self.connected = False

        if self.channel:
            await self.channel.close()
            logger.info(f"Disconnected from peer {self.peer_config.peer_id}")

    async def _handle_connected(self, response):
        """Handle connection response from peer.

        Args:
            response: ConnectedResponse message
        """
        current_seq = response.current_seq
        logger.info(
            f"Peer {response.server_peer_id} current seq: {current_seq}, "
            f"our watermark: {self.watermark}"
        )

    async def _handle_historical_batch(self, batch):
        """Handle batch of historical entries.

        Args:
            batch: HistoricalBatch message with entries
        """
        logger.info(
            f"Receiving historical batch [{batch.batch_start}-{batch.batch_end}]"
        )

        for entry in batch.entries:
            await self._apply_entry(entry)

        # Update watermark after batch
        await self._save_watermark(batch.batch_end)

    async def _handle_entry(self, entry: WALEntry):
        """Handle single real-time entry.

        Args:
            entry: WALEntry to apply
        """
        await self._apply_entry(entry)
        await self._save_watermark(entry.seq_num)

    async def _handle_error(self, error):
        """Handle error from peer.

        Args:
            error: ErrorResponse message
        """
        logger.error(f"Error from peer: {error.code} - {error.message}")

        if error.retryable:
            # Retry connection
            await self._reconnect_with_backoff()
        else:
            # Fatal error - disconnect
            await self.disconnect()

    async def _apply_entry(self, entry):
        """Apply WAL entry to local database.

        Handles conflict resolution and database writes.

        Args:
            entry: replication_pb2.WALEntry to apply
        """
        try:
            # Apply to local database
            if hasattr(self.db, '_append_wal'):
                self.db._append_wal(
                    operation=entry.operation,
                    key=entry.key,
                    value=entry.value,
                    tablespace=entry.tablespace
                )
                logger.info(
                    f"Applied entry seq={entry.seq_num} "
                    f"from peer {entry.source_peer_id}"
                )
            else:
                logger.warning("Database does not support WAL append")
        except Exception as e:
            logger.error(f"Failed to apply entry: {e}", exc_info=True)

    async def _load_watermark(self) -> int:
        """Load last watermark from disk.

        Returns:
            Last processed sequence number (0 if none)
        """
        if self.watermark_file.exists():
            try:
                content = self.watermark_file.read_text().strip()
                return int(content)
            except Exception as e:
                logger.warning(f"Failed to load watermark: {e}")
                return 0
        return 0

    async def _save_watermark(self, seq_num: int):
        """Save watermark to disk atomically.

        Args:
            seq_num: Sequence number to checkpoint
        """
        # Create directory if needed
        self.watermark_file.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write
        temp_file = self.watermark_file.with_suffix(".tmp")
        temp_file.write_text(str(seq_num))

        # Atomic rename
        temp_file.replace(self.watermark_file)

        self.watermark = seq_num

    async def _reconnect_with_backoff(self):
        """Reconnect with exponential backoff."""
        backoff = 1
        max_backoff = 60

        while not self.connected and backoff <= max_backoff:
            logger.info(f"Reconnecting in {backoff}s...")
            await asyncio.sleep(backoff)

            try:
                await self.subscribe()
                break
            except Exception as e:
                logger.error(f"Reconnection failed: {e}")
                backoff = min(backoff * 2, max_backoff)
