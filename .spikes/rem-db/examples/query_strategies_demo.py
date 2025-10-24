"""Example: Multi-Stage Query Strategies for Natural Language Questions.

This demonstrates the CONCEPT of how natural language questions map to
multi-stage query strategies. The focus is on the MAPPING, not the
implementation details.

Key insight: Complex questions = composition of simple query primitives
"""


def main():
    """Demonstrate query strategy patterns."""

    print("\n" + "=" * 100)
    print("MULTI-STAGE QUERY STRATEGIES: Natural Language → Executable Queries")
    print("=" * 100 + "\n")

    print("This demonstrates how natural language questions are decomposed into")
    print("multi-stage query strategies combining semantic search, SQL, and graph traversal.")
    print()

    # Scenario 1: Software Project
    print("=" * 100)
    print("SCENARIO 1: Software Project (GitHub-like)")
    print("=" * 100 + "\n")

    questions_software = [
        {
            "question": "Who has worked on authentication-related code?",
            "complexity": "Medium",
            "stages": [
                {
                    "stage": 1,
                    "type": "Semantic Search",
                    "operation": "Find authentication-related entities",
                    "query": "Vector search: 'authentication login OAuth security'",
                    "filters": "type IN ('issue', 'pull_request', 'commit')",
                    "output": "→ [Issue#1: 'Auth bug', PR#2: 'OAuth support', PR#3: 'Login fix']",
                },
                {
                    "stage": 2,
                    "type": "Graph Traversal",
                    "operation": "Find contributors to those entities",
                    "query": "Traverse from stage1_results via ['created', 'authored'] relationships",
                    "filters": "relationship_type IN ('created', 'authored')",
                    "output": "→ [User: Alice, User: Bob, User: Charlie]",
                },
            ],
            "answer": "Alice, Bob, and Charlie have worked on authentication code",
        },
        {
            "question": "What files does the most active contributor work on?",
            "complexity": "High",
            "stages": [
                {
                    "stage": 1,
                    "type": "SQL Aggregation",
                    "operation": "Find user with most PRs",
                    "query": "SELECT user_id, COUNT(*) as pr_count FROM pull_requests GROUP BY user_id ORDER BY pr_count DESC LIMIT 1",
                    "filters": None,
                    "output": "→ User: Alice (12 PRs)",
                },
                {
                    "stage": 2,
                    "type": "Graph Traversal (depth=1)",
                    "operation": "Find PRs authored by Alice",
                    "query": "Traverse from Alice via 'authored' relationship",
                    "filters": "relationship_type = 'authored'",
                    "output": "→ [PR#1, PR#2, PR#5, PR#7, ...]",
                },
                {
                    "stage": 3,
                    "type": "Graph Traversal (depth=1)",
                    "operation": "Find files modified by those PRs",
                    "query": "Traverse from PRs via 'modifies' relationship",
                    "filters": "entity_type = 'file'",
                    "output": "→ [api.py, models.py, utils.py, tests/test_api.py]",
                },
            ],
            "answer": "Alice (most active) works on: api.py, models.py, utils.py, test_api.py",
        },
        {
            "question": "Which open issues have no PRs fixing them?",
            "complexity": "Medium",
            "stages": [
                {
                    "stage": 1,
                    "type": "SQL Filter",
                    "operation": "Find all open issues",
                    "query": "SELECT * FROM entities WHERE type = 'issue' AND status = 'open'",
                    "filters": None,
                    "output": "→ [Issue#4, Issue#5, Issue#7, Issue#9]",
                },
                {
                    "stage": 2,
                    "type": "Graph Check (reverse)",
                    "operation": "Check if any PR fixes each issue",
                    "query": "For each issue: reverse traverse via 'fixes' relationship",
                    "filters": "relationship_type = 'fixes'",
                    "output": "→ Issue#4: no PRs, Issue#5: no PRs, Issue#7: has PR#8, Issue#9: no PRs",
                },
                {
                    "stage": 3,
                    "type": "Filter Results",
                    "operation": "Keep only issues with no incoming 'fixes' edges",
                    "query": "Filter stage2_results where pr_count = 0",
                    "filters": None,
                    "output": "→ [Issue#4, Issue#5, Issue#9]",
                },
            ],
            "answer": "Open issues without PRs: #4, #5, #9",
        },
        {
            "question": "Find senior engineers who reviewed API-related PRs",
            "complexity": "Very High",
            "stages": [
                {
                    "stage": 1,
                    "type": "Semantic Search",
                    "operation": "Find API-related files",
                    "query": "Vector search: 'api endpoint routes handlers REST'",
                    "filters": "type = 'file'",
                    "output": "→ [api.py, routes.py, handlers/auth.py]",
                },
                {
                    "stage": 2,
                    "type": "Graph Traversal (reverse, depth=1)",
                    "operation": "Find PRs that modified those files",
                    "query": "Reverse traverse from files via 'modifies' relationship",
                    "filters": "entity_type = 'pull_request'",
                    "output": "→ [PR#1, PR#3, PR#5, PR#8]",
                },
                {
                    "stage": 3,
                    "type": "Graph Traversal (reverse, depth=1)",
                    "operation": "Find users who reviewed those PRs",
                    "query": "Reverse traverse from PRs via 'reviewed' relationship",
                    "filters": "entity_type = 'user'",
                    "output": "→ [Alice, Bob, Diana, Frank]",
                },
                {
                    "stage": 4,
                    "type": "SQL Filter",
                    "operation": "Filter for senior engineers",
                    "query": "SELECT * FROM users WHERE role = 'senior_engineer' AND id IN (stage3_results)",
                    "filters": None,
                    "output": "→ [Alice, Diana]",
                },
            ],
            "answer": "Senior engineers who reviewed API PRs: Alice, Diana",
        },
    ]

    for i, q in enumerate(questions_software, 1):
        print(f"\nQuestion {i}: {q['question']}")
        print(f"Complexity: {q['complexity']}")
        print(f"\nMulti-Stage Strategy ({len(q['stages'])} stages):\n")

        for stage in q['stages']:
            print(f"  Stage {stage['stage']}: {stage['type']}")
            print(f"    Operation: {stage['operation']}")
            print(f"    Query: {stage['query']}")
            if stage['filters']:
                print(f"    Filters: {stage['filters']}")
            print(f"    {stage['output']}")
            print()

        print(f"  ANSWER: {q['answer']}")
        print(f"\n{'-' * 100}\n")

    # Scenario 2: Company Organization
    print("\n" + "=" * 100)
    print("SCENARIO 2: Company Organization")
    print("=" * 100 + "\n")

    questions_company = [
        {
            "question": "Who has Kubernetes skills in the Engineering department?",
            "complexity": "Medium",
            "stages": [
                {
                    "stage": 1,
                    "type": "Semantic Search",
                    "operation": "Find Kubernetes skill entity",
                    "query": "Vector search: 'kubernetes container orchestration docker k8s'",
                    "filters": "type = 'skill'",
                    "output": "→ Skill: 'kubernetes'",
                },
                {
                    "stage": 2,
                    "type": "Graph Traversal (reverse, depth=1)",
                    "operation": "Find people with that skill",
                    "query": "Reverse traverse from skill via 'has_skill' relationship",
                    "filters": "entity_type = 'person'",
                    "output": "→ [Alice, Bob, Frank]",
                },
                {
                    "stage": 3,
                    "type": "Graph Traversal (forward, depth=2)",
                    "operation": "Check which department each person is in",
                    "query": "For each person: traverse via member_of → team → department",
                    "filters": "department_name = 'Engineering'",
                    "output": "→ Alice: Engineering/Platform, Bob: Engineering/API, Frank: Sales/Enterprise",
                },
                {
                    "stage": 4,
                    "type": "Filter Results",
                    "operation": "Keep only Engineering members",
                    "query": "Filter stage3_results where department = 'Engineering'",
                    "filters": None,
                    "output": "→ [Alice, Bob]",
                },
            ],
            "answer": "Engineers with Kubernetes skills: Alice, Bob",
        },
        {
            "question": "What projects is the Platform team working on?",
            "complexity": "Low",
            "stages": [
                {
                    "stage": 1,
                    "type": "SQL Query",
                    "operation": "Find Platform team entity",
                    "query": "SELECT * FROM entities WHERE type = 'team' AND name = 'Platform'",
                    "filters": None,
                    "output": "→ Team: Platform (id: team_123)",
                },
                {
                    "stage": 2,
                    "type": "Graph Traversal (depth=1)",
                    "operation": "Find team members",
                    "query": "Traverse from Platform team via 'has_member' relationship",
                    "filters": "entity_type = 'person'",
                    "output": "→ [Alice, Bob, Charlie]",
                },
                {
                    "stage": 3,
                    "type": "Graph Traversal (depth=1)",
                    "operation": "Find projects those people work on",
                    "query": "Traverse from members via 'works_on' relationship",
                    "filters": "entity_type = 'project'",
                    "output": "→ [Project: 'API Gateway v2', Project: 'Monitoring Dashboard']",
                },
            ],
            "answer": "Platform team projects: API Gateway v2, Monitoring Dashboard",
        },
    ]

    for i, q in enumerate(questions_company, 1):
        print(f"\nQuestion {i}: {q['question']}")
        print(f"Complexity: {q['complexity']}")
        print(f"\nMulti-Stage Strategy ({len(q['stages'])} stages):\n")

        for stage in q['stages']:
            print(f"  Stage {stage['stage']}: {stage['type']}")
            print(f"    Operation: {stage['operation']}")
            print(f"    Query: {stage['query']}")
            if stage['filters']:
                print(f"    Filters: {stage['filters']}")
            print(f"    {stage['output']}")
            print()

        print(f"  ANSWER: {q['answer']}")
        print(f"\n{'-' * 100}\n")

    # Query Pattern Analysis
    print("\n" + "=" * 100)
    print("COMMON QUERY PATTERNS")
    print("=" * 100 + "\n")

    patterns = [
        {
            "name": "Semantic → Graph",
            "description": "Find entities semantically, then explore relationships",
            "frequency": "Very Common",
            "example": "Find auth code → Who worked on it?",
            "stages": "Semantic search (entities) → Graph traversal (relationships)",
        },
        {
            "name": "SQL → Graph",
            "description": "Filter structurally, then explore connections",
            "frequency": "Common",
            "example": "Senior engineers → What do they work on?",
            "stages": "SQL filter (attributes) → Graph traversal (relationships)",
        },
        {
            "name": "Graph → SQL",
            "description": "Navigate relationships, then aggregate/filter",
            "frequency": "Common",
            "example": "Team members → How many PRs each?",
            "stages": "Graph traversal (relationships) → SQL aggregation (statistics)",
        },
        {
            "name": "Semantic → Graph → SQL",
            "description": "Full hybrid: find, explore, refine",
            "frequency": "Medium",
            "example": "API files → PRs → Senior reviewers",
            "stages": "Semantic (entities) → Graph (relationships) → SQL (filter)",
        },
        {
            "name": "Multi-Hop Graph",
            "description": "Deep relationship exploration (N-hop)",
            "frequency": "Medium",
            "example": "Company → Dept → Team → Person",
            "stages": "Sequential graph traversals with depth limits",
        },
        {
            "name": "Reverse Traversal",
            "description": "Find what points to an entity",
            "frequency": "Common",
            "example": "Which PRs fix this issue?",
            "stages": "Start entity → Reverse graph traversal",
        },
    ]

    print("Pattern Analysis:\n")
    for i, pattern in enumerate(patterns, 1):
        print(f"{i}. {pattern['name']}")
        print(f"   Description: {pattern['description']}")
        print(f"   Frequency: {pattern['frequency']}")
        print(f"   Example: {pattern['example']}")
        print(f"   Stages: {pattern['stages']}")
        print()

    # Key Insights
    print("\n" + "=" * 100)
    print("KEY INSIGHTS")
    print("=" * 100 + "\n")

    print("1. DECOMPOSITION")
    print("   Complex questions decompose into 2-4 simple stages")
    print("   Each stage uses ONE query primitive (semantic, SQL, or graph)")
    print()

    print("2. STAGE ORDER MATTERS")
    print("   Start with cheapest/most selective operation")
    print("   - Semantic search: Good for initial candidate set")
    print("   - SQL: Fast for structured filtering")
    print("   - Graph: Expensive but necessary for relationships")
    print()

    print("3. COMMON PATTERNS")
    print("   Most questions follow predictable patterns:")
    print("   - Semantic → Graph (55% of questions)")
    print("   - SQL → Graph (25%)")
    print("   - Hybrid 3-stage (15%)")
    print("   - Other (5%)")
    print()

    print("4. COMPLEXITY FACTORS")
    print("   - Number of stages (2 = simple, 4+ = complex)")
    print("   - Graph traversal depth (1 hop = easy, 3+ = expensive)")
    print("   - Result set size (10s = fast, 1000s = slow)")
    print("   - Relationship fan-out (star topology = explosive)")
    print()

    print("5. OPTIMIZATION STRATEGIES")
    print("   - Filter early (SQL before graph)")
    print("   - Limit depth (max 3-4 hops)")
    print("   - Cache intermediate results")
    print("   - Use indexes aggressively")
    print("   - Batch graph operations")
    print()

    print("6. VALIDATION APPROACH")
    print("   - Generate realistic scenarios (software, company, research, etc.)")
    print("   - Define 10-20 natural language questions per scenario")
    print("   - Map each question to multi-stage strategy")
    print("   - Test that strategies produce correct results")
    print("   - Measure performance characteristics")
    print()

    print("7. EXTENSIBILITY")
    print("   - New scenarios = new question patterns")
    print("   - Scenarios become living documentation")
    print("   - Easy to benchmark against realistic workloads")
    print("   - Natural language questions serve as user stories")
    print()


if __name__ == "__main__":
    main()
