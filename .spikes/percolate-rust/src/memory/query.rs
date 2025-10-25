//! Query builder for REM memory system
//!
//! Provides a fluent interface for building queries with predicates, ordering, and limits.

use super::predicates::Predicate;
use serde::{Deserialize, Serialize};

/// Sort order for query results
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum Order {
    Asc,
    Desc,
}

/// Query builder for REM memory
///
/// # Example
///
/// ```rust
/// use percolate_rust::memory::{Query, Predicate, Order};
/// use serde_json::json;
///
/// let query = Query::new()
///     .filter(Predicate::Eq("status".into(), json!("active")))
///     .filter(Predicate::Gt("age".into(), json!(18)))
///     .order_by("created_at".into(), Order::Desc)
///     .limit(100);
/// ```
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Query {
    pub predicate: Predicate,
    pub order_by: Option<(String, Order)>,
    pub limit: Option<usize>,
    pub offset: Option<usize>,
}

impl Query {
    /// Create a new query with no filters (matches all)
    pub fn new() -> Self {
        Query {
            predicate: Predicate::All,
            order_by: None,
            limit: None,
            offset: None,
        }
    }

    /// Add a filter predicate (combines with existing filters using AND)
    ///
    /// # Example
    ///
    /// ```rust
    /// use percolate_rust::memory::{Query, Predicate};
    /// use serde_json::json;
    ///
    /// let query = Query::new()
    ///     .filter(Predicate::Eq("status".into(), json!("active")))
    ///     .filter(Predicate::Gt("age".into(), json!(18)));
    /// ```
    pub fn filter(mut self, predicate: Predicate) -> Self {
        self.predicate = match self.predicate {
            Predicate::All => predicate,
            existing => Predicate::And(vec![existing, predicate]),
        };
        self
    }

    /// Set ordering for results
    ///
    /// # Example
    ///
    /// ```rust
    /// use percolate_rust::memory::{Query, Order};
    ///
    /// let query = Query::new()
    ///     .order_by("created_at".into(), Order::Desc);
    /// ```
    pub fn order_by(mut self, field: String, order: Order) -> Self {
        self.order_by = Some((field, order));
        self
    }

    /// Limit the number of results
    ///
    /// # Example
    ///
    /// ```rust
    /// use percolate_rust::memory::Query;
    ///
    /// let query = Query::new().limit(100);
    /// ```
    pub fn limit(mut self, n: usize) -> Self {
        self.limit = Some(n);
        self
    }

    /// Skip the first N results (for pagination)
    ///
    /// # Example
    ///
    /// ```rust
    /// use percolate_rust::memory::Query;
    ///
    /// let query = Query::new()
    ///     .limit(100)
    ///     .offset(200); // Page 3 (skip first 200, take next 100)
    /// ```
    pub fn offset(mut self, n: usize) -> Self {
        self.offset = Some(n);
        self
    }
}

impl Default for Query {
    fn default() -> Self {
        Self::new()
    }
}

/// Builder for vector similarity queries
///
/// # Example
///
/// ```rust
/// use percolate_rust::memory::{Query, Predicate};
/// use serde_json::json;
///
/// let embedding = vec![0.1, 0.2, 0.3]; // 768-dim vector
///
/// let query = Query::new()
///     .filter(Predicate::VectorSimilar {
///         field: "embedding".into(),
///         query: embedding,
///         top_k: 20,
///         min_score: 0.7,
///     })
///     .filter(Predicate::Eq("language".into(), json!("en")))
///     .limit(10);
/// ```
pub struct VectorQueryBuilder {
    field: String,
    query: Vec<f32>,
    top_k: usize,
    min_score: f32,
    filters: Vec<Predicate>,
    limit: Option<usize>,
}

impl VectorQueryBuilder {
    /// Create a new vector query
    pub fn new(field: String, query: Vec<f32>) -> Self {
        VectorQueryBuilder {
            field,
            query,
            top_k: 10,
            min_score: 0.0,
            filters: Vec::new(),
            limit: None,
        }
    }

    /// Set the number of candidates to retrieve from vector index
    pub fn top_k(mut self, k: usize) -> Self {
        self.top_k = k;
        self
    }

    /// Set minimum similarity score threshold
    pub fn min_score(mut self, score: f32) -> Self {
        self.min_score = score;
        self
    }

    /// Add a filter predicate (applied after vector search)
    pub fn filter(mut self, predicate: Predicate) -> Self {
        self.filters.push(predicate);
        self
    }

    /// Limit final results (after filtering)
    pub fn limit(mut self, n: usize) -> Self {
        self.limit = Some(n);
        self
    }

    /// Build the final query
    pub fn build(self) -> Query {
        let mut predicates = vec![Predicate::VectorSimilar {
            field: self.field,
            query: self.query,
            top_k: self.top_k,
            min_score: self.min_score,
        }];
        predicates.extend(self.filters);

        let mut query = Query::new().filter(Predicate::And(predicates));
        if let Some(limit) = self.limit {
            query = query.limit(limit);
        }
        query
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_query_builder() {
        let query = Query::new()
            .filter(Predicate::Eq("status".to_string(), json!("active")))
            .filter(Predicate::Gt("age".to_string(), json!(18)))
            .order_by("created_at".to_string(), Order::Desc)
            .limit(100)
            .offset(0);

        assert!(matches!(query.predicate, Predicate::And(_)));
        assert!(query.order_by.is_some());
        assert_eq!(query.limit, Some(100));
        assert_eq!(query.offset, Some(0));
    }

    #[test]
    fn test_vector_query_builder() {
        let embedding = vec![0.1, 0.2, 0.3];
        let query = VectorQueryBuilder::new("embedding".to_string(), embedding)
            .top_k(20)
            .min_score(0.7)
            .filter(Predicate::Eq("language".to_string(), json!("en")))
            .limit(10)
            .build();

        assert!(matches!(query.predicate, Predicate::And(_)));
        assert_eq!(query.limit, Some(10));
    }

    #[test]
    fn test_empty_query() {
        let query = Query::new();
        assert!(matches!(query.predicate, Predicate::All));
        assert!(query.order_by.is_none());
        assert!(query.limit.is_none());
    }
}
