"""Scenario framework for testing multi-stage query strategies.

This module provides a framework for:
1. Generating realistic test data for different domains
2. Defining natural language questions
3. Mapping questions to multi-stage query strategies
4. Validating that strategies produce correct results

The goal is to test how well natural language questions can be
converted into effective multi-stage queries (semantic search + graph
traversal + predicate filtering).
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional


class QueryType(str, Enum):
    """Type of query operation."""

    SEMANTIC = "semantic"  # Vector similarity search
    SQL = "sql"  # SQL SELECT query
    GRAPH = "graph"  # Graph traversal
    HYBRID = "hybrid"  # Combination of multiple types


@dataclass
class QueryStage:
    """A single stage in a multi-stage query plan."""

    stage_number: int
    query_type: QueryType
    description: str
    query: str  # SQL, semantic query, or graph parameters
    filters: Optional[dict[str, Any]] = None
    expected_result_type: Optional[str] = None  # "entities", "ids", "count", etc.


@dataclass
class QueryStrategy:
    """Multi-stage strategy for answering a natural language question."""

    question: str
    strategy_name: str
    stages: list[QueryStage]
    expected_answer: str  # Natural language description of expected result
    validation_fn: Optional[Callable] = None  # Function to validate results


@dataclass
class Scenario:
    """A complete test scenario with data, questions, and query strategies."""

    name: str
    description: str
    domain: str  # "software", "research", "company", "ecommerce", etc.

    # Data generation
    generate_data: Callable  # Function that returns (entities, edges, resources)

    # Natural language questions and their query strategies
    questions: list[QueryStrategy]

    # Expected characteristics
    entity_count: int
    edge_count: int
    resource_count: int

    # Metadata
    tags: list[str]


# --- Scenario Generators ---


def generate_software_project_scenario() -> Scenario:
    """Generate a software project scenario (GitHub-like).

    Entities:
    - Repositories
    - Issues
    - Pull Requests
    - Commits
    - Users (developers)
    - Files
    - Tests

    Relationships:
    - User created Issue
    - User authored PR
    - PR fixes Issue
    - PR modifies File
    - Commit belongs to PR
    - Test covers File
    - User reviewed PR
    """

    def generate_data(db):
        """Generate software project data."""
        from datetime import date, timedelta
        from random import choice, randint, sample
        from rem_db import Entity

        entities = {}
        edges = []

        # Users
        users = ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank"]
        for user in users:
            entity = Entity(
                type="user",
                name=user,
                properties={
                    "role": choice(["senior_engineer", "engineer", "intern"]),
                    "join_date": str(date.today() - timedelta(days=randint(30, 730))),
                },
            )
            entity_id = db.create_entity(entity)
            entities[user] = entity_id

        # Repository
        entities["repo"] = db.create_entity(
            name="awesome-project",
            properties={"type": "repository", "stars": 1247, "language": "python"},
        )

        # Files
        files = ["api.py", "models.py", "utils.py", "tests/test_api.py", "README.md"]
        for file in files:
            entities[f"file:{file}"] = db.create_entity(
                name=file,
                properties={
                    "type": "file",
                    "language": "python" if file.endswith(".py") else "markdown",
                    "lines": randint(50, 500),
                },
            )
            edges.append((entities["repo"], entities[f"file:{file}"], "contains"))

        # Issues
        issue_titles = [
            "Authentication bug in login",
            "Add OAuth support",
            "Improve API performance",
            "Fix memory leak in worker",
            "Add dark mode",
        ]

        for i, title in enumerate(issue_titles, 1):
            issue_id = f"issue:{i}"
            entities[issue_id] = db.create_entity(
                name=title,
                properties={
                    "type": "issue",
                    "number": i,
                    "status": choice(["open", "closed"]),
                    "priority": choice(["low", "medium", "high"]),
                    "created_at": str(date.today() - timedelta(days=randint(1, 90))),
                },
            )
            # Issue creator
            creator = choice(users)
            edges.append((entities[creator], entities[issue_id], "created"))
            edges.append((entities["repo"], entities[issue_id], "has_issue"))

        # Pull Requests
        pr_titles = [
            "Fix auth bug (#1)",
            "Add OAuth integration (#2)",
            "Optimize database queries (#3)",
        ]

        for i, title in enumerate(pr_titles, 1):
            pr_id = f"pr:{i}"
            entities[pr_id] = db.create_entity(
                name=title,
                properties={
                    "type": "pull_request",
                    "number": i,
                    "status": "merged" if i <= 2 else "open",
                    "additions": randint(50, 300),
                    "deletions": randint(10, 100),
                },
            )

            # PR author
            author = choice(users)
            edges.append((entities[author], entities[pr_id], "authored"))
            edges.append((entities["repo"], entities[pr_id], "has_pr"))

            # PR fixes issue
            edges.append((entities[pr_id], entities[f"issue:{i}"], "fixes"))

            # PR modifies files
            modified_files = sample(files, k=randint(1, 3))
            for file in modified_files:
                edges.append((entities[pr_id], entities[f"file:{file}"], "modifies"))

            # PR reviewers
            reviewers = sample([u for u in users if u != author], k=randint(1, 2))
            for reviewer in reviewers:
                edges.append((entities[reviewer], entities[pr_id], "reviewed"))

        # Create edges in database
        for from_entity, to_entity, rel_type in edges:
            db.create_edge(from_entity, to_entity, rel_type)

        return entities, edges, []

    questions = [
        QueryStrategy(
            question="Who has worked on authentication-related code?",
            strategy_name="semantic_search_plus_graph_traversal",
            stages=[
                QueryStage(
                    stage_number=1,
                    query_type=QueryType.SEMANTIC,
                    description="Find authentication-related issues/PRs using semantic search",
                    query="authentication login OAuth security",
                    expected_result_type="entities",
                ),
                QueryStage(
                    stage_number=2,
                    query_type=QueryType.GRAPH,
                    description="Traverse to find users who created or authored those entities",
                    query="traverse from stage1_results via ['created', 'authored'] relationships",
                    expected_result_type="users",
                ),
            ],
            expected_answer="Users who created auth issues or authored auth PRs: Alice, Bob, Charlie",
        ),
        QueryStrategy(
            question="What files does the most active contributor work on?",
            strategy_name="sql_aggregation_plus_graph",
            stages=[
                QueryStage(
                    stage_number=1,
                    query_type=QueryType.SQL,
                    description="Find user with most PRs",
                    query="SELECT user FROM contributions GROUP BY user ORDER BY COUNT(*) DESC LIMIT 1",
                    expected_result_type="user",
                ),
                QueryStage(
                    stage_number=2,
                    query_type=QueryType.GRAPH,
                    description="Find all PRs by that user",
                    query="traverse from user via 'authored' to PRs",
                    expected_result_type="pull_requests",
                ),
                QueryStage(
                    stage_number=3,
                    query_type=QueryType.GRAPH,
                    description="Find all files modified by those PRs",
                    query="traverse from PRs via 'modifies' to files",
                    expected_result_type="files",
                ),
            ],
            expected_answer="Files modified by most active contributor: api.py, models.py, utils.py",
        ),
        QueryStrategy(
            question="Which open issues have no PRs fixing them?",
            strategy_name="sql_filter_plus_graph_check",
            stages=[
                QueryStage(
                    stage_number=1,
                    query_type=QueryType.SQL,
                    description="Find all open issues",
                    query="SELECT * FROM entities WHERE type = 'issue' AND status = 'open'",
                    expected_result_type="issues",
                ),
                QueryStage(
                    stage_number=2,
                    query_type=QueryType.GRAPH,
                    description="For each issue, check if any PR fixes it",
                    query="reverse traverse via 'fixes' relationship",
                    expected_result_type="filtered_issues",
                ),
            ],
            expected_answer="Open issues without PRs: issue #4, issue #5",
        ),
        QueryStrategy(
            question="Find senior engineers who reviewed PRs touching the API",
            strategy_name="hybrid_filter_and_traverse",
            stages=[
                QueryStage(
                    stage_number=1,
                    query_type=QueryType.SEMANTIC,
                    description="Find API-related files",
                    query="api endpoint routes handlers",
                    filters={"type": "file"},
                    expected_result_type="files",
                ),
                QueryStage(
                    stage_number=2,
                    query_type=QueryType.GRAPH,
                    description="Find PRs that modified those files (reverse traverse)",
                    query="reverse traverse via 'modifies'",
                    expected_result_type="pull_requests",
                ),
                QueryStage(
                    stage_number=3,
                    query_type=QueryType.GRAPH,
                    description="Find users who reviewed those PRs",
                    query="reverse traverse via 'reviewed'",
                    expected_result_type="users",
                ),
                QueryStage(
                    stage_number=4,
                    query_type=QueryType.SQL,
                    description="Filter for senior engineers",
                    query="SELECT * FROM users WHERE role = 'senior_engineer' AND id IN (stage3_results)",
                    expected_result_type="filtered_users",
                ),
            ],
            expected_answer="Senior engineers who reviewed API PRs: Alice, Diana",
        ),
    ]

    return Scenario(
        name="Software Project",
        description="GitHub-like software development scenario with repos, issues, PRs, users",
        domain="software",
        generate_data=generate_data,
        questions=questions,
        entity_count=20,  # ~6 users + 1 repo + 5 files + 5 issues + 3 PRs
        edge_count=30,  # Various relationships
        resource_count=0,  # No documents in this scenario
        tags=["github", "software", "collaboration", "code"],
    )


def generate_company_org_scenario() -> Scenario:
    """Generate company organizational hierarchy scenario.

    Entities:
    - Company
    - Departments
    - Teams
    - People
    - Projects
    - Skills

    Relationships:
    - Company has Department
    - Department has Team
    - Team has Member
    - Person has Skill
    - Person manages Team
    - Person works on Project
    - Project belongs to Department
    """

    def generate_data(db):
        """Generate company organizational data."""
        from random import choice, sample

        entities = {}
        edges = []

        # Company
        entities["company"] = db.create_entity(
            name="Acme Corp",
            properties={"type": "company", "size": "midsize", "industry": "technology"},
        )

        # Departments
        departments = ["Engineering", "Product", "Sales", "Marketing"]
        for dept in departments:
            dept_id = f"dept:{dept}"
            entities[dept_id] = db.create_entity(
                name=dept, properties={"type": "department", "budget": choice([500000, 1000000, 1500000])}
            )
            edges.append((entities["company"], entities[dept_id], "has_department"))

        # Teams
        teams = {
            "Engineering": ["Platform", "API", "Mobile"],
            "Product": ["Core", "Growth"],
            "Sales": ["Enterprise", "SMB"],
            "Marketing": ["Content", "Events"],
        }

        for dept, team_list in teams.items():
            for team in team_list:
                team_id = f"team:{team}"
                entities[team_id] = db.create_entity(
                    name=team, properties={"type": "team", "size": choice([3, 5, 8, 12])}
                )
                edges.append((entities[f"dept:{dept}"], entities[team_id], "has_team"))

        # People
        people_data = [
            ("Alice", "Staff Engineer", "Platform", ["python", "rust", "kubernetes"]),
            ("Bob", "Senior Engineer", "API", ["go", "postgresql", "redis"]),
            ("Charlie", "Product Manager", "Core", ["product", "analytics", "sql"]),
            ("Diana", "Engineering Manager", "Platform", ["leadership", "architecture"]),
            ("Eve", "Designer", "Core", ["figma", "user-research"]),
            ("Frank", "Sales Engineer", "Enterprise", ["demos", "integration"]),
        ]

        for name, role, team, skills in people_data:
            person_id = f"person:{name}"
            entities[person_id] = db.create_entity(
                name=name,
                properties={"type": "person", "role": role, "seniority": choice(["junior", "mid", "senior", "staff"])},
            )
            edges.append((entities[f"team:{team}"], entities[person_id], "has_member"))

            # Skills
            for skill in skills:
                skill_id = f"skill:{skill}"
                if skill_id not in entities:
                    entities[skill_id] = db.create_entity(name=skill, properties={"type": "skill"})
                edges.append((entities[person_id], entities[skill_id], "has_skill"))

        # Projects
        projects = [
            ("API Gateway v2", "Engineering", ["Alice", "Bob"]),
            ("Mobile App Redesign", "Product", ["Eve", "Charlie"]),
            ("Enterprise Dashboard", "Product", ["Charlie"]),
        ]

        for proj_name, dept, members in projects:
            proj_id = f"project:{proj_name}"
            entities[proj_id] = db.create_entity(
                name=proj_name, properties={"type": "project", "status": choice(["planning", "active", "completed"])}
            )
            edges.append((entities[f"dept:{dept}"], entities[proj_id], "owns_project"))

            for member in members:
                edges.append((entities[f"person:{member}"], entities[proj_id], "works_on"))

        # Management relationships
        edges.append((entities["person:Diana"], entities["team:Platform"], "manages"))

        # Create edges
        for from_entity, to_entity, rel_type in edges:
            db.create_edge(from_entity, to_entity, rel_type)

        return entities, edges, []

    questions = [
        QueryStrategy(
            question="Who has Kubernetes skills in Engineering?",
            strategy_name="skill_filter_and_department_check",
            stages=[
                QueryStage(
                    stage_number=1,
                    query_type=QueryType.SEMANTIC,
                    description="Find Kubernetes skill entity",
                    query="kubernetes container orchestration",
                    filters={"type": "skill"},
                    expected_result_type="skill",
                ),
                QueryStage(
                    stage_number=2,
                    query_type=QueryType.GRAPH,
                    description="Find people with that skill",
                    query="reverse traverse via 'has_skill'",
                    expected_result_type="people",
                ),
                QueryStage(
                    stage_number=3,
                    query_type=QueryType.GRAPH,
                    description="Check if they're in Engineering department",
                    query="traverse to team, then to department",
                    expected_result_type="filtered_people",
                ),
            ],
            expected_answer="Engineers with Kubernetes: Alice",
        ),
        QueryStrategy(
            question="What projects is the Platform team working on?",
            strategy_name="team_to_projects",
            stages=[
                QueryStage(
                    stage_number=1,
                    query_type=QueryType.SQL,
                    description="Find Platform team",
                    query="SELECT * FROM entities WHERE type = 'team' AND name = 'Platform'",
                    expected_result_type="team",
                ),
                QueryStage(
                    stage_number=2,
                    query_type=QueryType.GRAPH,
                    description="Find team members",
                    query="traverse via 'has_member'",
                    expected_result_type="people",
                ),
                QueryStage(
                    stage_number=3,
                    query_type=QueryType.GRAPH,
                    description="Find projects those people work on",
                    query="traverse via 'works_on'",
                    expected_result_type="projects",
                ),
            ],
            expected_answer="Platform team projects: API Gateway v2",
        ),
    ]

    return Scenario(
        name="Company Organization",
        description="Company org chart with departments, teams, people, skills, projects",
        domain="company",
        generate_data=generate_data,
        questions=questions,
        entity_count=35,  # 1 company + 4 depts + 8 teams + 6 people + 10+ skills + 3 projects
        edge_count=45,
        resource_count=0,
        tags=["organization", "hr", "management", "skills"],
    )


# Registry of all scenarios
SCENARIOS = {
    "software_project": generate_software_project_scenario,
    "company_org": generate_company_org_scenario,
}


def get_scenario(name: str) -> Scenario:
    """Get a scenario by name."""
    if name not in SCENARIOS:
        raise ValueError(f"Unknown scenario: {name}. Available: {list(SCENARIOS.keys())}")
    return SCENARIOS[name]()


def list_scenarios() -> list[str]:
    """List all available scenarios."""
    return list(SCENARIOS.keys())
