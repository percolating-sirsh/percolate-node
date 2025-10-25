//! Graph traversal operations (BFS/DFS).

use crate::types::Result;
use crate::types::Edge;
use uuid::Uuid;
use std::collections::{VecDeque, HashSet, HashMap};

/// Traversal direction.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum TraversalDirection {
    /// Follow outgoing edges
    Out,
    /// Follow incoming edges
    In,
    /// Follow both directions
    Both,
}

/// Edge provider trait for traversal.
///
/// This allows traversal to work with any edge source.
pub trait EdgeProvider {
    fn get_outgoing(&self, node: Uuid, rel_type: Option<&str>) -> Result<Vec<Edge>>;
    fn get_incoming(&self, node: Uuid, rel_type: Option<&str>) -> Result<Vec<Edge>>;
}

/// Graph traversal engine.
pub struct GraphTraversal<'a> {
    provider: &'a dyn EdgeProvider,
}

impl<'a> GraphTraversal<'a> {
    /// Create new graph traversal.
    pub fn new(provider: &'a dyn EdgeProvider) -> Self {
        Self { provider }
    }

    /// Breadth-first search from starting entity.
    ///
    /// # Arguments
    ///
    /// * `start` - Starting entity UUID
    /// * `direction` - Traversal direction
    /// * `depth` - Maximum traversal depth
    /// * `rel_type` - Optional relationship type filter
    ///
    /// # Returns
    ///
    /// Vector of entity UUIDs in BFS order
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::GraphError` if traversal fails
    pub fn bfs(
        &self,
        start: Uuid,
        direction: TraversalDirection,
        depth: usize,
        rel_type: Option<&str>,
    ) -> Result<Vec<Uuid>> {
        let mut visited = HashSet::new();
        let mut result = Vec::new();
        let mut queue = VecDeque::new();

        // Start with (node, current_depth)
        queue.push_back((start, 0));
        visited.insert(start);
        result.push(start);

        while let Some((node, current_depth)) = queue.pop_front() {
            if current_depth >= depth {
                continue;
            }

            // Get neighbors based on direction
            let neighbors = self.get_neighbors(node, direction, rel_type)?;

            for neighbor in neighbors {
                if !visited.contains(&neighbor) {
                    visited.insert(neighbor);
                    result.push(neighbor);
                    queue.push_back((neighbor, current_depth + 1));
                }
            }
        }

        Ok(result)
    }

    /// Depth-first search from starting entity.
    ///
    /// # Arguments
    ///
    /// * `start` - Starting entity UUID
    /// * `direction` - Traversal direction
    /// * `depth` - Maximum traversal depth
    /// * `rel_type` - Optional relationship type filter
    ///
    /// # Returns
    ///
    /// Vector of entity UUIDs in DFS order
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::GraphError` if traversal fails
    pub fn dfs(
        &self,
        start: Uuid,
        direction: TraversalDirection,
        depth: usize,
        rel_type: Option<&str>,
    ) -> Result<Vec<Uuid>> {
        let mut visited = HashSet::new();
        let mut result = Vec::new();

        self.dfs_recursive(start, direction, depth, 0, rel_type, &mut visited, &mut result)?;

        Ok(result)
    }

    /// Recursive DFS helper.
    fn dfs_recursive(
        &self,
        node: Uuid,
        direction: TraversalDirection,
        max_depth: usize,
        current_depth: usize,
        rel_type: Option<&str>,
        visited: &mut HashSet<Uuid>,
        result: &mut Vec<Uuid>,
    ) -> Result<()> {
        visited.insert(node);
        result.push(node);

        if current_depth >= max_depth {
            return Ok(());
        }

        let neighbors = self.get_neighbors(node, direction, rel_type)?;

        for neighbor in neighbors {
            if !visited.contains(&neighbor) {
                self.dfs_recursive(
                    neighbor,
                    direction,
                    max_depth,
                    current_depth + 1,
                    rel_type,
                    visited,
                    result,
                )?;
            }
        }

        Ok(())
    }

    /// Find shortest path between two entities.
    ///
    /// # Arguments
    ///
    /// * `start` - Starting entity UUID
    /// * `end` - Target entity UUID
    /// * `direction` - Traversal direction
    /// * `max_depth` - Maximum search depth
    ///
    /// # Returns
    ///
    /// Vector of entity UUIDs representing path, or empty if no path found
    ///
    /// # Errors
    ///
    /// Returns `DatabaseError::GraphError` if search fails
    pub fn shortest_path(
        &self,
        start: Uuid,
        end: Uuid,
        direction: TraversalDirection,
        max_depth: usize,
    ) -> Result<Vec<Uuid>> {
        if start == end {
            return Ok(vec![start]);
        }

        let mut visited = HashSet::new();
        let mut queue = VecDeque::new();
        let mut parent = HashMap::new();

        queue.push_back((start, 0));
        visited.insert(start);

        while let Some((node, current_depth)) = queue.pop_front() {
            if node == end {
                // Reconstruct path
                let mut path = Vec::new();
                let mut current = end;
                path.push(current);

                while let Some(&prev) = parent.get(&current) {
                    path.push(prev);
                    current = prev;
                }

                path.reverse();
                return Ok(path);
            }

            if current_depth >= max_depth {
                continue;
            }

            let neighbors = self.get_neighbors(node, direction, None)?;

            for neighbor in neighbors {
                if !visited.contains(&neighbor) {
                    visited.insert(neighbor);
                    parent.insert(neighbor, node);
                    queue.push_back((neighbor, current_depth + 1));
                }
            }
        }

        // No path found
        Ok(Vec::new())
    }

    /// Get neighbors of a node based on direction.
    fn get_neighbors(
        &self,
        node: Uuid,
        direction: TraversalDirection,
        rel_type: Option<&str>,
    ) -> Result<Vec<Uuid>> {
        let mut neighbors = Vec::new();

        match direction {
            TraversalDirection::Out => {
                let edges = self.provider.get_outgoing(node, rel_type)?;
                neighbors.extend(edges.iter().map(|e| e.dst));
            }
            TraversalDirection::In => {
                let edges = self.provider.get_incoming(node, rel_type)?;
                neighbors.extend(edges.iter().map(|e| e.src));
            }
            TraversalDirection::Both => {
                let out_edges = self.provider.get_outgoing(node, rel_type)?;
                neighbors.extend(out_edges.iter().map(|e| e.dst));

                let in_edges = self.provider.get_incoming(node, rel_type)?;
                neighbors.extend(in_edges.iter().map(|e| e.src));
            }
        }

        Ok(neighbors)
    }
}
