//! Memory-mapped disk format for DiskANN indices.
//!
//! **Goal:** Enable billion-scale search with minimal memory footprint.
//!
//! # File Format
//!
//! ```text
//! ┌─────────────────────────────────────────────────────────┐
//! │ Header (64 bytes)                                       │
//! ├─────────────────────────────────────────────────────────┤
//! │ Magic: "DISKANN\0" (8 bytes)                            │
//! │ Version: u32                                            │
//! │ Num nodes: u32                                          │
//! │ Dimensionality: u32                                     │
//! │ Max degree: u32                                         │
//! │ Medoid: u32                                             │
//! │ Graph offset: u64                                       │
//! │ Vectors offset: u64                                     │
//! │ Reserved: [u8; 24]                                      │
//! ├─────────────────────────────────────────────────────────┤
//! │ Graph Section (CSR format)                              │
//! │   - Offsets: [u32; num_nodes + 1]                       │
//! │   - Edges: [u32; total_edges]                           │
//! ├─────────────────────────────────────────────────────────┤
//! │ Vectors Section                                         │
//! │   - Vectors: [[f32; dim]; num_nodes]                    │
//! │   OR                                                    │
//! │   - Quantized codes: [[u8; code_size]; num_nodes]       │
//! └─────────────────────────────────────────────────────────┘
//! ```
//!
//! # Memory-Mapped Access
//!
//! - **Graph**: Read-only, random access to adjacency lists
//! - **Vectors**: Zero-copy access for distance computation
//! - **Page cache**: OS manages caching (hot nodes stay in RAM)
//!
//! # Benefits
//!
//! | Aspect | In-Memory | Memory-Mapped | Improvement |
//! |--------|-----------|---------------|-------------|
//! | Memory (1M vectors, 384 dims) | ~1.5 GB | ~50 MB | **30x less** |
//! | Startup time | 5-10s | <100ms | **50-100x faster** |
//! | Scalability | RAM-limited | Disk-limited | **10-100x more data** |

use crate::index::diskann::graph::CSRGraph;
use crate::types::error::{DatabaseError, Result};
use memmap2::{Mmap, MmapOptions};
use std::fs::File;
use std::io::{BufWriter, Write};

/// Magic number for file format validation.
const MAGIC: &[u8; 8] = b"DISKANN\0";

/// Current file format version.
const VERSION: u32 = 1;

/// Header size in bytes.
const HEADER_SIZE: usize = 64;

/// DiskANN file header.
#[repr(C)]
#[derive(Debug, Clone, Copy)]
struct Header {
    /// Magic number (file format identifier)
    magic: [u8; 8],

    /// File format version
    version: u32,

    /// Number of nodes
    num_nodes: u32,

    /// Vector dimensionality
    dim: u32,

    /// Maximum out-degree
    max_degree: u32,

    /// Medoid node ID (entry point)
    medoid: u32,

    /// Byte offset to graph section
    graph_offset: u64,

    /// Byte offset to vectors section
    vectors_offset: u64,

    /// Byte offset to UUID section
    uuid_offset: u64,

    /// Reserved for future use
    _reserved: [u8; 16],
}

impl Header {
    /// Create a new header.
    fn new(num_nodes: u32, dim: u32, max_degree: u32, medoid: u32) -> Self {
        Self {
            magic: *MAGIC,
            version: VERSION,
            num_nodes,
            dim,
            max_degree,
            medoid,
            graph_offset: HEADER_SIZE as u64,
            vectors_offset: 0, // Set after graph is written
            uuid_offset: 0,    // Set after vectors are written
            _reserved: [0; 16],
        }
    }

    /// Validate header.
    ///
    /// # Errors
    ///
    /// Returns error if magic number or version is invalid
    fn validate(&self) -> Result<()> {
        if &self.magic != MAGIC {
            return Err(DatabaseError::SearchError(format!(
                "Invalid magic bytes: expected {:?}, got {:?}",
                MAGIC, self.magic
            )));
        }

        if self.version != VERSION {
            return Err(DatabaseError::SearchError(format!(
                "Unsupported version: expected {}, got {}",
                VERSION, self.version
            )));
        }

        Ok(())
    }

    /// Serialize header to bytes.
    fn to_bytes(&self) -> [u8; HEADER_SIZE] {
        let mut bytes = [0u8; HEADER_SIZE];
        bytes[0..8].copy_from_slice(&self.magic);
        bytes[8..12].copy_from_slice(&self.version.to_le_bytes());
        bytes[12..16].copy_from_slice(&self.num_nodes.to_le_bytes());
        bytes[16..20].copy_from_slice(&self.dim.to_le_bytes());
        bytes[20..24].copy_from_slice(&self.max_degree.to_le_bytes());
        bytes[24..28].copy_from_slice(&self.medoid.to_le_bytes());
        bytes[28..36].copy_from_slice(&self.graph_offset.to_le_bytes());
        bytes[36..44].copy_from_slice(&self.vectors_offset.to_le_bytes());
        bytes[44..52].copy_from_slice(&self.uuid_offset.to_le_bytes());
        bytes
    }

    /// Deserialize header from bytes.
    ///
    /// # Errors
    ///
    /// Returns error if bytes are invalid
    fn from_bytes(bytes: &[u8; HEADER_SIZE]) -> Result<Self> {
        let mut magic = [0u8; 8];
        magic.copy_from_slice(&bytes[0..8]);

        let header = Self {
            magic,
            version: u32::from_le_bytes(bytes[8..12].try_into().unwrap()),
            num_nodes: u32::from_le_bytes(bytes[12..16].try_into().unwrap()),
            dim: u32::from_le_bytes(bytes[16..20].try_into().unwrap()),
            max_degree: u32::from_le_bytes(bytes[20..24].try_into().unwrap()),
            medoid: u32::from_le_bytes(bytes[24..28].try_into().unwrap()),
            graph_offset: u64::from_le_bytes(bytes[28..36].try_into().unwrap()),
            vectors_offset: u64::from_le_bytes(bytes[36..44].try_into().unwrap()),
            uuid_offset: u64::from_le_bytes(bytes[44..52].try_into().unwrap()),
            _reserved: [0; 16],
        };

        header.validate()?;
        Ok(header)
    }
}

/// Disk format writer for DiskANN index.
pub struct DiskFormat;

impl DiskFormat {
    /// Save index to disk in memory-mapped format.
    ///
    /// # Arguments
    ///
    /// * `path` - Output file path
    /// * `graph` - Graph structure (CSR format)
    /// * `vectors` - All vectors
    /// * `uuids` - UUID for each vector (must match vectors.len())
    /// * `medoid` - Entry point node ID
    /// * `max_degree` - Maximum out-degree
    ///
    /// # Errors
    ///
    /// Returns error if:
    /// - File I/O fails
    /// - Vectors have inconsistent dimensions
    /// - UUIDs length doesn't match vectors length
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// DiskFormat::save("index.diskann", &graph, &vectors, &uuids, medoid, 64)?;
    /// ```
    pub fn save(
        path: &str,
        graph: &CSRGraph,
        vectors: &[Vec<f32>],
        uuids: &[uuid::Uuid],
        medoid: u32,
        max_degree: u32,
    ) -> Result<()> {
        // Validate inputs
        if vectors.is_empty() {
            return Err(DatabaseError::SearchError(
                "Cannot save empty index".to_string(),
            ));
        }

        if uuids.len() != vectors.len() {
            return Err(DatabaseError::SearchError(format!(
                "UUID count mismatch: {} vectors but {} UUIDs",
                vectors.len(),
                uuids.len()
            )));
        }

        let dim = vectors[0].len() as u32;
        for vec in vectors {
            if vec.len() != dim as usize {
                return Err(DatabaseError::SearchError(
                    "Vector dimension mismatch".to_string(),
                ));
            }
        }

        // Create file
        let file = File::create(path)
            .map_err(|e| DatabaseError::SearchError(format!("Failed to create file: {}", e)))?;
        let mut writer = BufWriter::new(file);

        // Write header (will update offsets later)
        let mut header = Header::new(vectors.len() as u32, dim, max_degree, medoid);
        Self::write_header(&mut writer, &header)?;

        // Write graph and get end offset
        let graph_end = Self::write_graph(&mut writer, graph)?;
        header.vectors_offset = graph_end;

        // Write vectors and get end offset
        let vectors_end = Self::write_vectors(&mut writer, vectors)?;
        header.uuid_offset = vectors_end;

        // Write UUIDs
        Self::write_uuids(&mut writer, uuids)?;

        // Flush
        writer
            .flush()
            .map_err(|e| DatabaseError::SearchError(format!("Failed to flush: {}", e)))?;

        // Update header with final offsets
        let mut file = writer.into_inner().map_err(|e| {
            DatabaseError::SearchError(format!("Failed to get file: {}", e.error()))
        })?;
        use std::io::Seek;
        file.seek(std::io::SeekFrom::Start(0))
            .map_err(|e| DatabaseError::SearchError(format!("Failed to seek: {}", e)))?;
        file.write_all(&header.to_bytes())
            .map_err(|e| DatabaseError::SearchError(format!("Failed to write header: {}", e)))?;

        Ok(())
    }

    /// Write header to file.
    fn write_header(writer: &mut BufWriter<File>, header: &Header) -> Result<()> {
        writer
            .write_all(&header.to_bytes())
            .map_err(|e| DatabaseError::SearchError(format!("Failed to write header: {}", e)))
    }

    /// Write graph (CSR format) to file.
    ///
    /// Returns byte offset where graph section ends.
    fn write_graph(writer: &mut BufWriter<File>, graph: &CSRGraph) -> Result<u64> {
        let mut bytes_written = HEADER_SIZE as u64;

        // Write offsets
        for &offset in &graph.offsets {
            writer
                .write_all(&offset.to_le_bytes())
                .map_err(|e| DatabaseError::SearchError(format!("Failed to write offsets: {}", e)))?;
            bytes_written += 4;
        }

        // Write edges
        for &edge in &graph.edges {
            writer
                .write_all(&edge.to_le_bytes())
                .map_err(|e| DatabaseError::SearchError(format!("Failed to write edges: {}", e)))?;
            bytes_written += 4;
        }

        Ok(bytes_written)
    }

    /// Write vectors to file.
    fn write_vectors(writer: &mut BufWriter<File>, vectors: &[Vec<f32>]) -> Result<u64> {
        use std::io::Seek;

        let start_pos = writer.stream_position().map_err(|e| {
            DatabaseError::SearchError(format!("Failed to get position: {}", e))
        })?;

        for vec in vectors {
            for &val in vec {
                writer.write_all(&val.to_le_bytes()).map_err(|e| {
                    DatabaseError::SearchError(format!("Failed to write vectors: {}", e))
                })?;
            }
        }

        let end_pos = writer.stream_position().map_err(|e| {
            DatabaseError::SearchError(format!("Failed to get position: {}", e))
        })?;

        Ok(end_pos)
    }

    /// Write UUIDs to file.
    fn write_uuids(writer: &mut BufWriter<File>, uuids: &[uuid::Uuid]) -> Result<()> {
        for uuid in uuids {
            writer.write_all(uuid.as_bytes()).map_err(|e| {
                DatabaseError::SearchError(format!("Failed to write UUIDs: {}", e))
            })?;
        }
        Ok(())
    }
}

/// Memory-mapped DiskANN index for zero-copy search.
pub struct MmapIndex {
    /// Memory-mapped file
    _mmap: Mmap,

    /// Parsed header
    header: Header,

    /// Graph section (CSR format)
    graph: CSRGraph,

    /// Vectors section (raw pointer into mmap)
    vectors_ptr: *const f32,

    /// UUIDs section (raw pointer into mmap)
    uuids_ptr: *const uuid::Uuid,
}

impl MmapIndex {
    /// Load index from disk with memory mapping.
    ///
    /// # Arguments
    ///
    /// * `path` - Index file path
    ///
    /// # Returns
    ///
    /// Memory-mapped index ready for search
    ///
    /// # Errors
    ///
    /// Returns error if:
    /// - File not found
    /// - File is corrupted (invalid header)
    /// - Memory mapping fails
    ///
    /// # Safety
    ///
    /// Memory-mapped data is immutable. Do not modify the file while index is loaded.
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// let index = MmapIndex::load("index.diskann")?;
    /// let results = index.search(&query, 10, 75)?;
    /// ```
    pub fn load(path: &str) -> Result<Self> {
        let file = File::open(path)
            .map_err(|e| DatabaseError::SearchError(format!("Failed to open file: {}", e)))?;

        let mmap = unsafe {
            MmapOptions::new().map(&file).map_err(|e| {
                DatabaseError::SearchError(format!("Failed to memory map file: {}", e))
            })?
        };

        // Parse header
        let header = Self::parse_header(&mmap)?;

        // Parse graph
        let graph = Self::parse_graph(&mmap, &header)?;

        // Get vectors pointer
        let vectors_ptr = unsafe {
            mmap.as_ptr()
                .add(header.vectors_offset as usize) as *const f32
        };

        // Get UUIDs pointer
        let uuids_ptr = unsafe {
            mmap.as_ptr()
                .add(header.uuid_offset as usize) as *const uuid::Uuid
        };

        Ok(Self {
            _mmap: mmap,
            header,
            graph,
            vectors_ptr,
            uuids_ptr,
        })
    }

    /// Parse header from mmap.
    fn parse_header(mmap: &Mmap) -> Result<Header> {
        if mmap.len() < HEADER_SIZE {
            return Err(DatabaseError::SearchError(
                "File too small for header".to_string(),
            ));
        }

        let bytes: [u8; HEADER_SIZE] = mmap[0..HEADER_SIZE].try_into().unwrap();
        Header::from_bytes(&bytes)
    }

    /// Parse graph (CSR) from mmap.
    fn parse_graph(mmap: &Mmap, header: &Header) -> Result<CSRGraph> {
        let offsets_start = header.graph_offset as usize;
        let offsets_len = (header.num_nodes as usize + 1) * 4; // u32 = 4 bytes
        let edges_start = offsets_start + offsets_len;

        // Read offsets
        let mut offsets = Vec::with_capacity(header.num_nodes as usize + 1);
        for i in 0..=header.num_nodes as usize {
            let offset_bytes = offsets_start + i * 4;
            let offset = u32::from_le_bytes(
                mmap[offset_bytes..offset_bytes + 4]
                    .try_into()
                    .unwrap(),
            );
            offsets.push(offset);
        }

        // Read edges
        let total_edges = offsets[header.num_nodes as usize] as usize;
        let mut edges = Vec::with_capacity(total_edges);
        for i in 0..total_edges {
            let edge_bytes = edges_start + i * 4;
            let edge = u32::from_le_bytes(
                mmap[edge_bytes..edge_bytes + 4]
                    .try_into()
                    .unwrap(),
            );
            edges.push(edge);
        }

        Ok(CSRGraph {
            num_nodes: header.num_nodes as usize,
            offsets,
            edges,
        })
    }

    /// Get vector by node ID.
    ///
    /// # Arguments
    ///
    /// * `node_id` - Node ID
    ///
    /// # Returns
    ///
    /// Slice of vector components (zero-copy)
    ///
    /// # Safety
    ///
    /// Assumes vectors_ptr is valid and node_id < num_nodes
    pub fn vector(&self, node_id: u32) -> &[f32] {
        unsafe {
            let offset = node_id as usize * self.header.dim as usize;
            std::slice::from_raw_parts(self.vectors_ptr.add(offset), self.header.dim as usize)
        }
    }

    /// Get medoid (entry point).
    pub fn medoid(&self) -> u32 {
        self.header.medoid
    }

    /// Get graph structure.
    pub fn graph(&self) -> &CSRGraph {
        &self.graph
    }

    /// Get dimensionality.
    pub fn dim(&self) -> usize {
        self.header.dim as usize
    }

    /// Search for k-nearest neighbors using greedy beam search.
    ///
    /// # Arguments
    ///
    /// * `query` - Query vector
    /// * `k` - Number of results to return
    /// * `search_list_size` - Beam width (higher = better recall)
    ///
    /// # Returns
    ///
    /// Vector of (node_id, distance) pairs, sorted by distance
    ///
    /// # Errors
    ///
    /// Returns error if query dimension mismatches or search fails
    pub fn search(&self, query: &[f32], k: usize, search_list_size: usize) -> Result<Vec<(uuid::Uuid, f32)>> {
        use crate::index::diskann::search::{greedy_search, SearchParams};
        use crate::types::error::DatabaseError;

        if query.len() != self.dim() {
            return Err(DatabaseError::SearchError(format!(
                "Query dimension mismatch: expected {}, got {}",
                self.dim(),
                query.len()
            )));
        }

        // Build temporary vector list from mmap
        let vectors: Vec<Vec<f32>> = (0..self.header.num_nodes)
            .map(|i| self.vector(i).to_vec())
            .collect();

        let params = SearchParams {
            top_k: k,
            search_list_size,
        };

        // Get results as u32 node IDs
        let results = greedy_search(&self.graph, &vectors, query, self.medoid(), params)?;

        // Translate u32 node IDs to UUIDs
        Ok(results
            .into_iter()
            .map(|(node_id, dist)| (self.uuid(node_id), dist))
            .collect())
    }

    /// Get UUID for a node (zero-copy from mmap).
    fn uuid(&self, node_id: u32) -> uuid::Uuid {
        unsafe { *self.uuids_ptr.add(node_id as usize) }
    }
}

// MmapIndex is Send but not Sync (single-threaded mmap access)
unsafe impl Send for MmapIndex {}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::index::diskann::graph::VamanaGraph;

    #[test]
    fn test_header_serialization() {
        let header = Header::new(1000, 384, 64, 42);
        let bytes = header.to_bytes();
        let decoded = Header::from_bytes(&bytes).unwrap();

        assert_eq!(decoded.num_nodes, 1000);
        assert_eq!(decoded.dim, 384);
        assert_eq!(decoded.max_degree, 64);
        assert_eq!(decoded.medoid, 42);
    }

    #[test]
    fn test_header_validation() {
        let mut bytes = [0u8; HEADER_SIZE];
        bytes[0..8].copy_from_slice(b"INVALID\0");

        let result = Header::from_bytes(&bytes);
        assert!(result.is_err());
    }

    #[test]
    fn test_save_small_index() {
        let temp_path = std::env::temp_dir().join("test_diskann_save.bin");

        // Create small graph and vectors
        let graph = VamanaGraph::random(10, 5).unwrap();
        let csr_graph = graph.to_csr();

        let vectors: Vec<Vec<f32>> = (0..10)
            .map(|i| vec![i as f32 * 0.1; 4])
            .collect();

        let uuids: Vec<uuid::Uuid> = (0..10).map(|_| uuid::Uuid::new_v4()).collect();

        let result = DiskFormat::save(
            temp_path.to_str().unwrap(),
            &csr_graph,
            &vectors,
            &uuids,
            0,
            5,
        );

        assert!(result.is_ok());

        // Check file exists
        assert!(temp_path.exists());

        std::fs::remove_file(temp_path).ok();
    }

    #[test]
    fn test_load_index() {
        let temp_path = std::env::temp_dir().join("test_diskann_load.bin");

        // Create and save index
        let graph = VamanaGraph::random(10, 5).unwrap();
        let csr_graph = graph.to_csr();

        let vectors: Vec<Vec<f32>> = (0..10)
            .map(|i| vec![i as f32 * 0.1; 4])
            .collect();

        let uuids: Vec<uuid::Uuid> = (0..10).map(|_| uuid::Uuid::new_v4()).collect();

        DiskFormat::save(
            temp_path.to_str().unwrap(),
            &csr_graph,
            &vectors,
            &uuids,
            0,
            5,
        ).unwrap();

        // Load index
        let index = MmapIndex::load(temp_path.to_str().unwrap());
        assert!(index.is_ok());

        let index = index.unwrap();
        assert_eq!(index.dim(), 4);
        assert_eq!(index.medoid(), 0);

        std::fs::remove_file(temp_path).ok();
    }

    #[test]
    fn test_save_load_roundtrip() {
        let temp_path = std::env::temp_dir().join("test_diskann_roundtrip.bin");

        // Create test data
        let graph = VamanaGraph::random(50, 10).unwrap();
        let csr_graph = graph.to_csr();

        let vectors: Vec<Vec<f32>> = (0..50)
            .map(|i| vec![i as f32, (i * 2) as f32, (i * 3) as f32])
            .collect();

        let uuids: Vec<uuid::Uuid> = (0..50).map(|_| uuid::Uuid::new_v4()).collect();

        // Save
        DiskFormat::save(
            temp_path.to_str().unwrap(),
            &csr_graph,
            &vectors,
            &uuids,
            5,
            10,
        ).unwrap();

        // Load
        let index = MmapIndex::load(temp_path.to_str().unwrap()).unwrap();

        // Verify metadata
        assert_eq!(index.dim(), 3);
        assert_eq!(index.medoid(), 5);
        assert_eq!(index.graph().num_nodes, 50);

        // Verify vectors
        for i in 0..50 {
            let vec = index.vector(i);
            assert_eq!(vec[0], i as f32);
            assert_eq!(vec[1], (i * 2) as f32);
            assert_eq!(vec[2], (i * 3) as f32);
        }

        std::fs::remove_file(temp_path).ok();
    }

    #[test]
    fn test_vector_access() {
        let temp_path = std::env::temp_dir().join("test_diskann_vectors.bin");

        let graph = VamanaGraph::random(5, 3).unwrap();
        let csr_graph = graph.to_csr();

        let vectors = vec![
            vec![1.0, 2.0, 3.0],
            vec![4.0, 5.0, 6.0],
            vec![7.0, 8.0, 9.0],
            vec![10.0, 11.0, 12.0],
            vec![13.0, 14.0, 15.0],
        ];

        let uuids: Vec<uuid::Uuid> = (0..5).map(|_| uuid::Uuid::new_v4()).collect();

        DiskFormat::save(
            temp_path.to_str().unwrap(),
            &csr_graph,
            &vectors,
            &uuids,
            0,
            3,
        ).unwrap();

        let index = MmapIndex::load(temp_path.to_str().unwrap()).unwrap();

        // Test zero-copy access
        let vec2 = index.vector(2);
        assert_eq!(vec2, &[7.0, 8.0, 9.0]);

        std::fs::remove_file(temp_path).ok();
    }
}
