//! Predicate-based filtering for REM queries
//!
//! Provides SQL-like predicates that can be combined and evaluated against entities.

use serde::{Deserialize, Serialize};
use serde_json::Value;

/// Predicate for filtering entities and resources
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Predicate {
    // Comparison operations
    /// field == value
    Eq(String, Value),
    /// field != value
    Ne(String, Value),
    /// field > value
    Gt(String, Value),
    /// field >= value
    Gte(String, Value),
    /// field < value
    Lt(String, Value),
    /// field <= value
    Lte(String, Value),

    // Set operations
    /// field IN [values]
    In(String, Vec<Value>),
    /// field NOT IN [values]
    NotIn(String, Vec<Value>),

    // String operations
    /// field CONTAINS substring
    Contains(String, String),
    /// field STARTS WITH prefix
    StartsWith(String, String),
    /// field ENDS WITH suffix
    EndsWith(String, String),
    /// field MATCHES regex
    Matches(String, String),

    // Logical operations
    /// pred1 AND pred2 AND ...
    And(Vec<Predicate>),
    /// pred1 OR pred2 OR ...
    Or(Vec<Predicate>),
    /// NOT pred
    Not(Box<Predicate>),

    // Vector operations
    /// Semantic similarity search
    VectorSimilar {
        field: String,
        query: Vec<f32>,
        top_k: usize,
        min_score: f32,
    },

    // Existence checks
    /// field IS NOT NULL
    Exists(String),
    /// field IS NULL
    NotExists(String),

    // Always true/false (for composition)
    All,
    None,
}

impl Predicate {
    /// Evaluate predicate against a value map
    ///
    /// # Example
    ///
    /// ```rust
    /// use percolate_rust::memory::predicates::Predicate;
    /// use serde_json::{json, Value};
    /// use std::collections::HashMap;
    ///
    /// let mut fields = HashMap::new();
    /// fields.insert("status".to_string(), json!("active"));
    /// fields.insert("age".to_string(), json!(25));
    ///
    /// let pred = Predicate::Eq("status".into(), json!("active"));
    /// assert!(pred.evaluate(&fields));
    /// ```
    pub fn evaluate(&self, fields: &std::collections::HashMap<String, Value>) -> bool {
        match self {
            Predicate::Eq(field, value) => {
                fields.get(field).map(|v| v == value).unwrap_or(false)
            }
            Predicate::Ne(field, value) => {
                fields.get(field).map(|v| v != value).unwrap_or(true)
            }
            Predicate::Gt(field, value) => {
                fields.get(field).map(|v| compare_values(v, value) == std::cmp::Ordering::Greater).unwrap_or(false)
            }
            Predicate::Gte(field, value) => {
                fields.get(field).map(|v| {
                    let cmp = compare_values(v, value);
                    cmp == std::cmp::Ordering::Greater || cmp == std::cmp::Ordering::Equal
                }).unwrap_or(false)
            }
            Predicate::Lt(field, value) => {
                fields.get(field).map(|v| compare_values(v, value) == std::cmp::Ordering::Less).unwrap_or(false)
            }
            Predicate::Lte(field, value) => {
                fields.get(field).map(|v| {
                    let cmp = compare_values(v, value);
                    cmp == std::cmp::Ordering::Less || cmp == std::cmp::Ordering::Equal
                }).unwrap_or(false)
            }
            Predicate::In(field, values) => {
                fields.get(field).map(|v| values.contains(v)).unwrap_or(false)
            }
            Predicate::NotIn(field, values) => {
                fields.get(field).map(|v| !values.contains(v)).unwrap_or(true)
            }
            Predicate::Contains(field, substring) => {
                fields.get(field).and_then(|v| v.as_str()).map(|s| s.contains(substring)).unwrap_or(false)
            }
            Predicate::StartsWith(field, prefix) => {
                fields.get(field).and_then(|v| v.as_str()).map(|s| s.starts_with(prefix)).unwrap_or(false)
            }
            Predicate::EndsWith(field, suffix) => {
                fields.get(field).and_then(|v| v.as_str()).map(|s| s.ends_with(suffix)).unwrap_or(false)
            }
            Predicate::Matches(field, pattern) => {
                fields.get(field).and_then(|v| v.as_str()).map(|s| {
                    regex::Regex::new(pattern)
                        .map(|re| re.is_match(s))
                        .unwrap_or(false)
                }).unwrap_or(false)
            }
            Predicate::And(predicates) => {
                predicates.iter().all(|p| p.evaluate(fields))
            }
            Predicate::Or(predicates) => {
                predicates.iter().any(|p| p.evaluate(fields))
            }
            Predicate::Not(predicate) => {
                !predicate.evaluate(fields)
            }
            Predicate::VectorSimilar { .. } => {
                // Vector similarity requires HNSW index lookup, not evaluated here
                // This is handled at the query execution level
                true
            }
            Predicate::Exists(field) => {
                fields.contains_key(field)
            }
            Predicate::NotExists(field) => {
                !fields.contains_key(field)
            }
            Predicate::All => true,
            Predicate::None => false,
        }
    }
}

/// Compare two JSON values for ordering
fn compare_values(a: &Value, b: &Value) -> std::cmp::Ordering {
    use std::cmp::Ordering;

    match (a, b) {
        (Value::Number(a), Value::Number(b)) => {
            if let (Some(a_f), Some(b_f)) = (a.as_f64(), b.as_f64()) {
                a_f.partial_cmp(&b_f).unwrap_or(Ordering::Equal)
            } else {
                Ordering::Equal
            }
        }
        (Value::String(a), Value::String(b)) => a.cmp(b),
        (Value::Bool(a), Value::Bool(b)) => a.cmp(b),
        _ => Ordering::Equal,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use std::collections::HashMap;

    #[test]
    fn test_eq_predicate() {
        let mut fields = HashMap::new();
        fields.insert("status".to_string(), json!("active"));

        let pred = Predicate::Eq("status".to_string(), json!("active"));
        assert!(pred.evaluate(&fields));

        let pred = Predicate::Eq("status".to_string(), json!("inactive"));
        assert!(!pred.evaluate(&fields));
    }

    #[test]
    fn test_gt_predicate() {
        let mut fields = HashMap::new();
        fields.insert("age".to_string(), json!(25));

        let pred = Predicate::Gt("age".to_string(), json!(18));
        assert!(pred.evaluate(&fields));

        let pred = Predicate::Gt("age".to_string(), json!(30));
        assert!(!pred.evaluate(&fields));
    }

    #[test]
    fn test_and_predicate() {
        let mut fields = HashMap::new();
        fields.insert("status".to_string(), json!("active"));
        fields.insert("age".to_string(), json!(25));

        let pred = Predicate::And(vec![
            Predicate::Eq("status".to_string(), json!("active")),
            Predicate::Gt("age".to_string(), json!(18)),
        ]);
        assert!(pred.evaluate(&fields));
    }

    #[test]
    fn test_in_predicate() {
        let mut fields = HashMap::new();
        fields.insert("status".to_string(), json!("active"));

        let pred = Predicate::In(
            "status".to_string(),
            vec![json!("active"), json!("pending")],
        );
        assert!(pred.evaluate(&fields));
    }
}
