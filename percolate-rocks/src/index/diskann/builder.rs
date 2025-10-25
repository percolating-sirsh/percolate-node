//! Vamana graph construction algorithm.
//!
//! Builds a high-quality graph index using:
//! 1. Random initialization
//! 2. Iterative refinement with greedy search + robust pruning
//! 3. Medoid computation for optimal entry point
//!
//! # Algorithm Pseudocode
//!
//! ```text
//! VamanaBuild(vectors, R, alpha, L):
//!   1. G = random_graph(vectors, R)
//!   2. medoid = compute_medoid(vectors)
//!   3. For t = 1 to num_iterations:
//!        For each v in shuffle(vertices):
//!          neighbors = greedy_search(v, L, medoid)
//!          G[v] = robust_prune(neighbors, R, alpha)
//!          For each u in G[v]:
//!            if |G[u]| < R:
//!              G[u].add(v)
//!            else if v improves G[u]:
//!              G[u] = robust_prune(G[u] ∪ {v}, R, alpha)
//!   4. Return (G, medoid)
//! ```

use crate::index::diskann::graph::VamanaGraph;
use crate::types::error::Result;

/// Parameters for DiskANN index construction.
#[derive(Debug, Clone)]
pub struct BuildParams {
    /// Maximum out-degree per vertex (R parameter).
    ///
    /// Typical values: 32-128
    /// - Higher: Better recall, more memory
    /// - Lower: Faster build, less memory
    pub max_degree: usize,

    /// Diversity parameter for robust pruning (alpha parameter).
    ///
    /// Typical values: 1.0-1.2
    /// - 1.0: Pure nearest neighbors (less diverse)
    /// - 1.2: More diversity (better long-range connectivity)
    pub alpha: f32,

    /// Search list size during construction (L parameter).
    ///
    /// Typical values: 75-200
    /// - Higher: Better graph quality, slower build
    /// - Lower: Faster build, lower recall
    pub search_list_size: usize,

    /// Number of build iterations.
    ///
    /// Typical values: 2-4
    /// - More iterations: Better graph quality
    /// - Default: 2 (diminishing returns after)
    pub num_iterations: usize,
}

impl Default for BuildParams {
    fn default() -> Self {
        Self {
            max_degree: 64,
            alpha: 1.2,
            search_list_size: 100,
            num_iterations: 2,
        }
    }
}

/// Build a DiskANN index using the Vamana algorithm.
///
/// # Arguments
///
/// * `vectors` - Dense vectors (all must have same dimensionality)
/// * `params` - Build parameters
///
/// # Returns
///
/// Tuple of (graph, medoid) where medoid is the entry point node
///
/// # Errors
///
/// Returns error if:
/// - `vectors` is empty
/// - Vectors have inconsistent dimensions
/// - Parameters are invalid (e.g., max_degree = 0)
///
/// # Example
///
/// ```rust,ignore
/// let params = BuildParams::default();
/// let (graph, medoid) = build_index(&vectors, params)?;
/// ```
pub fn build_index(vectors: &[Vec<f32>], params: BuildParams) -> Result<(VamanaGraph, u32)> {
    validate_inputs(vectors, &params)?;

    // Step 1: Initialize random graph
    let mut graph = initialize_random_graph(vectors.len(), params.max_degree)?;

    // Step 2: Compute medoid (most central point)
    let medoid = compute_medoid(vectors)?;

    // Step 3: Iterative refinement
    for iteration in 0..params.num_iterations {
        refine_graph_iteration(&mut graph, vectors, medoid, &params, iteration)?;
    }

    Ok((graph, medoid))
}

/// Validate build inputs.
///
/// # Errors
///
/// Returns error if vectors are empty, inconsistent, or params invalid
fn validate_inputs(vectors: &[Vec<f32>], params: &BuildParams) -> Result<()> {
    use crate::types::error::DatabaseError;

    if vectors.is_empty() {
        return Err(DatabaseError::SearchError(
            "Cannot build index: no vectors provided".to_string(),
        ));
    }

    if params.max_degree == 0 {
        return Err(DatabaseError::SearchError(
            "Invalid max_degree: must be > 0".to_string(),
        ));
    }

    if params.max_degree >= vectors.len() {
        return Err(DatabaseError::SearchError(format!(
            "Invalid max_degree {}: must be < num_vectors {}",
            params.max_degree,
            vectors.len()
        )));
    }

    // Check dimension consistency
    let expected_dim = vectors[0].len();
    for (i, vec) in vectors.iter().enumerate() {
        if vec.len() != expected_dim {
            return Err(DatabaseError::SearchError(format!(
                "Dimension mismatch at vector {}: expected {}, got {}",
                i,
                expected_dim,
                vec.len()
            )));
        }
    }

    Ok(())
}

/// Initialize a random graph where each node connects to R random neighbors.
///
/// # Arguments
///
/// * `num_nodes` - Number of nodes (= vectors.len())
/// * `max_degree` - Target degree per node
///
/// # Returns
///
/// Randomly connected graph
///
/// # Errors
///
/// Returns error if num_nodes = 0 or max_degree > num_nodes
fn initialize_random_graph(num_nodes: usize, max_degree: usize) -> Result<VamanaGraph> {
    VamanaGraph::random(num_nodes, max_degree)
}

/// Compute the medoid (most central point) of the dataset.
///
/// The medoid is the point that minimizes the sum of distances to all other points.
/// We use a sampling approximation for large datasets.
///
/// # Arguments
///
/// * `vectors` - All vectors in the dataset
///
/// # Returns
///
/// Node ID of the medoid
///
/// # Errors
///
/// Returns error if vectors is empty
///
/// # Algorithm
///
/// ```text
/// For large datasets (n > 10000):
///   1. Sample 1000 random points
///   2. For each sample, compute avg distance to 100 random points
///   3. Return sample with minimum avg distance
///
/// For small datasets:
///   1. Compute all pairwise distances
///   2. Return point with minimum sum of distances
/// ```
fn compute_medoid(vectors: &[Vec<f32>]) -> Result<u32> {
    use crate::types::error::DatabaseError;
    use rand::seq::SliceRandom;
    use rand::thread_rng;

    if vectors.is_empty() {
        return Err(DatabaseError::SearchError(
            "Cannot compute medoid: no vectors".to_string(),
        ));
    }

    // For small datasets, compute exact medoid
    if vectors.len() <= 1000 {
        return compute_exact_medoid(vectors);
    }

    // For large datasets, use sampling approximation
    let mut rng = thread_rng();
    let sample_size = 1000.min(vectors.len());
    let probe_size = 100.min(vectors.len());

    let samples: Vec<usize> = (0..vectors.len()).collect::<Vec<_>>()
        .choose_multiple(&mut rng, sample_size)
        .copied()
        .collect();

    let mut best_idx = samples[0];
    let mut best_avg_dist = f32::MAX;

    for &candidate_idx in &samples {
        // Sample probe points for distance estimation
        let probes: Vec<usize> = (0..vectors.len()).collect::<Vec<_>>()
            .choose_multiple(&mut rng, probe_size)
            .copied()
            .collect();

        let avg_dist: f32 = probes
            .iter()
            .map(|&probe_idx| compute_l2_distance(&vectors[candidate_idx], &vectors[probe_idx]))
            .sum::<f32>()
            / probe_size as f32;

        if avg_dist < best_avg_dist {
            best_avg_dist = avg_dist;
            best_idx = candidate_idx;
        }
    }

    Ok(best_idx as u32)
}

/// Compute exact medoid for small datasets.
fn compute_exact_medoid(vectors: &[Vec<f32>]) -> Result<u32> {
    let mut best_idx = 0;
    let mut best_sum_dist = f32::MAX;

    for (i, vec_i) in vectors.iter().enumerate() {
        let sum_dist: f32 = vectors
            .iter()
            .map(|vec_j| compute_l2_distance(vec_i, vec_j))
            .sum();

        if sum_dist < best_sum_dist {
            best_sum_dist = sum_dist;
            best_idx = i;
        }
    }

    Ok(best_idx as u32)
}

/// Compute L2 (Euclidean) distance between two vectors.
fn compute_l2_distance(a: &[f32], b: &[f32]) -> f32 {
    debug_assert_eq!(a.len(), b.len());
    a.iter()
        .zip(b.iter())
        .map(|(x, y)| (x - y) * (x - y))
        .sum::<f32>()
        .sqrt()
}

/// Perform one iteration of graph refinement.
///
/// # Arguments
///
/// * `graph` - Current graph structure (modified in-place)
/// * `vectors` - All vectors
/// * `medoid` - Entry point for greedy search
/// * `params` - Build parameters
/// * `iteration` - Current iteration number (for logging)
///
/// # Errors
///
/// Returns error if search or pruning fails
fn refine_graph_iteration(
    graph: &mut VamanaGraph,
    vectors: &[Vec<f32>],
    medoid: u32,
    params: &BuildParams,
    iteration: usize,
) -> Result<()> {
    use crate::index::diskann::search::{greedy_search, SearchParams};
    use crate::index::diskann::prune::robust_prune;
    use rand::seq::SliceRandom;
    use rand::thread_rng;

    // Create shuffled list of vertices for random order processing
    let mut vertices: Vec<u32> = (0..graph.num_nodes() as u32).collect();
    let mut rng = thread_rng();
    vertices.shuffle(&mut rng);

    // Process each vertex
    for &vertex in &vertices {
        // Step 1: Use greedy search to find candidate neighbors
        let search_params = SearchParams {
            top_k: params.search_list_size,
            search_list_size: params.search_list_size,
        };

        let candidates = greedy_search(graph, vectors, &vectors[vertex as usize], medoid, search_params)?;

        // Step 2: Use robust prune to select diverse neighbors
        let pruned_neighbors = robust_prune(&candidates, vectors, params.max_degree, params.alpha)?;

        // Step 3: Update vertex's neighbor list
        graph.set_neighbors(vertex, pruned_neighbors.clone());

        // Step 4: Add reverse edges (bidirectional connectivity)
        for &neighbor in &pruned_neighbors {
            add_reverse_edge(graph, vertex, neighbor, vectors, params)?;
        }
    }

    Ok(())
}

/// Update reverse edges after forward edge is added.
///
/// When we add edge v -> u, we also want u -> v (if it improves u's neighborhood).
///
/// # Arguments
///
/// * `graph` - Graph structure (modified in-place)
/// * `source` - Source node that added an edge
/// * `target` - Target node of the edge
/// * `vectors` - All vectors (for distance computation)
/// * `params` - Build parameters
///
/// # Errors
///
/// Returns error if pruning fails
fn add_reverse_edge(
    graph: &mut VamanaGraph,
    source: u32,
    target: u32,
    vectors: &[Vec<f32>],
    params: &BuildParams,
) -> Result<()> {
    use crate::index::diskann::prune::robust_prune;

    // Get current neighbors of target
    let mut target_neighbors = graph.neighbors(target).to_vec();

    // Check if source is already a neighbor
    if target_neighbors.contains(&source) {
        return Ok(());
    }

    // If target has space, just add the edge
    if target_neighbors.len() < params.max_degree {
        target_neighbors.push(source);
        graph.set_neighbors(target, target_neighbors);
        return Ok(());
    }

    // Target is at capacity - need to prune
    // Create candidate list with distances to target
    let target_vec = &vectors[target as usize];
    let mut candidates: Vec<(u32, f32)> = target_neighbors
        .iter()
        .map(|&neighbor| {
            let dist = compute_l2_distance(target_vec, &vectors[neighbor as usize]);
            (neighbor, dist)
        })
        .collect();

    // Add source as a candidate
    let source_dist = compute_l2_distance(target_vec, &vectors[source as usize]);
    candidates.push((source, source_dist));

    // Use robust prune to select best neighbors
    let pruned = robust_prune(&candidates, vectors, params.max_degree, params.alpha)?;

    // Update target's neighbors
    graph.set_neighbors(target, pruned);

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_validate_inputs() {
        todo!("Test input validation")
    }

    #[test]
    fn test_initialize_random_graph() {
        todo!("Test random graph initialization")
    }

    #[test]
    fn test_compute_medoid_small() {
        todo!("Test medoid computation on small dataset")
    }

    #[test]
    fn test_compute_medoid_large() {
        todo!("Test medoid computation with sampling")
    }

    #[test]
    fn test_build_convergence() {
        todo!("Test that graph quality improves across iterations")
    }
}
