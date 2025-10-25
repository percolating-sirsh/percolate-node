//! Inverted index data structure for BM25.
//!
//! **Inverted index** maps terms to posting lists (documents containing the term).
//!
//! # Data Structure
//!
//! ```text
//! Term -> Posting List
//!
//! "rust"   -> [(doc_0, tf=2), (doc_2, tf=1)]
//! "python" -> [(doc_1, tf=1)]
//! "system" -> [(doc_0, tf=1)]
//! ```
//!
//! # Storage Layout in RocksDB
//!
//! ```text
//! Column Family: bm25_index
//!
//! Key Pattern                    | Value
//! -------------------------------|------------------
//! term:{term}:df                 | u32 (document frequency)
//! term:{term}:posting:{doc_id}   | u32 (term frequency)
//! meta:num_docs                  | u32
//! meta:avg_doc_length            | f64
//! doc:{doc_id}:length            | u32
//! ```

use crate::types::error::{DatabaseError, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Posting (term occurrence in a document).
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct Posting {
    /// Document ID
    pub doc_id: u32,

    /// Term frequency (number of times term appears in document)
    pub term_freq: u32,
}

/// Posting list for a term.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct PostingList {
    /// Document frequency (number of documents containing this term)
    pub doc_freq: u32,

    /// List of postings (doc_id -> term_freq)
    pub postings: Vec<Posting>,
}

impl PostingList {
    /// Create an empty posting list.
    pub fn new() -> Self {
        Self::default()
    }

    /// Add a posting to the list.
    ///
    /// # Arguments
    ///
    /// * `doc_id` - Document ID
    /// * `term_freq` - Term frequency in document
    pub fn add(&mut self, doc_id: u32, term_freq: u32) {
        self.postings.push(Posting { doc_id, term_freq });
        self.doc_freq += 1;
    }

    /// Remove a document from the posting list.
    ///
    /// # Arguments
    ///
    /// * `doc_id` - Document ID to remove
    ///
    /// # Returns
    ///
    /// `true` if document was found and removed
    pub fn remove(&mut self, doc_id: u32) -> bool {
        if let Some(pos) = self.postings.iter().position(|p| p.doc_id == doc_id) {
            self.postings.remove(pos);
            self.doc_freq -= 1;
            true
        } else {
            false
        }
    }

    /// Get term frequency for a document.
    ///
    /// # Arguments
    ///
    /// * `doc_id` - Document ID
    ///
    /// # Returns
    ///
    /// Term frequency, or 0 if document not in list
    pub fn term_freq(&self, doc_id: u32) -> u32 {
        self.postings
            .iter()
            .find(|p| p.doc_id == doc_id)
            .map(|p| p.term_freq)
            .unwrap_or(0)
    }
}

/// Inverted index mapping terms to posting lists.
#[derive(Debug, Clone, Default)]
pub struct InvertedIndex {
    /// Term -> PostingList
    index: HashMap<String, PostingList>,

    /// Total number of documents
    num_docs: u32,
}

impl InvertedIndex {
    /// Create a new empty inverted index.
    pub fn new() -> Self {
        Self::default()
    }

    /// Build inverted index from documents.
    ///
    /// # Arguments
    ///
    /// * `documents` - Iterator of (doc_id, term_frequencies) pairs
    ///   where term_frequencies is a HashMap<String, u32>
    ///
    /// # Returns
    ///
    /// Inverted index with all postings
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// let docs = vec![
    ///     (0, hashmap!{"rust".into() => 2, "system".into() => 1}),
    ///     (1, hashmap!{"python".into() => 1}),
    /// ];
    /// let index = InvertedIndex::build(docs.into_iter())?;
    /// ```
    pub fn build<I>(documents: I) -> Result<Self>
    where
        I: Iterator<Item = (u32, HashMap<String, u32>)>,
    {
        todo!("Build inverted index from term frequencies")
    }

    /// Get posting list for a term.
    ///
    /// # Arguments
    ///
    /// * `term` - Term to lookup
    ///
    /// # Returns
    ///
    /// Posting list, or empty list if term not found
    pub fn get(&self, term: &str) -> &PostingList {
        static EMPTY: PostingList = PostingList {
            doc_freq: 0,
            postings: Vec::new(),
        };
        self.index.get(term).unwrap_or(&EMPTY)
    }

    /// Add a document to the index.
    ///
    /// # Arguments
    ///
    /// * `doc_id` - Document ID
    /// * `term_freqs` - Term frequencies in document
    pub fn add_document(&mut self, doc_id: u32, term_freqs: HashMap<String, u32>) {
        for (term, freq) in term_freqs {
            self.index
                .entry(term)
                .or_insert_with(PostingList::new)
                .add(doc_id, freq);
        }
        self.num_docs += 1;
    }

    /// Remove a document from the index.
    ///
    /// # Arguments
    ///
    /// * `doc_id` - Document ID to remove
    pub fn remove_document(&mut self, doc_id: u32) {
        // Remove from all posting lists
        for posting_list in self.index.values_mut() {
            posting_list.remove(doc_id);
        }

        // Remove empty posting lists
        self.index.retain(|_, pl| pl.doc_freq > 0);

        self.num_docs -= 1;
    }

    /// Get total number of documents.
    pub fn num_docs(&self) -> u32 {
        self.num_docs
    }

    /// Get total number of unique terms.
    pub fn num_terms(&self) -> usize {
        self.index.len()
    }

    /// Get total number of postings (term occurrences).
    pub fn num_postings(&self) -> usize {
        self.index.values().map(|pl| pl.postings.len()).sum()
    }

    /// Iterate over all terms.
    pub fn terms(&self) -> impl Iterator<Item = &String> {
        self.index.keys()
    }

    /// Serialize to RocksDB.
    ///
    /// # Arguments
    ///
    /// * `storage` - RocksDB storage handle
    ///
    /// # Errors
    ///
    /// Returns error if storage fails
    pub fn save(&self, storage: &crate::storage::Storage) -> Result<()> {
        todo!("Write inverted index to RocksDB using key pattern")
    }

    /// Deserialize from RocksDB.
    ///
    /// # Arguments
    ///
    /// * `storage` - RocksDB storage handle
    ///
    /// # Returns
    ///
    /// Inverted index loaded from storage
    ///
    /// # Errors
    ///
    /// Returns error if storage fails or data corrupted
    pub fn load(storage: &crate::storage::Storage) -> Result<Self> {
        todo!("Read inverted index from RocksDB")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_posting_list_add() {
        todo!("Test adding postings to list")
    }

    #[test]
    fn test_posting_list_remove() {
        todo!("Test removing postings from list")
    }

    #[test]
    fn test_posting_list_term_freq() {
        todo!("Test term frequency lookup")
    }

    #[test]
    fn test_build_inverted_index() {
        todo!("Test building index from documents")
    }

    #[test]
    fn test_add_remove_document() {
        todo!("Test adding/removing documents")
    }

    #[test]
    fn test_index_stats() {
        todo!("Test statistics (num_docs, num_terms, num_postings)")
    }

    #[test]
    fn test_save_load_roundtrip() {
        todo!("Test RocksDB serialization")
    }
}
