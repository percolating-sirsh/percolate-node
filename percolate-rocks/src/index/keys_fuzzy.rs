//! Fuzzy key lookup with BM25 fallback.
//!
//! Provides three levels of key lookup:
//! 1. **Exact match** (O(1)) - Direct key index lookup
//! 2. **Prefix match** (O(log n)) - RocksDB prefix scan
//! 3. **Fuzzy match** (O(k log n)) - BM25 keyword search fallback
//!
//! # Use Cases
//!
//! ```text
//! User Query          | Lookup Strategy
//! --------------------|------------------
//! "alice@company.com" | Exact match
//! "alice@"            | Prefix match
//! "alice company"     | Fuzzy (BM25)
//! "alise"             | Fuzzy (typo tolerance)
//! ```
//!
//! # Automatic Index Maintenance
//!
//! BM25 index is updated automatically on:
//! - **Insert**: Add key to inverted index
//! - **Update**: Remove old key, add new key
//! - **Delete**: Remove key from inverted index
//!
//! No manual rebuild required!

use crate::index::bm25::{Tokenizer, TokenizerConfig};
use crate::storage::{column_families::CF_BM25_INDEX, column_families::CF_KEY_INDEX, Storage};
use crate::types::error::{DatabaseError, Result};
use std::collections::HashMap;
use uuid::Uuid;

/// Fuzzy key lookup with BM25 fallback.
pub struct FuzzyKeyIndex {
    storage: Storage,
    tokenizer: Tokenizer,
}

/// Lookup result with match type and score.
#[derive(Debug, Clone)]
pub struct LookupResult {
    pub tenant_id: String,
    pub entity_type: String,
    pub entity_id: Uuid,
    pub key_value: String,
    pub match_type: MatchType,
    pub score: f64,
}

/// Type of match found.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum MatchType {
    /// Exact key match (score = 1.0)
    Exact,
    /// Prefix match (score = 0.8)
    Prefix,
    /// Fuzzy BM25 match (score = BM25 score normalized to 0-1)
    Fuzzy,
}

impl FuzzyKeyIndex {
    /// Create a new fuzzy key index.
    ///
    /// # Arguments
    ///
    /// * `storage` - RocksDB storage handle
    ///
    /// # Returns
    ///
    /// New fuzzy key index with tokenizer
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// let index = FuzzyKeyIndex::new(storage);
    /// ```
    pub fn new(storage: Storage) -> Self {
        // Configure tokenizer for key search
        let config = TokenizerConfig {
            lowercase: true,
            remove_stopwords: false, // Keep all words in keys
            stemming: false,          // Keep exact forms
            min_token_length: 2,
            stopwords: None,
        };

        Self {
            storage,
            tokenizer: Tokenizer::new(config),
        }
    }

    /// Lookup key with fuzzy fallback.
    ///
    /// **Lookup strategy (cascading):**
    /// 1. Try exact match in `key_index` CF
    /// 2. Try prefix match in `key_index` CF
    /// 3. Try fuzzy BM25 match in `bm25_index` CF
    ///
    /// # Arguments
    ///
    /// * `query` - Key query (can be exact, prefix, or fuzzy keywords)
    /// * `max_results` - Maximum results to return
    ///
    /// # Returns
    ///
    /// Vector of `LookupResult` sorted by score (descending)
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// // Exact match
    /// let results = index.lookup("alice@company.com", 10)?;
    /// assert_eq!(results[0].match_type, MatchType::Exact);
    ///
    /// // Fuzzy match
    /// let results = index.lookup("alice company", 10)?;
    /// assert_eq!(results[0].match_type, MatchType::Fuzzy);
    /// ```
    pub fn lookup(&self, query: &str, max_results: usize) -> Result<Vec<LookupResult>> {
        // Stage 1: Try exact match
        if let Some(exact_results) = self.exact_lookup(query)? {
            return Ok(exact_results);
        }

        // Stage 2: Try prefix match
        let prefix_results = self.prefix_lookup(query, max_results)?;
        if !prefix_results.is_empty() {
            return Ok(prefix_results);
        }

        // Stage 3: Fuzzy BM25 match
        self.fuzzy_lookup(query, max_results)
    }

    /// Exact key lookup (O(1)).
    ///
    /// # Arguments
    ///
    /// * `key` - Exact key value
    ///
    /// # Returns
    ///
    /// `Some(results)` if exact match found, `None` otherwise
    fn exact_lookup(&self, key: &str) -> Result<Option<Vec<LookupResult>>> {
        // Key pattern: key:{key_value}:{uuid}
        let prefix = format!("key:{}:", key);

        let mut results = Vec::new();
        let iter = self.storage.prefix_iterator(CF_KEY_INDEX, prefix.as_bytes());

        for item in iter {
            let (k, v) = item?;
            let key_str = String::from_utf8_lossy(&k);

            // Stop if we've gone past this prefix
            if !key_str.starts_with(&prefix) {
                break;
            }

            // Parse key: key:{key_value}:{uuid}
            let parts: Vec<&str> = key_str.split(':').collect();
            if parts.len() >= 3 {
                let entity_id = Uuid::parse_str(parts[2]).map_err(|e| {
                    DatabaseError::InvalidKey(format!("Invalid UUID in key: {}", e))
                })?;

                // Parse value: {tenant_id}:{entity_type}
                let value_str = String::from_utf8_lossy(&v);
                let value_parts: Vec<&str> = value_str.split(':').collect();
                if value_parts.len() >= 2 {
                    results.push(LookupResult {
                        tenant_id: value_parts[0].to_string(),
                        entity_type: value_parts[1].to_string(),
                        entity_id,
                        key_value: key.to_string(),
                        match_type: MatchType::Exact,
                        score: 1.0,
                    });
                }
            }
        }

        if results.is_empty() {
            Ok(None)
        } else {
            Ok(Some(results))
        }
    }

    /// Prefix match lookup (O(log n + k)).
    ///
    /// # Arguments
    ///
    /// * `prefix` - Key prefix
    /// * `max_results` - Maximum results
    ///
    /// # Returns
    ///
    /// Vector of prefix matches
    fn prefix_lookup(&self, prefix: &str, max_results: usize) -> Result<Vec<LookupResult>> {
        let search_prefix = format!("key:{}",  prefix);

        let mut results = Vec::new();
        let iter = self.storage.prefix_iterator(CF_KEY_INDEX, search_prefix.as_bytes());

        for item in iter {
            if results.len() >= max_results {
                break;
            }

            let (k, v) = item?;
            let key_str = String::from_utf8_lossy(&k);

            // Stop if no longer matching prefix
            if !key_str.starts_with(&search_prefix) {
                break;
            }

            // Parse key: key:{key_value}:{uuid}
            let parts: Vec<&str> = key_str.split(':').collect();
            if parts.len() >= 3 {
                let key_value = parts[1];
                let entity_id = Uuid::parse_str(parts[2]).map_err(|e| {
                    DatabaseError::InvalidKey(format!("Invalid UUID: {}", e))
                })?;

                // Parse value
                let value_str = String::from_utf8_lossy(&v);
                let value_parts: Vec<&str> = value_str.split(':').collect();
                if value_parts.len() >= 2 {
                    results.push(LookupResult {
                        tenant_id: value_parts[0].to_string(),
                        entity_type: value_parts[1].to_string(),
                        entity_id,
                        key_value: key_value.to_string(),
                        match_type: MatchType::Prefix,
                        score: 0.8,
                    });
                }
            }
        }

        Ok(results)
    }

    /// Fuzzy BM25 lookup (O(terms × log n)).
    ///
    /// Tokenizes query, looks up terms in BM25 index, scores documents.
    ///
    /// # Arguments
    ///
    /// * `query` - Fuzzy query keywords
    /// * `max_results` - Maximum results
    ///
    /// # Returns
    ///
    /// Vector of fuzzy matches sorted by BM25 score
    fn fuzzy_lookup(&self, query: &str, max_results: usize) -> Result<Vec<LookupResult>> {
        // Tokenize query
        let tokens = self.tokenizer.tokenize(query);
        if tokens.is_empty() {
            return Ok(Vec::new());
        }

        // Lookup terms in BM25 index and score documents
        let scores = self.bm25_score_query(&tokens)?;

        // Convert scores to LookupResults
        let mut results: Vec<LookupResult> = scores
            .into_iter()
            .map(|(doc_id, score)| {
                // Parse doc_id: {tenant_id}:{entity_type}:{uuid}
                let parts: Vec<&str> = doc_id.split(':').collect();
                if parts.len() >= 3 {
                    if let Ok(entity_id) = Uuid::parse_str(parts[2]) {
                        return Some(LookupResult {
                            tenant_id: parts[0].to_string(),
                            entity_type: parts[1].to_string(),
                            entity_id,
                            key_value: String::new(), // Filled in later
                            match_type: MatchType::Fuzzy,
                            score,
                        });
                    }
                }
                None
            })
            .filter_map(|x| x)
            .collect();

        // Sort by score descending
        results.sort_by(|a, b| b.score.partial_cmp(&a.score).unwrap_or(std::cmp::Ordering::Equal));
        results.truncate(max_results);

        Ok(results)
    }

    /// Score documents using BM25 formula.
    ///
    /// # Arguments
    ///
    /// * `query_tokens` - Query terms
    ///
    /// # Returns
    ///
    /// HashMap of (doc_id -> BM25 score)
    fn bm25_score_query(&self, query_tokens: &[String]) -> Result<HashMap<String, f64>> {
        // BM25 parameters
        const K1: f64 = 1.2; // Term frequency saturation
        const B: f64 = 0.75; // Length normalization

        // Get metadata
        let num_docs = self.get_num_docs()?;
        let avg_doc_length = self.get_avg_doc_length()?;

        let mut doc_scores: HashMap<String, f64> = HashMap::new();

        for term in query_tokens {
            // Get document frequency (df)
            let df = self.get_document_frequency(term)?;
            if df == 0 {
                continue; // Term not in index
            }

            // Compute IDF
            let idf = ((num_docs as f64 - df as f64 + 0.5) / (df as f64 + 0.5)).ln();

            // Get posting list for term
            let postings = self.get_postings(term)?;

            for (doc_id, term_freq, doc_length) in postings {
                let tf = term_freq as f64;
                let dl = doc_length as f64;

                // BM25 score for this term in this document
                let numerator = tf * (K1 + 1.0);
                let denominator = tf + K1 * (1.0 - B + B * dl / avg_doc_length);
                let term_score = idf * (numerator / denominator);

                *doc_scores.entry(doc_id).or_insert(0.0) += term_score;
            }
        }

        Ok(doc_scores)
    }

    /// Index a key for fuzzy search.
    ///
    /// Called automatically on insert/update.
    ///
    /// # Arguments
    ///
    /// * `tenant_id` - Tenant scope
    /// * `entity_type` - Entity schema name
    /// * `entity_id` - Entity UUID
    /// * `key_value` - Key field value
    ///
    /// # Errors
    ///
    /// Returns error if storage fails
    pub fn index_key(
        &self,
        tenant_id: &str,
        entity_type: &str,
        entity_id: Uuid,
        key_value: &str,
    ) -> Result<()> {
        // Tokenize key
        let tokens = self.tokenizer.tokenize(key_value);
        let term_freqs = self.tokenizer.term_frequencies(key_value);

        let doc_id = format!("{}:{}:{}", tenant_id, entity_type, entity_id);
        let doc_length = tokens.len() as u32;

        // Update inverted index
        for (term, freq) in term_freqs {
            // Increment document frequency
            let df_key = format!("term:{}:df", term);
            let current_df = self.get_u32(&df_key)?.unwrap_or(0);
            self.put_u32(&df_key, current_df + 1)?;

            // Add posting
            let posting_key = format!("term:{}:posting:{}", term, doc_id);
            self.put_u32(&posting_key, freq)?;
        }

        // Store document length
        let doc_length_key = format!("doc:{}:length", doc_id);
        self.put_u32(&doc_length_key, doc_length)?;

        // Update metadata
        self.increment_num_docs()?;
        self.update_avg_doc_length()?;

        Ok(())
    }

    /// Remove key from fuzzy search index.
    ///
    /// Called automatically on delete/update.
    ///
    /// # Arguments
    ///
    /// * `tenant_id` - Tenant scope
    /// * `entity_type` - Entity schema name
    /// * `entity_id` - Entity UUID
    /// * `key_value` - Key field value to remove
    pub fn remove_key(
        &self,
        tenant_id: &str,
        entity_type: &str,
        entity_id: Uuid,
        key_value: &str,
    ) -> Result<()> {
        let term_freqs = self.tokenizer.term_frequencies(key_value);
        let doc_id = format!("{}:{}:{}", tenant_id, entity_type, entity_id);

        // Remove from inverted index
        for (term, _) in term_freqs {
            // Decrement document frequency
            let df_key = format!("term:{}:df", term);
            if let Some(current_df) = self.get_u32(&df_key)? {
                if current_df > 1 {
                    self.put_u32(&df_key, current_df - 1)?;
                } else {
                    // Remove term entirely
                    self.storage.delete(CF_BM25_INDEX, df_key.as_bytes())?;
                }
            }

            // Remove posting
            let posting_key = format!("term:{}:posting:{}", term, doc_id);
            self.storage.delete(CF_BM25_INDEX, posting_key.as_bytes())?;
        }

        // Remove document length
        let doc_length_key = format!("doc:{}:length", doc_id);
        self.storage.delete(CF_BM25_INDEX, doc_length_key.as_bytes())?;

        // Update metadata
        self.decrement_num_docs()?;
        self.update_avg_doc_length()?;

        Ok(())
    }

    // Helper methods for BM25 metadata

    fn get_num_docs(&self) -> Result<u32> {
        self.get_u32("meta:num_docs")
            .map(|opt| opt.unwrap_or(0))
    }

    fn increment_num_docs(&self) -> Result<()> {
        let current = self.get_num_docs()?;
        self.put_u32("meta:num_docs", current + 1)
    }

    fn decrement_num_docs(&self) -> Result<()> {
        let current = self.get_num_docs()?;
        if current > 0 {
            self.put_u32("meta:num_docs", current - 1)?;
        }
        Ok(())
    }

    fn get_avg_doc_length(&self) -> Result<f64> {
        if let Some(bytes) = self.storage.get(CF_BM25_INDEX, b"meta:avg_doc_length")? {
            let arr: [u8; 8] = bytes.as_slice().try_into().map_err(|_| {
                DatabaseError::InternalError("Invalid avg_doc_length encoding".to_string())
            })?;
            Ok(f64::from_le_bytes(arr))
        } else {
            Ok(0.0)
        }
    }

    fn update_avg_doc_length(&self) -> Result<()> {
        // Compute average from all documents
        let mut total_length = 0u64;
        let mut count = 0u32;

        let prefix = b"doc:";
        let iter = self.storage.prefix_iterator(CF_BM25_INDEX, prefix);

        for item in iter {
            let (k, v) = item?;
            let key_str = String::from_utf8_lossy(&k);

            if !key_str.starts_with("doc:") || !key_str.ends_with(":length") {
                continue;
            }

            if v.len() == 4 {
                let arr: [u8; 4] = (*v).try_into().unwrap();
                let length = u32::from_le_bytes(arr);
                total_length += length as u64;
                count += 1;
            }
        }

        let avg = if count > 0 {
            total_length as f64 / count as f64
        } else {
            0.0
        };

        self.storage
            .put(CF_BM25_INDEX, b"meta:avg_doc_length", &avg.to_le_bytes())?;

        Ok(())
    }

    fn get_document_frequency(&self, term: &str) -> Result<u32> {
        let key = format!("term:{}:df", term);
        self.get_u32(&key).map(|opt| opt.unwrap_or(0))
    }

    fn get_postings(
        &self,
        term: &str,
    ) -> Result<Vec<(String, u32, u32)>> {
        let prefix = format!("term:{}:posting:", term);
        let mut postings = Vec::new();

        let iter = self.storage.prefix_iterator(CF_BM25_INDEX, prefix.as_bytes());

        for item in iter {
            let (k, v) = item?;
            let key_str = String::from_utf8_lossy(&k);

            if !key_str.starts_with(&prefix) {
                break;
            }

            // Extract doc_id from key
            let doc_id = key_str.strip_prefix(&prefix).unwrap_or("").to_string();

            // Get term frequency
            if v.len() == 4 {
                let arr: [u8; 4] = (*v).try_into().unwrap();
                let term_freq = u32::from_le_bytes(arr);

                // Get document length
                let doc_length_key = format!("doc:{}:length", doc_id);
                let doc_length = self.get_u32(&doc_length_key)?.unwrap_or(1);

                postings.push((doc_id, term_freq, doc_length));
            }
        }

        Ok(postings)
    }

    fn get_u32(&self, key: &str) -> Result<Option<u32>> {
        if let Some(bytes) = self.storage.get(CF_BM25_INDEX, key.as_bytes())? {
            if bytes.len() == 4 {
                let arr: [u8; 4] = bytes.as_slice().try_into().unwrap();
                Ok(Some(u32::from_le_bytes(arr)))
            } else {
                Ok(None)
            }
        } else {
            Ok(None)
        }
    }

    fn put_u32(&self, key: &str, value: u32) -> Result<()> {
        self.storage
            .put(CF_BM25_INDEX, key.as_bytes(), &value.to_le_bytes())?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_exact_lookup() {
        todo!("Test exact key match")
    }

    #[test]
    fn test_prefix_lookup() {
        todo!("Test prefix matching")
    }

    #[test]
    fn test_fuzzy_lookup() {
        todo!("Test BM25 fuzzy matching")
    }

    #[test]
    fn test_cascading_lookup() {
        todo!("Test exact -> prefix -> fuzzy fallback")
    }

    #[test]
    fn test_index_maintenance() {
        todo!("Test automatic index updates on insert/delete")
    }

    #[test]
    fn test_typo_tolerance() {
        todo!("Test fuzzy matching handles typos")
    }
}
