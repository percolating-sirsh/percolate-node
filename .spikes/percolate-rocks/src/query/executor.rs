//! Query execution engine.

use crate::types::{Result, Entity};
use crate::storage::Storage;

/// Query executor for SQL statements.
pub struct QueryExecutor {
    storage: Storage,
}

impl QueryExecutor {
    /// Create new query executor.
    pub fn new(storage: Storage) -> Self {
        todo!("Implement QueryExecutor::new")
    }

    /// Execute SELECT query.
    ///
    /// # Arguments
    ///
    /// * `sql` - SQL SELECT statement
    /// * `tenant_id` - Tenant scope
    ///
    /// # Returns
    ///
    /// Vector of matching entities
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::QueryError` if execution fails
    pub fn execute_select(&self, sql: &str, tenant_id: &str) -> Result<Vec<Entity>> {
        todo!("Implement QueryExecutor::execute_select")
    }

    /// Execute COUNT query.
    ///
    /// # Arguments
    ///
    /// * `sql` - SQL COUNT statement
    /// * `tenant_id` - Tenant scope
    ///
    /// # Returns
    ///
    /// Row count
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::QueryError` if execution fails
    pub fn execute_count(&self, sql: &str, tenant_id: &str) -> Result<usize> {
        todo!("Implement QueryExecutor::execute_count")
    }
}
