//! SQL query parser.

use crate::types::Result;
use sqlparser::ast::Statement;

/// SQL query parser.
pub struct QueryParser;

impl QueryParser {
    /// Parse SQL query string.
    ///
    /// # Arguments
    ///
    /// * `sql` - SQL query string
    ///
    /// # Returns
    ///
    /// Parsed `Statement`
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::ParseError` if SQL is invalid
    pub fn parse(sql: &str) -> Result<Statement> {
        todo!("Implement QueryParser::parse")
    }

    /// Validate query syntax.
    ///
    /// # Arguments
    ///
    /// * `sql` - SQL query string
    ///
    /// # Returns
    ///
    /// `true` if syntax is valid
    pub fn validate(sql: &str) -> bool {
        todo!("Implement QueryParser::validate")
    }
}
