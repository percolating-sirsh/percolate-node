"""Example: Full carrier agent-let pattern with model_config.

This demonstrates the complete agent-let pattern as used in carrier:
1. Pydantic model with rich docstring (system prompt)
2. model_config with json_schema_extra (FQN, version, tools)
3. Field annotations with descriptions and examples
4. Full JSON schema export
5. SQL queries over registered schemas
"""

import tempfile
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rem_db import MCPTool, REMDatabase


# Agent-let following carrier pattern
class PersonAgent(BaseModel):
    """You are a Person entity representing an employee or contractor.

    ## Your Role

    You maintain information about individuals in the organization including:
    - Contact details (name, email)
    - Organizational assignment (role, team, manager)
    - Skills and capabilities
    - Employment status

    ## Your Capabilities

    You can be queried to find people by role, team, skills, or status.
    You have access to MCP tools to interact with external systems.

    When asked about yourself, reference your properties accurately.
    When asked about team members, query using indexed fields for fast results.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "fully_qualified_name": "rem.entities.person.PersonAgent",
            "short_name": "person",
            "version": "1.0.0",
            "indexed_fields": ["role", "team", "status"],
            "tools": [
                {
                    "name": "send_email",
                    "description": "Send an email to this person",
                    "server": "email_server",
                    "usage": "Use to notify person of updates or requests",
                },
                {
                    "name": "get_calendar",
                    "description": "Retrieve calendar availability",
                    "server": "calendar_server",
                    "usage": "Check availability before scheduling meetings",
                },
            ],
        }
    )

    name: str = Field(
        description="Full name of the person",
        examples=["Alice Johnson", "Bob Smith"],
    )

    email: str = Field(
        description="Primary email address",
        examples=["alice@example.com"],
    )

    role: str = Field(
        description="Job role or title",
        examples=["Senior Engineer", "Product Designer", "Engineering Manager"],
    )

    team: str = Field(
        description="Team or department",
        examples=["Platform", "Product", "Infrastructure"],
    )

    status: Literal["active", "inactive", "on_leave"] = Field(
        default="active",
        description="Employment status",
    )

    skills: list[str] = Field(
        default_factory=list,
        description="List of technical or professional skills",
        examples=[["python", "rust", "kubernetes"], ["figma", "user-research"]],
    )

    manager: str | None = Field(
        None,
        description="Name of direct manager",
        examples=["Diana Martinez"],
    )


class ProjectAgent(BaseModel):
    """You are a Project entity tracking a work initiative.

    ## Your Role

    You maintain the complete lifecycle of a project including:
    - Basic information (name, description, goals)
    - Status tracking (planning, active, completed, archived)
    - Resource allocation (owner, budget, team size)
    - Priority and urgency

    ## Your Capabilities

    You can be queried to find projects by status, owner, priority, or budget.
    You track milestones and deliverables (via MCP tools).

    When reporting status, be specific about current phase and blockers.
    When asked about priorities, explain ranking criteria.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "fully_qualified_name": "rem.entities.project.ProjectAgent",
            "short_name": "project",
            "version": "1.0.0",
            "indexed_fields": ["status", "owner", "priority"],
            "tools": [
                {
                    "name": "update_status",
                    "description": "Update project status",
                    "server": "project_server",
                    "usage": "Use when transitioning between lifecycle phases",
                },
                {
                    "name": "add_milestone",
                    "description": "Add a milestone with due date",
                    "server": "project_server",
                    "usage": "Track key deliverables and checkpoints",
                },
            ],
        }
    )

    name: str = Field(
        description="Project name",
        examples=["REM Database", "API Gateway v2", "Mobile App Redesign"],
    )

    description: str = Field(
        description="Detailed project description and goals",
        examples=["Build new memory system with vector search and SQL interface"],
    )

    status: Literal["planning", "active", "completed", "archived", "on_hold"] = Field(
        description="Current project status"
    )

    owner: str = Field(
        description="Project owner (person name)",
        examples=["Alice Johnson"],
    )

    priority: int = Field(
        description="Priority from 1 (low) to 5 (critical)",
        ge=1,
        le=5,
        examples=[3, 5],
    )

    budget: float = Field(
        description="Budget in dollars",
        ge=0,
        examples=[500000.0, 1200000.0],
    )

    team_size: int = Field(
        default=1,
        description="Number of people working on project",
        ge=1,
    )


def main():
    """Demonstrate full carrier agent-let pattern."""

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create database
        db = REMDatabase(tenant_id="acme-corp", path=tmpdir)

        print("=== Registering Agent-let Schemas ===\n")

        # Register PersonAgent (model_config provides all metadata)
        person_schema = db.register_schema(
            name="person",  # Table name
            model=PersonAgent,
            # All other metadata comes from model_config.json_schema_extra
        )

        print(f"Schema: {person_schema.name}")
        print(f"FQN: {person_schema.fully_qualified_name}")
        print(f"Version: {person_schema.version}")
        print(f"Title: {person_schema.title}")
        print(f"Description (first 100 chars): {person_schema.description[:100]}...")
        print(f"Indexed fields: {person_schema.indexed_fields}")
        print(f"MCP Tools: {[t.name for t in person_schema.tools]}")
        print()

        # Register ProjectAgent
        project_schema = db.register_schema(name="project", model=ProjectAgent)
        print(f"Registered: {project_schema.fully_qualified_name}\n")

        print("=== JSON Schema Export ===\n")

        # Export as JSON schema (for storage/transfer)
        json_schema = person_schema.to_json_schema()
        print(f"Schema properties: {list(json_schema['properties'].keys())}")
        print(f"Required fields: {json_schema['required']}")
        print(f"Field 'name' type: {json_schema['properties']['name']['type']}")
        print(f"Field 'name' description: {json_schema['properties']['name']['description']}")
        print(f"Field 'name' examples: {json_schema['properties']['name'].get('examples')}")
        print(f"Field 'status' enum: {json_schema['properties']['status'].get('enum')}")
        print()

        print("=== Insert Data (Validated Against Schema) ===\n")

        # Insert people
        alice_id = db.insert(
            "person",
            {
                "name": "Alice Johnson",
                "email": "alice@acme.com",
                "role": "Senior Engineer",
                "team": "Platform",
                "status": "active",
                "skills": ["python", "rust", "kubernetes"],
                "manager": "Diana Martinez",
            },
        )

        db.insert(
            "person",
            {
                "name": "Bob Smith",
                "email": "bob@acme.com",
                "role": "Senior Engineer",
                "team": "Platform",
                "status": "active",
                "skills": ["javascript", "react", "graphql"],
                "manager": "Diana Martinez",
            },
        )

        db.insert(
            "person",
            {
                "name": "Charlie Davis",
                "email": "charlie@acme.com",
                "role": "Product Designer",
                "team": "Product",
                "status": "active",
                "skills": ["figma", "user-research"],
            },
        )

        db.insert(
            "person",
            {
                "name": "Diana Martinez",
                "email": "diana@acme.com",
                "role": "Engineering Manager",
                "team": "Platform",
                "status": "active",
                "skills": ["leadership", "agile"],
            },
        )

        print("Inserted 4 people")

        # Insert projects
        db.insert(
            "project",
            {
                "name": "REM Database",
                "description": "Build new memory system with vector search and SQL",
                "status": "active",
                "owner": "Alice Johnson",
                "priority": 5,
                "budget": 500000.0,
                "team_size": 3,
            },
        )

        db.insert(
            "project",
            {
                "name": "Mobile App Redesign",
                "description": "Modernize mobile UI/UX",
                "status": "planning",
                "owner": "Charlie Davis",
                "priority": 3,
                "budget": 200000.0,
                "team_size": 2,
            },
        )

        print("Inserted 2 projects\n")

        print("=== SQL Queries (Using Indexes) ===\n")

        # Query 1: Find all Senior Engineers (indexed field: role)
        print("Q1: SELECT name, email FROM person WHERE role = 'Senior Engineer'")
        engineers = db.sql("SELECT name, email FROM person WHERE role = 'Senior Engineer'")
        for eng in engineers:
            print(f"  → {eng['name']}: {eng['email']}")
        print()

        # Query 2: Platform team members (indexed field: team)
        print("Q2: SELECT name, role FROM person WHERE team = 'Platform' ORDER BY role")
        platform = db.sql("SELECT name, role FROM person WHERE team = 'Platform' ORDER BY role")
        for person in platform:
            print(f"  → {person['name']}: {person['role']}")
        print()

        # Query 3: High priority projects (indexed field: priority)
        print("Q3: SELECT * FROM project WHERE priority >= 4")
        high_priority = db.sql("SELECT name, owner, priority, budget FROM project WHERE priority >= 4")
        for proj in high_priority:
            print(f"  → {proj['name']} (P{proj['priority']}): ${proj['budget']:,.0f}")
        print()

        # Query 4: Complex query with AND
        print("Q4: Active projects owned by Alice")
        results = db.sql(
            "SELECT name, status FROM project WHERE status = 'active' AND owner = 'Alice Johnson'"
        )
        for proj in results:
            print(f"  → {proj['name']}: {proj['status']}")
        print()

        # Query 5: Enum constraint (status field)
        print("Q5: SELECT * FROM person WHERE status IN ('active', 'on_leave')")
        active_people = db.sql("SELECT name, status FROM person WHERE status IN ('active', 'on_leave')")
        print(f"  Found {len(active_people)} people")
        print()

        print("=== Agent-let Metadata Access ===\n")

        # Access agent-let metadata for runtime
        person_schema = db.get_schema("person")

        print(f"Schema: {person_schema.fully_qualified_name}")
        print(f"\nSystem Prompt (first 200 chars):\n{person_schema.description[:200]}...\n")

        print("Available MCP Tools:")
        for tool in person_schema.tools:
            print(f"  - {tool.name}: {tool.description}")
            print(f"    Server: {tool.server}")
            print(f"    Usage: {tool.usage}")
            print()

        print("Field Definitions:")
        for field_name in ["name", "email", "role", "skills", "status"]:
            field_def = person_schema.properties[field_name]
            print(f"  {field_name}:")
            print(f"    Type: {field_def.get('type', field_def.get('anyOf'))}")
            print(f"    Description: {field_def.get('description')}")
            if "examples" in field_def:
                print(f"    Examples: {field_def['examples']}")
            if "enum" in field_def:
                print(f"    Enum: {field_def['enum']}")
            print()

        db.close()
        print("Done!")


if __name__ == "__main__":
    main()
