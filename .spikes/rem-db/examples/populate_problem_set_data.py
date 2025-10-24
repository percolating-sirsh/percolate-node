"""Populate test data for problem set evaluation.

Creates all entities, resources, and relationships needed to answer
the 10 questions in problem-set.md.

Key structures:
- entity:{tenant}:{uuid} - Entity storage by ID
- resource:{tenant}:{uuid} - Resource storage by ID
- edge:{tenant}:{src}:{dst}:{type} - Graph edges
- index:{field}:{tenant}:{value} - Secondary indexes

Fast entity lookup patterns:
1. By ID: Direct key lookup entity:{tenant}:{id}
2. By name: Index scan or entity properties
3. By aliases: Stored in entity.aliases list
4. By type: Scan entity prefix, filter by type field
"""

import os
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from rem_db import Edge, Entity, REMDatabase


def clean_database(db_path: Path) -> None:
    """Remove existing database."""
    if db_path.exists():
        shutil.rmtree(db_path)
        print(f"✓ Cleaned existing database at {db_path}")


def create_users(db: REMDatabase) -> dict[str, UUID]:
    """Create user entities for testing.

    Returns mapping of user names to UUIDs.
    """
    print("\n" + "="*60)
    print("CREATING USERS")
    print("="*60)

    users = {}
    user_data = [
        {
            "name": "Alice",
            "role": "senior_engineer",
            "employee_id": "EMP-001",
            "join_date": "2023-01-15",
        },
        {
            "name": "Bob",
            "role": "engineer",
            "employee_id": "EMP-002",
            "join_date": "2023-06-20",
        },
        {
            "name": "Charlie",
            "role": "engineer",
            "employee_id": "EMP-003",
            "join_date": "2024-03-10",
        },
        {
            "name": "Diana",
            "role": "senior_engineer",
            "employee_id": "EMP-004",
            "join_date": "2022-11-05",
        },
        {
            "name": "Eve",
            "role": "intern",
            "employee_id": "EMP-005",
            "join_date": "2024-09-01",
        },
        {
            "name": "Frank",
            "role": "engineer",
            "employee_id": "EMP-006",
            "join_date": "2024-01-20",
        },
    ]

    for data in user_data:
        entity = Entity(
            type="user",
            name=data["name"],
            aliases=[data["employee_id"]],  # Allow lookup by employee ID
            properties=data,
        )
        entity_id = db.create_entity(entity)
        users[data["name"]] = entity_id
        print(f"  ✓ {data['name']} (ID: {entity_id}, employee_id: {data['employee_id']})")

    return users


def create_issues(db: REMDatabase, users: dict[str, UUID]) -> dict[str, UUID]:
    """Create issue entities with numeric and code identifiers.

    Tests entity lookup patterns:
    - Numeric ID: "12345"
    - Code pattern: "TAP-1234"
    """
    print("\n" + "="*60)
    print("CREATING ISSUES")
    print("="*60)

    issues = {}
    issue_data = [
        {
            "name": "Issue #12345",  # For Q1: "What is 12345?"
            "issue_number": "12345",
            "title": "Fix authentication bug in OAuth flow",
            "status": "open",
            "priority": "high",
            "created_by": "Alice",
        },
        {
            "name": "TAP-1234",  # For Q2: "Find TAP-1234"
            "ticket_id": "TAP-1234",
            "title": "Implement rate limiting for API endpoints",
            "status": "in_progress",
            "priority": "medium",
            "created_by": "Bob",
        },
        {
            "name": "TAP-5678",
            "ticket_id": "TAP-5678",
            "title": "Add logging to authentication service",
            "status": "open",
            "priority": "low",
            "created_by": "Charlie",
        },
    ]

    for data in issue_data:
        # Use issue_number or ticket_id as alias for entity lookup
        alias = data.get("issue_number") or data.get("ticket_id")

        entity = Entity(
            type="issue",
            name=data["name"],
            aliases=[alias, data["name"]],  # Allow lookup by number or name
            properties=data,
        )
        entity_id = db.create_entity(entity)
        issues[data["name"]] = entity_id
        print(f"  ✓ {data['name']} (ID: {entity_id}, alias: {alias})")

    # Create edges: user -> created -> issue
    for issue_name, issue_id in issues.items():
        issue_entity = db.get_entity(issue_id)
        creator_name = issue_entity.properties["created_by"]
        creator_id = users[creator_name]

        edge = Edge(
            src_id=creator_id,
            dst_id=issue_id,
            edge_type="created",
            properties={"created_at": str(datetime.now(UTC))},
        )
        db.create_edge(edge)
        print(f"    → {creator_name} created {issue_name}")

    return issues


def create_carriers(db: REMDatabase) -> dict[str, UUID]:
    """Create carrier entities for brand name lookup.

    Tests entity lookup: "Tell me about DHL"
    """
    print("\n" + "="*60)
    print("CREATING CARRIERS")
    print("="*60)

    carriers = {}
    carrier_data = [
        {
            "name": "DHL",  # For Q3: "Tell me about DHL"
            "full_name": "DHL Express",
            "country": "Germany",
            "services": ["express", "freight", "supply_chain"],
        },
        {
            "name": "FedEx",
            "full_name": "Federal Express",
            "country": "USA",
            "services": ["express", "ground", "freight"],
        },
        {
            "name": "UPS",
            "full_name": "United Parcel Service",
            "country": "USA",
            "services": ["ground", "air", "freight"],
        },
    ]

    for data in carrier_data:
        entity = Entity(
            type="carrier",
            name=data["name"],
            aliases=[data["full_name"], data["name"]],
            properties=data,
        )
        entity_id = db.create_entity(entity)
        carriers[data["name"]] = entity_id
        print(f"  ✓ {data['name']} (ID: {entity_id}, full_name: {data['full_name']})")

    return carriers


def create_resources(db: REMDatabase) -> dict[str, UUID]:
    """Create resources for SQL and vector queries.

    Tests:
    - Q4: "resources with category tutorial"
    - Q5: "agents created in last 7 days"
    - Q6: "resources where status is active or published"
    - Q7: "resources about authentication and security"
    - Q8: "tutorials for beginners learning to code"
    - Q9: "Python resources from last month"
    """
    print("\n" + "="*60)
    print("CREATING RESOURCES")
    print("="*60)

    resources = {}
    now = datetime.now(UTC)

    resource_data = [
        # Category = "tutorial" (for Q4)
        {
            "name": "Python for Beginners",
            "content": "Learn Python programming from scratch. This tutorial covers variables, functions, classes, and object-oriented programming. Perfect for beginners learning to code.",
            "category": "tutorial",
            "status": "published",
            "created_at": now - timedelta(days=5),  # Recent (for Q9)
        },
        {
            "name": "JavaScript Basics",
            "content": "Introduction to JavaScript for beginners. Learn DOM manipulation, async programming, and modern ES6+ features. Great tutorial for new developers.",
            "category": "tutorial",
            "status": "active",
            "created_at": now - timedelta(days=15),
        },
        {
            "name": "Rust Programming Guide",
            "content": "Advanced Rust programming guide covering ownership, lifetimes, and systems programming. For experienced developers.",
            "category": "guide",
            "status": "published",
            "created_at": now - timedelta(days=60),  # Older
        },

        # Authentication/security content (for Q7)
        {
            "name": "OAuth 2.0 Implementation",
            "content": "Complete guide to implementing OAuth 2.0 authentication in web applications. Covers authorization flows, token management, and security best practices.",
            "category": "tutorial",
            "status": "active",
            "created_at": now - timedelta(days=20),
        },
        {
            "name": "Security Best Practices",
            "content": "Web application security guide covering authentication, authorization, HTTPS, encryption, and common vulnerabilities like SQL injection and XSS.",
            "category": "guide",
            "status": "published",
            "created_at": now - timedelta(days=30),
        },
        {
            "name": "Login Systems with JWT",
            "content": "Building secure login systems using JSON Web Tokens (JWT). Covers token generation, validation, refresh tokens, and authentication middleware.",
            "category": "tutorial",
            "status": "draft",  # Not active or published
            "created_at": now - timedelta(days=10),
        },

        # Python content (for Q9)
        {
            "name": "Python Web Development",
            "content": "Building web applications with Python using Flask and Django frameworks. REST APIs, database integration, and deployment.",
            "category": "guide",
            "status": "active",
            "created_at": now - timedelta(days=3),  # Very recent
        },
        {
            "name": "Python Data Science",
            "content": "Data analysis and machine learning with Python. NumPy, Pandas, scikit-learn, and visualization libraries.",
            "category": "tutorial",
            "status": "published",
            "created_at": now - timedelta(days=45),  # Older than 1 month
        },
    ]

    for data in resource_data:
        # Convert datetime to timestamp for storage
        created_at = data.pop("created_at")

        # Use insert() to go through schema validation and store as entity
        insert_data = {
            "name": data["name"],
            "content": data["content"],
            "category": data["category"],
            "metadata": {"status": data["status"]},
        }

        # Insert as entity with type="resources"
        resource_id = db.insert("resources", insert_data)

        # Update created_at manually (hack for now, should support in insert())
        entity = db.get_entity(resource_id)
        entity.created_at = created_at
        key = db._key("entity", str(resource_id))
        db._put(key, entity.model_dump(mode="json"))

        resources[data["name"]] = resource_id

        # Show days ago
        days_ago = (now - created_at).days
        print(f"  ✓ {data['name']}")
        print(f"      category={data['category']}, status={data['status']}, age={days_ago} days")

    return resources


def create_agents(db: REMDatabase) -> dict[str, UUID]:
    """Create agent entities for temporal queries.

    Tests Q5: "agents created in last 7 days"
    """
    print("\n" + "="*60)
    print("CREATING AGENTS")
    print("="*60)

    agents = {}
    now = datetime.now(UTC)

    agent_data = [
        # Recent agents (< 7 days)
        {
            "name": "Code Review Agent",
            "description": "Reviews code for best practices and potential bugs",
            "category": "development",
            "created_at": now - timedelta(days=2),
        },
        {
            "name": "Documentation Generator",
            "description": "Generates API documentation from code comments",
            "category": "documentation",
            "created_at": now - timedelta(days=5),
        },

        # Older agents (> 7 days)
        {
            "name": "Test Generator",
            "description": "Generates unit tests for Python functions",
            "category": "testing",
            "created_at": now - timedelta(days=15),
        },
        {
            "name": "Security Scanner",
            "description": "Scans code for security vulnerabilities",
            "category": "security",
            "created_at": now - timedelta(days=30),
        },
    ]

    for data in agent_data:
        created_at = data.pop("created_at")

        # Create as entity since we don't have Agent pydantic model with insert
        entity = Entity(
            type="agent",
            name=data["name"],
            properties=data,
            created_at=created_at,
        )
        entity_id = db.create_entity(entity)
        agents[data["name"]] = entity_id

        days_ago = (now - created_at).days
        is_recent = days_ago <= 7
        status = "✓ RECENT" if is_recent else "  older"
        print(f"  {status} {data['name']} ({days_ago} days ago)")

    return agents


def create_code_files_and_relationships(
    db: REMDatabase,
    users: dict[str, UUID]
) -> dict[str, UUID]:
    """Create code file entities and authorship relationships.

    Tests Q10: "Who has worked on authentication-related code?"

    Graph pattern:
    - Files with auth-related content
    - Users who created/authored/modified those files
    - Edges: user -> created/authored/modified -> file
    """
    print("\n" + "="*60)
    print("CREATING CODE FILES & RELATIONSHIPS")
    print("="*60)

    files = {}

    # Files with authentication-related content
    auth_files = [
        {
            "name": "auth.py",
            "content": "Authentication module with OAuth 2.0 implementation, login handlers, and session management.",
            "type": "python",
            "path": "src/auth/auth.py",
            "authors": ["Alice", "Bob"],  # Multiple contributors
        },
        {
            "name": "login.py",
            "content": "Login page handlers and JWT token generation for user authentication.",
            "type": "python",
            "path": "src/auth/login.py",
            "authors": ["Alice"],
        },
        {
            "name": "oauth_flow.py",
            "content": "OAuth authorization flow implementation with PKCE for secure authentication.",
            "type": "python",
            "path": "src/auth/oauth_flow.py",
            "authors": ["Charlie"],
        },
    ]

    # Non-auth files (for comparison)
    other_files = [
        {
            "name": "database.py",
            "content": "Database connection and query utilities using SQLAlchemy ORM.",
            "type": "python",
            "path": "src/db/database.py",
            "authors": ["Diana"],
        },
        {
            "name": "utils.py",
            "content": "General utility functions for string manipulation and date formatting.",
            "type": "python",
            "path": "src/utils/utils.py",
            "authors": ["Eve"],
        },
    ]

    all_files = auth_files + other_files

    for file_data in all_files:
        authors = file_data.pop("authors")

        # Store as resource entity (type="resources") for vector search
        insert_data = {
            "name": file_data["name"],
            "content": file_data["content"],
            "category": "code",
            "metadata": {
                "type": file_data["type"],
                "path": file_data["path"],
            },
        }
        file_id = db.insert("resources", insert_data)
        files[file_data["name"]] = file_id

        is_auth = file_data["name"] in [f["name"] for f in auth_files]
        status = "🔐 AUTH" if is_auth else "  regular"
        print(f"  {status} {file_data['name']}")

        # Create authorship edges
        for author_name in authors:
            author_id = users[author_name]

            # Create edge: user -> authored -> file
            edge = Edge(
                src_id=author_id,
                dst_id=file_id,
                edge_type="authored",
                properties={"role": "author", "created_at": str(datetime.now(UTC))},
            )
            db.create_edge(edge)
            print(f"      → {author_name} authored this file")

    return files


def wait_for_embeddings(db: REMDatabase) -> None:
    """Wait for background worker to generate embeddings."""
    print("\n" + "="*60)
    print("GENERATING EMBEDDINGS")
    print("="*60)
    print("  Waiting for background worker to generate embeddings...")

    success = db.wait_for_worker(timeout=30.0)
    if success:
        print("  ✓ All embeddings generated successfully")
    else:
        print("  ⚠ Warning: Worker timeout (embeddings may still be generating)")


def print_summary(
    users: dict,
    issues: dict,
    carriers: dict,
    resources: dict,
    agents: dict,
    files: dict,
) -> None:
    """Print summary of created data."""
    print("\n" + "="*60)
    print("DATA SUMMARY")
    print("="*60)
    print(f"  Users:     {len(users)}")
    print(f"  Issues:    {len(issues)}")
    print(f"  Carriers:  {len(carriers)}")
    print(f"  Resources: {len(resources)}")
    print(f"  Agents:    {len(agents)}")
    print(f"  Files:     {len(files)}")
    print(f"  Total:     {len(users) + len(issues) + len(carriers) + len(resources) + len(agents) + len(files)}")

    print("\n" + "="*60)
    print("ENTITY LOOKUP EXAMPLES")
    print("="*60)
    print("  Numeric ID:    12345 → Issue #12345")
    print("  Code pattern:  TAP-1234 → Issue TAP-1234")
    print("  Brand name:    DHL → Carrier DHL Express")
    print("  Employee ID:   EMP-001 → User Alice")

    print("\n" + "="*60)
    print("SQL QUERY EXAMPLES")
    print("="*60)
    print("  Category filter:   SELECT * FROM resources WHERE category = 'tutorial'")
    print("  Temporal filter:   SELECT * FROM agents WHERE created_at >= '7 days ago'")
    print("  IN operator:       SELECT * FROM resources WHERE status IN ('active', 'published')")

    print("\n" + "="*60)
    print("VECTOR SEARCH EXAMPLES")
    print("="*60)
    print("  Semantic:    SELECT * FROM resources WHERE embedding.cosine('authentication security')")
    print("  Paraphrase:  SELECT * FROM resources WHERE embedding.cosine('tutorials for beginners')")

    print("\n" + "="*60)
    print("HYBRID QUERY EXAMPLE")
    print("="*60)
    print("  Semantic + temporal: Python resources from last month")

    print("\n" + "="*60)
    print("GRAPH TRAVERSAL EXAMPLE")
    print("="*60)
    print("  Multi-stage: Who worked on auth code?")
    print("    Stage 1: Find auth files (vector search)")
    print("    Stage 2: Traverse 'authored' edges backwards")
    print("    Result: Alice, Bob, Charlie")


def main():
    """Populate test database with problem set data."""
    print("="*60)
    print("POPULATING PROBLEM SET TEST DATA")
    print("="*60)

    # Database path
    db_path = Path("/tmp/problem_set_db")

    # Clean existing database
    clean_database(db_path)

    # Create database
    print(f"\nCreating database at {db_path}")
    db = REMDatabase(tenant_id="test", path=str(db_path))
    print("✓ Database created")

    # Populate data
    users = create_users(db)
    issues = create_issues(db, users)
    carriers = create_carriers(db)
    resources = create_resources(db)
    agents = create_agents(db)
    files = create_code_files_and_relationships(db, users)

    # Wait for embeddings
    wait_for_embeddings(db)

    # Print summary
    print_summary(users, issues, carriers, resources, agents, files)

    # Close database
    db.close()

    print("\n" + "="*60)
    print("✓ DATA POPULATION COMPLETE")
    print("="*60)
    print(f"\nDatabase location: {db_path}")
    print(f"\nNext steps:")
    print(f"  1. Review data: rem-db info --path {db_path} --tenant test")
    print(f"  2. Run queries: python examples/run_problem_set.py")
    print(f"  3. Evaluate results: Check query type accuracy\n")


if __name__ == "__main__":
    main()
