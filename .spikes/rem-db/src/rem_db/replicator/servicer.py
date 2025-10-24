"""gRPC servicer implementation for ReplicationService."""

import asyncio
import logging
from . import replication_pb2, replication_pb2_grpc

logger = logging.getLogger(__name__)


class ReplicationServicer(replication_pb2_grpc.ReplicationServiceServicer):
    """Implements the ReplicationService gRPC API."""

    def __init__(self, server):
        """Initialize servicer with ReplicationServer instance.

        Args:
            server: ReplicationServer instance
        """
        self.server = server

    async def StreamWAL(self, request_iterator, context):
        """Bidirectional streaming RPC for WAL replication.

        Handles:
        1. Initial subscription with watermark
        2. Historical entries (catchup)
        3. Real-time streaming
        4. Receiving peer entries

        Args:
            request_iterator: Stream of WALRequest from peer
            context: gRPC context

        Yields:
            WALResponse messages
        """
        peer_id = None
        peer_queue = asyncio.Queue(maxsize=1000)

        try:
            # Get first request (subscription)
            first_request = await request_iterator.__anext__()

            if not first_request.HasField("subscribe"):
                yield replication_pb2.WALResponse(
                    error=replication_pb2.ErrorResponse(
                        code="INVALID_REQUEST",
                        message="First request must be subscribe",
                        retryable=False
                    )
                )
                return

            subscribe = first_request.subscribe
            peer_id = subscribe.peer_id
            watermark = subscribe.watermark

            logger.info(f"Peer {peer_id} subscribing with watermark {watermark}")

            # Register peer
            self.server.peer_queues[peer_id] = peer_queue
            self.server.peer_watermarks[peer_id] = watermark

            # Send connection response
            current_seq = self.server.db.get_current_seq() if hasattr(self.server.db, 'get_current_seq') else 0
            yield replication_pb2.WALResponse(
                connected=replication_pb2.ConnectedResponse(
                    current_seq=current_seq,
                    server_peer_id=self.server.peer_id,
                    server_timestamp=0  # TODO: time.time_ns()
                )
            )

            # Send historical entries if needed
            if watermark < current_seq:
                logger.info(f"Sending historical entries from {watermark} to {current_seq}")
                async for batch_response in self._stream_historical(watermark, current_seq):
                    yield batch_response

            # Start receive task in background
            async def receive_peer_entries():
                """Receive entries from peer."""
                try:
                    async for request in request_iterator:
                        if request.HasField("push_entry"):
                            # Apply peer entry to local DB
                            pb_entry = request.push_entry
                            await self._apply_peer_entry(pb_entry)

                        elif request.HasField("ack"):
                            # Update watermark
                            self.server.peer_watermarks[peer_id] = request.ack.seq_num
                except Exception as e:
                    logger.error(f"Error receiving from peer {peer_id}: {e}")

            receive_task = asyncio.create_task(receive_peer_entries())

            # Stream real-time entries to peer
            while self.server.running:
                try:
                    entry = await asyncio.wait_for(peer_queue.get(), timeout=30.0)
                    if entry is None:
                        break

                    # Convert WALEntry to protobuf
                    pb_entry = replication_pb2.WALEntry(
                        seq_num=entry.seq_num,
                        tenant_id=entry.tenant_id,
                        tablespace=entry.tablespace,
                        operation=entry.operation,
                        key=entry.key,
                        value=entry.value,
                        timestamp=entry.timestamp,
                        source_peer_id=entry.source_peer_id
                    )
                    yield replication_pb2.WALResponse(entry=pb_entry)

                except asyncio.TimeoutError:
                    # Timeout - keep connection alive
                    continue

            # Wait for receive to complete
            receive_task.cancel()
            try:
                await receive_task
            except asyncio.CancelledError:
                pass

        except Exception as e:
            logger.error(f"Error in StreamWAL for peer {peer_id}: {e}", exc_info=True)
            yield replication_pb2.WALResponse(
                error=replication_pb2.ErrorResponse(
                    code="INTERNAL_ERROR",
                    message=str(e),
                    retryable=True
                )
            )

        finally:
            # Cleanup
            if peer_id:
                self.server.peer_queues.pop(peer_id, None)
                logger.info(f"Peer {peer_id} disconnected")

    async def _stream_historical(self, start_seq, end_seq):
        """Stream historical WAL entries in batches.

        Args:
            start_seq: Starting sequence (exclusive)
            end_seq: Ending sequence (inclusive)

        Yields:
            WALResponse with HistoricalBatch
        """
        batch_size = 100
        current = start_seq + 1

        while current <= end_seq:
            # Get batch from database
            if hasattr(self.server.db, 'get_wal_entries'):
                entries_data = self.server.db.get_wal_entries(
                    start_seq=current - 1,
                    end_seq=min(current + batch_size - 1, end_seq),
                    limit=batch_size
                )
            else:
                entries_data = []

            if not entries_data:
                break

            # Convert to protobuf
            pb_entries = []
            for entry_data in entries_data:
                pb_entry = replication_pb2.WALEntry(
                    seq_num=entry_data["seq_num"],
                    tenant_id=entry_data["tenant_id"],
                    tablespace=entry_data["tablespace"],
                    operation=entry_data["operation"],
                    key=bytes.fromhex(entry_data["key"]),
                    value=bytes.fromhex(entry_data["value"]),
                    timestamp=entry_data["timestamp"],
                    source_peer_id=self.server.peer_id
                )
                pb_entries.append(pb_entry)

            # Send batch
            batch_start = pb_entries[0].seq_num if pb_entries else current
            batch_end = pb_entries[-1].seq_num if pb_entries else current
            has_more = batch_end < end_seq

            yield replication_pb2.WALResponse(
                historical=replication_pb2.HistoricalBatch(
                    entries=pb_entries,
                    batch_start=batch_start,
                    batch_end=batch_end,
                    has_more=has_more
                )
            )

            current = batch_end + 1

    async def _apply_peer_entry(self, pb_entry):
        """Apply entry from peer to local database.

        Args:
            pb_entry: replication_pb2.WALEntry from peer
        """
        try:
            # Apply to local database
            if hasattr(self.server.db, '_append_wal'):
                self.server.db._append_wal(
                    operation=pb_entry.operation,
                    key=pb_entry.key,
                    value=pb_entry.value,
                    tablespace=pb_entry.tablespace
                )
                logger.info(
                    f"Applied peer entry seq={pb_entry.seq_num} "
                    f"operation={pb_entry.operation} from {pb_entry.source_peer_id}"
                )
            else:
                logger.warning("Database does not support WAL append")
        except Exception as e:
            logger.error(f"Failed to apply peer entry: {e}", exc_info=True)

    async def _run_send_stream(self, generator):
        """Helper to run async generator and yield results."""
        async for item in generator:
            yield item

    async def HealthCheck(self, request, context):
        """Health check RPC.

        Args:
            request: HealthRequest
            context: gRPC context

        Returns:
            HealthResponse
        """
        status = await self.server.health_check()

        peer_statuses = [
            replication_pb2.PeerStatus(
                peer_id=p["peer_id"],
                watermark=p["watermark"],
                last_seen=0,  # TODO: track timestamps
                connected=p["connected"]
            )
            for p in status.get("peers", [])
        ]

        return replication_pb2.HealthResponse(
            healthy=status["healthy"],
            current_seq=status["current_seq"],
            server_timestamp=0,  # TODO: time.time_ns()
            peers=peer_statuses
        )
