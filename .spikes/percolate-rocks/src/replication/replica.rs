//! Replica node for replication (gRPC client).
//!
//! Connects to primary via gRPC and applies WAL entries locally.

#[cfg(feature = "python")]
use crate::replication::protocol::{self, pb};
use crate::replication::{SyncStateMachine, WriteAheadLog};
use crate::types::{DatabaseError, Result};
use std::sync::Arc;
use tokio::sync::RwLock;

#[cfg(feature = "python")]
use tokio_stream::StreamExt;
#[cfg(feature = "python")]
use tonic::transport::Channel;

/// Replica replication node (gRPC client).
///
/// Connects to primary node and streams WAL entries for local application.
///
/// # Example
///
/// ```rust,ignore
/// let storage = Storage::open("./replica")?;
/// let wal = WriteAheadLog::new(storage)?;
/// let replica = ReplicaNode::new(wal, "http://localhost:50051".to_string());
///
/// replica.connect().await?;
/// replica.follow().await?;  // Blocks, continuously syncs
/// ```
pub struct ReplicaNode {
    wal: Arc<RwLock<WriteAheadLog>>,
    primary_host: String,
    sync_state: Arc<RwLock<SyncStateMachine>>,
    #[cfg(feature = "python")]
    client: Option<pb::replication_service_client::ReplicationServiceClient<Channel>>,
}

impl ReplicaNode {
    /// Create new replica node.
    ///
    /// # Arguments
    ///
    /// * `wal` - Local WAL for storing replicated entries
    /// * `primary_host` - Primary node address (e.g., "http://localhost:50051")
    ///
    /// # Returns
    ///
    /// New `ReplicaNode`
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// let wal = WriteAheadLog::new(storage)?;
    /// let replica = ReplicaNode::new(wal, "http://localhost:50051".to_string());
    /// ```
    pub fn new(wal: WriteAheadLog, primary_host: String) -> Self {
        Self {
            wal: Arc::new(RwLock::new(wal)),
            primary_host,
            sync_state: Arc::new(RwLock::new(SyncStateMachine::new())),
            #[cfg(feature = "python")]
            client: None,
        }
    }

    /// Connect to primary and initialize client.
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::ReplicationError` if connection fails
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// replica.connect().await?;
    /// ```
    #[cfg(feature = "python")]
    pub async fn connect(&mut self) -> Result<()> {
        let mut state = self.sync_state.write().await;
        state.start_connecting();

        let client = pb::replication_service_client::ReplicationServiceClient::connect(
            self.primary_host.clone()
        )
        .await
        .map_err(|e| DatabaseError::ReplicationError(format!("Connection failed: {}", e)))?;

        self.client = Some(client);
        state.start_syncing();

        Ok(())
    }

    /// Connect (no-op when python feature disabled).
    #[cfg(not(feature = "python"))]
    pub async fn connect(&mut self) -> Result<()> {
        Err(DatabaseError::ConfigError(
            "gRPC replication requires 'python' feature".to_string()
        ))
    }

    /// Follow primary and apply changes in real-time.
    ///
    /// Blocks until connection is lost or error occurs.
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::ReplicationError` if streaming fails
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// // This blocks and continuously syncs
    /// replica.follow().await?;
    /// ```
    #[cfg(feature = "python")]
    pub async fn follow(&mut self) -> Result<()> {
        let client = self.client.as_mut()
            .ok_or_else(|| DatabaseError::ReplicationError("Not connected".to_string()))?;

        // Get current local position
        let local_seq = {
            let wal = self.wal.read().await;
            wal.current_position()
        };

        // Create subscribe request
        let (tx, rx) = tokio::sync::mpsc::channel(10);
        let outbound = tokio_stream::wrappers::ReceiverStream::new(rx);

        // Send initial subscribe request
        tx.send(pb::SubscribeRequest {
            from_seq: local_seq,
            replica_id: "replica-1".to_string(),
            heartbeat: false,
            ack_seq: 0,
        })
        .await
        .map_err(|e| DatabaseError::ReplicationError(format!("Send failed: {}", e)))?;

        // Start streaming
        let mut stream = client.subscribe(outbound).await
            .map_err(|e| DatabaseError::ReplicationError(format!("Subscribe failed: {}", e)))?
            .into_inner();

        // Process entries
        while let Some(result) = stream.next().await {
            let entry = result
                .map_err(|e| DatabaseError::ReplicationError(format!("Stream error: {}", e)))?;

            // Convert proto to WAL operation
            let op = match entry.op {
                Some(op_proto) => protocol::from_proto_op(op_proto)
                    .map_err(|e| DatabaseError::ReplicationError(e))?,
                None => {
                    return Err(DatabaseError::ReplicationError("Missing operation".to_string()));
                }
            };

            // Apply to local WAL
            let mut wal = self.wal.write().await;
            wal.append(op)?;

            // TODO: Apply to local database (not just WAL)
        }

        // Mark synced
        let mut state = self.sync_state.write().await;
        state.mark_synced();

        Ok(())
    }

    /// Follow (no-op when python feature disabled).
    #[cfg(not(feature = "python"))]
    pub async fn follow(&mut self) -> Result<()> {
        Err(DatabaseError::ConfigError(
            "gRPC replication requires 'python' feature".to_string()
        ))
    }

    /// Get replication status.
    ///
    /// # Returns
    ///
    /// Replication lag and connection state
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// let status = replica.status().await;
    /// println!("Lag: {} entries", status.primary_seq - status.local_seq);
    /// ```
    pub async fn status(&self) -> ReplicationStatus {
        let state = self.sync_state.read().await;
        let wal = self.wal.read().await;

        ReplicationStatus {
            connected: state.state() == crate::replication::sync::SyncState::Synced,
            local_seq: wal.current_position(),
            primary_seq: 0,  // TODO: Query primary for current position
            lag_ms: 0,  // TODO: Calculate replication lag
        }
    }
}

/// Replication status information.
#[derive(Debug, Clone)]
pub struct ReplicationStatus {
    pub connected: bool,
    pub local_seq: u64,
    pub primary_seq: u64,
    pub lag_ms: u64,
}
