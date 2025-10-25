#!/usr/bin/env python3
"""Basic example of using REM database from Python.

This demonstrates the Python bindings (PyO3) for the Rust REM database.
"""

import asyncio
from pathlib import Path
import json

# Import the Rust extension module
try:
    from rem_db import Database
    print("✓ Successfully imported rem_db")
except ImportError as e:
    print(f"✗ Failed to import rem_db: {e}")
    print("  Run: maturin develop --release")
    exit(1)


async def main():
    """Demonstrate basic database operations."""

    # Create/open database
    db_path = Path("./python-test-db")
    print(f"\n1. Opening database at: {db_path}")
    db = Database(str(db_path))
    print("✓ Database opened")

    # Register a schema
    print("\n2. Registering schema...")
    schema = {
        "title": "Person",
        "version": "1.0.0",
        "short_name": "people",
        "description": "People in our database",
        "properties": {
            "name": {"type": "string", "description": "Person's name"},
            "email": {"type": "string", "description": "Email address"},
            "age": {"type": "integer", "description": "Age in years"},
            "role": {"type": "string", "description": "Job role"}
        },
        "required": ["name", "email"],
        "json_schema_extra": {
            "indexed_fields": ["email", "role"],
            "key_field": "email",
            "category": "user"
        }
    }

    # Save schema to temp file
    schema_file = Path("/tmp/person_schema.json")
    schema_file.write_text(json.dumps(schema, indent=2))

    db.register_schema_from_file(str(schema_file))
    print("✓ Schema registered")

    # Insert some entities
    print("\n3. Inserting entities...")
    people = [
        {"name": "Alice", "email": "alice@company.com", "age": 30, "role": "engineer"},
        {"name": "Bob", "email": "bob@company.com", "age": 35, "role": "manager"},
        {"name": "Charlie", "email": "charlie@company.com", "age": 28, "role": "engineer"},
        {"name": "Diana", "email": "diana@company.com", "age": 32, "role": "designer"},
    ]

    for person in people:
        entity_id = db.insert("default", "people", person)
        print(f"  Inserted: {person['name']} → {entity_id}")

    # Count entities
    print("\n4. Counting entities...")
    count = db.count("default", "people", include_deleted=False)
    print(f"✓ Total people: {count}")

    # Query with SQL
    print("\n5. Querying with SQL...")
    sql = "SELECT name, email, role FROM people WHERE role = 'engineer'"
    results = db.query_sql("default", sql)
    print(f"  Engineers ({len(results)} found):")
    for result in results:
        print(f"    - {result}")

    # Get entity by ID
    print("\n6. Get specific entity...")
    # Use deterministic UUID based on key_field
    import hashlib
    key_value = "alice@company.com"
    # This would need to match the Rust blake3 implementation
    # For now, just query by email
    sql = "SELECT * FROM people WHERE email = 'alice@company.com'"
    results = db.query_sql("default", sql)
    if results:
        print(f"  Alice's data: {results[0]}")

    # List all entities
    print("\n7. List all entities...")
    all_people = db.list("default", "people", include_deleted=False, limit=None)
    print(f"  All people ({len(all_people)}):")
    for person in all_people:
        print(f"    - {person['name']}: {person['role']}")

    # Update an entity
    print("\n8. Updating entity...")
    updated_data = {"name": "Alice", "email": "alice@company.com", "age": 31, "role": "senior engineer"}
    db.update("default", "alice@company.com", "people", updated_data)
    print("✓ Updated Alice's role")

    # Verify update
    sql = "SELECT name, role, age FROM people WHERE email = 'alice@company.com'"
    results = db.query_sql("default", sql)
    if results:
        print(f"  After update: {results[0]}")

    # Delete an entity (soft delete)
    print("\n9. Soft deleting entity...")
    db.delete("default", "charlie@company.com", "people")
    print("✓ Deleted Charlie")

    # Count after delete
    count_active = db.count("default", "people", include_deleted=False)
    count_total = db.count("default", "people", include_deleted=True)
    print(f"  Active: {count_active}, Total (including deleted): {count_total}")

    print("\n✓ All operations completed successfully!")
    print(f"\nDatabase location: {db_path}")
    print("To inspect: ./target/release/rem --db-path python-test-db query 'SELECT * FROM people'")


if __name__ == "__main__":
    asyncio.run(main())
