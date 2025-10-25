//! DiskANN vector index implementation.
//!
//! DiskANN (Disk-based Approximate Nearest Neighbor) is a graph-based ANN algorithm
//! optimized for SSD storage and billion-scale datasets. Key innovations:
//!
//! 1. **Vamana graph**: Degree-bounded graph with robust pruning for quality
//! 2. **Memory-mapped I/O**: Zero-copy disk access for massive datasets
//! 3. **Greedy search**: Single-layer beam search (vs HNSW's multi-layer)
//! 4. **Diversity-aware pruning**: Better graph connectivity than pure nearest neighbors
//!
//! # Algorithm Overview
//!
//! **Build phase** (Vamana algorithm):
//! ```text
//! 1. Initialize random graph (each node connects to R random neighbors)
//! 2. For each vertex v (in random order):
//!    a. Greedy search to find candidate neighbors
//!    b. Robust prune: select diverse, high-quality neighbors
//!    c. Add reverse edges to maintain connectivity
//! 3. Compute medoid (most central point for search entry)
//! ```
//!
//! **Search phase**:
//! ```text
//! 1. Start from medoid (global entry point)
//! 2. Greedy beam search:
//!    - Maintain priority queue of size L (search list)
//!    - Expand closest unvisited neighbors
//!    - Terminate when no improvement
//! 3. Return top-k results
//! ```
//!
//! # Performance Characteristics
//!
//! | Metric | Value | Notes |
//! |--------|-------|-------|
//! | Build time | O(n * R * L * d) | n=vectors, R=degree, L=search list, d=dims |
//! | Search time | O(L * d) | Independent of dataset size (graph property) |
//! | Memory (build) | O(n * R * 4 bytes) | Graph structure only |
//! | Memory (search) | O(L + R) | Beam + neighbors (tiny!) |
//! | Disk usage | O(n * (R*4 + d*4)) | Graph + vectors (or compressed) |
//!
//! # Example
//!
//! ```rust,ignore
//! use percolate_rocks::index::diskann::{DiskANNIndex, BuildParams};
//!
//! // Build index from vectors
//! let vectors = vec![vec![0.1, 0.2, 0.3], vec![0.4, 0.5, 0.6]];
//! let params = BuildParams {
//!     max_degree: 64,
//!     alpha: 1.2,
//!     search_list_size: 100,
//! };
//! let index = DiskANNIndex::build(&vectors, params)?;
//!
//! // Search
//! let query = vec![0.2, 0.3, 0.4];
//! let results = index.search(&query, 10, 75)?;
//!
//! // Save to disk (memory-mapped format)
//! index.save("index.diskann")?;
//!
//! // Load from disk (zero-copy)
//! let index = DiskANNIndex::load("index.diskann")?;
//! ```

mod builder;
mod graph;
mod mmap;
mod prune;
mod search;

pub use builder::{build_index, BuildParams};
pub use graph::{CSRGraph, GraphNeighbors, VamanaGraph};
pub use mmap::{DiskFormat, MmapIndex};
pub use prune::robust_prune;
pub use search::{greedy_search, SearchParams};

use crate::types::error::Result;

/// DiskANN index with Vamana graph structure.
///
/// Supports both in-memory and memory-mapped operation modes.
#[derive(Debug)]
pub struct DiskANNIndex {
    /// Graph structure (adjacency lists)
    graph: VamanaGraph,

    /// Entry point for search (most central node)
    medoid: u32,

    /// Maximum out-degree per vertex
    max_degree: usize,

    /// Vector dimensionality
    dim: usize,

    /// UUID mapping (node_id → uuid)
    uuids: Vec<uuid::Uuid>,
}

impl DiskANNIndex {
    /// Build a new DiskANN index from vectors.
    ///
    /// Uses the Vamana algorithm to construct a high-quality graph.
    ///
    /// # Arguments
    ///
    /// * `data` - Vector of (UUID, vector) tuples
    /// * `params` - Build parameters (degree, alpha, search list size)
    ///
    /// # Returns
    ///
    /// Constructed index ready for search
    ///
    /// # Errors
    ///
    /// Returns error if vectors are empty or have inconsistent dimensions
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// let data = vec![(uuid1, vec![0.1, 0.2]), (uuid2, vec![0.3, 0.4])];
    /// let params = BuildParams::default();
    /// let index = DiskANNIndex::build(data, params)?;
    /// ```
    pub fn build(data: Vec<(uuid::Uuid, Vec<f32>)>, params: BuildParams) -> Result<Self> {
        // Validate inputs
        if data.is_empty() {
            return Err(crate::types::error::DatabaseError::SearchError(
                "Cannot build index from empty vector set".to_string(),
            ));
        }

        // Separate UUIDs and vectors
        let (uuids, vectors): (Vec<_>, Vec<_>) = data.into_iter().unzip();
        let dim = vectors[0].len();

        // Build Vamana graph
        let (graph, medoid) = build_index(&vectors, params.clone())?;

        Ok(Self {
            graph,
            medoid,
            max_degree: params.max_degree,
            dim,
            uuids,
        })
    }

    /// Search for k-nearest neighbors.
    ///
    /// Uses greedy beam search starting from the medoid.
    ///
    /// # Arguments
    ///
    /// * `query` - Query vector (must match index dimensionality)
    /// * `k` - Number of results to return
    /// * `search_list_size` - Beam width (higher = better recall, slower)
    ///
    /// # Returns
    ///
    /// Vector of (node_id, distance) pairs, sorted by distance
    ///
    /// # Errors
    ///
    /// Returns error if query dimension mismatches index
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// let results = index.search(&query, 10, 75)?;
    /// assert_eq!(results.len(), 10);
    /// ```
    pub fn search(&self, query: &[f32], k: usize, search_list_size: usize) -> Result<Vec<(u32, f32)>> {
        use crate::types::error::DatabaseError;

        if query.len() != self.dim {
            return Err(DatabaseError::SearchError(format!(
                "Query dimension mismatch: expected {}, got {}",
                self.dim,
                query.len()
            )));
        }

        let search_params = SearchParams {
            top_k: k,
            search_list_size,
        };

        // Note: This is a placeholder - we need vectors to compute distances
        // In a real implementation, vectors would be stored separately
        // For now, return error indicating this needs vector storage
        Err(DatabaseError::SearchError(
            "Search requires vector storage - use with saved index or provide vectors".to_string(),
        ))
    }

    /// Save index to disk in memory-mapped format.
    ///
    /// # Arguments
    ///
    /// * `path` - Output file path
    /// * `vectors` - Vector data to save with the graph
    ///
    /// # Errors
    ///
    /// Returns error if file I/O fails
    pub fn save(&self, path: &str, vectors: &[Vec<f32>]) -> Result<()> {
        // Convert graph to CSR
        let csr_graph = self.graph.to_csr();

        // Save using DiskFormat (includes UUIDs)
        DiskFormat::save(path, &csr_graph, vectors, &self.uuids, self.medoid, self.max_degree as u32)
    }

    /// Load index from disk with memory mapping.
    ///
    /// Uses zero-copy access for efficient large-scale search.
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
    /// Returns error if file not found or corrupted
    pub fn load_mmap(path: &str) -> Result<MmapIndex> {
        MmapIndex::load(path)
    }

    /// Get index statistics.
    ///
    /// # Returns
    ///
    /// Statistics including node count, edge count, avg degree
    pub fn stats(&self) -> IndexStats {
        IndexStats {
            num_nodes: self.graph.num_nodes(),
            num_edges: self.graph.num_edges(),
            avg_degree: self.graph.num_edges() as f64 / self.graph.num_nodes() as f64,
            max_degree: self.max_degree,
            medoid: self.medoid,
        }
    }

    /// Get number of vectors in index.
    pub fn num_vectors(&self) -> usize {
        self.graph.num_nodes()
    }
}

/// Index statistics for monitoring and debugging.
#[derive(Debug, Clone)]
pub struct IndexStats {
    /// Total number of nodes
    pub num_nodes: usize,

    /// Total number of edges
    pub num_edges: usize,

    /// Average out-degree
    pub avg_degree: f64,

    /// Maximum out-degree
    pub max_degree: usize,

    /// Medoid node ID
    pub medoid: u32,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_build_small_index() {
        use uuid::Uuid;

        let data = vec![
            (Uuid::new_v4(), vec![1.0, 0.0, 0.0]),
            (Uuid::new_v4(), vec![0.9, 0.1, 0.0]),
            (Uuid::new_v4(), vec![0.0, 1.0, 0.0]),
            (Uuid::new_v4(), vec![0.0, 0.9, 0.1]),
            (Uuid::new_v4(), vec![0.0, 0.0, 1.0]),
        ];

        let params = BuildParams {
            max_degree: 3,
            alpha: 1.2,
            search_list_size: 5,
            num_iterations: 2,
        };

        let index = DiskANNIndex::build(data, params);
        assert!(index.is_ok());

        let index = index.unwrap();
        assert_eq!(index.num_vectors(), 5);
        assert_eq!(index.dim, 3);
    }

    #[test]
    fn test_save_load_roundtrip() {
        use uuid::Uuid;

        let data = vec![
            (Uuid::new_v4(), vec![1.0, 0.0]),
            (Uuid::new_v4(), vec![0.9, 0.1]),
            (Uuid::new_v4(), vec![0.0, 1.0]),
            (Uuid::new_v4(), vec![0.1, 0.9]),
        ];

        // Extract vectors for save (still needed for separate parameter)
        let vectors: Vec<Vec<f32>> = data.iter().map(|(_, v)| v.clone()).collect();

        let params = BuildParams {
            max_degree: 2,
            alpha: 1.2,
            search_list_size: 4,
            num_iterations: 1,
        };

        let index = DiskANNIndex::build(data, params).unwrap();

        // Save
        let temp_path = std::env::temp_dir().join("test_diskann_full.bin");
        index.save(temp_path.to_str().unwrap(), &vectors).unwrap();

        // Load
        let loaded = DiskANNIndex::load_mmap(temp_path.to_str().unwrap()).unwrap();
        assert_eq!(loaded.dim(), 2);
        assert_eq!(loaded.graph().num_nodes, 4);

        std::fs::remove_file(temp_path).ok();
    }

    #[test]
    fn test_mmap_search() {
        use uuid::Uuid;

        let uuid1 = Uuid::new_v4();
        let uuid2 = Uuid::new_v4();

        let data = vec![
            (uuid1, vec![1.0, 0.0, 0.0]),
            (uuid2, vec![0.9, 0.1, 0.0]),
            (Uuid::new_v4(), vec![0.0, 1.0, 0.0]),
            (Uuid::new_v4(), vec![0.0, 0.9, 0.1]),
            (Uuid::new_v4(), vec![0.0, 0.0, 1.0]),
        ];

        // Extract vectors for save
        let vectors: Vec<Vec<f32>> = data.iter().map(|(_, v)| v.clone()).collect();

        let params = BuildParams {
            max_degree: 3,
            alpha: 1.2,
            search_list_size: 5,
            num_iterations: 2,
        };
        let index = DiskANNIndex::build(data, params).unwrap();

        // Save
        let temp_path = std::env::temp_dir().join("test_diskann_search.bin");
        index.save(temp_path.to_str().unwrap(), &vectors).unwrap();

        // Load and search
        let loaded = DiskANNIndex::load_mmap(temp_path.to_str().unwrap()).unwrap();
        let query = vec![1.0, 0.0, 0.0];
        let results = loaded.search(&query, 3, 5).unwrap();

        // Should find results
        assert!(!results.is_empty());
        assert!(results.len() <= 3);

        // First result should be closest to query (uuid1 or uuid2)
        let (first_uuid, first_dist) = results[0];
        assert!(first_uuid == uuid1 || first_uuid == uuid2);
        assert!(first_dist < 0.5);  // Should be close

        std::fs::remove_file(temp_path).ok();
    }
}
