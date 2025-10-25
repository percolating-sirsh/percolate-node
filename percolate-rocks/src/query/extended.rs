//! Extended SQL syntax for REM database.
//!
//! Supports:
//! - Key lookups: `SELECT * FROM kv WHERE key IN (...)`
//! - Graph traversal: `TRAVERSE FROM uuid DEPTH n DIRECTION dir [TYPE rel]`
//! - Semantic search: `SEARCH 'query' IN table [WHERE ...]`

use crate::types::{Result, DatabaseError};
use serde::{Deserialize, Serialize};

/// Extended query types beyond standard SQL.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ExtendedQuery {
    /// Key lookup query.
    KeyLookup(KeyLookupQuery),

    /// Graph traversal query.
    Traverse(TraverseQuery),

    /// Semantic search query.
    Search(SearchQuery),

    /// Standard SQL (passthrough to sqlparser).
    Sql(String),
}

/// Key lookup query.
///
/// Syntax: `SELECT * FROM kv WHERE key IN ('key1', 'key2', ...)`
/// Or: `LOOKUP 'key1', 'key2', ...`
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KeyLookupQuery {
    /// Keys to lookup (global key index search).
    pub keys: Vec<String>,

    /// Optional field selection (default: all fields).
    pub fields: Option<Vec<String>>,

    /// Include system fields (id, created_at, etc.).
    pub include_system: bool,

    /// Include edges.
    pub include_edges: bool,
}

impl KeyLookupQuery {
    /// Parse from SQL: `SELECT * FROM kv WHERE key IN (...)`
    ///
    /// # Arguments
    ///
    /// * `sql` - SQL string
    ///
    /// # Returns
    ///
    /// Parsed `KeyLookupQuery`
    ///
    /// # Errors
    ///
    /// Returns error if SQL doesn't match key lookup pattern
    pub fn from_sql(sql: &str) -> Result<Self> {
        let sql_lower = sql.to_lowercase();

        // Check for "where key in" pattern
        if !sql_lower.contains("where key in") && !sql_lower.contains("where key=") {
            return Err(DatabaseError::QueryError(
                "Not a key lookup query (missing WHERE key IN or WHERE key=)".to_string()
            ));
        }

        // Extract keys from IN clause
        let keys = Self::extract_keys_from_sql(sql)?;

        // Check field selection
        let fields = if sql_lower.contains("select *") {
            None
        } else {
            Some(Self::extract_fields_from_sql(sql)?)
        };

        Ok(Self {
            keys,
            fields,
            include_system: true,
            include_edges: false,
        })
    }

    /// Parse from LOOKUP syntax: `LOOKUP 'key1', 'key2'`
    pub fn from_lookup_syntax(syntax: &str) -> Result<Self> {
        let trimmed = syntax.trim();

        if !trimmed.to_lowercase().starts_with("lookup") {
            return Err(DatabaseError::QueryError(
                "Not a LOOKUP query".to_string()
            ));
        }

        // Extract keys after LOOKUP keyword
        let keys_str = trimmed[6..].trim();
        let keys = Self::parse_key_list(keys_str)?;

        Ok(Self {
            keys,
            fields: None,
            include_system: true,
            include_edges: false,
        })
    }

    fn extract_keys_from_sql(sql: &str) -> Result<Vec<String>> {
        // Find IN (...) clause
        let in_start = sql.to_lowercase().find("in").ok_or_else(|| {
            DatabaseError::QueryError("Missing IN clause".to_string())
        })?;

        let rest = &sql[in_start + 2..].trim();
        let paren_start = rest.find('(').ok_or_else(|| {
            DatabaseError::QueryError("Missing opening parenthesis".to_string())
        })?;

        let paren_end = rest.find(')').ok_or_else(|| {
            DatabaseError::QueryError("Missing closing parenthesis".to_string())
        })?;

        let keys_str = &rest[paren_start + 1..paren_end];
        Self::parse_key_list(keys_str)
    }

    fn parse_key_list(keys_str: &str) -> Result<Vec<String>> {
        let keys: Vec<String> = keys_str
            .split(',')
            .map(|k| k.trim().trim_matches('\'').trim_matches('"').to_string())
            .filter(|k| !k.is_empty())
            .collect();

        if keys.is_empty() {
            return Err(DatabaseError::QueryError("No keys specified".to_string()));
        }

        Ok(keys)
    }

    fn extract_fields_from_sql(_sql: &str) -> Result<Vec<String>> {
        // TODO: Parse field list from SELECT clause
        // For now, return error to encourage SELECT *
        Err(DatabaseError::QueryError(
            "Field selection not yet supported - use SELECT *".to_string()
        ))
    }
}

/// Graph traversal query.
///
/// Syntax: `TRAVERSE FROM 'uuid' DEPTH n DIRECTION dir [TYPE 'rel']`
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TraverseQuery {
    /// Starting entity UUID.
    pub start_uuid: String,

    /// Traversal depth (1-10).
    pub depth: usize,

    /// Traversal direction.
    pub direction: TraverseDirection,

    /// Optional relationship type filter.
    pub rel_type: Option<String>,

    /// Include edge properties.
    pub include_edge_props: bool,
}

/// Traversal direction.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
pub enum TraverseDirection {
    /// Follow outgoing edges.
    Out,
    /// Follow incoming edges.
    In,
    /// Follow both directions.
    Both,
}

impl TraverseQuery {
    /// Parse from TRAVERSE syntax.
    ///
    /// # Syntax
    ///
    /// ```text
    /// TRAVERSE FROM 'uuid' DEPTH 2 DIRECTION out
    /// TRAVERSE FROM 'uuid' DEPTH 3 DIRECTION both TYPE 'authored'
    /// ```
    pub fn from_syntax(syntax: &str) -> Result<Self> {
        let lower = syntax.to_lowercase();

        if !lower.starts_with("traverse") {
            return Err(DatabaseError::QueryError("Not a TRAVERSE query".to_string()));
        }

        // Extract UUID
        let start_uuid = Self::extract_value_after(&lower, "from")?;

        // Extract depth
        let depth_str = Self::extract_value_after(&lower, "depth")?;
        let depth: usize = depth_str.parse()
            .map_err(|_| DatabaseError::QueryError(format!("Invalid depth: {}", depth_str)))?;

        if depth == 0 || depth > 10 {
            return Err(DatabaseError::QueryError("Depth must be 1-10".to_string()));
        }

        // Extract direction
        let direction_str = Self::extract_value_after(&lower, "direction")?;
        let direction = match direction_str.as_str() {
            "out" => TraverseDirection::Out,
            "in" => TraverseDirection::In,
            "both" => TraverseDirection::Both,
            _ => return Err(DatabaseError::QueryError(
                format!("Invalid direction: {} (use out/in/both)", direction_str)
            )),
        };

        // Optional: Extract relationship type
        let rel_type = if lower.contains("type") {
            Some(Self::extract_value_after(&lower, "type")?)
        } else {
            None
        };

        Ok(Self {
            start_uuid,
            depth,
            direction,
            rel_type,
            include_edge_props: true,
        })
    }

    fn extract_value_after(text: &str, keyword: &str) -> Result<String> {
        let start = text.find(keyword).ok_or_else(|| {
            DatabaseError::QueryError(format!("Missing {} keyword", keyword))
        })?;

        let rest = &text[start + keyword.len()..].trim();

        // Extract value (either quoted string or next word)
        let value = if rest.starts_with('\'') || rest.starts_with('"') {
            let quote = rest.chars().next().unwrap();
            let end = rest[1..].find(quote).ok_or_else(|| {
                DatabaseError::QueryError(format!("Unclosed quote after {}", keyword))
            })?;
            rest[1..=end].to_string()
        } else {
            rest.split_whitespace()
                .next()
                .ok_or_else(|| DatabaseError::QueryError(
                    format!("Missing value after {}", keyword)
                ))?
                .to_string()
        };

        Ok(value)
    }
}

/// Semantic search query.
///
/// Syntax: `SEARCH 'query text' IN table [WHERE conditions] [LIMIT n]`
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchQuery {
    /// Search query text.
    pub query: String,

    /// Target table/schema.
    pub table: String,

    /// Optional SQL WHERE conditions for hybrid search.
    pub where_clause: Option<String>,

    /// Result limit (default: 10).
    pub limit: usize,
}

impl SearchQuery {
    /// Parse from SEARCH syntax.
    ///
    /// # Syntax
    ///
    /// ```text
    /// SEARCH 'rust programming' IN articles
    /// SEARCH 'python' IN articles WHERE category='tutorial' LIMIT 5
    /// ```
    pub fn from_syntax(syntax: &str) -> Result<Self> {
        let lower = syntax.to_lowercase();

        if !lower.starts_with("search") {
            return Err(DatabaseError::QueryError("Not a SEARCH query".to_string()));
        }

        // Extract query text (first quoted string)
        let query = Self::extract_quoted_string(syntax, "search")?;

        // Extract table name after IN (use original text, not lowercase)
        let table = Self::extract_value_after_keyword(syntax, "IN")?;

        // Extract WHERE clause if present
        let where_clause = if lower.contains("where") {
            let where_start = lower.find("where").unwrap();
            let limit_pos = lower.find("limit");

            let where_end = limit_pos.unwrap_or(syntax.len());
            let clause = syntax[where_start + 5..where_end].trim().to_string();

            Some(clause)
        } else {
            None
        };

        // Extract LIMIT if present
        let limit = if lower.contains("limit") {
            let limit_str = Self::extract_value_after_keyword(&lower, "limit")?;
            limit_str.parse().unwrap_or(10)
        } else {
            10
        };

        Ok(Self {
            query,
            table,
            where_clause,
            limit,
        })
    }

    fn extract_quoted_string(text: &str, after_keyword: &str) -> Result<String> {
        let lower = text.to_lowercase();
        let start = lower.find(after_keyword).ok_or_else(|| {
            DatabaseError::QueryError(format!("Missing {} keyword", after_keyword))
        })?;

        let rest = &text[start + after_keyword.len()..].trim();

        let quote = if rest.starts_with('\'') {
            '\''
        } else if rest.starts_with('"') {
            '"'
        } else {
            return Err(DatabaseError::QueryError("Missing quoted string".to_string()));
        };

        let end = rest[1..].find(quote).ok_or_else(|| {
            DatabaseError::QueryError("Unclosed quote".to_string())
        })?;

        Ok(rest[1..=end].to_string())
    }

    fn extract_value_after_keyword(text: &str, keyword: &str) -> Result<String> {
        // Case-insensitive search with word boundary
        let lower_text = text.to_lowercase();
        let lower_keyword = format!(" {} ", keyword.to_lowercase());

        let start = lower_text.find(&lower_keyword).ok_or_else(|| {
            DatabaseError::QueryError(format!("Missing {} keyword", keyword))
        })?;

        // Start after the keyword and surrounding spaces
        let rest = text[start + lower_keyword.len()..].trim();

        Ok(rest.split_whitespace()
            .next()
            .ok_or_else(|| DatabaseError::QueryError(
                format!("Missing value after {}", keyword)
            ))?
            .to_string())
    }
}

/// Parse extended query syntax.
///
/// # Arguments
///
/// * `query` - Query string (SQL, LOOKUP, TRAVERSE, or SEARCH)
///
/// # Returns
///
/// Parsed `ExtendedQuery`
///
/// # Errors
///
/// Returns error if query syntax is invalid
pub fn parse_extended_query(query: &str) -> Result<ExtendedQuery> {
    let trimmed = query.trim();
    let lower = trimmed.to_lowercase();

    // Detect query type by keyword
    if lower.starts_with("lookup") {
        Ok(ExtendedQuery::KeyLookup(KeyLookupQuery::from_lookup_syntax(trimmed)?))
    } else if lower.starts_with("traverse") {
        Ok(ExtendedQuery::Traverse(TraverseQuery::from_syntax(trimmed)?))
    } else if lower.starts_with("search") {
        Ok(ExtendedQuery::Search(SearchQuery::from_syntax(trimmed)?))
    } else if lower.contains("where key in") || lower.contains("where key=") {
        Ok(ExtendedQuery::KeyLookup(KeyLookupQuery::from_sql(trimmed)?))
    } else if lower.starts_with("select") {
        Ok(ExtendedQuery::Sql(trimmed.to_string()))
    } else {
        Err(DatabaseError::QueryError(
            "Unknown query type - use SELECT, LOOKUP, TRAVERSE, or SEARCH".to_string()
        ))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // ===== KEY LOOKUP TESTS =====

    #[test]
    fn test_key_lookup_single() {
        let query = KeyLookupQuery::from_lookup_syntax("LOOKUP 'user-550e8400'").unwrap();
        assert_eq!(query.keys.len(), 1);
        assert_eq!(query.keys[0], "user-550e8400");
    }

    #[test]
    fn test_key_lookup_multiple() {
        let query = KeyLookupQuery::from_lookup_syntax("LOOKUP 'alice', 'bob', 'charlie'").unwrap();
        assert_eq!(query.keys.len(), 3);
        assert_eq!(query.keys, vec!["alice", "bob", "charlie"]);
    }

    #[test]
    fn test_key_lookup_jira() {
        let query = KeyLookupQuery::from_lookup_syntax("LOOKUP 'TAP-1234'").unwrap();
        assert_eq!(query.keys[0], "TAP-1234");
    }

    #[test]
    fn test_key_lookup_sql_style() {
        let query = KeyLookupQuery::from_sql(
            "SELECT * FROM kv WHERE key IN ('alice', 'bob')"
        ).unwrap();
        assert_eq!(query.keys.len(), 2);
        assert_eq!(query.keys[0], "alice");
        assert_eq!(query.keys[1], "bob");
    }

    // ===== GRAPH TRAVERSAL TESTS =====

    #[test]
    fn test_traverse_outgoing_1hop() {
        let query = TraverseQuery::from_syntax(
            "TRAVERSE FROM '550e8400-e29b-41d4-a716-446655440000' DEPTH 1 DIRECTION out"
        ).unwrap();
        assert_eq!(query.depth, 1);
        assert_eq!(query.direction, TraverseDirection::Out);
        assert_eq!(query.rel_type, None);
    }

    #[test]
    fn test_traverse_reverse_with_type() {
        let query = TraverseQuery::from_syntax(
            "TRAVERSE FROM 'doc-uuid-123' DEPTH 1 DIRECTION in TYPE 'authored'"
        ).unwrap();
        assert_eq!(query.start_uuid, "doc-uuid-123");
        assert_eq!(query.direction, TraverseDirection::In);
        assert_eq!(query.rel_type, Some("authored".to_string()));
    }

    #[test]
    fn test_traverse_bidirectional() {
        let query = TraverseQuery::from_syntax(
            "TRAVERSE FROM 'user-alice' DEPTH 3 DIRECTION both"
        ).unwrap();
        assert_eq!(query.depth, 3);
        assert_eq!(query.direction, TraverseDirection::Both);
    }

    #[test]
    fn test_traverse_collaborators() {
        let query = TraverseQuery::from_syntax(
            "TRAVERSE FROM 'user-alice' DEPTH 2 DIRECTION out TYPE 'collaborated_with'"
        ).unwrap();
        assert_eq!(query.rel_type, Some("collaborated_with".to_string()));
    }

    #[test]
    fn test_traverse_invalid_depth() {
        let result = TraverseQuery::from_syntax(
            "TRAVERSE FROM 'uuid' DEPTH 15 DIRECTION out"
        );
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("Depth must be 1-10"));
    }

    // ===== SEMANTIC SEARCH TESTS =====

    #[test]
    fn test_search_basic() {
        let query = SearchQuery::from_syntax(
            "SEARCH 'rust programming' IN articles"
        ).unwrap();
        assert_eq!(query.query, "rust programming");
        assert_eq!(query.table, "articles");
        assert_eq!(query.limit, 10); // default
        assert_eq!(query.where_clause, None);
    }

    #[test]
    fn test_search_with_limit() {
        let query = SearchQuery::from_syntax(
            "SEARCH 'machine learning' IN papers LIMIT 5"
        ).unwrap();
        assert_eq!(query.query, "machine learning");
        assert_eq!(query.limit, 5);
    }

    #[test]
    fn test_search_hybrid_with_where() {
        let query = SearchQuery::from_syntax(
            "SEARCH 'Python tutorials' IN articles WHERE category='tutorial'"
        ).unwrap();
        assert_eq!(query.query, "Python tutorials");
        assert_eq!(query.table, "articles");
        assert!(query.where_clause.is_some());
        assert!(query.where_clause.unwrap().contains("category='tutorial'"));
    }

    #[test]
    fn test_search_time_filter() {
        let query = SearchQuery::from_syntax(
            "SEARCH 'async programming' IN articles WHERE created_at > '2024-01-01' LIMIT 10"
        ).unwrap();
        assert_eq!(query.limit, 10);
        assert!(query.where_clause.is_some());
    }

    #[test]
    fn test_search_multi_field_filter() {
        let query = SearchQuery::from_syntax(
            "SEARCH 'database design' IN articles WHERE category='engineering' AND status='published'"
        ).unwrap();
        let where_clause = query.where_clause.unwrap();
        assert!(where_clause.contains("category='engineering'"));
        assert!(where_clause.contains("AND"));
        assert!(where_clause.contains("status='published'"));
    }

    #[test]
    fn test_search_question_based() {
        let query = SearchQuery::from_syntax(
            "SEARCH 'How do I handle errors in Rust?' IN documentation"
        ).unwrap();
        assert_eq!(query.query, "How do I handle errors in Rust?");
        assert_eq!(query.table, "documentation");
    }

    // ===== PARSE EXTENDED QUERY TESTS =====

    #[test]
    fn test_parse_lookup() {
        let q = parse_extended_query("LOOKUP 'key1'").unwrap();
        assert!(matches!(q, ExtendedQuery::KeyLookup(_)));
    }

    #[test]
    fn test_parse_traverse() {
        let q = parse_extended_query("TRAVERSE FROM 'uuid' DEPTH 2 DIRECTION out").unwrap();
        assert!(matches!(q, ExtendedQuery::Traverse(_)));
    }

    #[test]
    fn test_parse_search() {
        let q = parse_extended_query("SEARCH 'query' IN table").unwrap();
        assert!(matches!(q, ExtendedQuery::Search(_)));
    }

    #[test]
    fn test_parse_sql() {
        let q = parse_extended_query("SELECT * FROM users WHERE age > 18").unwrap();
        assert!(matches!(q, ExtendedQuery::Sql(_)));
    }

    #[test]
    fn test_parse_sql_with_key_in() {
        let q = parse_extended_query("SELECT * FROM kv WHERE key IN ('a', 'b')").unwrap();
        assert!(matches!(q, ExtendedQuery::KeyLookup(_)));
    }

    // ===== DOCUMENTATION EXAMPLES TESTS =====

    #[test]
    fn test_doc_example_user_lookup() {
        let q = parse_extended_query("LOOKUP 'user-123'").unwrap();
        if let ExtendedQuery::KeyLookup(lookup) = q {
            assert_eq!(lookup.keys, vec!["user-123"]);
        } else {
            panic!("Expected KeyLookup");
        }
    }

    #[test]
    fn test_doc_example_find_authors() {
        let q = parse_extended_query(
            "TRAVERSE FROM 'doc-uuid' DEPTH 1 DIRECTION in TYPE 'authored'"
        ).unwrap();
        if let ExtendedQuery::Traverse(trav) = q {
            assert_eq!(trav.direction, TraverseDirection::In);
            assert_eq!(trav.rel_type, Some("authored".to_string()));
        } else {
            panic!("Expected Traverse");
        }
    }

    #[test]
    fn test_doc_example_hybrid_search() {
        let q = parse_extended_query(
            "SEARCH 'Python tutorials' IN articles WHERE category='tutorial' AND created_at > '2024-01-01'"
        ).unwrap();
        if let ExtendedQuery::Search(search) = q {
            assert_eq!(search.query, "Python tutorials");
            assert!(search.where_clause.is_some());
        } else {
            panic!("Expected Search");
        }
    }

    #[test]
    fn test_doc_example_recent_content() {
        let q = parse_extended_query(
            "SEARCH 'Rust async' IN articles WHERE created_at > '2024-01-01' LIMIT 10"
        ).unwrap();
        if let ExtendedQuery::Search(search) = q {
            assert_eq!(search.limit, 10);
        } else {
            panic!("Expected Search");
        }
    }

    #[test]
    fn test_doc_example_knowledge_graph() {
        let q = parse_extended_query(
            "TRAVERSE FROM 'concept-rust' DEPTH 2 DIRECTION both TYPE 'related_to'"
        ).unwrap();
        if let ExtendedQuery::Traverse(trav) = q {
            assert_eq!(trav.depth, 2);
            assert_eq!(trav.direction, TraverseDirection::Both);
            assert_eq!(trav.rel_type, Some("related_to".to_string()));
        } else {
            panic!("Expected Traverse");
        }
    }

    // ===== ERROR HANDLING TESTS =====

    #[test]
    fn test_error_missing_direction() {
        let result = TraverseQuery::from_syntax("TRAVERSE FROM 'uuid' DEPTH 2");
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("Missing direction"));
    }

    #[test]
    fn test_error_invalid_direction() {
        let result = TraverseQuery::from_syntax(
            "TRAVERSE FROM 'uuid' DEPTH 2 DIRECTION sideways"
        );
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("Invalid direction"));
    }

    #[test]
    fn test_error_unclosed_quote() {
        let result = SearchQuery::from_syntax("SEARCH 'rust programming IN articles");
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("Unclosed quote"));
    }

    #[test]
    fn test_error_no_keys() {
        let result = KeyLookupQuery::from_lookup_syntax("LOOKUP ");
        assert!(result.is_err());
    }

    #[test]
    fn test_error_unknown_query_type() {
        let result = parse_extended_query("DELETE FROM users");
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("Unknown query type"));
    }
}
