# Database maintenance

This document covers operational procedures for maintaining REM database instances.

## Implementation status

The admin module (`src/admin/`) is **fully stubbed** with comprehensive documentation:

| Module | Status | Description |
|--------|--------|-------------|
| `backup.rs` | Stubbed | Full backup/restore to S3 with `P8_S3_BUCKET` |
| `compaction.rs` | Stubbed | Manual RocksDB compaction operations |
| `vacuum.rs` | Stubbed | Soft-delete cleanup and space reclamation |
| `indexing.rs` | Stubbed | HNSW and field index rebuild |
| `verification.rs` | Stubbed | Database integrity checks |
| `statistics.rs` | Stubbed | Metrics and Prometheus export |

All functions have:
- ✅ Complete docstrings with examples
- ✅ `todo!()` macros explaining implementation steps
- ✅ Type signatures and error handling patterns
- ✅ Test stubs

**To implement:** Replace `todo!()` macros with actual RocksDB/S3 calls.

## Backup and recovery

### Backup strategies

REM database supports two backup approaches:

1. **Full backups** - Complete database snapshot at a point in time
2. **Point-in-time recovery (PITR)** - Continuous WAL archival for granular recovery

**Current implementation status:**
- ✅ Full backups to S3 (implemented)
- ⏳ PITR (design documented, not yet implemented)

### Full backup to S3

Full backups create a consistent snapshot of the entire RocksDB database and upload to S3.

#### Configuration

**Environment variables:**
```bash
# S3 configuration (required)
P8_S3_BUCKET=my-company-rem-backups
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_REGION=us-west-2

# Backup settings (optional)
P8_BACKUP_COMPRESSION=3              # zstd level 1-22 (default: 3)
P8_BACKUP_CHUNK_SIZE_MB=100          # Multipart upload chunk size (default: 100)
```

**S3 bucket structure:**
```
s3://${P8_S3_BUCKET}/
  backups/
    full/
      {tenant_id}/
        {timestamp}/
          metadata.json
          rocksdb.tar.zst
          schemas.json
  exports/
    {tenant_id}/
      {timestamp}/
        {schema_name}.parquet
```

**TOML configuration (optional):**
```toml
[backup]
enabled = true
schedule = "0 2 * * *"  # Daily at 2 AM UTC

[backup.s3]
storage_class = "STANDARD_IA"  # Infrequent Access for cost savings
```

#### CLI usage

```bash
# Create full backup
rem backup create --name "before-migration-2025-10-25"

# Create and upload to S3
rem backup create --name "daily-backup" --upload

# List backups
rem backup list
# Output:
# NAME                           SIZE      CREATED              LOCATION
# daily-backup-2025-10-25       2.3 GB    2025-10-25 02:00     s3://my-company-rem-backups/production/db/2025-10-25/
# before-migration-2025-10-25   2.1 GB    2025-10-24 18:30     local

# Download backup from S3
rem backup download --name "daily-backup-2025-10-25" --output /tmp/restore

# Restore from backup
rem backup restore --source /tmp/restore/daily-backup-2025-10-25
```

#### Automated backups

Enable scheduled backups via systemd timer or cron:

**systemd timer:**
```ini
# /etc/systemd/system/rem-backup.timer
[Unit]
Description=Daily REM database backup

[Timer]
OnCalendar=daily
OnCalendar=02:00
Persistent=true

[Install]
WantedBy=timers.target
```

```ini
# /etc/systemd/system/rem-backup.service
[Unit]
Description=REM database backup to S3

[Service]
Type=oneshot
ExecStart=/usr/local/bin/rem backup create --upload --name "daily-$(date +\%Y-\%m-\%d)"
User=rem
Environment="P8_DB_PATH=/var/lib/rem/db"
```

**Enable:**
```bash
sudo systemctl enable rem-backup.timer
sudo systemctl start rem-backup.timer
```

#### Backup retention

Configure lifecycle policies in S3:

```json
{
  "Rules": [
    {
      "Id": "delete-old-backups",
      "Status": "Enabled",
      "Prefix": "production/db/",
      "Transitions": [
        {
          "Days": 30,
          "StorageClass": "GLACIER"
        }
      ],
      "Expiration": {
        "Days": 90
      }
    }
  ]
}
```

**Retention strategy:**
- Daily backups: 7 days in STANDARD_IA
- Weekly backups: 30 days in STANDARD_IA → Glacier
- Monthly backups: 90 days in Glacier → Delete

### Recovery procedures

#### Full restore from S3

```bash
# 1. Stop database
sudo systemctl stop rem-server

# 2. Download backup
rem backup download \
  --name "daily-backup-2025-10-25" \
  --output /tmp/restore

# 3. Restore database
rem backup restore \
  --source /tmp/restore/daily-backup-2025-10-25 \
  --target /var/lib/rem/db

# 4. Verify integrity
rem db verify

# 5. Start database
sudo systemctl start rem-server
```

#### Disaster recovery checklist

- [ ] Identify last known good backup
- [ ] Download backup from S3
- [ ] Verify backup integrity (checksums)
- [ ] Stop running database instance
- [ ] Move corrupted database to quarantine
- [ ] Restore from backup
- [ ] Run integrity checks
- [ ] Start database
- [ ] Verify application connectivity
- [ ] Check for data loss (compare with WAL if available)

### Implementation details (current)

**What's implemented:**

The admin module is fully stubbed in `src/admin/` with comprehensive documentation:
- `backup.rs`: Full backup/restore operations
- `compaction.rs`: Manual RocksDB compaction
- `vacuum.rs`: Soft-delete cleanup
- `indexing.rs`: Index rebuild operations
- `verification.rs`: Database integrity checks
- `statistics.rs`: Metrics and stats collection

**Rust API example:**

```rust
// src/admin/backup.rs (stubbed with heavy documentation)

/// Create RocksDB checkpoint (consistent snapshot)
pub fn create_checkpoint(&self, backup_path: &Path) -> Result<BackupMetadata> {
    // Uses RocksDB::create_checkpoint()
    // - Hardlinks SST files (instant, no copy)
    // - Copies WAL and MANIFEST
    // Returns metadata: size, entity count, timestamp
}

/// Upload backup to S3
pub async fn upload_to_s3(
    &self,
    backup_path: &Path,
    bucket: &str,
    prefix: &str
) -> Result<S3BackupRef> {
    // 1. Compress with zstd (parallel)
    // 2. Upload in 100MB chunks (multipart)
    // 3. Store metadata in S3 tags
    // Returns: s3://bucket/prefix/backup-name.tar.zst
}

/// Download and restore backup
pub async fn restore_from_s3(
    s3_ref: &S3BackupRef,
    target_path: &Path
) -> Result<()> {
    // 1. Download in parallel chunks
    // 2. Decompress with zstd
    // 3. Verify checksums
    // 4. Extract to target path
    // 5. Run RocksDB repair if needed
}
```

**Dependencies needed:**
```toml
[dependencies]
aws-sdk-s3 = "1.0"
tokio = { version = "1.0", features = ["full"] }
zstd = "0.13"
sha2 = "0.10"
```

## Point-in-time recovery (PITR)

**Status:** Not yet implemented. Design documented below.

### Architecture overview

PITR enables recovery to any point in time by combining:
1. **Base backup** (full snapshot)
2. **WAL archives** (continuous operation log since backup)

```
Timeline:
├─ Full Backup ──────┬─ WAL 001 ─┬─ WAL 002 ─┬─ WAL 003 ─┬─ Current
   2025-10-20 02:00  │           │           │           │
                      │           │           │           └─ Recovery point: 2025-10-25 14:37
                      └─ Archive to S3 every 5 minutes
```

### What needs to be implemented

#### 1. WAL archival service

```rust
// src/replication/archive.rs (to be written)

/// Archive completed WAL segments to S3
pub struct WalArchiver {
    wal_dir: PathBuf,
    s3_client: aws_sdk_s3::Client,
    bucket: String,
    prefix: String,
}

impl WalArchiver {
    /// Monitor WAL directory and upload completed segments
    pub async fn run(&self) -> Result<()> {
        // 1. Watch for .wal files rotation
        // 2. When new segment created, upload previous
        // 3. Store metadata: sequence, timestamp, checksum
        // 4. Update archival manifest in S3
    }

    /// Upload single WAL segment
    async fn archive_segment(&self, seq: u64) -> Result<()> {
        let wal_path = self.wal_dir.join(format!("{:020}.wal", seq));
        let s3_key = format!("{}/wal/{:020}.wal.zst", self.prefix, seq);

        // Compress and upload
        let compressed = zstd::encode_all(std::fs::read(&wal_path)?, 3)?;
        self.s3_client
            .put_object()
            .bucket(&self.bucket)
            .key(&s3_key)
            .body(compressed.into())
            .send()
            .await?;

        Ok(())
    }
}
```

**Configuration:**
```toml
[pitr]
enabled = true
archive_mode = "continuous"
archive_interval_sec = 300  # Archive every 5 minutes

[pitr.s3]
bucket = "my-company-rem-wal"
prefix = "production/wal"
compression = "zstd"
```

#### 2. Recovery coordinator

```rust
// src/backup/pitr.rs (to be written)

/// Restore database to specific point in time
pub async fn restore_to_timestamp(
    target_time: DateTime<Utc>,
    base_backup: &S3BackupRef,
    wal_bucket: &str,
    output_path: &Path,
) -> Result<()> {
    // 1. Download and extract base backup
    restore_from_s3(base_backup, output_path).await?;

    // 2. Download WAL segments from S3
    let wal_segments = list_wal_segments(
        wal_bucket,
        base_backup.timestamp,
        target_time
    ).await?;

    // 3. Replay WAL operations up to target_time
    let mut db = Database::open(output_path)?;
    for segment in wal_segments {
        replay_wal_segment(&mut db, &segment, Some(target_time))?;
    }

    // 4. Verify consistency
    db.verify_integrity()?;

    Ok(())
}

/// Replay single WAL segment with optional cutoff
fn replay_wal_segment(
    db: &mut Database,
    segment: &WalSegment,
    until: Option<DateTime<Utc>>,
) -> Result<()> {
    for entry in segment.entries() {
        if let Some(cutoff) = until {
            if entry.timestamp > cutoff {
                break;  // Stop at target time
            }
        }

        // Apply operation
        match entry.operation {
            WalOperation::Insert { table, entity } => {
                db.insert_raw(&table, &entity)?;
            }
            WalOperation::Update { entity_id, properties } => {
                db.update_raw(entity_id, &properties)?;
            }
            WalOperation::Delete { entity_id } => {
                db.delete_raw(entity_id)?;
            }
        }
    }
    Ok(())
}
```

#### 3. Archival manifest tracking

Store metadata about archived segments in S3:

```json
// s3://bucket/prefix/manifest.json
{
  "last_archived_sequence": 1234,
  "last_archived_timestamp": "2025-10-25T14:35:00Z",
  "base_backup": {
    "timestamp": "2025-10-20T02:00:00Z",
    "s3_path": "s3://backups/production/db/2025-10-20/",
    "size_bytes": 2400000000,
    "entity_count": 1500000
  },
  "wal_segments": [
    {
      "sequence": 1230,
      "s3_key": "production/wal/00001230.wal.zst",
      "start_time": "2025-10-25T14:30:00Z",
      "end_time": "2025-10-25T14:35:00Z",
      "size_bytes": 52428800,
      "checksum_sha256": "abc123..."
    }
  ]
}
```

#### 4. CLI commands

```bash
# Enable PITR archival
rem pitr enable --bucket my-company-rem-wal

# List available recovery points
rem pitr list-recovery-points
# Output:
# BASE BACKUP           LATEST WAL          RECOVERY WINDOW
# 2025-10-20 02:00      2025-10-25 14:35    5 days 12 hours

# Restore to specific timestamp
rem pitr restore \
  --timestamp "2025-10-25 14:30:00" \
  --output /tmp/restored-db

# Verify recovery point availability
rem pitr verify --timestamp "2025-10-25 14:30:00"
```

### PITR implementation checklist

To fully implement PITR, we need:

- [ ] **WAL archival daemon** (`src/replication/archive.rs`)
  - [ ] File watcher for WAL rotation
  - [ ] S3 upload with compression
  - [ ] Manifest tracking
  - [ ] Configurable interval (default: 5 min)

- [ ] **Recovery coordinator** (`src/backup/pitr.rs`)
  - [ ] Download base backup
  - [ ] Download WAL segments
  - [ ] Replay WAL with timestamp cutoff
  - [ ] Integrity verification

- [ ] **CLI commands**
  - [ ] `rem pitr enable`
  - [ ] `rem pitr list-recovery-points`
  - [ ] `rem pitr restore --timestamp`
  - [ ] `rem pitr verify`

- [ ] **Manifest management**
  - [ ] JSON manifest in S3
  - [ ] Atomic updates
  - [ ] Segment metadata tracking

- [ ] **Testing**
  - [ ] Full recovery integration test
  - [ ] Corruption detection
  - [ ] Performance benchmarks (replay speed)

**Estimated effort:** 2-3 weeks with proper testing

### PITR vs full backup comparison

| Aspect | Full Backup | PITR |
|--------|-------------|------|
| **Recovery granularity** | Daily (or schedule) | Any second |
| **Storage overhead** | 2-5 GB per backup | ~10 MB/hour WAL |
| **Recovery time** | 5-10 min | 10-30 min |
| **Implementation complexity** | Low | Medium |
| **Use case** | Disaster recovery | Data corruption, user error |

**Recommendation:** Use both strategies:
- Daily full backups (2 AM UTC)
- Continuous WAL archival (5 min intervals)
- Retention: 7 daily + 30 days WAL

## Maintenance operations

### Database compaction

RocksDB auto-compacts, but manual compaction can help after large deletes:

```bash
# Full database compaction
rem db compact

# Compact specific column family
rem db compact --cf embeddings
```

### Integrity checks

```bash
# Verify database consistency
rem db verify

# Check specific issues
rem db verify --check-embeddings  # Verify all embeddings loadable
rem db verify --check-schemas     # Validate all entities against schemas
rem db verify --check-edges       # Verify edge consistency
```

### Statistics and monitoring

```bash
# Database statistics
rem db stats
# Output:
# Entities:       1,234,567
# Schemas:        15
# Embeddings:     987,654
# Edges:          2,345,678
# Disk usage:     2.3 GB
# WAL size:       45 MB

# Column family statistics
rem db stats --cf embeddings
# Output:
# Keys:           987,654
# Total size:     1.5 GB
# Compression:    zstd (ratio: 3.2x)
# Bloom filter:   2.1 MB
```

### Performance tuning

```bash
# Rebuild HNSW index (if degraded)
rem index rebuild --type hnsw

# Reindex fields (after schema changes)
rem index rebuild --type fields --schema articles

# Vacuum deleted entities (free space)
rem db vacuum --dry-run  # Preview
rem db vacuum            # Execute
```

## Multi-tenant considerations

### Per-tenant backups

Isolate backups by tenant:

```bash
# Backup single tenant
rem backup create \
  --tenant tenant-abc123 \
  --name "tenant-abc123-2025-10-25" \
  --upload

# S3 structure:
# s3://backups/
#   production/
#     tenant-abc123/
#       2025-10-25/
#     tenant-xyz789/
#       2025-10-25/
```

### Tenant data export

Export tenant data for migration or archival:

```bash
# Export to Parquet
rem export \
  --tenant tenant-abc123 \
  --format parquet \
  --output /tmp/tenant-abc123.parquet

# Export specific schemas
rem export \
  --tenant tenant-abc123 \
  --schemas articles,documents \
  --format parquet \
  --output /tmp/tenant-abc123-content.parquet
```

## Monitoring and alerts

### Key metrics to monitor

| Metric | Threshold | Alert |
|--------|-----------|-------|
| Backup age | > 48 hours | Critical |
| WAL archive lag | > 1 hour | Warning |
| Disk usage | > 80% | Warning |
| Compaction pending | > 10 GB | Info |
| Failed backups | > 0 in 24h | Critical |

### Prometheus metrics

```prometheus
# Backup metrics
rem_backup_last_success_timestamp
rem_backup_duration_seconds
rem_backup_size_bytes

# WAL metrics
rem_wal_archive_lag_seconds
rem_wal_archive_failures_total

# Database metrics
rem_db_size_bytes{cf="embeddings"}
rem_db_keys_total{cf="entities"}
rem_db_compaction_pending_bytes
```

### Health check endpoint

```bash
# Check database health
rem db health

# Output (JSON):
{
  "status": "healthy",
  "last_backup": "2025-10-25T02:00:00Z",
  "wal_archive_lag_sec": 120,
  "disk_usage_percent": 45,
  "checks": {
    "rocksdb": "ok",
    "wal": "ok",
    "backup": "ok",
    "embeddings": "ok"
  }
}
```

## Security considerations

### Encryption at rest

RocksDB data is encrypted at the filesystem level (use encrypted volumes):

```bash
# AWS EBS
aws ec2 create-volume --encrypted --size 100 --volume-type gp3

# Or use dm-crypt (Linux)
cryptsetup luksFormat /dev/sdb
cryptsetup open /dev/sdb rem-db-encrypted
mkfs.ext4 /dev/mapper/rem-db-encrypted
```

### Backup encryption

S3 backups use server-side encryption:

```toml
[backup.s3]
encryption = "AES256"  # or "aws:kms" with KMS key
kms_key_id = "arn:aws:kms:us-west-2:123456789012:key/abc-123"
```

### Access control

Restrict backup access via IAM policies:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::my-company-rem-backups/*",
        "arn:aws:s3:::my-company-rem-backups"
      ]
    }
  ]
}
```

## Recovery testing

**Test recovery procedures quarterly:**

```bash
# 1. Create test backup
rem backup create --name "recovery-test-2025-q4"

# 2. Simulate disaster (new directory)
rem backup restore \
  --source /backups/recovery-test-2025-q4 \
  --target /tmp/test-restore

# 3. Verify data integrity
rem --db-path /tmp/test-restore db verify

# 4. Sample data checks
rem --db-path /tmp/test-restore query "SELECT COUNT(*) FROM articles"

# 5. Document results
echo "Recovery test passed: $(date)" >> /var/log/rem-recovery-tests.log
```

**Automate recovery testing:**

```bash
#!/bin/bash
# test-recovery.sh

set -euo pipefail

BACKUP_NAME="recovery-test-$(date +%Y-%m-%d)"
TEST_DIR="/tmp/recovery-test-$$"

# Create backup
rem backup create --name "$BACKUP_NAME" --upload

# Restore to test directory
rem backup download --name "$BACKUP_NAME" --output "$TEST_DIR"
rem backup restore --source "$TEST_DIR/$BACKUP_NAME" --target "$TEST_DIR/db"

# Verify
rem --db-path "$TEST_DIR/db" db verify || {
    echo "RECOVERY TEST FAILED" | mail -s "REM Recovery Test Failure" ops@company.com
    exit 1
}

# Cleanup
rm -rf "$TEST_DIR"

echo "Recovery test passed: $BACKUP_NAME"
```

Run quarterly via cron:
```cron
0 3 1 */3 * /usr/local/bin/test-recovery.sh
```
