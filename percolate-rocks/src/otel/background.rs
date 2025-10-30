//! Background job instrumentation.
//!
//! For async operations like indexing, embedding, and compaction.
//! Uses INTERNAL span kind since these are not database client operations.

use tracing::{span, Level, Span};

/// Background job types.
#[derive(Debug, Clone, Copy)]
pub enum BackgroundJobType {
    /// HNSW index build/rebuild
    IndexBuild,
    /// HNSW index save to disk
    IndexSave,
    /// HNSW index load from disk
    IndexLoad,
    /// Generate embeddings
    EmbeddingGeneration,
    /// WAL flush
    WalFlush,
    /// RocksDB compaction
    Compaction,
    /// Field index rebuild
    FieldIndexRebuild,
    /// Key index rebuild
    KeyIndexRebuild,
}

impl BackgroundJobType {
    /// Get job type as string.
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::IndexBuild => "index.build",
            Self::IndexSave => "index.save",
            Self::IndexLoad => "index.load",
            Self::EmbeddingGeneration => "embedding.generate",
            Self::WalFlush => "wal.flush",
            Self::Compaction => "db.compact",
            Self::FieldIndexRebuild => "index.field.rebuild",
            Self::KeyIndexRebuild => "index.key.rebuild",
        }
    }
}

/// Create background job span.
///
/// # Arguments
///
/// * `job_type` - Type of background job
/// * `target` - Job target (schema name, CF name, etc.)
///
/// # Returns
///
/// Tracing span with job attributes
///
/// # Example
///
/// ```rust,ignore
/// let span = background_span(BackgroundJobType::IndexBuild, "articles");
/// let _guard = span.entered();
/// ```
pub fn background_span(job_type: BackgroundJobType, target: &str) -> Span {
    span!(
        Level::INFO,
        "background.job",
        otel.name = format!("{} {}", job_type.as_str(), target),
        otel.kind = "internal",
        job.type = job_type.as_str(),
        job.target = target,
    )
}

/// Record background job metrics.
///
/// # Arguments
///
/// * `batch_size` - Number of items processed (optional)
/// * `duration_ms` - Processing duration in milliseconds (optional)
/// * `status` - Job status ("success", "failed", "partial")
///
/// # Example
///
/// ```rust,ignore
/// let span = background_span(BackgroundJobType::EmbeddingGeneration, "articles");
/// let _guard = span.entered();
///
/// let count = generate_embeddings(texts)?;
/// record_background_metrics(Some(count), None, "success");
/// ```
pub fn record_background_metrics(
    batch_size: Option<usize>,
    duration_ms: Option<u64>,
    status: &str,
) {
    let span = Span::current();
    if let Some(size) = batch_size {
        span.record("job.batch_size", size);
    }
    if let Some(duration) = duration_ms {
        span.record("job.duration_ms", duration);
    }
    span.record("job.status", status);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_job_type_names() {
        assert_eq!(BackgroundJobType::IndexBuild.as_str(), "index.build");
        assert_eq!(BackgroundJobType::EmbeddingGeneration.as_str(), "embedding.generate");
    }

    #[test]
    fn test_background_span_creation() {
        let span = background_span(BackgroundJobType::IndexBuild, "articles");
        assert_eq!(span.metadata().unwrap().name(), "background.job");
    }
}
