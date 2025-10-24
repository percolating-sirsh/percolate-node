//! Simple SQL query parser and executor.
//!
//! Supports basic SELECT queries with WHERE predicates:
//! - SELECT * FROM table WHERE field = 'value'
//! - SELECT * FROM table WHERE field = 'value' AND field2 = 'value2'

use crate::types::{DatabaseError, Entity, Result};

/// Parsed SQL query.
#[derive(Debug, Clone)]
pub struct SqlQuery {
    pub table: String,
    pub predicates: Vec<Predicate>,
}

/// WHERE predicate.
#[derive(Debug, Clone)]
pub struct Predicate {
    pub field: String,
    pub operator: Operator,
    pub value: String,
}

/// Comparison operator.
#[derive(Debug, Clone, PartialEq)]
pub enum Operator {
    Equal,
    NotEqual,
    GreaterThan,
    LessThan,
}

impl SqlQuery {
    /// Parse a simple SELECT query.
    ///
    /// Supports: SELECT * FROM table WHERE field = 'value'
    pub fn parse(sql: &str) -> Result<Self> {
        let sql = sql.trim();

        // Extract table name
        let table = Self::extract_table(sql)?;

        // Extract predicates from WHERE clause
        let predicates = Self::extract_predicates(sql)?;

        Ok(SqlQuery { table, predicates })
    }

    /// Extract table name from SELECT statement.
    fn extract_table(sql: &str) -> Result<String> {
        // Find "FROM <table>"
        let from_idx = sql.to_lowercase().find("from ")
            .ok_or_else(|| DatabaseError::QueryError("Missing FROM clause".to_string()))?;

        let after_from = &sql[from_idx + 5..].trim();

        // Table name is next word (until space or WHERE)
        let table_end = after_from
            .find(|c: char| c.is_whitespace())
            .unwrap_or(after_from.len());

        Ok(after_from[..table_end].to_string())
    }

    /// Extract WHERE predicates.
    fn extract_predicates(sql: &str) -> Result<Vec<Predicate>> {
        let where_idx = match sql.to_lowercase().find("where ") {
            Some(idx) => idx,
            None => return Ok(Vec::new()), // No WHERE clause
        };

        let where_clause = &sql[where_idx + 6..].trim();

        // Split by AND (simple approach)
        let conditions: Vec<&str> = where_clause
            .split(" AND ")
            .map(|s| s.trim())
            .collect();

        let mut predicates = Vec::new();

        for condition in conditions {
            predicates.push(Self::parse_predicate(condition)?);
        }

        Ok(predicates)
    }

    /// Parse a single predicate: field = 'value'
    fn parse_predicate(condition: &str) -> Result<Predicate> {
        // Find operator
        let (operator, op_str) = if condition.contains(" = ") {
            (Operator::Equal, " = ")
        } else if condition.contains(" != ") {
            (Operator::NotEqual, " != ")
        } else if condition.contains(" > ") {
            (Operator::GreaterThan, " > ")
        } else if condition.contains(" < ") {
            (Operator::LessThan, " < ")
        } else {
            return Err(DatabaseError::QueryError(
                format!("Unsupported operator in: {}", condition)
            ));
        };

        let parts: Vec<&str> = condition.split(op_str).collect();
        if parts.len() != 2 {
            return Err(DatabaseError::QueryError(
                format!("Invalid predicate: {}", condition)
            ));
        }

        let field = parts[0].trim().to_string();
        let mut value = parts[1].trim().to_string();

        // Remove quotes from value
        if (value.starts_with('\'') && value.ends_with('\'')) ||
           (value.starts_with('"') && value.ends_with('"')) {
            value = value[1..value.len()-1].to_string();
        }

        Ok(Predicate { field, operator, value })
    }

    /// Execute query against entities.
    pub fn execute(&self, entities: Vec<Entity>) -> Vec<Entity> {
        entities
            .into_iter()
            .filter(|entity| self.matches(entity))
            .collect()
    }

    /// Check if entity matches all predicates.
    fn matches(&self, entity: &Entity) -> bool {
        for predicate in &self.predicates {
            if !self.matches_predicate(entity, predicate) {
                return false;
            }
        }
        true
    }

    /// Check if entity matches a single predicate.
    fn matches_predicate(&self, entity: &Entity, predicate: &Predicate) -> bool {
        // Get field value from entity properties
        let field_value = match entity.properties.get(&predicate.field) {
            Some(value) => match value.as_str() {
                Some(s) => s,
                None => return false,
            },
            None => return false,
        };

        // Compare based on operator
        match predicate.operator {
            Operator::Equal => field_value == predicate.value,
            Operator::NotEqual => field_value != predicate.value,
            Operator::GreaterThan => field_value > predicate.value.as_str(),
            Operator::LessThan => field_value < predicate.value.as_str(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_simple_query() {
        let sql = "SELECT * FROM resources WHERE category = 'documentation'";
        let query = SqlQuery::parse(sql).unwrap();

        assert_eq!(query.table, "resources");
        assert_eq!(query.predicates.len(), 1);
        assert_eq!(query.predicates[0].field, "category");
        assert_eq!(query.predicates[0].value, "documentation");
    }

    #[test]
    fn test_parse_and_query() {
        let sql = "SELECT * FROM resources WHERE category = 'tutorial' AND uri = 'test.md'";
        let query = SqlQuery::parse(sql).unwrap();

        assert_eq!(query.predicates.len(), 2);
        assert_eq!(query.predicates[0].field, "category");
        assert_eq!(query.predicates[1].field, "uri");
    }
}
