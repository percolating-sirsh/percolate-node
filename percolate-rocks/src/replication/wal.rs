//! Write-ahead log for replication durability.
//!
//! WAL stores all write operations for replication and crash recovery.
//! Entries are stored in RocksDB WAL column family with sequence numbers as keys.
//!
//! # Encryption (TODO)
//!
//! **Current**: WAL entries stored unencrypted
//!
//! **Planned**:
//! - WAL entries encrypted before storage and replication
//! - Encryption key derived from tenant's key pair
//! - Ensures WAL is encrypted at rest and in transit
//! - Replica nodes must have same tenant key pair to decrypt
//!
//! **Replication Security**:
//! - gRPC stream protected by mTLS (transport layer)
//! - WAL entries encrypted (application layer)
//! - Defense in depth: even if TLS compromised, data remains encrypted

use crate::storage::column_families::CF_WAL;
use crate::storage::Storage;
use crate::types::{DatabaseError, Result};
use chrono::Utc;
use serde::{Deserialize, Serialize};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;

/// WAL entry representing a database operation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WalEntry {
    /// Sequence number (monotonically increasing)
    pub seq: u64,
    /// Operation type
    pub op: WalOperation,
    /// Timestamp (ISO 8601)
    pub timestamp: String,
}

/// WAL operation types.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum WalOperation {
    Insert {
        tenant_id: String,
        entity: serde_json::Value,
    },
    Update {
        tenant_id: String,
        entity_id: String,
        changes: serde_json::Value,
    },
    Delete {
        tenant_id: String,
        entity_id: String,
    },
}

/// Write-ahead log for durability and replication.
///
/// # Example
///
/// ```
/// use rem_db::replication::{WriteAheadLog, WalOperation};
/// use rem_db::storage::Storage;
///
/// let storage = Storage::open_temp("wal_test")?;
/// let mut wal = WriteAheadLog::new(storage)?;
///
/// let op = WalOperation::Insert {
///     tenant_id: "tenant-1".to_string(),
///     entity: serde_json::json!({"name": "Alice"}),
/// };
///
/// let seq = wal.append(op)?;
/// assert_eq!(seq, 1);
/// ```
pub struct WriteAheadLog {
    storage: Arc<Storage>,
    current_seq: Arc<AtomicU64>,
}

impl WriteAheadLog {
    /// Create new WAL.
    ///
    /// Reads the latest sequence number from storage to resume after restart.
    ///
    /// # Arguments
    ///
    /// * `storage` - RocksDB storage instance
    ///
    /// # Returns
    ///
    /// New `WriteAheadLog` instance
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::WalError` if storage read fails
    ///
    /// # Example
    ///
    /// ```
    /// let storage = Storage::open_temp("wal")?;
    /// let wal = WriteAheadLog::new(storage)?;
    /// ```
    pub fn new(storage: Arc<Storage>) -> Result<Self> {
        // Find latest sequence number by scanning WAL CF backwards
        let current_seq = Self::read_latest_seq(&storage)?;

        Ok(Self {
            storage,
            current_seq: Arc::new(AtomicU64::new(current_seq)),
        })
    }

    /// Read latest sequence number from storage.
    ///
    /// # Arguments
    ///
    /// * `storage` - Storage instance
    ///
    /// # Returns
    ///
    /// Latest sequence number (0 if WAL is empty)
    fn read_latest_seq(storage: &Arc<Storage>) -> Result<u64> {
        // Iterate backwards to find latest key
        let iter = storage.iterator_reverse(CF_WAL);

        for item in iter {
            let (key, _) = item?;
            // Key format: "wal:{seq}"
            if let Some(seq_str) = key.strip_prefix(b"wal:") {
                let seq = std::str::from_utf8(seq_str)
                    .map_err(|e| DatabaseError::WalError(format!("Invalid WAL key: {}", e)))?
                    .parse::<u64>()
                    .map_err(|e| {
                        DatabaseError::WalError(format!("Invalid sequence number: {}", e))
                    })?;
                return Ok(seq);
            }
        }

        Ok(0) // Empty WAL
    }

    /// Append entry to WAL.
    ///
    /// # Arguments
    ///
    /// * `op` - Operation to log
    ///
    /// # Returns
    ///
    /// Sequence number of logged entry
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::WalError` if append fails
    ///
    /// # Example
    ///
    /// ```
    /// let op = WalOperation::Insert {
    ///     tenant_id: "tenant-1".to_string(),
    ///     entity: serde_json::json!({"name": "Alice"}),
    /// };
    /// let seq = wal.append(op)?;
    /// ```
    pub fn append(&mut self, op: WalOperation) -> Result<u64> {
        // Get next sequence number (atomic increment)
        let seq = self.current_seq.fetch_add(1, Ordering::SeqCst) + 1;

        // Create WAL entry
        let entry = WalEntry {
            seq,
            op,
            timestamp: Utc::now().to_rfc3339(),
        };

        // Serialize with JSON (supports serde_json::Value)
        let value = serde_json::to_vec(&entry)?;

        // Key format: "wal:{seq}" (zero-padded for sorting)
        let key = format!("wal:{:020}", seq);

        // Write to WAL CF
        self.storage.put(CF_WAL, key.as_bytes(), &value)?;

        Ok(seq)
    }

    /// Get WAL entry by sequence number.
    ///
    /// # Arguments
    ///
    /// * `seq` - Sequence number
    ///
    /// # Returns
    ///
    /// WAL entry if found
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::WalError` if lookup fails
    ///
    /// # Example
    ///
    /// ```
    /// let entry = wal.get(5)?;
    /// if let Some(e) = entry {
    ///     println!("Operation: {:?}", e.op);
    /// }
    /// ```
    pub fn get(&self, seq: u64) -> Result<Option<WalEntry>> {
        let key = format!("wal:{:020}", seq);
        let value = self.storage.get(CF_WAL, key.as_bytes())?;

        match value {
            Some(bytes) => {
                let entry = serde_json::from_slice(&bytes)?;
                Ok(Some(entry))
            }
            None => Ok(None),
        }
    }

    /// Get current WAL position.
    ///
    /// # Returns
    ///
    /// Current sequence number
    ///
    /// # Example
    ///
    /// ```
    /// let pos = wal.current_position();
    /// println!("Current WAL position: {}", pos);
    /// ```
    pub fn current_position(&self) -> u64 {
        self.current_seq.load(Ordering::SeqCst)
    }

    /// Get entries after sequence number.
    ///
    /// # Arguments
    ///
    /// * `after_seq` - Starting sequence number (exclusive)
    /// * `limit` - Maximum entries to return
    ///
    /// # Returns
    ///
    /// Vector of WAL entries
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::WalError` if read fails
    ///
    /// # Example
    ///
    /// ```
    /// // Get up to 100 entries after position 50
    /// let entries = wal.get_entries_after(50, 100)?;
    /// for entry in entries {
    ///     println!("Seq {}: {:?}", entry.seq, entry.op);
    /// }
    /// ```
    pub fn get_entries_after(&self, after_seq: u64, limit: usize) -> Result<Vec<WalEntry>> {
        let mut entries = Vec::new();
        let start_key = format!("wal:{:020}", after_seq + 1);

        // Iterate forward from "wal:" prefix, filtering by start_key
        let iter = self.storage.prefix_iterator(CF_WAL, b"wal:");

        for item in iter {
            let (key, value) = item?;

            // Skip entries before start_key
            if key.as_ref() < start_key.as_bytes() {
                continue;
            }

            // Stop after limit
            if entries.len() >= limit {
                break;
            }

            let entry: WalEntry = serde_json::from_slice(&value)?;
            entries.push(entry);
        }

        Ok(entries)
    }

    /// Compact WAL by removing entries before sequence number.
    ///
    /// Use this to prevent WAL from growing unbounded.
    ///
    /// # Arguments
    ///
    /// * `before_seq` - Delete all entries before this sequence (exclusive)
    ///
    /// # Returns
    ///
    /// Number of entries deleted
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::WalError` if compaction fails
    ///
    /// # Example
    ///
    /// ```
    /// // Delete all entries before sequence 1000
    /// let deleted = wal.compact(1000)?;
    /// println!("Deleted {} old entries", deleted);
    /// ```
    pub fn compact(&mut self, before_seq: u64) -> Result<usize> {
        let mut deleted = 0;
        let end_key = format!("wal:{:020}", before_seq);

        // Iterate from start to before_seq
        let iter = self.storage.prefix_iterator(CF_WAL, b"wal:");

        for item in iter {
            let (key, _) = item?;

            // Stop when we reach before_seq
            if key.as_ref() >= end_key.as_bytes() {
                break;
            }

            self.storage.delete(CF_WAL, &key)?;
            deleted += 1;
        }

        Ok(deleted)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_wal_new_empty() {
        let storage = Arc::new(Storage::open_temp().unwrap());
        let wal = WriteAheadLog::new(storage).unwrap();

        assert_eq!(wal.current_position(), 0);
    }

    #[test]
    fn test_wal_append() {
        let storage = Arc::new(Storage::open_temp().unwrap());
        let mut wal = WriteAheadLog::new(storage).unwrap();

        let op = WalOperation::Insert {
            tenant_id: "tenant-1".to_string(),
            entity: serde_json::json!({"name": "Alice"}),
        };

        let seq = wal.append(op).unwrap();
        assert_eq!(seq, 1);
        assert_eq!(wal.current_position(), 1);
    }

    #[test]
    fn test_wal_get() {
        let storage = Arc::new(Storage::open_temp().unwrap());
        let mut wal = WriteAheadLog::new(storage).unwrap();

        let op = WalOperation::Insert {
            tenant_id: "tenant-1".to_string(),
            entity: serde_json::json!({"name": "Bob"}),
        };

        let seq = wal.append(op.clone()).unwrap();
        let entry = wal.get(seq).unwrap().unwrap();

        assert_eq!(entry.seq, seq);
        assert!(matches!(entry.op, WalOperation::Insert { .. }));
    }

    #[test]
    fn test_wal_get_entries_after() {
        let storage = Arc::new(Storage::open_temp().unwrap());
        let mut wal = WriteAheadLog::new(storage).unwrap();

        // Insert 10 entries
        for i in 0..10 {
            let op = WalOperation::Insert {
                tenant_id: "tenant-1".to_string(),
                entity: serde_json::json!({"id": i}),
            };
            wal.append(op).unwrap();
        }

        // Get entries after seq 5
        let entries = wal.get_entries_after(5, 100).unwrap();
        assert_eq!(entries.len(), 5);
        assert_eq!(entries[0].seq, 6);
        assert_eq!(entries[4].seq, 10);
    }

    #[test]
    fn test_wal_get_entries_after_with_limit() {
        let storage = Arc::new(Storage::open_temp().unwrap());
        let mut wal = WriteAheadLog::new(storage).unwrap();

        // Insert 10 entries
        for i in 0..10 {
            let op = WalOperation::Insert {
                tenant_id: "tenant-1".to_string(),
                entity: serde_json::json!({"id": i}),
            };
            wal.append(op).unwrap();
        }

        // Get only 3 entries after seq 2
        let entries = wal.get_entries_after(2, 3).unwrap();
        assert_eq!(entries.len(), 3);
        assert_eq!(entries[0].seq, 3);
        assert_eq!(entries[2].seq, 5);
    }

    #[test]
    fn test_wal_compact() {
        let storage = Arc::new(Storage::open_temp().unwrap());
        let mut wal = WriteAheadLog::new(storage).unwrap();

        // Insert 10 entries
        for i in 0..10 {
            let op = WalOperation::Insert {
                tenant_id: "tenant-1".to_string(),
                entity: serde_json::json!({"id": i}),
            };
            wal.append(op).unwrap();
        }

        // Compact entries before seq 5
        let deleted = wal.compact(5).unwrap();
        assert_eq!(deleted, 4); // Deleted entries 1-4

        // Verify entries 1-4 are gone
        assert!(wal.get(1).unwrap().is_none());
        assert!(wal.get(4).unwrap().is_none());

        // Verify entries 5-10 still exist
        assert!(wal.get(5).unwrap().is_some());
        assert!(wal.get(10).unwrap().is_some());
    }

    #[test]
    fn test_wal_persistence() {
        let path = tempfile::tempdir().unwrap();
        let path_str = path.path().to_str().unwrap().to_string();

        // Create WAL and append entries
        {
            let storage = Arc::new(Storage::open(&path_str, None).unwrap());
            let mut wal = WriteAheadLog::new(storage).unwrap();

            for i in 0..5 {
                let op = WalOperation::Insert {
                    tenant_id: "tenant-1".to_string(),
                    entity: serde_json::json!({"id": i}),
                };
                wal.append(op).unwrap();
            }
        }

        // Reopen and verify sequence number is restored
        {
            let storage = Arc::new(Storage::open(&path_str, None).unwrap());
            let wal = WriteAheadLog::new(storage).unwrap();

            assert_eq!(wal.current_position(), 5);
            assert!(wal.get(1).unwrap().is_some());
            assert!(wal.get(5).unwrap().is_some());
        }
    }
}
