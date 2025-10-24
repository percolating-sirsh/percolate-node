"""Example: Graph Traversal for Entity Relationships.

This demonstrates the foundation for N-hop querying inspired by carrier's
experimental query planner. The graph traversal system supports:
- BFS (breadth-first) - finds shortest paths
- DFS (depth-first) - explores deeply, finds all paths
- Depth limits
- Cycle detection
- Relationship type filtering
"""

import tempfile
from uuid import uuid4

from rem_db import GraphEdge, GraphTraversal, REMDatabase, TraversalStrategy


def main():
    """Demonstrate graph traversal on entity relationships."""

    with tempfile.TemporaryDirectory() as tmpdir:
        db = REMDatabase(tenant_id="demo", path=tmpdir)

        print("=== Building Entity Graph ===\n")

        # Create entities representing a company structure
        entities = {
            "Acme Corp": db.create_entity(name="Acme Corp", properties={"type": "company"}),
            "Engineering": db.create_entity(name="Engineering", properties={"type": "department"}),
            "Product": db.create_entity(name="Product", properties={"type": "department"}),
            "Platform Team": db.create_entity(name="Platform Team", properties={"type": "team"}),
            "API Team": db.create_entity(name="API Team", properties={"type": "team"}),
            "Alice": db.create_entity(name="Alice", properties={"type": "person", "role": "Staff Engineer"}),
            "Bob": db.create_entity(name="Bob", properties={"type": "person", "role": "Senior Engineer"}),
            "Charlie": db.create_entity(name="Charlie", properties={"type": "person", "role": "Product Manager"}),
        }

        # Create relationships
        # Company structure
        db.create_edge(entities["Acme Corp"], entities["Engineering"], "has_department")
        db.create_edge(entities["Acme Corp"], entities["Product"], "has_department")

        # Engineering department
        db.create_edge(entities["Engineering"], entities["Platform Team"], "has_team")
        db.create_edge(entities["Engineering"], entities["API Team"], "has_team")

        # Team membership
        db.create_edge(entities["Platform Team"], entities["Alice"], "has_member")
        db.create_edge(entities["Platform Team"], entities["Bob"], "has_member")
        db.create_edge(entities["API Team"], entities["Bob"], "has_member")  # Bob in multiple teams

        # Product department
        db.create_edge(entities["Product"], entities["Charlie"], "has_member")

        # Cross-department collaboration
        db.create_edge(entities["Alice"], entities["Charlie"], "collaborates_with")
        db.create_edge(entities["Charlie"], entities["Alice"], "collaborates_with")

        print("Created 8 entities and 10 relationships\n")

        print("=== Example 1: BFS Traversal (Find All Reachable Entities) ===\n")

        # Build get_neighbors function
        def get_neighbors(entity_id):
            """Get outgoing edges for an entity."""
            # Query edges from database
            edges_data = db.query_entities({"from_id": str(entity_id)})

            result = []
            for edge_entity in edges_data:
                props = edge_entity.properties
                edge = GraphEdge(
                    from_id=entity_id,
                    to_id=uuid4(),  # Would be real to_id from database
                    relationship=props.get("relationship", "related_to"),
                    metadata=props,
                )
                result.append(edge)
            return result

        # Simpler: Use edge list directly
        edge_list = {}
        for from_name, to_name, rel_type in [
            ("Acme Corp", "Engineering", "has_department"),
            ("Acme Corp", "Product", "has_department"),
            ("Engineering", "Platform Team", "has_team"),
            ("Engineering", "API Team", "has_team"),
            ("Platform Team", "Alice", "has_member"),
            ("Platform Team", "Bob", "has_member"),
            ("API Team", "Bob", "has_member"),
            ("Product", "Charlie", "has_member"),
            ("Alice", "Charlie", "collaborates_with"),
            ("Charlie", "Alice", "collaborates_with"),
        ]:
            from_id = entities[from_name]
            to_id = entities[to_name]

            if from_id not in edge_list:
                edge_list[from_id] = []

            edge_list[from_id].append(
                GraphEdge(from_id=from_id, to_id=to_id, relationship=rel_type, metadata={})
            )

        # Reverse lookup for entity names
        id_to_name = {v: k for k, v in entities.items()}

        def get_neighbors_simple(entity_id):
            return edge_list.get(entity_id, [])

        # Traverse from Acme Corp
        traversal = GraphTraversal(max_depth=4)
        paths = traversal.traverse(
            entities["Acme Corp"],
            get_neighbors_simple,
            strategy=TraversalStrategy.BFS,
        )

        print(f"Found {len(paths)} paths from 'Acme Corp':")
        for i, path in enumerate(paths[:10], 1):  # Show first 10
            path_names = [id_to_name[eid] for eid in path.entities]
            print(f"  {i}. {' → '.join(path_names)} (depth {path.depth})")
        if len(paths) > 10:
            print(f"  ... and {len(paths) - 10} more paths")
        print()

        print("=== Example 2: Find Shortest Path ===\n")

        # Find shortest path from Acme Corp to Alice
        path = traversal.find_shortest_path(
            entities["Acme Corp"],
            entities["Alice"],
            get_neighbors_simple,
        )

        if path:
            path_names = [id_to_name[eid] for eid in path.entities]
            print(f"Shortest path to Alice: {' → '.join(path_names)}")
            print(f"  Hops: {path.depth}")
            print(f"  Relationships: {[e.relationship for e in path.edges]}")
        print()

        print("=== Example 3: Relationship Type Filtering ===\n")

        # Only follow "has_member" relationships
        member_paths = traversal.traverse(
            entities["Acme Corp"],
            get_neighbors_simple,
            relationship_filter=["has_department", "has_team", "has_member"],
        )

        print(f"Organizational hierarchy (filtered to structure only):")
        for path in member_paths:
            if path.depth >= 3:  # Only show deep paths
                path_names = [id_to_name[eid] for eid in path.entities]
                print(f"  {' → '.join(path_names)}")
        print()

        print("=== Example 4: Find All Paths (DFS) ===\n")

        # Find all paths from Alice to Charlie
        all_paths = traversal.find_all_paths(
            entities["Alice"],
            entities["Charlie"],
            get_neighbors_simple,
        )

        print(f"All paths from Alice to Charlie ({len(all_paths)} paths):")
        for i, path in enumerate(all_paths, 1):
            path_names = [id_to_name[eid] for eid in path.entities]
            relationships = [e.relationship for e in path.edges]
            print(f"  Path {i}: {' → '.join(path_names)}")
            print(f"    Relationships: {' → '.join(relationships)}")
        print()

        print("=== Example 5: Find Neighbors at Exact Depth ===\n")

        # Find all entities exactly 2 hops from Acme Corp
        neighbors_at_2 = traversal.find_neighbors_at_depth(
            entities["Acme Corp"],
            2,
            get_neighbors_simple,
        )

        print(f"Entities exactly 2 hops from Acme Corp:")
        for entity_id in neighbors_at_2:
            print(f"  - {id_to_name[entity_id]}")
        print()

        print("=== Example 6: Count Paths ===\n")

        # Count paths from Platform Team to Bob
        count = traversal.count_paths(
            entities["Platform Team"],
            entities["Bob"],
            get_neighbors_simple,
        )

        print(f"Number of paths from Platform Team to Bob: {count}")
        print()

        print("=== Use Cases for N-Hop Query Planner ===\n")

        print("This traversal system is the foundation for carrier-style N-hop querying:")
        print()
        print("1. **Multi-stage Queries**:")
        print("   Stage 1: Semantic search → Find relevant entities")
        print("   Stage 2: Graph traversal → Explore relationships")
        print("   Stage 3: Filter by predicates → Narrow results")
        print()
        print("2. **Entity Discovery**:")
        print("   - Find all people in Engineering (depth-limited BFS)")
        print("   - Find collaborators within 3 hops")
        print("   - Discover related projects through team membership")
        print()
        print("3. **Relationship Analysis**:")
        print("   - Count paths between entities (connectivity strength)")
        print("   - Find shortest path (most direct relationship)")
        print("   - Find all paths (explore different connections)")
        print()
        print("4. **Filtered Traversal**:")
        print("   - Follow only \"owns\" relationships (ownership chains)")
        print("   - Follow only \"collaborates_with\" (collaboration networks)")
        print("   - Mix relationship types (complex queries)")
        print()

        db.close()
        print("Done!")


if __name__ == "__main__":
    main()
