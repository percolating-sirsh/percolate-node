//! Primary node for replication (gRPC server).
//!
//! Implements gRPC service to stream WAL entries to replicas.

#[cfg(feature = "python")]
use crate::replication::protocol::{self, pb};
use crate::replication::WriteAheadLog;
use crate::types::{DatabaseError, Result};
use std::sync::Arc;
use tokio::sync::RwLock;

#[cfg(feature = "python")]
use tokio_stream::wrappers::ReceiverStream;
#[cfg(feature = "python")]
use tonic::{transport::Server, Request, Response, Status};

/// Primary replication node (gRPC server).
///
/// Exposes WAL entries via gRPC streaming for replicas to consume.
///
/// # Example
///
/// ```rust,ignore
/// let storage = Storage::open("./primary")?;
/// let wal = WriteAheadLog::new(storage)?;
/// let primary = PrimaryNode::new(wal, 50051);
///
/// // Start server (blocks)
/// primary.serve().await?;
/// ```
pub struct PrimaryNode {
    wal: Arc<RwLock<WriteAheadLog>>,
    port: u16,
}

impl PrimaryNode {
    /// Create new primary node.
    ///
    /// # Arguments
    ///
    /// * `wal` - Write-ahead log
    /// * `port` - gRPC server port
    ///
    /// # Returns
    ///
    /// New `PrimaryNode`
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// let wal = WriteAheadLog::new(storage)?;
    /// let primary = PrimaryNode::new(wal, 50051);
    /// ```
    pub fn new(wal: WriteAheadLog, port: u16) -> Self {
        Self {
            wal: Arc::new(RwLock::new(wal)),
            port,
        }
    }

    /// Start gRPC replication server.
    ///
    /// Blocks until server is stopped.
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::ReplicationError` if server fails to start
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// primary.serve().await?;
    /// ```
    #[cfg(feature = "python")]
    pub async fn serve(&self) -> Result<()> {
        let addr = format!("0.0.0.0:{}", self.port).parse()
            .map_err(|e| DatabaseError::ReplicationError(format!("Invalid address: {}", e)))?;

        let service = ReplicationServiceImpl {
            wal: self.wal.clone(),
        };

        Server::builder()
            .add_service(pb::replication_service_server::ReplicationServiceServer::new(service))
            .serve(addr)
            .await
            .map_err(|e| DatabaseError::ReplicationError(format!("Server failed: {}", e)))?;

        Ok(())
    }

    /// Start server (no-op when python feature disabled).
    #[cfg(not(feature = "python"))]
    pub async fn serve(&self) -> Result<()> {
        Err(DatabaseError::ConfigError(
            "gRPC replication requires 'python' feature".to_string()
        ))
    }

    /// Get WAL status.
    ///
    /// # Returns
    ///
    /// Current WAL position and stats
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// let status = primary.wal_status().await;
    /// println!("Current sequence: {}", status.sequence);
    /// ```
    pub async fn wal_status(&self) -> WalStatus {
        let wal = self.wal.read().await;
        WalStatus {
            sequence: wal.current_position(),
            entries: 0,  // TODO: Track entry count
            size_bytes: 0,  // TODO: Track size
        }
    }
}

/// WAL status information.
#[derive(Debug, Clone)]
pub struct WalStatus {
    pub sequence: u64,
    pub entries: usize,
    pub size_bytes: usize,
}

/// gRPC service implementation.
#[cfg(feature = "python")]
struct ReplicationServiceImpl {
    wal: Arc<RwLock<WriteAheadLog>>,
}

#[cfg(feature = "python")]
#[tonic::async_trait]
impl pb::replication_service_server::ReplicationService for ReplicationServiceImpl {
    type SubscribeStream = ReceiverStream<std::result::Result<pb::WalEntryProto, Status>>;

    async fn subscribe(
        &self,
        request: Request<tonic::Streaming<pb::SubscribeRequest>>,
    ) -> std::result::Result<Response<Self::SubscribeStream>, Status> {
        let mut stream = request.into_inner();
        let wal = self.wal.clone();

        let (tx, rx) = tokio::sync::mpsc::channel(100);

        // Spawn task to handle streaming
        tokio::spawn(async move {
            let mut from_seq = 0u64;

            while let Ok(Some(req)) = stream.message().await {
                if req.heartbeat {
                    // Ignore heartbeats for now
                    continue;
                }

                // Update from_seq if replica sends new position
                if req.from_seq > 0 {
                    from_seq = req.from_seq;
                }

                // Stream entries after from_seq
                let wal_read = wal.read().await;
                let entries = match wal_read.get_entries_after(from_seq, 100) {
                    Ok(entries) => entries,
                    Err(e) => {
                        let _ = tx.send(Err(Status::internal(format!("WAL error: {}", e)))).await;
                        break;
                    }
                };

                // Send each entry
                for entry in entries {
                    let proto = pb::WalEntryProto {
                        seq: entry.seq,
                        op: Some(protocol::to_proto_op(&entry.op)),
                        timestamp: entry.timestamp,
                    };

                    if tx.send(Ok(proto)).await.is_err() {
                        // Client disconnected
                        break;
                    }

                    from_seq = entry.seq;
                }
            }
        });

        Ok(Response::new(ReceiverStream::new(rx)))
    }

    async fn get_status(
        &self,
        _request: Request<pb::StatusRequest>,
    ) -> std::result::Result<Response<pb::StatusResponse>, Status> {
        let wal = self.wal.read().await;
        let response = pb::StatusResponse {
            current_seq: wal.current_position(),
            replica_count: 0,  // TODO: Track connected replicas
            entry_count: 0,  // TODO: Track entry count
            healthy: true,
        };

        Ok(Response::new(response))
    }
}
