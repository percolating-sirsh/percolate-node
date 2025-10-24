"""Tests for schema registry and SQL query interface."""

import tempfile

import pytest
from pydantic import BaseModel, Field

from rem_db import MCPTool, REMDatabase, Schema


class Person(BaseModel):
    """A person in the organization."""

    name: str = Field(description="Full name of the person")
    email: str = Field(description="Email address")
    role: str = Field(description="Job role")
    team: str = Field(description="Team name")
    active: bool = Field(default=True, description="Is person active")


class Project(BaseModel):
    """A project in the organization."""

    name: str = Field(description="Project name")
    status: str = Field(description="Project status (active, completed, archived)")
    owner: str = Field(description="Project owner name")
    priority: int = Field(description="Priority (1-5)", ge=1, le=5)


@pytest.fixture
def db_with_schemas():
    """Create database with registered schemas."""
    with tempfile.TemporaryDirectory() as tmpdir:
        database = REMDatabase(tenant_id="test-tenant", path=tmpdir)

        # Register Person schema
        database.register_schema(
            name="person",
            model=Person,
            description="A person in the organization with contact details and role",
            system_prompt="You are a person entity. You have a name, email, role, and team.",
            indexed_fields=["role", "team", "active"],
            mcp_tools=[
                MCPTool(name="send_email", description="Send email to this person"),
                MCPTool(name="get_calendar", description="Get person's calendar"),
            ],
        )

        # Register Project schema
        database.register_schema(
            name="project",
            model=Project,
            description="A project with status and ownership",
            system_prompt="You are a project entity. Track status and deliverables.",
            indexed_fields=["status", "priority"],
            mcp_tools=[
                MCPTool(name="update_status", description="Update project status"),
            ],
        )

        yield database
        database.close()


def test_register_schema(db_with_schemas):
    """Test schema registration."""
    # Check schemas exist
    schemas = db_with_schemas.list_schemas()
    assert "person" in schemas
    assert "project" in schemas

    # Get person schema
    person_schema = db_with_schemas.get_schema("person")
    assert person_schema is not None
    assert person_schema.name == "person"
    assert person_schema.description == "A person in the organization with contact details and role"
    assert person_schema.short_name == "person"
    assert person_schema.version == "1.0.0"
    assert "role" in person_schema.indexed_fields
    assert len(person_schema.tools) == 2


def test_schema_field_metadata(db_with_schemas):
    """Test schema field metadata extraction from JSON schema."""
    person_schema = db_with_schemas.get_schema("person")

    # Check field metadata from properties (JSON schema)
    assert "name" in person_schema.properties
    name_field = person_schema.properties["name"]
    assert name_field["description"] == "Full name of the person"
    assert "name" in person_schema.required  # Required field

    assert "active" in person_schema.properties
    active_field = person_schema.properties["active"]
    assert active_field["type"] == "boolean"
    assert active_field.get("default") is True


def test_insert_with_schema_validation(db_with_schemas):
    """Test insert with schema validation."""
    # Valid insert
    person_id = db_with_schemas.insert(
        "person",
        {"name": "Alice", "email": "alice@example.com", "role": "engineer", "team": "platform"},
    )
    assert person_id is not None

    # Invalid insert (missing required field)
    with pytest.raises(Exception):  # Pydantic ValidationError
        db_with_schemas.insert("person", {"name": "Bob", "role": "engineer"})

    # Invalid table
    with pytest.raises(ValueError):
        db_with_schemas.insert("nonexistent", {"foo": "bar"})


def test_sql_select_star(db_with_schemas):
    """Test SELECT * FROM table."""
    # Insert test data
    db_with_schemas.insert(
        "person",
        {"name": "Alice", "email": "alice@example.com", "role": "engineer", "team": "platform"},
    )
    db_with_schemas.insert(
        "person",
        {"name": "Bob", "email": "bob@example.com", "role": "designer", "team": "product"},
    )

    # Query
    results = db_with_schemas.sql("SELECT * FROM person")

    assert len(results) == 2
    assert results[0]["name"] in ["Alice", "Bob"]
    assert "email" in results[0]
    assert "role" in results[0]


def test_sql_select_specific_fields(db_with_schemas):
    """Test SELECT field1, field2 FROM table."""
    db_with_schemas.insert(
        "person",
        {"name": "Alice", "email": "alice@example.com", "role": "engineer", "team": "platform"},
    )

    results = db_with_schemas.sql("SELECT name, email FROM person")

    assert len(results) == 1
    assert results[0] == {"name": "Alice", "email": "alice@example.com"}
    assert "role" not in results[0]
    assert "team" not in results[0]


def test_sql_where_equals(db_with_schemas):
    """Test WHERE field = value."""
    # Insert test data
    for i in range(5):
        db_with_schemas.insert(
            "person",
            {
                "name": f"Person {i}",
                "email": f"person{i}@example.com",
                "role": "engineer" if i < 3 else "designer",
                "team": "platform",
            },
        )

    # Query with WHERE
    results = db_with_schemas.sql("SELECT name FROM person WHERE role = 'engineer'")

    assert len(results) == 3
    for result in results:
        assert "Person" in result["name"]


def test_sql_where_and(db_with_schemas):
    """Test WHERE cond1 AND cond2."""
    # Insert test data
    db_with_schemas.insert(
        "person",
        {"name": "Alice", "email": "alice@example.com", "role": "engineer", "team": "platform"},
    )
    db_with_schemas.insert(
        "person", {"name": "Bob", "email": "bob@example.com", "role": "engineer", "team": "infra"}
    )
    db_with_schemas.insert(
        "person",
        {"name": "Charlie", "email": "charlie@example.com", "role": "designer", "team": "platform"},
    )

    # Query with AND
    results = db_with_schemas.sql(
        "SELECT name FROM person WHERE role = 'engineer' AND team = 'platform'"
    )

    assert len(results) == 1
    assert results[0]["name"] == "Alice"


def test_sql_where_or(db_with_schemas):
    """Test WHERE cond1 OR cond2."""
    db_with_schemas.insert(
        "person",
        {"name": "Alice", "email": "alice@example.com", "role": "engineer", "team": "platform"},
    )
    db_with_schemas.insert(
        "person", {"name": "Bob", "email": "bob@example.com", "role": "designer", "team": "product"}
    )

    results = db_with_schemas.sql("SELECT name FROM person WHERE role = 'engineer' OR team = 'product'")

    assert len(results) == 2


def test_sql_where_in(db_with_schemas):
    """Test WHERE field IN (val1, val2)."""
    for role in ["engineer", "designer", "manager", "analyst"]:
        db_with_schemas.insert(
            "person",
            {"name": f"{role}_person", "email": f"{role}@example.com", "role": role, "team": "team"},
        )

    results = db_with_schemas.sql("SELECT name FROM person WHERE role IN ('engineer', 'designer')")

    assert len(results) == 2


def test_sql_where_comparison(db_with_schemas):
    """Test WHERE with comparison operators (>, <, >=, <=)."""
    for i in range(1, 6):
        db_with_schemas.insert(
            "project", {"name": f"Project {i}", "status": "active", "owner": "Alice", "priority": i}
        )

    # Greater than
    results = db_with_schemas.sql("SELECT name FROM project WHERE priority > 3")
    assert len(results) == 2

    # Less than or equal
    results = db_with_schemas.sql("SELECT name FROM project WHERE priority <= 2")
    assert len(results) == 2


def test_sql_order_by(db_with_schemas):
    """Test ORDER BY field ASC/DESC."""
    for name in ["Charlie", "Alice", "Bob"]:
        db_with_schemas.insert(
            "person", {"name": name, "email": f"{name.lower()}@example.com", "role": "engineer", "team": "team"}
        )

    # ORDER BY ASC
    results = db_with_schemas.sql("SELECT name FROM person ORDER BY name ASC")
    names = [r["name"] for r in results]
    assert names == ["Alice", "Bob", "Charlie"]

    # ORDER BY DESC
    results = db_with_schemas.sql("SELECT name FROM person ORDER BY name DESC")
    names = [r["name"] for r in results]
    assert names == ["Charlie", "Bob", "Alice"]


def test_sql_limit_offset(db_with_schemas):
    """Test LIMIT and OFFSET."""
    for i in range(20):
        db_with_schemas.insert(
            "person",
            {"name": f"Person {i:02d}", "email": f"p{i}@example.com", "role": "engineer", "team": "team"},
        )

    # LIMIT
    results = db_with_schemas.sql("SELECT name FROM person ORDER BY name LIMIT 5")
    assert len(results) == 5

    # LIMIT and OFFSET (pagination)
    page1 = db_with_schemas.sql("SELECT name FROM person ORDER BY name LIMIT 5 OFFSET 0")
    page2 = db_with_schemas.sql("SELECT name FROM person ORDER BY name LIMIT 5 OFFSET 5")

    assert len(page1) == 5
    assert len(page2) == 5
    assert page1[0]["name"] != page2[0]["name"]


def test_sql_complex_query(db_with_schemas):
    """Test complex SQL query with multiple clauses."""
    # Insert diverse data
    for i in range(10):
        db_with_schemas.insert(
            "person",
            {
                "name": f"Person {i}",
                "email": f"person{i}@example.com",
                "role": "engineer" if i % 2 == 0 else "designer",
                "team": "platform" if i < 5 else "product",
                "active": i < 8,
            },
        )

    # Complex query
    results = db_with_schemas.sql(
        """
        SELECT name, role, team
        FROM person
        WHERE (role = 'engineer' AND team = 'platform') OR active = FALSE
        ORDER BY name DESC
        LIMIT 3
        """
    )

    assert len(results) == 3
    for result in results:
        assert "name" in result
        assert "role" in result
        assert "team" in result


def test_schema_with_mcp_tools(db_with_schemas):
    """Test that MCP tools are stored with schema."""
    person_schema = db_with_schemas.get_schema("person")

    assert len(person_schema.tools) == 2

    email_tool = next((t for t in person_schema.tools if t.name == "send_email"), None)
    assert email_tool is not None
    assert email_tool.description == "Send email to this person"


def test_indexed_fields_query_performance(db_with_schemas):
    """Test that indexed fields are used for queries."""
    # Insert many entities
    for i in range(100):
        db_with_schemas.insert(
            "person",
            {
                "name": f"Person {i}",
                "email": f"p{i}@example.com",
                "role": "engineer" if i % 2 == 0 else "designer",
                "team": "platform",
            },
        )

    # Query with indexed field (role)
    results = db_with_schemas.sql("SELECT name FROM person WHERE role = 'engineer'")

    # Should use index and return correct results
    assert len(results) == 50
