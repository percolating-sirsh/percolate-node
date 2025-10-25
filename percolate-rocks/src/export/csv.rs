//! CSV export for spreadsheets.

use crate::types::{Result, Entity, DatabaseError};
use csv::Writer;
use std::collections::BTreeSet;
use std::fs::File;
use std::path::Path;

/// CSV exporter.
pub struct CsvExporter;

impl CsvExporter {
    /// Export entities to CSV file.
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
        Self::export_with_delimiter(entities, path, b',')
    }

    /// Export with custom delimiter.
    ///
    /// # Arguments
    ///
    /// * `entities` - Entities to export
    /// * `path` - Output file path
    /// * `delimiter` - Field delimiter (default: ',')
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::ExportError` if export fails
    pub fn export_with_delimiter<P: AsRef<Path>>(
        entities: &[Entity],
        path: P,
        delimiter: u8,
    ) -> Result<()> {
        if entities.is_empty() {
            return Err(DatabaseError::ExportError("No entities to export".to_string()));
        }

        let file = File::create(path.as_ref())
            .map_err(|e| DatabaseError::ExportError(format!("Failed to create file: {}", e)))?;

        let mut writer = csv::WriterBuilder::new()
            .delimiter(delimiter)
            .from_writer(file);

        // Collect all unique field names from all entities
        let mut all_fields = BTreeSet::new();

        // System fields first
        all_fields.insert("id".to_string());
        all_fields.insert("entity_type".to_string());
        all_fields.insert("created_at".to_string());
        all_fields.insert("modified_at".to_string());
        all_fields.insert("deleted_at".to_string());

        // Collect property fields from all entities
        for entity in entities {
            if let Some(obj) = entity.properties.as_object() {
                for key in obj.keys() {
                    all_fields.insert(key.clone());
                }
            }
        }

        let fields: Vec<String> = all_fields.into_iter().collect();

        // Write header
        writer.write_record(&fields)
            .map_err(|e| DatabaseError::ExportError(format!("Failed to write header: {}", e)))?;

        // Write rows
        for entity in entities {
            let mut row = Vec::new();

            for field in &fields {
                let value = match field.as_str() {
                    "id" => entity.system.id.to_string(),
                    "entity_type" => entity.system.entity_type.clone(),
                    "created_at" => entity.system.created_at.clone(),
                    "modified_at" => entity.system.modified_at.clone(),
                    "deleted_at" => entity.system.deleted_at.clone().unwrap_or_default(),
                    _ => {
                        // Get from properties
                        entity.properties
                            .get(field)
                            .map(|v| match v {
                                serde_json::Value::String(s) => s.clone(),
                                serde_json::Value::Null => String::new(),
                                other => other.to_string(),
                            })
                            .unwrap_or_default()
                    }
                };
                row.push(value);
            }

            writer.write_record(&row)
                .map_err(|e| DatabaseError::ExportError(format!("Failed to write row: {}", e)))?;
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
    fn test_csv_export() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("test.csv");

        let entities = vec![
            Entity::new(Uuid::new_v4(), "articles".to_string(), json!({"title": "Article 1", "views": 100})),
            Entity::new(Uuid::new_v4(), "articles".to_string(), json!({"title": "Article 2", "views": 200})),
        ];

        CsvExporter::export(&entities, &path).unwrap();

        let content = fs::read_to_string(&path).unwrap();

        // Should have header + 2 rows
        let lines: Vec<&str> = content.lines().collect();
        assert_eq!(lines.len(), 3);

        // Header should contain system fields + property fields
        assert!(lines[0].contains("id"));
        assert!(lines[0].contains("entity_type"));
        assert!(lines[0].contains("title"));
        assert!(lines[0].contains("views"));
    }

    #[test]
    fn test_csv_export_with_tsv() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("test.tsv");

        let entities = vec![
            Entity::new(Uuid::new_v4(), "articles".to_string(), json!({"title": "Test"})),
        ];

        CsvExporter::export_with_delimiter(&entities, &path, b'\t').unwrap();

        let content = fs::read_to_string(&path).unwrap();

        // Should use tabs
        assert!(content.contains('\t'));
    }

    #[test]
    fn test_csv_export_empty() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("test.csv");

        let entities = vec![];

        let result = CsvExporter::export(&entities, &path);
        assert!(result.is_err());
    }
}
