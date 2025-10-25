//! PDF parsing.

use crate::types::Result;
use std::path::Path;

/// PDF parser.
pub struct PdfParser;

impl PdfParser {
    /// Parse PDF file to text.
    ///
    /// # Arguments
    ///
    /// * `path` - PDF file path
    ///
    /// # Returns
    ///
    /// Extracted text
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::IngestError` if parsing fails
    pub fn parse<P: AsRef<Path>>(path: P) -> Result<String> {
        todo!("Implement PdfParser::parse")
    }

    /// Parse PDF with page numbers.
    ///
    /// # Arguments
    ///
    /// * `path` - PDF file path
    ///
    /// # Returns
    ///
    /// Vector of (page_number, text) tuples
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::IngestError` if parsing fails
    pub fn parse_with_pages<P: AsRef<Path>>(path: P) -> Result<Vec<(usize, String)>> {
        todo!("Implement PdfParser::parse_with_pages")
    }
}
