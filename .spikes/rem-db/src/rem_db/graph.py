"""Graph traversal for entity relationships.

Implements N-hop graph traversal with:
- BFS (breadth-first search) - finds shortest paths
- DFS (depth-first search) - explores deeply
- Cycle detection
- Relationship type filtering
- Path tracking
"""

from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional
from uuid import UUID


class TraversalStrategy(str, Enum):
    """Graph traversal strategy."""

    BFS = "bfs"  # Breadth-first search
    DFS = "dfs"  # Depth-first search


@dataclass
class GraphEdge:
    """Graph edge with relationship metadata."""

    from_id: UUID
    to_id: UUID
    relationship: str
    metadata: dict[str, Any]


@dataclass
class TraversalPath:
    """Path from source to target entity."""

    entities: list[UUID]  # Entity IDs in path
    edges: list[GraphEdge]  # Edges connecting entities
    depth: int  # Path length (number of edges)

    def __len__(self) -> int:
        return self.depth


class GraphTraversal:
    """Graph traversal with cycle detection and filtering."""

    def __init__(self, max_depth: int = 3):
        """Initialize graph traversal.

        Args:
            max_depth: Maximum traversal depth (default: 3 hops)
        """
        self.max_depth = max_depth

    def traverse(
        self,
        start_id: UUID,
        get_neighbors_fn,
        strategy: TraversalStrategy = TraversalStrategy.BFS,
        relationship_filter: Optional[list[str]] = None,
        target_id: Optional[UUID] = None,
    ) -> list[TraversalPath]:
        """Traverse graph from start entity.

        Args:
            start_id: Starting entity ID
            get_neighbors_fn: Function (entity_id) -> list[GraphEdge]
            strategy: BFS or DFS traversal
            relationship_filter: Only follow these relationship types
            target_id: Stop when this entity is found

        Returns:
            List of paths found during traversal
        """
        if strategy == TraversalStrategy.BFS:
            return self._bfs(start_id, get_neighbors_fn, relationship_filter, target_id)
        else:
            return self._dfs(start_id, get_neighbors_fn, relationship_filter, target_id)

    def _bfs(
        self,
        start_id: UUID,
        get_neighbors_fn,
        relationship_filter: Optional[list[str]],
        target_id: Optional[UUID],
    ) -> list[TraversalPath]:
        """Breadth-first search (finds shortest paths first)."""
        paths = []
        visited = {start_id}
        queue = deque([(start_id, [start_id], [], 0)])  # (entity_id, path_entities, path_edges, depth)

        while queue:
            entity_id, path_entities, path_edges, depth = queue.popleft()

            # Check depth limit
            if depth >= self.max_depth:
                continue

            # Get neighbors
            edges = get_neighbors_fn(entity_id)

            # Filter by relationship type
            if relationship_filter:
                edges = [e for e in edges if e.relationship in relationship_filter]

            for edge in edges:
                neighbor_id = edge.to_id

                # Skip cycles
                if neighbor_id in visited:
                    continue

                # Build path (append neighbor to existing path)
                new_path_entities = path_entities + [neighbor_id]
                new_path_edges = path_edges + [edge]
                new_depth = depth + 1

                # Create path object
                path = TraversalPath(
                    entities=new_path_entities,
                    edges=new_path_edges,
                    depth=new_depth,
                )
                paths.append(path)

                # Check if target found
                if target_id and neighbor_id == target_id:
                    return [path]  # Return immediately (shortest path in BFS)

                # Mark visited and continue
                visited.add(neighbor_id)
                queue.append((neighbor_id, new_path_entities, new_path_edges, new_depth))

        return paths

    def _dfs(
        self,
        start_id: UUID,
        get_neighbors_fn,
        relationship_filter: Optional[list[str]],
        target_id: Optional[UUID],
    ) -> list[TraversalPath]:
        """Depth-first search (explores deeply before wide)."""
        paths = []
        visited = set()

        def dfs_recursive(
            entity_id: UUID,
            path_entities: list[UUID],
            path_edges: list[GraphEdge],
            depth: int,
        ):
            # Check depth limit
            if depth >= self.max_depth:
                return

            # Mark visited (for this path only)
            visited.add(entity_id)

            # Get neighbors
            edges = get_neighbors_fn(entity_id)

            # Filter by relationship type
            if relationship_filter:
                edges = [e for e in edges if e.relationship in relationship_filter]

            for edge in edges:
                neighbor_id = edge.to_id

                # Skip cycles
                if neighbor_id in visited:
                    continue

                # Build path (append neighbor to existing path)
                new_path_entities = path_entities + [neighbor_id]
                new_path_edges = path_edges + [edge]
                new_depth = depth + 1

                # Create path object
                path = TraversalPath(
                    entities=new_path_entities,
                    edges=new_path_edges,
                    depth=new_depth,
                )
                paths.append(path)

                # Check if target found
                if target_id and neighbor_id == target_id:
                    return  # Stop this branch

                # Recurse
                dfs_recursive(neighbor_id, new_path_entities, new_path_edges, new_depth)

            # Unmark visited (backtrack)
            visited.remove(entity_id)

        dfs_recursive(start_id, [start_id], [], 0)
        return paths

    def find_shortest_path(
        self,
        start_id: UUID,
        target_id: UUID,
        get_neighbors_fn,
        relationship_filter: Optional[list[str]] = None,
    ) -> Optional[TraversalPath]:
        """Find shortest path between two entities (BFS).

        Args:
            start_id: Starting entity ID
            target_id: Target entity ID
            get_neighbors_fn: Function (entity_id) -> list[GraphEdge]
            relationship_filter: Only follow these relationship types

        Returns:
            Shortest path or None if no path exists
        """
        paths = self._bfs(start_id, get_neighbors_fn, relationship_filter, target_id)
        return paths[0] if paths else None

    def find_all_paths(
        self,
        start_id: UUID,
        target_id: UUID,
        get_neighbors_fn,
        relationship_filter: Optional[list[str]] = None,
    ) -> list[TraversalPath]:
        """Find all paths between two entities (DFS).

        Args:
            start_id: Starting entity ID
            target_id: Target entity ID
            get_neighbors_fn: Function (entity_id) -> list[GraphEdge]
            relationship_filter: Only follow these relationship types

        Returns:
            List of all paths within max_depth
        """
        paths = self._dfs(start_id, get_neighbors_fn, relationship_filter, target_id)
        return [p for p in paths if p.entities[-1] == target_id]

    def find_neighbors_at_depth(
        self,
        start_id: UUID,
        depth: int,
        get_neighbors_fn,
        relationship_filter: Optional[list[str]] = None,
    ) -> set[UUID]:
        """Find all entities at exactly N hops from start.

        Args:
            start_id: Starting entity ID
            depth: Exact number of hops
            get_neighbors_fn: Function (entity_id) -> list[GraphEdge]
            relationship_filter: Only follow these relationship types

        Returns:
            Set of entity IDs at specified depth
        """
        paths = self._bfs(start_id, get_neighbors_fn, relationship_filter, None)
        return {p.entities[-1] for p in paths if p.depth == depth}

    def count_paths(
        self,
        start_id: UUID,
        target_id: UUID,
        get_neighbors_fn,
        relationship_filter: Optional[list[str]] = None,
    ) -> int:
        """Count number of paths between two entities.

        Args:
            start_id: Starting entity ID
            target_id: Target entity ID
            get_neighbors_fn: Function (entity_id) -> list[GraphEdge]
            relationship_filter: Only follow these relationship types

        Returns:
            Number of distinct paths
        """
        paths = self.find_all_paths(start_id, target_id, get_neighbors_fn, relationship_filter)
        return len(paths)
