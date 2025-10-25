//! Database administration operations.
//!
//! This module provides administrative operations for REM database:
//! - **Backup and restore**: Full backups to S3 with optional PITR
//! - **Compaction**: Manual RocksDB compaction for specific column families
//! - **Vacuuming**: Reclaim space from soft-deleted entities
//! - **Indexing**: Rebuild HNSW vector indexes and field indexes
//! - **Verification**: Database integrity checks and validation
//! - **Statistics**: Database size, entity counts, performance metrics
//!
//! # Architecture
//!
//! Admin operations are designed to run:
//! - **Offline** (database stopped): Full backup/restore, major compaction
//! - **Online** (database running): Statistics, light compaction, index rebuilds
//!
//! # S3 Backup Conventions
//!
//! All backups use `P8_S3_BUCKET` environment variable as root:
//!
//! ```text
//! s3://${P8_S3_BUCKET}/
//!   backups/
//!     full/
//!       {tenant_id}/
//!         {timestamp}/
//!           metadata.json
//!           rocksdb.tar.zst
//!           schemas.json
//!     wal/
//!       {tenant_id}/
//!         {sequence}.wal.zst
//!   exports/
//!     {tenant_id}/
//!       {timestamp}/
//!         {schema_name}.parquet
//! ```
//!
//! # Example Usage
//!
//! ```rust,no_run
//! use percolate_rocks::admin::{BackupManager, CompactionManager};
//!
//! # async fn example() -> anyhow::Result<()> {
//! // Create full backup to S3
//! let backup_mgr = BackupManager::new("my-bucket")?;
//! let backup_ref = backup_mgr.create_full_backup(
//!     "tenant-123",
//!     "/var/lib/rem/db",
//!     None  // Auto-generate name
//! ).await?;
//!
//! // Restore from S3
//! backup_mgr.restore_full_backup(
//!     &backup_ref,
//!     "/tmp/restored-db"
//! ).await?;
//!
//! // Manual compaction
//! let compaction_mgr = CompactionManager::new("/var/lib/rem/db")?;
//! compaction_mgr.compact_column_family("embeddings").await?;
//! # Ok(())
//! # }
//! ```
//!
//! # Configuration
//!
//! Environment variables:
//! - `P8_S3_BUCKET`: S3 bucket for backups (required)
//! - `AWS_REGION`: AWS region (default: us-west-2)
//! - `AWS_ACCESS_KEY_ID`: AWS credentials
//! - `AWS_SECRET_ACCESS_KEY`: AWS credentials
//! - `P8_BACKUP_COMPRESSION`: zstd level 1-22 (default: 3)
//! - `P8_BACKUP_CHUNK_SIZE_MB`: Multipart upload size (default: 100)

pub mod backup;
pub mod compaction;
pub mod vacuum;
pub mod indexing;
pub mod verification;
pub mod statistics;

pub use backup::{BackupManager, BackupMetadata, BackupRef, RestoreOptions};
pub use compaction::{CompactionManager, CompactionStats};
pub use vacuum::{VacuumManager, VacuumStats};
pub use indexing::{IndexManager, IndexRebuildOptions};
pub use verification::{VerificationManager, VerificationReport};
pub use statistics::{StatisticsManager, DatabaseStats};
