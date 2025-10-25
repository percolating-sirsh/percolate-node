//! Integration tests for multi-peer replication.
//!
//! Tests replication scenarios with primary and multiple replicas.

#[cfg(feature = "python")]
mod replication_tests {
    use percolate_rocks::replication::{PrimaryNode, ReplicaNode, WriteAheadLog, WalOperation};
    use percolate_rocks::storage::Storage;
    use std::time::Duration;
    use tokio::time::sleep;

    /// Test basic replication: Primary → Replica.
    #[tokio::test]
    async fn test_basic_replication() {
        // Setup primary
        let primary_storage = Storage::open_temp().unwrap();
        let mut primary_wal = WriteAheadLog::new(primary_storage).unwrap();

        // Insert some data on primary
        let op1 = WalOperation::Insert {
            tenant_id: "tenant-1".to_string(),
            entity: serde_json::json!({"name": "Alice"}),
        };
        let op2 = WalOperation::Insert {
            tenant_id: "tenant-1".to_string(),
            entity: serde_json::json!({"name": "Bob"}),
        };

        primary_wal.append(op1).unwrap();
        primary_wal.append(op2).unwrap();

        // Start primary server
        let primary = PrimaryNode::new(primary_wal, 50051);
        tokio::spawn(async move {
            primary.serve().await.unwrap();
        });

        // Wait for server to start
        sleep(Duration::from_millis(100)).await;

        // Setup replica
        let replica_storage = Storage::open_temp().unwrap();
        let replica_wal = WriteAheadLog::new(replica_storage).unwrap();
        let mut replica = ReplicaNode::new(replica_wal, "http://localhost:50051".to_string());

        // Connect and follow
        replica.connect().await.unwrap();

        tokio::spawn(async move {
            replica.follow().await.unwrap();
        });

        // Wait for replication
        sleep(Duration::from_secs(1)).await;

        // TODO: Verify replica has both entries
        // let status = replica.status().await;
        // assert_eq!(status.local_seq, 2);
    }

    /// Test multi-replica: Primary → Replica1 + Replica2.
    #[tokio::test]
    async fn test_multi_replica() {
        // Setup primary
        let primary_storage = Storage::open_temp().unwrap();
        let mut primary_wal = WriteAheadLog::new(primary_storage).unwrap();

        // Insert data
        for i in 0..10 {
            let op = WalOperation::Insert {
                tenant_id: "tenant-1".to_string(),
                entity: serde_json::json!({"id": i, "name": format!("User {}", i)}),
            };
            primary_wal.append(op).unwrap();
        }

        // Start primary
        let primary = PrimaryNode::new(primary_wal, 50052);
        tokio::spawn(async move {
            primary.serve().await.unwrap();
        });

        sleep(Duration::from_millis(100)).await;

        // Setup replica 1
        let replica1_storage = Storage::open_temp().unwrap();
        let replica1_wal = WriteAheadLog::new(replica1_storage).unwrap();
        let mut replica1 = ReplicaNode::new(replica1_wal, "http://localhost:50052".to_string());

        // Setup replica 2
        let replica2_storage = Storage::open_temp().unwrap();
        let replica2_wal = WriteAheadLog::new(replica2_storage).unwrap();
        let mut replica2 = ReplicaNode::new(replica2_wal, "http://localhost:50052".to_string());

        // Connect both replicas
        replica1.connect().await.unwrap();
        replica2.connect().await.unwrap();

        // Follow concurrently
        let handle1 = tokio::spawn(async move {
            replica1.follow().await.unwrap();
        });

        let handle2 = tokio::spawn(async move {
            replica2.follow().await.unwrap();
        });

        // Wait for replication
        sleep(Duration::from_secs(1)).await;

        // TODO: Verify both replicas have all 10 entries
        // assert_eq!(replica1.status().await.local_seq, 10);
        // assert_eq!(replica2.status().await.local_seq, 10);

        // Cleanup
        handle1.abort();
        handle2.abort();
    }

    /// Test replica catchup: Replica starts behind and catches up.
    #[tokio::test]
    async fn test_replica_catchup() {
        // Setup primary with existing data
        let primary_storage = Storage::open_temp().unwrap();
        let mut primary_wal = WriteAheadLog::new(primary_storage).unwrap();

        // Insert 5 entries before replica connects
        for i in 0..5 {
            let op = WalOperation::Insert {
                tenant_id: "tenant-1".to_string(),
                entity: serde_json::json!({"id": i}),
            };
            primary_wal.append(op).unwrap();
        }

        // Start primary
        let primary = PrimaryNode::new(primary_wal, 50053);
        tokio::spawn(async move {
            primary.serve().await.unwrap();
        });

        sleep(Duration::from_millis(100)).await;

        // Setup replica (starts from seq=0)
        let replica_storage = Storage::open_temp().unwrap();
        let replica_wal = WriteAheadLog::new(replica_storage).unwrap();
        let mut replica = ReplicaNode::new(replica_wal, "http://localhost:50053".to_string());

        replica.connect().await.unwrap();

        tokio::spawn(async move {
            replica.follow().await.unwrap();
        });

        // Wait for catchup
        sleep(Duration::from_secs(1)).await;

        // TODO: Verify replica has all 5 entries
    }
}

#[cfg(not(feature = "python"))]
mod replication_tests {
    #[test]
    fn test_replication_requires_python_feature() {
        // No-op when python feature is disabled
        println!("Replication tests require 'python' feature");
    }
}
