"""Tests for nested Pydantic model schemas."""

import tempfile
from typing import Literal

import pytest
from pydantic import BaseModel, ConfigDict, Field

from rem_db import REMDatabase


# Nested models
class Address(BaseModel):
    """Address information."""

    street: str = Field(description="Street address")
    city: str = Field(description="City name")
    state: str = Field(description="State code", min_length=2, max_length=2)
    zip_code: str = Field(description="ZIP code", pattern=r"^\d{5}(-\d{4})?$")
    country: str = Field(default="US", description="Country code")


class ContactInfo(BaseModel):
    """Contact information."""

    email: str = Field(description="Email address")
    phone: str | None = Field(None, description="Phone number")
    address: Address = Field(description="Physical address")


class EmployeeProfile(BaseModel):
    """Employee profile with nested contact information."""

    model_config = ConfigDict(
        json_schema_extra={
            "fully_qualified_name": "rem.entities.employee.EmployeeProfile",
            "short_name": "employee",
            "version": "1.0.0",
            "indexed_fields": ["department", "active"],
        }
    )

    name: str = Field(description="Employee full name")
    employee_id: str = Field(description="Unique employee ID")
    department: str = Field(description="Department name")
    contact: ContactInfo = Field(description="Contact information")
    active: bool = Field(default=True, description="Employment status")


class Priority(BaseModel):
    """Priority classification."""

    level: Literal["low", "medium", "high", "critical"] = Field(description="Priority level")
    reason: str = Field(description="Reason for priority level")


class Classification(BaseModel):
    """Ticket classification."""

    category: str = Field(description="Primary category")
    subcategory: str | None = Field(None, description="Subcategory if applicable")
    tags: list[str] = Field(default_factory=list, description="Additional tags")


class SupportTicket(BaseModel):
    """Support ticket with nested classification and priority.

    ## Your Role

    You are a support ticket entity tracking customer issues and requests.
    You maintain structured information about the issue, its priority, and classification.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "fully_qualified_name": "rem.entities.support.SupportTicket",
            "short_name": "ticket",
            "version": "1.0.0",
            "indexed_fields": ["status", "priority.level"],
            "tools": [
                {
                    "name": "assign_agent",
                    "description": "Assign ticket to support agent",
                    "server": "support_server",
                }
            ],
        }
    )

    ticket_id: str = Field(description="Unique ticket identifier")
    title: str = Field(description="Ticket title")
    description: str = Field(description="Detailed description of issue")
    status: Literal["open", "in_progress", "resolved", "closed"] = Field(description="Ticket status")
    priority: Priority = Field(description="Priority classification")
    classification: Classification = Field(description="Ticket classification")
    customer_email: str = Field(description="Customer email address")


@pytest.fixture
def db_with_nested_schemas():
    """Create database with nested schemas."""
    with tempfile.TemporaryDirectory() as tmpdir:
        database = REMDatabase(tenant_id="test-tenant", path=tmpdir)

        # Register schemas with nested models
        database.register_schema(name="employee", model=EmployeeProfile)
        database.register_schema(name="ticket", model=SupportTicket)

        yield database
        database.close()


def test_nested_schema_defs(db_with_nested_schemas):
    """Test that nested models are captured in $defs."""
    employee_schema = db_with_nested_schemas.get_schema("employee")

    # Should have $defs for nested models
    assert employee_schema.defs is not None
    assert "Address" in employee_schema.defs
    assert "ContactInfo" in employee_schema.defs

    # Check Address definition
    address_def = employee_schema.defs["Address"]
    assert address_def["type"] == "object"
    assert "street" in address_def["properties"]
    assert "city" in address_def["properties"]
    assert "state" in address_def["properties"]
    assert address_def["properties"]["state"]["minLength"] == 2
    assert address_def["properties"]["state"]["maxLength"] == 2

    # Check ContactInfo definition
    contact_def = employee_schema.defs["ContactInfo"]
    assert contact_def["type"] == "object"
    assert "email" in contact_def["properties"]
    assert "address" in contact_def["properties"]


def test_deeply_nested_schema_defs(db_with_nested_schemas):
    """Test deeply nested models (3+ levels)."""
    ticket_schema = db_with_nested_schemas.get_schema("ticket")

    # Should have $defs for all nested levels
    assert ticket_schema.defs is not None
    assert "Priority" in ticket_schema.defs
    assert "Classification" in ticket_schema.defs

    # Check Priority has enum constraint
    priority_def = ticket_schema.defs["Priority"]
    assert "level" in priority_def["properties"]
    assert "enum" in priority_def["properties"]["level"]
    assert set(priority_def["properties"]["level"]["enum"]) == {"low", "medium", "high", "critical"}


def test_insert_with_nested_data(db_with_nested_schemas):
    """Test inserting entities with nested data."""
    # Insert employee with nested contact info
    employee_id = db_with_nested_schemas.insert(
        "employee",
        {
            "name": "Alice Johnson",
            "employee_id": "EMP001",
            "department": "Engineering",
            "contact": {
                "email": "alice@example.com",
                "phone": "+1-555-0100",
                "address": {
                    "street": "123 Main St",
                    "city": "San Francisco",
                    "state": "CA",
                    "zip_code": "94102",
                    "country": "US",
                },
            },
            "active": True,
        },
    )

    assert employee_id is not None

    # Retrieve and verify nested structure
    results = db_with_nested_schemas.sql("SELECT * FROM employee WHERE name = 'Alice Johnson'")
    assert len(results) == 1

    employee = results[0]
    assert employee["name"] == "Alice Johnson"
    assert employee["contact"]["email"] == "alice@example.com"
    assert employee["contact"]["address"]["city"] == "San Francisco"
    assert employee["contact"]["address"]["state"] == "CA"


def test_nested_validation(db_with_nested_schemas):
    """Test that nested model validation works."""
    # Invalid state (too long)
    with pytest.raises(Exception):  # Pydantic ValidationError
        db_with_nested_schemas.insert(
            "employee",
            {
                "name": "Bob Smith",
                "employee_id": "EMP002",
                "department": "Sales",
                "contact": {
                    "email": "bob@example.com",
                    "address": {
                        "street": "456 Oak Ave",
                        "city": "Austin",
                        "state": "TEXAS",  # Should be 2 chars
                        "zip_code": "78701",
                    },
                },
            },
        )

    # Invalid ZIP code pattern
    with pytest.raises(Exception):
        db_with_nested_schemas.insert(
            "employee",
            {
                "name": "Bob Smith",
                "employee_id": "EMP002",
                "department": "Sales",
                "contact": {
                    "email": "bob@example.com",
                    "address": {
                        "street": "456 Oak Ave",
                        "city": "Austin",
                        "state": "TX",
                        "zip_code": "INVALID",  # Should match \d{5}(-\d{4})?
                    },
                },
            },
        )


def test_query_with_nested_fields(db_with_nested_schemas):
    """Test querying entities with nested fields."""
    # Insert test data
    for i, dept in enumerate(["Engineering", "Sales", "Marketing"]):
        db_with_nested_schemas.insert(
            "employee",
            {
                "name": f"Employee {i}",
                "employee_id": f"EMP{i:03d}",
                "department": dept,
                "contact": {
                    "email": f"emp{i}@example.com",
                    "address": {
                        "street": f"{i} Main St",
                        "city": "San Francisco",
                        "state": "CA",
                        "zip_code": "94102",
                    },
                },
            },
        )

    # Query by top-level field (indexed)
    results = db_with_nested_schemas.sql("SELECT name, department FROM employee WHERE department = 'Engineering'")
    assert len(results) == 1
    assert results[0]["department"] == "Engineering"


def test_nested_list_fields(db_with_nested_schemas):
    """Test nested models with list fields."""
    # Insert ticket with classification tags
    ticket_id = db_with_nested_schemas.insert(
        "ticket",
        {
            "ticket_id": "TICK-001",
            "title": "Login not working",
            "description": "Cannot log in to the application",
            "status": "open",
            "priority": {"level": "high", "reason": "Blocking user access"},
            "classification": {
                "category": "authentication",
                "subcategory": "login",
                "tags": ["critical", "security", "urgent"],
            },
            "customer_email": "customer@example.com",
        },
    )

    assert ticket_id is not None

    # Retrieve and verify list field
    results = db_with_nested_schemas.sql("SELECT * FROM ticket WHERE ticket_id = 'TICK-001'")
    assert len(results) == 1

    ticket = results[0]
    assert ticket["classification"]["tags"] == ["critical", "security", "urgent"]
    assert ticket["priority"]["level"] == "high"


def test_nested_optional_fields(db_with_nested_schemas):
    """Test nested models with optional fields."""
    # Insert without optional phone
    employee_id = db_with_nested_schemas.insert(
        "employee",
        {
            "name": "Charlie Davis",
            "employee_id": "EMP100",
            "department": "Product",
            "contact": {
                "email": "charlie@example.com",
                # phone is optional
                "address": {
                    "street": "789 Pine St",
                    "city": "Seattle",
                    "state": "WA",
                    "zip_code": "98101",
                },
            },
        },
    )

    results = db_with_nested_schemas.sql("SELECT * FROM employee WHERE employee_id = 'EMP100'")
    assert len(results) == 1
    assert results[0]["contact"]["phone"] is None

    # Insert with optional phone
    db_with_nested_schemas.insert(
        "employee",
        {
            "name": "Diana Martinez",
            "employee_id": "EMP101",
            "department": "Product",
            "contact": {
                "email": "diana@example.com",
                "phone": "+1-555-0200",
                "address": {
                    "street": "321 Elm St",
                    "city": "Seattle",
                    "state": "WA",
                    "zip_code": "98102",
                },
            },
        },
    )

    results = db_with_nested_schemas.sql("SELECT * FROM employee WHERE employee_id = 'EMP101'")
    assert results[0]["contact"]["phone"] == "+1-555-0200"


def test_nested_default_values(db_with_nested_schemas):
    """Test nested models with default values."""
    # Insert without country (should default to "US")
    db_with_nested_schemas.insert(
        "employee",
        {
            "name": "Eve Wilson",
            "employee_id": "EMP200",
            "department": "HR",
            "contact": {
                "email": "eve@example.com",
                "address": {
                    "street": "555 Broadway",
                    "city": "New York",
                    "state": "NY",
                    "zip_code": "10012",
                    # country should default to "US"
                },
            },
        },
    )

    results = db_with_nested_schemas.sql("SELECT * FROM employee WHERE employee_id = 'EMP200'")
    assert results[0]["contact"]["address"]["country"] == "US"


def test_json_schema_export_with_nested_models(db_with_nested_schemas):
    """Test JSON schema export includes $defs."""
    employee_schema = db_with_nested_schemas.get_schema("employee")
    json_schema = employee_schema.to_json_schema()

    # Should include $defs in export
    assert "$defs" in json_schema
    assert "Address" in json_schema["$defs"]
    assert "ContactInfo" in json_schema["$defs"]

    # Should preserve field references to nested models
    contact_field = json_schema["properties"]["contact"]
    assert "$ref" in contact_field
    assert contact_field["$ref"] == "#/$defs/ContactInfo"


def test_nested_model_with_agent_metadata(db_with_nested_schemas):
    """Test that agent-let metadata works with nested models."""
    ticket_schema = db_with_nested_schemas.get_schema("ticket")

    # Check metadata
    assert ticket_schema.fully_qualified_name == "rem.entities.support.SupportTicket"
    assert ticket_schema.short_name == "ticket"
    assert ticket_schema.version == "1.0.0"

    # Check system prompt from docstring
    assert "support ticket entity" in ticket_schema.description.lower()
    assert "Your Role" in ticket_schema.description

    # Check MCP tools
    assert len(ticket_schema.tools) == 1
    assert ticket_schema.tools[0].name == "assign_agent"

    # Check indexed fields (including nested field)
    assert "status" in ticket_schema.indexed_fields
    assert "priority.level" in ticket_schema.indexed_fields


def test_multiple_entities_with_shared_nested_models(db_with_nested_schemas):
    """Test inserting multiple entities that share nested model definitions."""
    # Insert multiple employees (all share Address, ContactInfo models)
    for i in range(5):
        db_with_nested_schemas.insert(
            "employee",
            {
                "name": f"Employee {i}",
                "employee_id": f"EMP{i:03d}",
                "department": "Engineering",
                "contact": {
                    "email": f"emp{i}@example.com",
                    "address": {
                        "street": f"{i * 100} Market St",
                        "city": "San Francisco",
                        "state": "CA",
                        "zip_code": f"9410{i}",
                    },
                },
            },
        )

    # All should share the same schema definition
    results = db_with_nested_schemas.sql("SELECT * FROM employee")
    assert len(results) == 5

    # Verify nested structure is consistent
    for result in results:
        assert "contact" in result
        assert "address" in result["contact"]
        assert result["contact"]["address"]["city"] == "San Francisco"
