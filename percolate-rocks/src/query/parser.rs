//! SQL query parser using sqlparser-rs.
//!
//! Supports SELECT queries without joins:
//! - SELECT fields FROM table WHERE conditions
//! - Aggregates: COUNT(*), SUM(field), AVG(field), MIN(field), MAX(field)
//! - GROUP BY field
//! - ORDER BY field [ASC|DESC]
//! - LIMIT n

use crate::types::{Result, DatabaseError};
use sqlparser::ast::{Statement, SelectItem, Expr, TableFactor};
use sqlparser::dialect::GenericDialect;
use sqlparser::parser::Parser;

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
/// Returns `DatabaseError::QueryError` if SQL is invalid or unsupported
pub fn parse_sql(sql: &str) -> Result<Statement> {
    let dialect = GenericDialect {};

    let statements = Parser::parse_sql(&dialect, sql)
        .map_err(|e| DatabaseError::QueryError(format!("Parse error: {}", e)))?;

    if statements.is_empty() {
        return Err(DatabaseError::QueryError("No statement found".to_string()));
    }

    if statements.len() > 1 {
        return Err(DatabaseError::QueryError("Multiple statements not supported".to_string()));
    }

    let statement = statements.into_iter().next().unwrap();

    // Validate it's a SELECT statement
    if !matches!(statement, Statement::Query(_)) {
        return Err(DatabaseError::QueryError("Only SELECT queries are supported".to_string()));
    }

    // Validate no joins
    if let Statement::Query(ref query) = statement {
        if let sqlparser::ast::SetExpr::Select(ref select) = *query.body {
            // Check for joins
            if select.from.len() > 1 {
                return Err(DatabaseError::QueryError("Multiple FROM tables (joins) not supported".to_string()));
            }

            if !select.from.is_empty() {
                if let Some(first_table) = select.from.first() {
                    if !first_table.joins.is_empty() {
                        return Err(DatabaseError::QueryError("JOIN clauses not supported".to_string()));
                    }
                }
            }
        }
    }

    Ok(statement)
}

/// Validate query syntax.
pub fn validate_sql(sql: &str) -> bool {
    parse_sql(sql).is_ok()
}

/// Extract table name from SELECT statement.
pub fn extract_table_name(statement: &Statement) -> Result<String> {
    if let Statement::Query(query) = statement {
        if let sqlparser::ast::SetExpr::Select(select) = query.body.as_ref() {
            if select.from.is_empty() {
                return Err(DatabaseError::QueryError("No FROM clause".to_string()));
            }

            let first_table = &select.from[0];
            if let TableFactor::Table { name, .. } = &first_table.relation {
                return Ok(name.to_string());
            }
        }
    }

    Err(DatabaseError::QueryError("Invalid SELECT statement".to_string()))
}

/// Check if query has aggregates.
pub fn has_aggregates(statement: &Statement) -> bool {
    if let Statement::Query(query) = statement {
        if let sqlparser::ast::SetExpr::Select(select) = query.body.as_ref() {
            for item in &select.projection {
                if let SelectItem::UnnamedExpr(Expr::Function(_)) = item {
                    return true;
                }
            }
        }
    }
    false
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_simple_select() {
        let sql = "SELECT * FROM person";
        let result = parse_sql(sql);
        assert!(result.is_ok());
    }

    #[test]
    fn test_parse_with_where() {
        let sql = "SELECT name, age FROM person WHERE age > 30";
        let result = parse_sql(sql);
        assert!(result.is_ok());
    }

    #[test]
    fn test_parse_with_aggregate() {
        let sql = "SELECT COUNT(*) FROM person";
        let result = parse_sql(sql);
        assert!(result.is_ok());
    }

    #[test]
    fn test_parse_with_limit() {
        let sql = "SELECT * FROM person LIMIT 10";
        let result = parse_sql(sql);
        assert!(result.is_ok());
    }

    #[test]
    fn test_parse_with_order_by() {
        let sql = "SELECT * FROM person ORDER BY age DESC";
        let result = parse_sql(sql);
        assert!(result.is_ok());
    }

    #[test]
    fn test_reject_join() {
        let sql = "SELECT * FROM person JOIN company ON person.company_id = company.id";
        let result = parse_sql(sql);
        assert!(result.is_err());
    }

    #[test]
    fn test_extract_table_name() {
        let sql = "SELECT * FROM person WHERE age > 30";
        let stmt = parse_sql(sql).unwrap();
        let table = extract_table_name(&stmt).unwrap();
        assert_eq!(table, "person");
    }
}
