//! Replica node for replication (gRPC client).

use crate::types::Result;
use crate::storage::Storage;

/// Replica replication node (gRPC client).
pub struct ReplicaNode {
    storage: Storage,
    primary_host: String,
    local_seq: u64,
}

impl ReplicaNode {
    /// Create new replica node.
    ///
    /// # Arguments
    ///
    /// * `storage` - Local storage
    /// * `primary_host` - Primary node address (host:port)
    ///
    /// # Returns
    ///
    /// New `ReplicaNode`
    pub fn new(storage: Storage, primary_host: String) -> Self {
        todo!("Implement ReplicaNode::new")
    }

    /// Connect to primary and sync initial state.
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::ReplicationError` if connection fails
    pub async fn connect(&mut self) -> Result<()> {
        todo!("Implement ReplicaNode::connect")
    }

    /// Follow primary and apply changes in real-time.
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::ReplicationError` if streaming fails
    pub async fn follow(&mut self) -> Result<()> {
        todo!("Implement ReplicaNode::follow")
    }

    /// Get replication status.
    ///
    /// # Returns
    ///
    /// Replication lag and connection state
    pub fn status(&self) -> ReplicationStatus {
        todo!("Implement ReplicaNode::status")
    }
}

/// Replication status information.
#[derive(Debug)]
pub struct ReplicationStatus {
    pub connected: bool,
    pub local_seq: u64,
    pub primary_seq: u64,
    pub lag_ms: u64,
}
