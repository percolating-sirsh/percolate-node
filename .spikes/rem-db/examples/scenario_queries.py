"""Example: Scenario-Based Query Strategy Testing.

This demonstrates how natural language questions are converted into
multi-stage query strategies combining:
- Semantic search (vector similarity)
- SQL queries (structured filtering)
- Graph traversal (relationship navigation)

The scenarios validate that the system can handle real-world questions
effectively.
"""

import tempfile

from rem_db import GraphTraversal, REMDatabase, TraversalStrategy
from rem_db.scenarios import get_scenario, list_scenarios


def execute_query_strategy(db, strategy, entities):
    """Execute a multi-stage query strategy.

    Args:
        db: REMDatabase instance
        strategy: QueryStrategy with stages
        entities: Dict mapping names to entity IDs

    Returns:
        Final results after all stages
    """
    print(f"\n{'=' * 80}")
    print(f"QUESTION: {strategy.question}")
    print(f"STRATEGY: {strategy.strategy_name}")
    print(f"{'=' * 80}\n")

    results = None
    traversal = GraphTraversal(max_depth=4)

    for stage in strategy.stages:
        print(f"Stage {stage.stage_number}: {stage.description}")
        print(f"  Type: {stage.query_type}")
        print(f"  Query: {stage.query}")

        # Execute stage based on type
        if stage.query_type.value == "semantic":
            print(f"  → Semantic search: '{stage.query}'")
            # In real implementation, would use vector search
            # For demo, simulate by filtering entity names
            query_lower = stage.query.lower()
            matching = []
            for name, entity_id in entities.items():
                if any(word in name.lower() for word in query_lower.split()):
                    matching.append((name, entity_id))

            results = matching
            print(f"  ✓ Found {len(results)} matches: {[m[0] for m in results[:3]]}")

        elif stage.query_type.value == "sql":
            print(f"  → SQL query: {stage.query}")
            # Execute SQL query
            # For demo, simulate
            results = ["simulated SQL results"]
            print(f"  ✓ Query returned {len(results)} rows")

        elif stage.query_type.value == "graph":
            print(f"  → Graph traversal: {stage.query}")
            # Execute graph traversal
            # For demo, show how it would work
            if results:
                print(f"  ✓ Traversed from {len(results)} starting points")
                # In real implementation, would use GraphTraversal
                results = ["traversal results"]
            else:
                print("  ✗ No starting points from previous stage")

        elif stage.query_type.value == "hybrid":
            print(f"  → Hybrid query combining multiple approaches")
            results = ["hybrid results"]

        print()

    print(f"EXPECTED ANSWER: {strategy.expected_answer}")
    print(f"{'=' * 80}\n")

    return results


def demonstrate_software_project_scenario():
    """Demonstrate software project scenario with realistic queries."""
    print("\n" + "=" * 100)
    print("SCENARIO: Software Project (GitHub-like)")
    print("=" * 100 + "\n")

    scenario = get_scenario("software_project")

    print(f"Description: {scenario.description}")
    print(f"Domain: {scenario.domain}")
    print(f"Expected entities: {scenario.entity_count}")
    print(f"Expected edges: {scenario.edge_count}")
    print()

    with tempfile.TemporaryDirectory() as tmpdir:
        db = REMDatabase(tenant_id="software-demo", path=tmpdir)

        print("Generating scenario data...")
        entities, edges, resources = scenario.generate_data(db)
        print(f"✓ Generated {len(entities)} entities, {len(edges)} edges\n")

        # Show sample entities
        print("Sample entities:")
        for i, (name, entity_id) in enumerate(list(entities.items())[:10], 1):
            entity = db.get_entity(entity_id)
            print(f"  {i}. {name} ({entity.properties.get('type', 'unknown')})")
        print()

        # Execute query strategies
        for i, strategy in enumerate(scenario.questions[:2], 1):  # Demo first 2
            execute_query_strategy(db, strategy, entities)

        db.close()


def demonstrate_company_org_scenario():
    """Demonstrate company organization scenario."""
    print("\n" + "=" * 100)
    print("SCENARIO: Company Organization")
    print("=" * 100 + "\n")

    scenario = get_scenario("company_org")

    print(f"Description: {scenario.description}")
    print(f"Domain: {scenario.domain}")
    print()

    with tempfile.TemporaryDirectory() as tmpdir:
        db = REMDatabase(tenant_id="company-demo", path=tmpdir)

        print("Generating scenario data...")
        entities, edges, resources = scenario.generate_data(db)
        print(f"✓ Generated {len(entities)} entities, {len(edges)} edges\n")

        # Show organizational structure
        print("Organizational structure:")
        company_entities = [(n, e) for n, e in entities.items() if "company" in n or "dept:" in n or "team:" in n[:6]]
        for name, entity_id in sorted(company_entities):
            entity = db.get_entity(entity_id)
            entity_type = entity.properties.get("type", "unknown")
            indent = "  " if "dept:" in name else ("    " if "team:" in name else "")
            print(f"{indent}• {name} ({entity_type})")
        print()

        # Show people and skills
        print("People and their skills:")
        people = [(n, e) for n, e in entities.items() if n.startswith("person:")]
        for name, entity_id in people[:5]:
            entity = db.get_entity(entity_id)
            role = entity.properties.get("role", "unknown")
            print(f"  • {name.split(':')[1]} - {role}")

            # Find skills (would use graph traversal in real implementation)
            skills = [n.split(':')[1] for n, e in entities.items()
                     if n.startswith("skill:") and name.split(':')[1].lower() in n.lower()]
            if skills:
                print(f"    Skills: {', '.join(skills[:3])}")
        print()

        # Execute query strategies
        for strategy in scenario.questions:
            execute_query_strategy(db, strategy, entities)

        db.close()


def show_query_strategy_patterns():
    """Show common multi-stage query patterns."""
    print("\n" + "=" * 100)
    print("COMMON MULTI-STAGE QUERY PATTERNS")
    print("=" * 100 + "\n")

    patterns = [
        {
            "name": "Semantic Search → Graph Traversal",
            "use_case": "Find related entities through semantic similarity",
            "example": "Who worked on authentication? → Find auth-related entities → Traverse to contributors",
            "stages": [
                "1. Semantic search for 'authentication login OAuth'",
                "2. Graph traversal via 'created' and 'authored' relationships",
            ],
        },
        {
            "name": "SQL Filter → Graph Expansion",
            "use_case": "Start with structured query, explore relationships",
            "example": "What do senior engineers work on? → Filter by role → Find their projects",
            "stages": [
                "1. SQL: SELECT * WHERE role = 'senior_engineer'",
                "2. Graph traversal via 'works_on' relationship",
            ],
        },
        {
            "name": "Graph Traversal → SQL Aggregation",
            "use_case": "Navigate graph, then aggregate results",
            "example": "How many PRs per team? → Find teams → Count PRs",
            "stages": [
                "1. Graph: Start from company → teams",
                "2. Graph: For each team → members → PRs",
                "3. SQL: GROUP BY team, COUNT(PRs)",
            ],
        },
        {
            "name": "Hybrid: Semantic + SQL + Graph",
            "use_case": "Complex queries combining all approaches",
            "example": "Senior engineers who reviewed API PRs",
            "stages": [
                "1. Semantic: Find 'API' files",
                "2. Graph: Reverse traverse to PRs via 'modifies'",
                "3. Graph: Traverse to reviewers via 'reviewed'",
                "4. SQL: Filter WHERE role = 'senior_engineer'",
            ],
        },
        {
            "name": "Iterative Refinement (N-hop)",
            "use_case": "Progressive narrowing through multiple hops",
            "example": "Find experts near me",
            "stages": [
                "1. Semantic: Find 'machine learning' skill",
                "2. Graph: 1-hop to people with skill",
                "3. Graph: 2-hop to teams",
                "4. Graph: 3-hop to departments",
                "5. SQL: Filter by location",
            ],
        },
    ]

    for i, pattern in enumerate(patterns, 1):
        print(f"{i}. {pattern['name']}")
        print(f"   Use Case: {pattern['use_case']}")
        print(f"   Example: {pattern['example']}")
        print(f"   Stages:")
        for stage in pattern['stages']:
            print(f"     {stage}")
        print()


def main():
    """Run all scenario demonstrations."""
    print("\n" + "=" * 100)
    print("SCENARIO-BASED QUERY STRATEGY TESTING")
    print("=" * 100)
    print()
    print("This demonstrates how natural language questions are converted into")
    print("multi-stage queries combining semantic search, SQL, and graph traversal.")
    print()

    # List available scenarios
    print("Available scenarios:")
    for scenario_name in list_scenarios():
        scenario = get_scenario(scenario_name)
        print(f"  • {scenario.name} - {scenario.domain}")
        print(f"    {scenario.description}")
        print(f"    Questions: {len(scenario.questions)}")
    print()

    # Demonstrate each scenario
    demonstrate_software_project_scenario()
    demonstrate_company_org_scenario()

    # Show query patterns
    show_query_strategy_patterns()

    print("\n" + "=" * 100)
    print("KEY INSIGHTS")
    print("=" * 100 + "\n")

    print("1. NATURAL LANGUAGE → QUERY MAPPING")
    print("   User questions naturally map to multi-stage strategies")
    print("   Each stage focuses on a specific aspect of the question")
    print()

    print("2. COMPOSITION OF PRIMITIVES")
    print("   Complex queries = composition of simple operations")
    print("   - Semantic search (find relevant entities)")
    print("   - SQL filtering (structured conditions)")
    print("   - Graph traversal (relationship navigation)")
    print()

    print("3. SCENARIO VALIDATION")
    print("   Different domains require different query patterns")
    print("   Real-world scenarios validate system capabilities")
    print("   Data generation ensures comprehensive testing")
    print()

    print("4. QUERY OPTIMIZATION")
    print("   Stage order matters for performance")
    print("   Filter early (SQL) before expensive operations (graph traversal)")
    print("   Semantic search for initial candidate set")
    print()

    print("5. EXTENSIBILITY")
    print("   Adding new scenarios = adding new question patterns")
    print("   Scenarios become living documentation")
    print("   Easy to test new features against realistic workloads")
    print()


if __name__ == "__main__":
    main()
