"""Example: Agent-let aware schemas with SQL queries.

This demonstrates how to:
1. Define Pydantic models as schemas (tables)
2. Register schemas with rich descriptions and MCP tools
3. Insert validated entities
4. Query using SQL
5. Access schema metadata (agent-let prompts, tools)
"""

import tempfile

from pydantic import BaseModel, Field

from rem_db import MCPTool, REMDatabase


# Define Pydantic models with rich metadata
class Person(BaseModel):
    """A person in the organization."""

    name: str = Field(description="Full name of the person")
    email: str = Field(description="Email address")
    role: str = Field(description="Job role (engineer, designer, manager, etc.)")
    team: str = Field(description="Team name")
    active: bool = Field(default=True, description="Is this person currently active")
    skills: list[str] = Field(default_factory=list, description="List of skills")


class Project(BaseModel):
    """A project being worked on."""

    name: str = Field(description="Project name")
    description: str = Field(description="Project description")
    status: str = Field(
        description="Project status: planning, active, completed, archived"
    )
    owner: str = Field(description="Project owner (person name)")
    priority: int = Field(description="Priority from 1 (low) to 5 (high)", ge=1, le=5)
    budget: float = Field(description="Project budget in dollars")


def main():
    """Demonstrate agent-let schemas with SQL."""

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create database
        db = REMDatabase(tenant_id="acme-corp", path=tmpdir)

        print("=== Registering Schemas (Agent-lets) ===\n")

        # Register Person schema with agent-let metadata
        person_schema = db.register_schema(
            name="person",
            model=Person,
            description="A person entity representing employees and contractors",
            system_prompt="""You are a Person entity in the organization.

You have contact information, role, team assignment, and skills.
You can be queried to find people by role, team, or skills.
You have access to tools to send emails and view calendars.

When asked about yourself, reference your properties (name, role, team, etc.).
When asked about your capabilities, reference your skills.
""",
            indexed_fields=["role", "team", "active"],  # Fast queries on these
            mcp_tools=[
                MCPTool(
                    name="send_email",
                    description="Send an email to this person",
                    server="email_server",
                ),
                MCPTool(
                    name="get_calendar",
                    description="Get this person's calendar availability",
                    server="calendar_server",
                ),
                MCPTool(
                    name="assign_task",
                    description="Assign a task to this person",
                    server="task_server",
                ),
            ],
        )

        print(f"Registered schema: {person_schema.name}")
        print(f"Description: {person_schema.description}")
        print(f"Indexed fields: {person_schema.indexed_fields}")
        print(f"MCP tools: {[t.name for t in person_schema.mcp_tools]}\n")

        # Register Project schema
        project_schema = db.register_schema(
            name="project",
            model=Project,
            description="A project entity tracking work initiatives",
            system_prompt="""You are a Project entity.

You have a name, description, status, owner, priority, and budget.
You track the lifecycle of a project from planning through completion.
You can be queried to find projects by status, owner, or priority.

When asked about progress, reference your status.
When asked about importance, reference your priority.
""",
            indexed_fields=["status", "owner", "priority"],
            mcp_tools=[
                MCPTool(
                    name="update_status",
                    description="Update project status",
                    server="project_server",
                ),
                MCPTool(
                    name="add_milestone",
                    description="Add a milestone to the project",
                    server="project_server",
                ),
                MCPTool(
                    name="generate_report",
                    description="Generate status report for this project",
                    server="reporting_server",
                ),
            ],
        )

        print(f"Registered schema: {project_schema.name}\n")

        print("=== Inserting Data (with validation) ===\n")

        # Insert people
        alice_id = db.insert(
            "person",
            {
                "name": "Alice Johnson",
                "email": "alice@acme.com",
                "role": "engineer",
                "team": "platform",
                "skills": ["python", "rust", "kubernetes"],
            },
        )

        bob_id = db.insert(
            "person",
            {
                "name": "Bob Smith",
                "email": "bob@acme.com",
                "role": "engineer",
                "team": "platform",
                "skills": ["javascript", "react", "graphql"],
            },
        )

        charlie_id = db.insert(
            "person",
            {
                "name": "Charlie Davis",
                "email": "charlie@acme.com",
                "role": "designer",
                "team": "product",
                "skills": ["figma", "user-research"],
            },
        )

        diana_id = db.insert(
            "person",
            {
                "name": "Diana Martinez",
                "email": "diana@acme.com",
                "role": "manager",
                "team": "platform",
                "skills": ["leadership", "agile"],
            },
        )

        print(f"Inserted {len([alice_id, bob_id, charlie_id, diana_id])} people")

        # Insert projects
        db.insert(
            "project",
            {
                "name": "REM Database",
                "description": "Build new memory system",
                "status": "active",
                "owner": "Alice Johnson",
                "priority": 5,
                "budget": 500000.0,
            },
        )

        db.insert(
            "project",
            {
                "name": "UI Redesign",
                "description": "Modernize user interface",
                "status": "planning",
                "owner": "Charlie Davis",
                "priority": 3,
                "budget": 200000.0,
            },
        )

        db.insert(
            "project",
            {
                "name": "API Gateway",
                "description": "Unified API gateway",
                "status": "completed",
                "owner": "Bob Smith",
                "priority": 4,
                "budget": 300000.0,
            },
        )

        print("Inserted 3 projects\n")

        print("=== SQL Queries ===\n")

        # Query 1: Find all engineers
        print("Query 1: SELECT * FROM person WHERE role = 'engineer'")
        engineers = db.sql("SELECT name, email, team FROM person WHERE role = 'engineer'")
        for eng in engineers:
            print(f"  - {eng['name']} ({eng['team']})")
        print()

        # Query 2: Find platform team members
        print("Query 2: SELECT * FROM person WHERE team = 'platform'")
        platform = db.sql("SELECT name, role FROM person WHERE team = 'platform' ORDER BY role")
        for person in platform:
            print(f"  - {person['name']}: {person['role']}")
        print()

        # Query 3: Complex query with OR and AND
        print("Query 3: Engineers OR designers")
        results = db.sql(
            "SELECT name, role, team FROM person WHERE role = 'engineer' OR role = 'designer' ORDER BY name"
        )
        for person in results:
            print(f"  - {person['name']}: {person['role']} ({person['team']})")
        print()

        # Query 4: Active projects with high priority
        print("Query 4: High priority active projects")
        projects = db.sql(
            """
            SELECT name, owner, priority, budget
            FROM project
            WHERE status = 'active' AND priority >= 4
            ORDER BY priority DESC
            """
        )
        for proj in projects:
            print(f"  - {proj['name']} (P{proj['priority']}, ${proj['budget']:,.0f})")
        print()

        # Query 5: Pagination
        print("Query 5: Paginated results (2 per page)")
        page1 = db.sql("SELECT name FROM person ORDER BY name LIMIT 2 OFFSET 0")
        page2 = db.sql("SELECT name FROM person ORDER BY name LIMIT 2 OFFSET 2")
        print(f"  Page 1: {[p['name'] for p in page1]}")
        print(f"  Page 2: {[p['name'] for p in page2]}")
        print()

        # Query 6: Comparison operators
        print("Query 6: Projects with budget > $250k")
        expensive = db.sql("SELECT name, budget FROM project WHERE budget > 250000")
        for proj in expensive:
            print(f"  - {proj['name']}: ${proj['budget']:,.0f}")
        print()

        # Query 7: IN operator
        print("Query 7: Projects in specific statuses")
        active_or_planning = db.sql(
            "SELECT name, status FROM project WHERE status IN ('active', 'planning')"
        )
        for proj in active_or_planning:
            print(f"  - {proj['name']}: {proj['status']}")
        print()

        print("=== Schema Introspection (Agent-let Metadata) ===\n")

        # Access schema metadata
        person_schema = db.get_schema("person")
        print(f"Schema: {person_schema.name}")
        print(f"\nDescription:\n{person_schema.description}")
        print(f"\nSystem Prompt:\n{person_schema.system_prompt[:150]}...")
        print(f"\nFields:")
        for field_name, field_meta in person_schema.fields.items():
            print(
                f"  - {field_name} ({field_meta.type}): {field_meta.description or 'No description'}"
            )
        print(f"\nIndexed fields: {person_schema.indexed_fields}")
        print(f"\nAvailable MCP Tools:")
        for tool in person_schema.mcp_tools:
            print(f"  - {tool.name}: {tool.description}")

        print("\n=== Query Planner Uses Indexes ===\n")

        # The query planner automatically uses indexes for indexed fields
        print("Query with indexed field (role='engineer'):")
        print("  -> Uses index:entity:person:role:engineer")
        print("  -> Skips full scan, only loads matching entities")
        print()

        print("Query with non-indexed field (name='Alice'):")
        print("  -> No index available")
        print("  -> Performs full scan of person table")
        print()

        db.close()
        print("Done!")


if __name__ == "__main__":
    main()
