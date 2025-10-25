//! Document ingestion and chunking.

pub mod chunker;
pub mod pdf;
pub mod text;

pub use chunker::{Chunker, ChunkStrategy};
pub use pdf::PdfParser;
pub use text::TextChunker;
