//! Primary node for replication (gRPC server).

use crate::types::Result;
use crate::replication::WriteAheadLog;

/// Primary replication node (gRPC server).
pub struct PrimaryNode {
    wal: WriteAheadLog,
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
    pub fn new(wal: WriteAheadLog, port: u16) -> Self {
        todo!("Implement PrimaryNode::new")
    }

    /// Start gRPC replication server.
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::ReplicationError` if server fails to start
    pub async fn serve(&self) -> Result<()> {
        todo!("Implement PrimaryNode::serve")
    }

    /// Get WAL status.
    ///
    /// # Returns
    ///
    /// Current WAL position and stats
    pub fn wal_status(&self) -> WalStatus {
        todo!("Implement PrimaryNode::wal_status")
    }
}

/// WAL status information.
#[derive(Debug)]
pub struct WalStatus {
    pub sequence: u64,
    pub entries: usize,
    pub size_bytes: usize,
}
