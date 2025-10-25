//! Vamana graph data structure.
//!
//! Represents a degree-bounded directed graph where each node has:
//! - Out-edges: Forward adjacency list (node -> neighbors)
//! - In-edges: Reverse adjacency list (node -> reverse neighbors) [optional]
//!
//! # Memory Layout
//!
//! **Compact representation** (CSR - Compressed Sparse Row):
//! ```text
//! Graph with nodes [0, 1, 2]:
//! - Node 0: neighbors [1, 2]
//! - Node 1: neighbors [0, 2]
//! - Node 2: neighbors [1]
//!
//! CSR format:
//! offsets: [0, 2, 4, 5]       // offsets[i] = start of node i's neighbors
//! edges:   [1, 2, 0, 2, 1]    // concatenated neighbor lists
//!
//! Memory: O(num_edges) vs O(num_nodes * max_degree) for dense
//! ```

use crate::types::error::{DatabaseError, Result};
use serde::{Deserialize, Serialize};

/// Trait for graph structures that support neighbor queries.
///
/// Both VamanaGraph and CSRGraph implement this for search.
pub trait GraphNeighbors {
    /// Get neighbors of a node.
    fn neighbors(&self, node_id: u32) -> &[u32];

    /// Get number of nodes in the graph.
    fn num_nodes(&self) -> usize;
}

/// Vamana graph with degree-bounded adjacency lists.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VamanaGraph {
    /// Number of nodes in the graph
    num_nodes: usize,

    /// Adjacency lists (out-edges): node_id -> Vec<neighbor_id>
    ///
    /// Uses Vec<Vec<u32>> for build phase (easy modification).
    /// TODO: Compress to CSR format for search/save.
    adjacency: Vec<Vec<u32>>,
}

impl GraphNeighbors for VamanaGraph {
    fn neighbors(&self, node_id: u32) -> &[u32] {
        &self.adjacency[node_id as usize]
    }

    fn num_nodes(&self) -> usize {
        self.num_nodes
    }
}

impl VamanaGraph {
    /// Create a new empty graph.
    ///
    /// # Arguments
    ///
    /// * `num_nodes` - Number of nodes to allocate
    ///
    /// # Returns
    ///
    /// Empty graph with no edges
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// let graph = VamanaGraph::new(1000);
    /// ```
    pub fn new(num_nodes: usize) -> Self {
        Self {
            num_nodes,
            adjacency: vec![Vec::new(); num_nodes],
        }
    }

    /// Create a graph with random edges.
    ///
    /// Each node connects to `degree` random neighbors (without replacement).
    ///
    /// # Arguments
    ///
    /// * `num_nodes` - Number of nodes
    /// * `degree` - Target out-degree per node
    ///
    /// # Returns
    ///
    /// Randomly connected graph
    ///
    /// # Errors
    ///
    /// Returns error if degree >= num_nodes
    pub fn random(num_nodes: usize, degree: usize) -> Result<Self> {
        use rand::seq::SliceRandom;
        use rand::thread_rng;

        if degree >= num_nodes {
            return Err(DatabaseError::SearchError(
                format!("Degree {} must be < num_nodes {}", degree, num_nodes)
            ));
        }

        let mut graph = Self::new(num_nodes);
        let mut rng = thread_rng();

        // For each node, select random neighbors
        for node in 0..num_nodes {
            let mut candidates: Vec<u32> = (0..num_nodes as u32)
                .filter(|&n| n != node as u32)
                .collect();

            candidates.shuffle(&mut rng);
            graph.adjacency[node] = candidates.into_iter().take(degree).collect();
        }

        Ok(graph)
    }

    /// Get neighbors of a node.
    ///
    /// # Arguments
    ///
    /// * `node_id` - Node to query
    ///
    /// # Returns
    ///
    /// Slice of neighbor IDs (empty if node has no edges)
    ///
    /// # Panics
    ///
    /// Panics if node_id >= num_nodes (debug builds only)
    pub fn neighbors(&self, node_id: u32) -> &[u32] {
        debug_assert!((node_id as usize) < self.num_nodes);
        &self.adjacency[node_id as usize]
    }

    /// Set neighbors of a node (replaces existing edges).
    ///
    /// # Arguments
    ///
    /// * `node_id` - Node to update
    /// * `neighbors` - New neighbor list
    ///
    /// # Panics
    ///
    /// Panics if node_id >= num_nodes
    pub fn set_neighbors(&mut self, node_id: u32, neighbors: Vec<u32>) {
        debug_assert!((node_id as usize) < self.num_nodes);
        self.adjacency[node_id as usize] = neighbors;
    }

    /// Add an edge from source to target.
    ///
    /// Does not check for duplicates (caller must ensure uniqueness).
    ///
    /// # Arguments
    ///
    /// * `source` - Source node
    /// * `target` - Target node
    ///
    /// # Panics
    ///
    /// Panics if source >= num_nodes
    pub fn add_edge(&mut self, source: u32, target: u32) {
        debug_assert!((source as usize) < self.num_nodes);
        self.adjacency[source as usize].push(target);
    }

    /// Get out-degree of a node.
    ///
    /// # Arguments
    ///
    /// * `node_id` - Node to query
    ///
    /// # Returns
    ///
    /// Number of out-edges
    pub fn degree(&self, node_id: u32) -> usize {
        self.adjacency[node_id as usize].len()
    }

    /// Get number of nodes.
    pub fn num_nodes(&self) -> usize {
        self.num_nodes
    }

    /// Get total number of edges.
    pub fn num_edges(&self) -> usize {
        self.adjacency.iter().map(|neighbors| neighbors.len()).sum()
    }

    /// Compute average out-degree.
    pub fn avg_degree(&self) -> f64 {
        self.num_edges() as f64 / self.num_nodes as f64
    }

    /// Compute maximum out-degree.
    pub fn max_degree(&self) -> usize {
        self.adjacency
            .iter()
            .map(|neighbors| neighbors.len())
            .max()
            .unwrap_or(0)
    }

    /// Convert to Compressed Sparse Row (CSR) format.
    ///
    /// More memory-efficient for large graphs (reduces pointer overhead).
    ///
    /// # Returns
    ///
    /// CSR representation
    pub fn to_csr(&self) -> CSRGraph {
        let mut offsets = Vec::with_capacity(self.num_nodes + 1);
        let mut edges = Vec::new();

        let mut current_offset = 0u32;
        offsets.push(current_offset);

        for neighbors in &self.adjacency {
            edges.extend_from_slice(neighbors);
            current_offset += neighbors.len() as u32;
            offsets.push(current_offset);
        }

        CSRGraph {
            num_nodes: self.num_nodes,
            offsets,
            edges,
        }
    }

    /// Load from CSR format.
    ///
    /// # Arguments
    ///
    /// * `csr` - CSR graph representation
    ///
    /// # Returns
    ///
    /// VamanaGraph reconstructed from CSR
    pub fn from_csr(csr: &CSRGraph) -> Self {
        let mut adjacency = Vec::with_capacity(csr.num_nodes);

        for node in 0..csr.num_nodes {
            let start = csr.offsets[node] as usize;
            let end = csr.offsets[node + 1] as usize;
            adjacency.push(csr.edges[start..end].to_vec());
        }

        Self {
            num_nodes: csr.num_nodes,
            adjacency,
        }
    }
}

/// Compressed Sparse Row graph representation.
///
/// Space-efficient format for serialization and memory-mapped access.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CSRGraph {
    /// Number of nodes
    pub num_nodes: usize,

    /// Offsets into edges array: offsets[i] = start index for node i
    ///
    /// Length: num_nodes + 1 (last element = total edge count)
    pub offsets: Vec<u32>,

    /// Concatenated edge lists: edges[offsets[i]..offsets[i+1]] = neighbors of node i
    pub edges: Vec<u32>,
}

impl GraphNeighbors for CSRGraph {
    fn neighbors(&self, node_id: u32) -> &[u32] {
        let start = self.offsets[node_id as usize] as usize;
        let end = self.offsets[node_id as usize + 1] as usize;
        &self.edges[start..end]
    }

    fn num_nodes(&self) -> usize {
        self.num_nodes
    }
}

impl CSRGraph {
    /// Get neighbors of a node.
    ///
    /// # Arguments
    ///
    /// * `node_id` - Node to query
    ///
    /// # Returns
    ///
    /// Slice of neighbor IDs
    pub fn neighbors(&self, node_id: u32) -> &[u32] {
        GraphNeighbors::neighbors(self, node_id)
    }

    /// Get out-degree of a node.
    pub fn degree(&self, node_id: u32) -> usize {
        (self.offsets[node_id as usize + 1] - self.offsets[node_id as usize]) as usize
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_new_graph() {
        todo!("Test graph creation")
    }

    #[test]
    fn test_random_graph() {
        todo!("Test random graph generation")
    }

    #[test]
    fn test_add_edge() {
        todo!("Test edge addition")
    }

    #[test]
    fn test_set_neighbors() {
        todo!("Test neighbor replacement")
    }

    #[test]
    fn test_graph_stats() {
        todo!("Test degree statistics")
    }

    #[test]
    fn test_csr_conversion() {
        todo!("Test CSR round-trip conversion")
    }
}
