//! JSON Schema validation.

use crate::types::Result;

/// Schema validator for entity validation.
pub struct SchemaValidator {
    schema: serde_json::Value,
    compiled: jsonschema::JSONSchema,
}

impl SchemaValidator {
    /// Create new validator from JSON Schema.
    ///
    /// # Arguments
    ///
    /// * `schema` - JSON Schema
    ///
    /// # Returns
    ///
    /// New `SchemaValidator`
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::ValidationError` if schema is invalid
    pub fn new(schema: serde_json::Value) -> Result<Self> {
        use crate::types::DatabaseError;

        // Compile JSON Schema for validation
        let compiled = jsonschema::JSONSchema::compile(&schema)
            .map_err(|e| DatabaseError::ValidationError(format!("Invalid JSON Schema: {}", e)))?;

        Ok(Self { schema, compiled })
    }

    /// Validate data against schema.
    ///
    /// # Arguments
    ///
    /// * `data` - Data to validate
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::ValidationError` if validation fails
    pub fn validate(&self, data: &serde_json::Value) -> Result<()> {
        use crate::types::DatabaseError;

        // Run validation
        if let Err(errors) = self.compiled.validate(data) {
            let error_msgs: Vec<String> = errors
                .map(|e| format!("{}", e))
                .collect();

            return Err(DatabaseError::ValidationError(
                format!("Validation failed: {}", error_msgs.join(", "))
            ));
        }

        Ok(())
    }

    /// Check if data is valid (without error details).
    ///
    /// # Arguments
    ///
    /// * `data` - Data to validate
    ///
    /// # Returns
    ///
    /// `true` if valid
    pub fn is_valid(&self, data: &serde_json::Value) -> bool {
        self.compiled.is_valid(data)
    }

    /// Validate that all properties have descriptions.
    ///
    /// # Returns
    ///
    /// Ok if all fields have descriptions
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::ValidationError` if any field is missing a description
    ///
    /// # Why Critical
    ///
    /// Field descriptions are mandatory for LLM query building.
    /// The LLM uses descriptions to understand field semantics and construct accurate queries.
    ///
    /// # Example
    ///
    /// ```json
    /// {
    ///   "properties": {
    ///     "title": {
    ///       "type": "string",
    ///       "description": "Article title"  // Required!
    ///     }
    ///   }
    /// }
    /// ```
    pub fn validate_field_descriptions(&self) -> Result<()> {
        use crate::types::DatabaseError;

        let properties = self.schema
            .get("properties")
            .and_then(|p| p.as_object())
            .ok_or_else(|| DatabaseError::ValidationError("Schema missing 'properties' field".into()))?;

        // Check each property has a description
        for (field_name, field_schema) in properties {
            if field_schema.get("description").is_none() {
                return Err(DatabaseError::ValidationError(
                    format!("Field '{}' is missing description (required for LLM query building)", field_name)
                ));
            }
        }

        Ok(())
    }

    /// Validate required fields in schema definition.
    ///
    /// # Returns
    ///
    /// Ok if schema has all required metadata
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::ValidationError` if missing required fields
    ///
    /// # Required Fields
    ///
    /// - `title` (string): Schema name
    /// - `description` (string): Schema description
    /// - `version` (string): Semantic version
    /// - `short_name` (string): Table name
    /// - `name` (string): Unique identifier
    /// - `properties` (object): Field definitions
    pub fn validate_schema_metadata(&self) -> Result<()> {
        use crate::types::DatabaseError;

        let required_fields = vec![
            ("title", "Schema title"),
            ("description", "Schema description"),
            ("version", "Schema version"),
            ("short_name", "Table name"),
            ("properties", "Field definitions"),
        ];

        for (field, desc) in required_fields {
            if self.schema.get(field).is_none() {
                return Err(DatabaseError::ValidationError(
                    format!("Schema missing required field '{}' ({})", field, desc)
                ));
            }
        }

        Ok(())
    }

    /// Validate semantic versioning format.
    ///
    /// # Arguments
    ///
    /// * `version` - Version string to validate
    ///
    /// # Returns
    ///
    /// Ok if version follows semver (e.g., "1.0.0", "2.1.3")
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::ValidationError` if version format is invalid
    pub fn validate_version_format(version: &str) -> Result<()> {
        use crate::types::DatabaseError;

        let parts: Vec<&str> = version.split('.').collect();
        if parts.len() != 3 {
            return Err(DatabaseError::ValidationError(
                format!("Invalid version format '{}' (expected: major.minor.patch)", version)
            ));
        }

        // Validate each part is a number
        for (i, part) in parts.iter().enumerate() {
            if part.parse::<u32>().is_err() {
                let label = match i {
                    0 => "major",
                    1 => "minor",
                    2 => "patch",
                    _ => "unknown",
                };
                return Err(DatabaseError::ValidationError(
                    format!("Invalid {} version '{}' (expected number)", label, part)
                ));
            }
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_validate_field_descriptions() {
        let schema = json!({
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Article title"
                },
                "content": {
                    "type": "string"
                    // Missing description - should fail
                }
            }
        });

        let validator = SchemaValidator::new(schema).unwrap();
        assert!(validator.validate_field_descriptions().is_err());
    }

    #[test]
    fn test_validate_version_format() {
        assert!(SchemaValidator::validate_version_format("1.0.0").is_ok());
        assert!(SchemaValidator::validate_version_format("2.1.3").is_ok());
        assert!(SchemaValidator::validate_version_format("invalid").is_err());
        assert!(SchemaValidator::validate_version_format("1.0").is_err());
    }
}
