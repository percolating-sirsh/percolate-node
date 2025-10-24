"""Tests for graph traversal."""

from uuid import UUID, uuid4

import pytest

from rem_db import GraphEdge, GraphTraversal, TraversalPath, TraversalStrategy


# Test graph structure:
#
#     A --owns--> B --contains--> C
#     |                           ^
#     |--contains--> D --refs-----+
#     |
#     +--owns--> E --owns--> F
#
# Cycles:
#     X --owns--> Y --refs--> Z --refs--> X


@pytest.fixture
def simple_graph():
    """Create simple test graph."""
    # Create entity IDs
    ids = {name: uuid4() for name in ["A", "B", "C", "D", "E", "F", "X", "Y", "Z"]}

    # Define edges
    edges = {
        ids["A"]: [
            GraphEdge(ids["A"], ids["B"], "owns", {}),
            GraphEdge(ids["A"], ids["D"], "contains", {}),
            GraphEdge(ids["A"], ids["E"], "owns", {}),
        ],
        ids["B"]: [
            GraphEdge(ids["B"], ids["C"], "contains", {}),
        ],
        ids["C"]: [],
        ids["D"]: [
            GraphEdge(ids["D"], ids["C"], "refs", {}),
        ],
        ids["E"]: [
            GraphEdge(ids["E"], ids["F"], "owns", {}),
        ],
        ids["F"]: [],
        # Cycle
        ids["X"]: [
            GraphEdge(ids["X"], ids["Y"], "owns", {}),
        ],
        ids["Y"]: [
            GraphEdge(ids["Y"], ids["Z"], "refs", {}),
        ],
        ids["Z"]: [
            GraphEdge(ids["Z"], ids["X"], "refs", {}),  # Back to X
        ],
    }

    def get_neighbors(entity_id: UUID) -> list[GraphEdge]:
        return edges.get(entity_id, [])

    return ids, get_neighbors


def test_bfs_basic_traversal(simple_graph):
    """Test basic BFS traversal."""
    ids, get_neighbors = simple_graph

    traversal = GraphTraversal(max_depth=3)
    paths = traversal.traverse(
        ids["A"],
        get_neighbors,
        strategy=TraversalStrategy.BFS,
    )

    # BFS finds one path to each reachable node
    # A -> B (depth 1)
    # A -> D (depth 1)
    # A -> E (depth 1)
    # A -> B -> C (depth 2) [C marked visited]
    # A -> E -> F (depth 2)
    # Note: A -> D -> C is skipped because C already visited
    assert len(paths) == 5

    # Check depths
    depths = [p.depth for p in paths]
    assert depths.count(1) == 3  # B, D, E
    assert depths.count(2) == 2  # C, F


def test_dfs_basic_traversal(simple_graph):
    """Test basic DFS traversal."""
    ids, get_neighbors = simple_graph

    traversal = GraphTraversal(max_depth=3)
    paths = traversal.traverse(
        ids["A"],
        get_neighbors,
        strategy=TraversalStrategy.DFS,
    )

    # DFS explores deeply first
    assert len(paths) == 6

    # First path should go deep before wide
    first_path = paths[0]
    assert first_path.depth >= 1


def test_depth_limit(simple_graph):
    """Test depth limit enforcement."""
    ids, get_neighbors = simple_graph

    # Max depth 1: Only immediate neighbors
    traversal = GraphTraversal(max_depth=1)
    paths = traversal.traverse(ids["A"], get_neighbors)

    assert len(paths) == 3  # B, D, E
    assert all(p.depth == 1 for p in paths)

    # Max depth 2: Two hops
    traversal = GraphTraversal(max_depth=2)
    paths = traversal.traverse(ids["A"], get_neighbors)

    assert len(paths) == 5  # B, D, E, C, F (C only visited once)
    assert all(p.depth <= 2 for p in paths)


def test_cycle_detection(simple_graph):
    """Test cycle detection prevents infinite loops."""
    ids, get_neighbors = simple_graph

    # Start from cycle node X
    traversal = GraphTraversal(max_depth=5)
    paths = traversal.traverse(ids["X"], get_neighbors)

    # Should not loop forever
    # X -> Y (depth 1)
    # X -> Y -> Z (depth 2)
    # Z tries to go back to X but cycle detected
    assert len(paths) == 2
    assert paths[0].depth == 1  # X -> Y
    assert paths[1].depth == 2  # X -> Y -> Z


def test_relationship_filtering(simple_graph):
    """Test filtering by relationship type."""
    ids, get_neighbors = simple_graph

    traversal = GraphTraversal(max_depth=3)

    # Only follow "owns" relationships
    paths = traversal.traverse(
        ids["A"],
        get_neighbors,
        relationship_filter=["owns"],
    )

    # A --owns--> B
    # A --owns--> E --owns--> F
    assert len(paths) == 3  # B, E, F

    # All edges should be "owns"
    for path in paths:
        for edge in path.edges:
            assert edge.relationship == "owns"

    # Only follow "contains" relationships
    paths = traversal.traverse(
        ids["A"],
        get_neighbors,
        relationship_filter=["contains"],
    )

    # A --contains--> D
    assert len(paths) == 1
    assert paths[0].edges[0].relationship == "contains"


def test_find_shortest_path(simple_graph):
    """Test shortest path finding."""
    ids, get_neighbors = simple_graph

    traversal = GraphTraversal(max_depth=5)

    # Find shortest path A -> C
    path = traversal.find_shortest_path(ids["A"], ids["C"], get_neighbors)

    assert path is not None
    assert path.entities[0] == ids["A"]
    assert path.entities[-1] == ids["C"]
    assert path.depth == 2  # A -> B -> C or A -> D -> C


def test_find_shortest_path_not_found(simple_graph):
    """Test shortest path when no path exists."""
    ids, get_neighbors = simple_graph

    traversal = GraphTraversal(max_depth=3)

    # No path from C to A (graph is directed)
    path = traversal.find_shortest_path(ids["C"], ids["A"], get_neighbors)

    assert path is None


def test_find_all_paths(simple_graph):
    """Test finding all paths between entities."""
    ids, get_neighbors = simple_graph

    traversal = GraphTraversal(max_depth=3)

    # Find all paths A -> C
    paths = traversal.find_all_paths(ids["A"], ids["C"], get_neighbors)

    # Two paths: A -> B -> C and A -> D -> C
    assert len(paths) == 2

    # Both should end at C
    assert all(p.entities[-1] == ids["C"] for p in paths)

    # Both should have depth 2
    assert all(p.depth == 2 for p in paths)


def test_find_neighbors_at_depth(simple_graph):
    """Test finding neighbors at exact depth."""
    ids, get_neighbors = simple_graph

    traversal = GraphTraversal(max_depth=3)

    # Neighbors at depth 1 (immediate)
    neighbors = traversal.find_neighbors_at_depth(ids["A"], 1, get_neighbors)
    assert neighbors == {ids["B"], ids["D"], ids["E"]}

    # Neighbors at depth 2 (two hops)
    neighbors = traversal.find_neighbors_at_depth(ids["A"], 2, get_neighbors)
    assert neighbors == {ids["C"], ids["F"]}  # C reachable via B or D

    # Neighbors at depth 3 (none in this graph)
    neighbors = traversal.find_neighbors_at_depth(ids["A"], 3, get_neighbors)
    assert len(neighbors) == 0


def test_count_paths(simple_graph):
    """Test counting paths between entities."""
    ids, get_neighbors = simple_graph

    traversal = GraphTraversal(max_depth=3)

    # Two paths from A to C
    count = traversal.count_paths(ids["A"], ids["C"], get_neighbors)
    assert count == 2

    # One path from A to F
    count = traversal.count_paths(ids["A"], ids["F"], get_neighbors)
    assert count == 1

    # No path from C to A
    count = traversal.count_paths(ids["C"], ids["A"], get_neighbors)
    assert count == 0


def test_path_structure(simple_graph):
    """Test path structure and metadata."""
    ids, get_neighbors = simple_graph

    traversal = GraphTraversal(max_depth=2)
    path = traversal.find_shortest_path(ids["A"], ids["C"], get_neighbors)

    # Check path structure
    assert isinstance(path, TraversalPath)
    assert len(path.entities) == 3  # [A, B/D, C]
    assert len(path.edges) == 2
    assert path.depth == 2

    # Check entities
    assert path.entities[0] == ids["A"]
    assert path.entities[-1] == ids["C"]

    # Check edges connect properly
    assert path.edges[0].from_id == path.entities[0]
    assert path.edges[0].to_id == path.entities[1]
    assert path.edges[1].from_id == path.entities[1]
    assert path.edges[1].to_id == path.entities[2]


def test_empty_graph():
    """Test traversal in empty graph (no edges)."""
    start_id = uuid4()

    def get_neighbors(entity_id: UUID) -> list[GraphEdge]:
        return []

    traversal = GraphTraversal(max_depth=3)
    paths = traversal.traverse(start_id, get_neighbors)

    assert len(paths) == 0


def test_single_edge():
    """Test traversal with single edge."""
    a_id = uuid4()
    b_id = uuid4()

    edges = {
        a_id: [GraphEdge(a_id, b_id, "refs", {})],
        b_id: [],
    }

    def get_neighbors(entity_id: UUID) -> list[GraphEdge]:
        return edges.get(entity_id, [])

    traversal = GraphTraversal(max_depth=3)
    paths = traversal.traverse(a_id, get_neighbors)

    assert len(paths) == 1
    assert paths[0].entities == [a_id, b_id]
    assert paths[0].depth == 1


def test_linear_chain():
    """Test traversal in linear chain (A -> B -> C -> D -> E)."""
    ids = [uuid4() for _ in range(5)]

    edges = {
        ids[i]: [GraphEdge(ids[i], ids[i + 1], "next", {})] for i in range(4)
    }
    edges[ids[4]] = []

    def get_neighbors(entity_id: UUID) -> list[GraphEdge]:
        return edges.get(entity_id, [])

    # Max depth 5 should reach end
    traversal = GraphTraversal(max_depth=5)
    paths = traversal.traverse(ids[0], get_neighbors)

    # Should find 4 paths (to each next node)
    assert len(paths) == 4
    assert max(p.depth for p in paths) == 4

    # Max depth 2 should stop early
    traversal = GraphTraversal(max_depth=2)
    paths = traversal.traverse(ids[0], get_neighbors)

    assert len(paths) == 2
    assert max(p.depth for p in paths) == 2


def test_star_graph():
    """Test traversal in star graph (central node with many edges)."""
    center = uuid4()
    leaves = [uuid4() for _ in range(5)]

    edges = {
        center: [GraphEdge(center, leaf, "connects", {}) for leaf in leaves],
    }
    for leaf in leaves:
        edges[leaf] = []

    def get_neighbors(entity_id: UUID) -> list[GraphEdge]:
        return edges.get(entity_id, [])

    traversal = GraphTraversal(max_depth=2)
    paths = traversal.traverse(center, get_neighbors)

    # Should find all 5 leaves at depth 1
    assert len(paths) == 5
    assert all(p.depth == 1 for p in paths)

    # All paths should have same source
    assert all(p.entities[0] == center for p in paths)


def test_complex_filtering():
    """Test complex relationship filtering."""
    a_id, b_id, c_id, d_id = [uuid4() for _ in range(4)]

    edges = {
        a_id: [
            GraphEdge(a_id, b_id, "owns", {}),
            GraphEdge(a_id, c_id, "refs", {}),
        ],
        b_id: [
            GraphEdge(b_id, d_id, "owns", {}),
        ],
        c_id: [
            GraphEdge(c_id, d_id, "refs", {}),
        ],
        d_id: [],
    }

    def get_neighbors(entity_id: UUID) -> list[GraphEdge]:
        return edges.get(entity_id, [])

    traversal = GraphTraversal(max_depth=3)

    # Multiple relationship types
    paths = traversal.traverse(
        a_id,
        get_neighbors,
        relationship_filter=["owns", "refs"],
    )
    # A -> B, A -> C, A -> B -> D (D visited once via first path)
    assert len(paths) == 3

    # Single relationship type
    paths = traversal.traverse(
        a_id,
        get_neighbors,
        relationship_filter=["owns"],
    )
    assert len(paths) == 2  # Only "owns" paths
    assert all(e.relationship == "owns" for p in paths for e in p.edges)


def test_traversal_path_length():
    """Test TraversalPath length property."""
    path = TraversalPath(
        entities=[uuid4(), uuid4(), uuid4()],
        edges=[
            GraphEdge(uuid4(), uuid4(), "test", {}),
            GraphEdge(uuid4(), uuid4(), "test", {}),
        ],
        depth=2,
    )

    assert len(path) == 2
    assert path.depth == 2
