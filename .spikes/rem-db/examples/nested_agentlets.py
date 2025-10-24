"""Real-world nested agent-let example: Project Management System.

This demonstrates complex nested Pydantic models used as agent-lets:
- Multiple levels of nesting (3+ deep)
- Lists of nested objects
- Optional nested fields
- Enum constraints in nested models
- Full JSON schema with $defs
- MCP tools on agent-lets
- Querying across nested structures
"""

import tempfile
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from rem_db import MCPTool, REMDatabase


# Nested models for Address/Contact (reusable)
class Address(BaseModel):
    """Physical address."""

    street: str = Field(description="Street address")
    city: str = Field(description="City name")
    state: str = Field(description="State/province code", min_length=2, max_length=2)
    postal_code: str = Field(description="Postal/ZIP code")
    country: str = Field(default="US", description="Country code")


class ContactInfo(BaseModel):
    """Contact information."""

    email: str = Field(description="Primary email", examples=["alice@example.com"])
    phone: str | None = Field(None, description="Phone number", examples=["+1-555-0100"])
    address: Address | None = Field(None, description="Physical address")


# Nested models for Project structure
class TaskStatus(BaseModel):
    """Task status with tracking."""

    state: Literal["todo", "in_progress", "review", "done", "blocked"] = Field(
        description="Current task state"
    )
    updated_at: date = Field(description="Last status update date")
    updated_by: str = Field(description="Person who updated status")
    notes: str | None = Field(None, description="Status notes")


class Task(BaseModel):
    """Individual task within a project."""

    title: str = Field(description="Task title", examples=["Implement user authentication"])
    description: str = Field(description="Detailed task description")
    assignee: str | None = Field(None, description="Person assigned to task")
    status: TaskStatus = Field(description="Task status")
    priority: Literal["low", "medium", "high", "critical"] = Field(
        default="medium", description="Task priority"
    )
    estimated_hours: float | None = Field(
        None, description="Estimated hours to complete", ge=0
    )
    tags: list[str] = Field(default_factory=list, description="Task tags")


class Milestone(BaseModel):
    """Project milestone."""

    name: str = Field(description="Milestone name", examples=["MVP Launch", "Beta Release"])
    description: str = Field(description="Milestone description")
    due_date: date = Field(description="Target completion date")
    completed: bool = Field(default=False, description="Whether milestone is completed")
    deliverables: list[str] = Field(
        default_factory=list, description="Expected deliverables"
    )


class Budget(BaseModel):
    """Project budget tracking."""

    total_allocated: float = Field(description="Total budget allocated", ge=0)
    spent: float = Field(default=0.0, description="Amount spent so far", ge=0)
    currency: str = Field(default="USD", description="Currency code")
    breakdown: dict[str, float] = Field(
        default_factory=dict, description="Budget breakdown by category"
    )


# Main agent-let: Project
class ProjectAgent(BaseModel):
    """You are a Project entity managing a work initiative.

    ## Your Role

    You coordinate all aspects of a project including:
    - Task management and assignment
    - Milestone tracking
    - Budget oversight
    - Team member coordination
    - Status reporting

    ## Your Capabilities

    You can be queried to find projects by status, owner, or priority.
    You track tasks, milestones, and budget in structured nested data.
    You have access to MCP tools for project management operations.

    When reporting status:
    - Summarize task completion rates
    - Highlight blocked tasks
    - Flag budget overruns
    - Identify upcoming milestone risks

    When asked about team capacity:
    - Analyze task assignments
    - Identify overloaded team members
    - Suggest task rebalancing
    """

    model_config = ConfigDict(
        json_schema_extra={
            "fully_qualified_name": "rem.entities.projects.ProjectAgent",
            "short_name": "project",
            "version": "2.0.0",
            "indexed_fields": ["status", "owner", "priority"],
            "tools": [
                {
                    "name": "send_status_report",
                    "description": "Send project status report to stakeholders",
                    "server": "project_server",
                    "usage": "Use weekly or when significant milestones are reached",
                },
                {
                    "name": "update_task_status",
                    "description": "Update the status of a specific task",
                    "server": "project_server",
                    "usage": "Call when tasks progress or become blocked",
                },
                {
                    "name": "allocate_resources",
                    "description": "Request resource allocation from management",
                    "server": "resource_server",
                    "usage": "Use when project needs additional budget or people",
                },
            ],
        }
    )

    # Basic info
    name: str = Field(description="Project name", examples=["Customer Portal Redesign"])
    description: str = Field(description="Detailed project description and goals")
    owner: str = Field(description="Project owner/manager name")

    # Status and priority
    status: Literal["planning", "active", "on_hold", "completed", "cancelled"] = Field(
        description="Current project status"
    )
    priority: Literal["low", "medium", "high", "critical"] = Field(
        description="Project priority level"
    )

    # Nested structures
    tasks: list[Task] = Field(
        default_factory=list, description="List of project tasks"
    )
    milestones: list[Milestone] = Field(
        default_factory=list, description="Project milestones"
    )
    budget: Budget | None = Field(None, description="Budget information")

    # Team
    team_members: list[str] = Field(
        default_factory=list, description="Team member names"
    )

    # Dates
    start_date: date = Field(description="Project start date")
    target_end_date: date = Field(description="Target completion date")
    actual_end_date: date | None = Field(None, description="Actual completion date")


# Main agent-let: Team Member
class TeamMemberAgent(BaseModel):
    """You are a Team Member entity representing a person in the organization.

    ## Your Role

    You maintain information about team members including:
    - Contact information
    - Skills and expertise
    - Current project assignments
    - Availability and capacity

    ## Your Capabilities

    You can be queried to find team members by skills, location, or availability.
    You track project assignments to identify capacity.
    You have access to MCP tools for collaboration.

    When asked about capacity:
    - Count current task assignments
    - Estimate total workload
    - Flag if overloaded

    When asked about expertise:
    - List relevant skills
    - Identify projects that match skill set
    """

    model_config = ConfigDict(
        json_schema_extra={
            "fully_qualified_name": "rem.entities.team.TeamMemberAgent",
            "short_name": "member",
            "version": "1.0.0",
            "indexed_fields": ["role", "location", "active"],
            "tools": [
                {
                    "name": "send_message",
                    "description": "Send message to team member",
                    "server": "messaging_server",
                    "usage": "Use for important notifications or requests",
                },
                {
                    "name": "check_calendar",
                    "description": "Check team member's calendar availability",
                    "server": "calendar_server",
                    "usage": "Before scheduling meetings or assigning urgent tasks",
                },
            ],
        }
    )

    name: str = Field(description="Full name", examples=["Alice Johnson"])
    employee_id: str = Field(description="Unique employee ID", examples=["EMP001"])
    role: str = Field(
        description="Job role",
        examples=["Senior Software Engineer", "Product Designer", "Engineering Manager"],
    )
    contact: ContactInfo = Field(description="Contact information")

    skills: list[str] = Field(
        default_factory=list,
        description="Skills and expertise",
        examples=[["python", "rust", "kubernetes"], ["figma", "user-research"]],
    )

    active: bool = Field(default=True, description="Is currently employed")
    location: str = Field(description="Primary work location", examples=["San Francisco, CA"])

    current_projects: list[str] = Field(
        default_factory=list, description="List of current project names"
    )


def main():
    """Demonstrate nested agent-lets with complex project management data."""

    with tempfile.TemporaryDirectory() as tmpdir:
        db = REMDatabase(tenant_id="acme-corp", path=tmpdir)

        print("=== Registering Nested Agent-let Schemas ===\n")

        # Register schemas
        project_schema = db.register_schema(name="project", model=ProjectAgent)
        member_schema = db.register_schema(name="member", model=TeamMemberAgent)

        print(f"Project Schema: {project_schema.fully_qualified_name}")
        print(f"  Version: {project_schema.version}")
        print(f"  Indexed fields: {project_schema.indexed_fields}")
        print(f"  MCP Tools: {[t.name for t in project_schema.tools]}")
        print()

        print("Project Schema $defs:")
        for def_name in (project_schema.defs or {}).keys():
            print(f"  - {def_name}")
        print()

        print(f"Team Member Schema: {member_schema.fully_qualified_name}")
        print(f"  Indexed fields: {member_schema.indexed_fields}")
        print()

        print("Member Schema $defs:")
        for def_name in (member_schema.defs or {}).keys():
            print(f"  - {def_name}")
        print()

        print("=== Inserting Team Members with Nested Data ===\n")

        # Insert team members
        alice_id = db.insert(
            "member",
            {
                "name": "Alice Johnson",
                "employee_id": "EMP001",
                "role": "Senior Software Engineer",
                "contact": {
                    "email": "alice@acme.com",
                    "phone": "+1-555-0100",
                    "address": {
                        "street": "123 Market St",
                        "city": "San Francisco",
                        "state": "CA",
                        "postal_code": "94102",
                    },
                },
                "skills": ["python", "rust", "kubernetes", "postgresql"],
                "location": "San Francisco, CA",
                "current_projects": ["Customer Portal Redesign", "API Gateway v2"],
            },
        )

        bob_id = db.insert(
            "member",
            {
                "name": "Bob Smith",
                "employee_id": "EMP002",
                "role": "Product Designer",
                "contact": {
                    "email": "bob@acme.com",
                    "phone": "+1-555-0101",
                },
                "skills": ["figma", "user-research", "prototyping"],
                "location": "New York, NY",
                "current_projects": ["Customer Portal Redesign"],
            },
        )

        charlie_id = db.insert(
            "member",
            {
                "name": "Charlie Davis",
                "employee_id": "EMP003",
                "role": "Frontend Engineer",
                "contact": {
                    "email": "charlie@acme.com",
                },
                "skills": ["react", "typescript", "css"],
                "location": "Austin, TX",
                "current_projects": ["Customer Portal Redesign"],
            },
        )

        print("Inserted 3 team members\n")

        print("=== Inserting Projects with Deeply Nested Data ===\n")

        # Insert project with complex nested structure
        project_id = db.insert(
            "project",
            {
                "name": "Customer Portal Redesign",
                "description": "Modernize customer-facing portal with new UI/UX and improved performance",
                "owner": "Alice Johnson",
                "status": "active",
                "priority": "high",
                "start_date": "2025-01-15",
                "target_end_date": "2025-06-30",
                "team_members": ["Alice Johnson", "Bob Smith", "Charlie Davis"],
                "tasks": [
                    {
                        "title": "Design new UI mockups",
                        "description": "Create high-fidelity mockups for all portal screens",
                        "assignee": "Bob Smith",
                        "priority": "high",
                        "estimated_hours": 80.0,
                        "status": {
                            "state": "done",
                            "updated_at": "2025-02-15",
                            "updated_by": "Bob Smith",
                            "notes": "Mockups approved by stakeholders",
                        },
                        "tags": ["design", "ui"],
                    },
                    {
                        "title": "Implement authentication flow",
                        "description": "Build OAuth 2.0 authentication with social login support",
                        "assignee": "Alice Johnson",
                        "priority": "critical",
                        "estimated_hours": 40.0,
                        "status": {
                            "state": "in_progress",
                            "updated_at": "2025-03-01",
                            "updated_by": "Alice Johnson",
                            "notes": "OAuth integration 70% complete",
                        },
                        "tags": ["backend", "security", "critical"],
                    },
                    {
                        "title": "Build dashboard components",
                        "description": "Create reusable React components for dashboard",
                        "assignee": "Charlie Davis",
                        "priority": "high",
                        "estimated_hours": 60.0,
                        "status": {
                            "state": "todo",
                            "updated_at": "2025-02-20",
                            "updated_by": "Alice Johnson",
                        },
                        "tags": ["frontend", "react"],
                    },
                    {
                        "title": "Performance optimization",
                        "description": "Optimize API response times and frontend rendering",
                        "assignee": "Alice Johnson",
                        "priority": "medium",
                        "estimated_hours": 30.0,
                        "status": {
                            "state": "blocked",
                            "updated_at": "2025-03-05",
                            "updated_by": "Alice Johnson",
                            "notes": "Waiting for database migration to complete",
                        },
                        "tags": ["performance", "optimization"],
                    },
                ],
                "milestones": [
                    {
                        "name": "Design Complete",
                        "description": "All UI mockups finalized and approved",
                        "due_date": "2025-02-28",
                        "completed": True,
                        "deliverables": ["UI mockups", "Design system documentation"],
                    },
                    {
                        "name": "MVP Launch",
                        "description": "Minimum viable product with core features",
                        "due_date": "2025-04-30",
                        "completed": False,
                        "deliverables": [
                            "Authentication",
                            "Dashboard",
                            "Basic reporting",
                        ],
                    },
                    {
                        "name": "Full Launch",
                        "description": "Complete portal with all features",
                        "due_date": "2025-06-30",
                        "completed": False,
                        "deliverables": [
                            "All MVP features",
                            "Advanced analytics",
                            "Mobile responsive",
                        ],
                    },
                ],
                "budget": {
                    "total_allocated": 250000.0,
                    "spent": 85000.0,
                    "currency": "USD",
                    "breakdown": {
                        "engineering": 150000.0,
                        "design": 50000.0,
                        "infrastructure": 30000.0,
                        "misc": 20000.0,
                    },
                },
            },
        )

        print("Inserted complex project with:")
        print("  - 4 tasks (with nested TaskStatus)")
        print("  - 3 milestones")
        print("  - Budget with breakdown")
        print()

        print("=== Querying with Indexed Fields ===\n")

        # Query 1: Active high-priority projects
        print("Q1: Active high-priority projects")
        projects = db.sql(
            "SELECT name, owner, status FROM project WHERE status = 'active' AND priority = 'high'"
        )
        for proj in projects:
            print(f"  → {proj['name']} (owned by {proj['owner']})")
        print()

        # Query 2: Team members in San Francisco
        print("Q2: Team members in San Francisco")
        sf_members = db.sql("SELECT name, role FROM member WHERE location = 'San Francisco, CA'")
        for member in sf_members:
            print(f"  → {member['name']}: {member['role']}")
        print()

        # Query 3: All active team members
        print("Q3: All active team members ordered by role")
        members = db.sql("SELECT name, role FROM member WHERE active = TRUE ORDER BY role")
        for member in members:
            print(f"  → {member['name']}: {member['role']}")
        print()

        print("=== Analyzing Nested Data ===\n")

        # Retrieve full project with nested data
        full_project = db.sql("SELECT * FROM project WHERE name = 'Customer Portal Redesign'")[0]

        print(f"Project: {full_project['name']}")
        print(f"Owner: {full_project['owner']}")
        print(f"Status: {full_project['status']}")
        print(f"Priority: {full_project['priority']}")
        print(f"Team size: {len(full_project['team_members'])}")
        print()

        print("Tasks breakdown:")
        task_counts = {}
        for task in full_project["tasks"]:
            state = task["status"]["state"]
            task_counts[state] = task_counts.get(state, 0) + 1
        for state, count in task_counts.items():
            print(f"  {state}: {count}")
        print()

        print("Blocked tasks:")
        for task in full_project["tasks"]:
            if task["status"]["state"] == "blocked":
                print(f"  - {task['title']}")
                print(f"    Assignee: {task['assignee']}")
                print(f"    Notes: {task['status']['notes']}")
        print()

        print("Budget status:")
        budget = full_project["budget"]
        spent_pct = (budget["spent"] / budget["total_allocated"]) * 100
        remaining = budget["total_allocated"] - budget["spent"]
        print(f"  Allocated: ${budget['total_allocated']:,.0f} {budget['currency']}")
        print(f"  Spent: ${budget['spent']:,.0f} ({spent_pct:.1f}%)")
        print(f"  Remaining: ${remaining:,.0f}")
        print()

        print("Upcoming milestones:")
        for milestone in full_project["milestones"]:
            if not milestone["completed"]:
                print(f"  - {milestone['name']} (due {milestone['due_date']})")
                print(f"    Deliverables: {', '.join(milestone['deliverables'])}")
        print()

        print("=== Nested Data Access ===\n")

        # Show nested contact info
        alice = db.sql("SELECT * FROM member WHERE name = 'Alice Johnson'")[0]
        print(f"Alice's contact info:")
        print(f"  Email: {alice['contact']['email']}")
        print(f"  Phone: {alice['contact']['phone']}")
        if alice['contact']['address']:
            print(f"  Location: {alice['contact']['address']['city']}, {alice['contact']['address']['state']}")
        print(f"  Skills: {', '.join(alice['skills'])}")
        print(f"  Current projects: {', '.join(alice['current_projects'])}")
        print()

        db.close()
        print("Done!")


if __name__ == "__main__":
    main()
