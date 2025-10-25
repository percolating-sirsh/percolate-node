//! JSONL export for streaming/batch processing.

use crate::types::{Result, Entity, DatabaseError};
use std::fs::File;
use std::io::{BufWriter, Write};
use std::path::Path;

/// JSONL exporter.
pub struct JsonlExporter;

impl JsonlExporter {
    /// Export entities to JSONL file.
    ///
    /// # Arguments
    ///
    /// * `entities` - Entities to export
    /// * `path` - Output file path
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::ExportError` if export fails
    pub fn export<P: AsRef<Path>>(entities: &[Entity], path: P) -> Result<()> {
        Self::export_with_options(entities, path, false)
    }

    /// Export with pretty-printing.
    ///
    /// # Arguments
    ///
    /// * `entities` - Entities to export
    /// * `path` - Output file path
    /// * `pretty` - Enable pretty-printing
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::ExportError` if export fails
    pub fn export_with_options<P: AsRef<Path>>(
        entities: &[Entity],
        path: P,
        pretty: bool,
    ) -> Result<()> {
        let file = File::create(path.as_ref())
            .map_err(|e| DatabaseError::ExportError(format!("Failed to create file: {}", e)))?;

        let mut writer = BufWriter::new(file);

        for entity in entities {
            let line = if pretty {
                serde_json::to_string_pretty(entity)?
            } else {
                serde_json::to_string(entity)?
            };

            writeln!(writer, "{}", line)
                .map_err(|e| DatabaseError::ExportError(format!("Failed to write: {}", e)))?;
        }

        writer.flush()
            .map_err(|e| DatabaseError::ExportError(format!("Failed to flush: {}", e)))?;

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::types::Entity;
    use serde_json::json;
    use std::fs;
    use tempfile::tempdir;
    use uuid::Uuid;

    #[test]
    fn test_jsonl_export() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("test.jsonl");

        let entities = vec![
            Entity::new(Uuid::new_v4(), "articles".to_string(), json!({"title": "Article 1"})),
            Entity::new(Uuid::new_v4(), "articles".to_string(), json!({"title": "Article 2"})),
        ];

        JsonlExporter::export(&entities, &path).unwrap();

        let content = fs::read_to_string(&path).unwrap();
        let lines: Vec<&str> = content.lines().collect();

        assert_eq!(lines.len(), 2);

        // Verify each line is valid JSON
        for line in lines {
            let _entity: Entity = serde_json::from_str(line).unwrap();
        }
    }

    #[test]
    fn test_jsonl_export_pretty() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("test_pretty.jsonl");

        let entities = vec![
            Entity::new(Uuid::new_v4(), "articles".to_string(), json!({"title": "Test"})),
        ];

        JsonlExporter::export_with_options(&entities, &path, true).unwrap();

        let content = fs::read_to_string(&path).unwrap();

        // Pretty-printed JSON should contain newlines
        assert!(content.contains("  \""));
    }
}
