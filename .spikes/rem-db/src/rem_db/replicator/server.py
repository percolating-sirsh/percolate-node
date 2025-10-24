"""gRPC replication server implementation.

Serves WAL streams to peer clients for replication.
"""

import asyncio
import logging
from typing import AsyncIterator, Dict, Optional
from dataclasses import dataclass

import grpc
from . import replication_pb2, replication_pb2_grpc
from .servicer import ReplicationServicer

logger = logging.getLogger(__name__)


@dataclass
class WALEntry:
    """Write-Ahead Log entry for replication.

    Represents a single database operation that can be replicated
    to peer instances.
    """

    seq_num: int
    tenant_id: str
    tablespace: str
    operation: str  # "PUT" or "DELETE"
    key: bytes
    value: bytes
    timestamp: int  # Nanoseconds since epoch
    source_peer_id: str


@dataclass
class Watermark:
    """Replication watermark for tracking sync progress."""

    peer_id: str
    seq_num: int  # Last acknowledged sequence number


class ReplicationServer:
    """gRPC server for peer replication streams.

    Responsibilities:
    - Accept peer subscriptions
    - Stream historical WAL entries from watermark
    - Stream real-time WAL entries as they occur
    - Receive and apply peer WAL entries (bidirectional)
    - Track peer watermarks for flow control

    Architecture:
        Each peer connection maintains:
        - Subscription queue for outgoing entries
        - Watermark for resumption
        - Connection state (connected, disconnected)

        The server broadcasts local writes to all connected peers
        and receives writes from peers for local application.

    Usage:
        server = ReplicationServer(
            db=rem_database,
            peer_id="instance-a",
            bind_address="0.0.0.0:9000"
        )
        await server.start()
    """

    def __init__(
        self,
        db,  # REMDatabase instance
        peer_id: str,
        bind_address: str = "0.0.0.0:9000",
        encryption_enabled: bool = False,
    ):
        """Initialize replication server.

        Args:
            db: REMDatabase instance for accessing WAL
            peer_id: This server's peer ID
            bind_address: Address to bind gRPC server
            encryption_enabled: Whether to enable encryption (cross-tenant)
        """
        self.db = db
        self.peer_id = peer_id
        self.bind_address = bind_address
        self.encryption_enabled = encryption_enabled

        # Track connected peers: peer_id -> queue
        self.peer_queues: Dict[str, asyncio.Queue] = {}

        # Track peer watermarks: peer_id -> seq_num
        self.peer_watermarks: Dict[str, int] = {}

        # Server state
        self.running = False
        self.server = None

    async def start(self):
        """Start the gRPC server.

        Starts listening for peer connections and begins
        serving replication streams.
        """
        # Create gRPC server
        self.server = grpc.aio.server()
        replication_pb2_grpc.add_ReplicationServiceServicer_to_server(
            ReplicationServicer(self), self.server
        )
        self.server.add_insecure_port(self.bind_address)
        await self.server.start()

        self.running = True
        logger.info(f"Replication server started on {self.bind_address}")

    async def stop(self):
        """Stop the gRPC server and disconnect all peers."""
        self.running = False

        # Clear peer queues
        for queue in self.peer_queues.values():
            # Signal shutdown
            await queue.put(None)

        self.peer_queues.clear()

        if self.server:
            await self.server.stop(grace=5.0)
            logger.info("Replication server stopped")

    async def stream_wal(
        self, request_iterator: AsyncIterator
    ) -> AsyncIterator:
        """Bidirectional streaming RPC for WAL replication.

        This is the core replication method. Handles:
        1. Peer subscription with watermark
        2. Historical entry streaming (catchup)
        3. Real-time entry streaming
        4. Receiving peer entries for local application
        5. ACK handling for flow control

        Args:
            request_iterator: Stream of WALRequest messages from peer

        Yields:
            WALResponse messages (Connected, HistoricalBatch, Entry, Error)
        """
        peer_id = None
        peer_queue = asyncio.Queue(maxsize=1000)

        try:
            # Process first request (subscribe)
            first_request = await request_iterator.__anext__()

            # Extract subscription info
            # subscribe = first_request.subscribe
            # peer_id = subscribe.peer_id
            # tenant_id = subscribe.tenant_id
            # watermark = subscribe.watermark

            # TODO: Authenticate peer

            # Register peer connection
            # self.peer_queues[peer_id] = peer_queue
            # self.peer_watermarks[peer_id] = watermark

            # Send connection response
            # yield ConnectedResponse(
            #     current_seq=self.db.get_current_seq(),
            #     server_peer_id=self.peer_id
            # )

            # Stream historical entries (catchup)
            # if watermark < self.db.get_current_seq():
            #     async for batch in self._get_historical_entries(watermark):
            #         yield HistoricalBatch(entries=batch)

            # Stream real-time entries + receive peer entries
            # async def send_realtime():
            #     while self.running:
            #         entry = await peer_queue.get()
            #         if entry is None:
            #             break
            #         yield Entry(entry=entry)
            #
            # async def receive_peer_entries():
            #     async for request in request_iterator:
            #         if request.HasField("push_entry"):
            #             await self._apply_peer_entry(request.push_entry)
            #         elif request.HasField("ack"):
            #             self.peer_watermarks[peer_id] = request.ack.seq_num

            # Run both concurrently
            # await asyncio.gather(send_realtime(), receive_peer_entries())

            pass  # Stub for now

        except Exception as e:
            logger.error(f"Error in stream_wal for peer {peer_id}: {e}")
            # yield ErrorResponse(code="INTERNAL_ERROR", message=str(e))

        finally:
            # Cleanup peer connection
            if peer_id:
                self.peer_queues.pop(peer_id, None)
                logger.info(f"Peer {peer_id} disconnected")

    async def broadcast_entry(self, entry: WALEntry):
        """Broadcast WAL entry to all connected peers.

        Called when local database writes occur. Sends the entry
        to all active peer connections for replication.

        Args:
            entry: WAL entry to broadcast
        """
        for peer_id, queue in self.peer_queues.items():
            try:
                # Non-blocking put - drop if queue full
                queue.put_nowait(entry)
            except asyncio.QueueFull:
                logger.warning(
                    f"Peer {peer_id} queue full, dropping entry {entry.seq_num}"
                )

    async def _get_historical_entries(
        self, start_seq: int
    ) -> AsyncIterator[list[WALEntry]]:
        """Get historical WAL entries for catchup.

        Yields batches of historical entries from start_seq to current.
        Batches are limited to 100 entries for efficient streaming.

        Args:
            start_seq: Starting sequence number (exclusive)

        Yields:
            Lists of WALEntry objects (batches of 100)
        """
        # TODO: Query database for entries > start_seq
        # current_seq = self.db.get_current_seq()
        # batch_size = 100
        #
        # for seq in range(start_seq + 1, current_seq + 1, batch_size):
        #     batch = self.db.get_wal_entries(seq, seq + batch_size)
        #     yield batch

        return
        yield  # Make it a generator

    async def _apply_peer_entry(self, entry: WALEntry):
        """Apply WAL entry received from peer.

        Handles conflict resolution and writes entry to local database.

        Args:
            entry: WAL entry from peer to apply locally
        """
        # TODO: Apply to local database with conflict resolution
        # if entry.operation == "PUT":
        #     self.db.put(entry.key, entry.value, entry.timestamp)
        # elif entry.operation == "DELETE":
        #     self.db.delete(entry.key, entry.timestamp)

        logger.debug(
            f"Applied peer entry {entry.seq_num} from {entry.source_peer_id}"
        )

    async def health_check(self) -> dict:
        """Get server health status.

        Returns:
            Dictionary with health status, current seq, and peer info
        """
        return {
            "healthy": self.running,
            "current_seq": 0,  # TODO: self.db.get_current_seq(),
            "peers": [
                {
                    "peer_id": peer_id,
                    "watermark": self.peer_watermarks.get(peer_id, 0),
                    "connected": peer_id in self.peer_queues,
                }
                for peer_id in self.peer_watermarks.keys()
            ],
        }
