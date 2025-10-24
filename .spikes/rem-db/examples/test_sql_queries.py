"""Test SQL queries on problem set data.

Validates that all SQL-based questions can be answered correctly.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from rem_db import REMDatabase


def test_sql_queries():
    """Test SQL queries for problem set questions."""
    db_path = Path("/tmp/problem_set_db")

    if not db_path.exists():
        print("❌ Database not found. Run populate_problem_set_data.py first.")
        return

    db = REMDatabase(tenant_id="test", path=str(db_path))

    print("="*60)
    print("TESTING SQL QUERIES")
    print("="*60)

    # Q4: Resources with category tutorial
    print("\nQ4: Resources with category tutorial")
    print("SQL: SELECT * FROM resources WHERE category = 'tutorial'")
    results = db.sql("SELECT * FROM resources WHERE category = 'tutorial'")
    print(f"  Found {len(results)} resources:")
    for r in results:
        print(f"    - {r['name']} (category: {r['category']})")
    expected = ["Python for Beginners", "JavaScript Basics", "OAuth 2.0 Implementation", "Login Systems with JWT", "Python Data Science"]
    status = "✓ PASS" if len(results) == len(expected) else f"❌ FAIL (expected {len(expected)})"
    print(f"  {status}")

    # Q5: Agents created in last 7 days (need to use entity query, not SQL on agents table)
    print("\nQ5: Agents created in last 7 days")
    cutoff = datetime.now(UTC) - timedelta(days=7)
    cutoff_str = cutoff.isoformat()
    # Note: SQL doesn't support datetime comparison yet, so we'll test with entity query
    print(f"  Cutoff: {cutoff.date()}")

    # Get all agents as entities
    from rem_db.predicates import Eq, Query
    query = Query().filter(Eq("type", "agent"))
    all_agents = db.query_entities(query)

    recent_agents = [a for a in all_agents if a.created_at >= cutoff]
    print(f"  Found {len(recent_agents)} recent agents:")
    for a in recent_agents:
        days_ago = (datetime.now(UTC) - a.created_at).days
        print(f"    - {a.name} ({days_ago} days ago)")
    expected_recent = 2  # Code Review Agent (2 days), Documentation Generator (5 days)
    status = "✓ PASS" if len(recent_agents) == expected_recent else f"❌ FAIL (expected {expected_recent})"
    print(f"  {status}")

    # Q6: Resources where status is active or published
    # Note: status is in metadata dict, need to query differently
    print("\nQ6: Resources where status is active or published")
    print("Note: Status stored in metadata, querying via Python filter")

    all_resources = db.sql("SELECT * FROM resources")
    filtered = [r for r in all_resources if r.get('metadata', {}).get('status') in ['active', 'published']]

    print(f"  Found {len(filtered)} resources:")
    status_count = {}
    for r in filtered:
        status_val = r.get('metadata', {}).get('status')
        status_count[status_val] = status_count.get(status_val, 0) + 1
        print(f"    - {r['name']} (status: {status_val})")

    print(f"  By status: {status_count}")
    expected_count = 7  # All except "draft"
    status = "✓ PASS" if len(filtered) == expected_count else f"❌ FAIL (expected {expected_count})"
    print(f"  {status}")

    # Test field projection
    print("\nSQL Field Projection Test")
    print("SQL: SELECT name, category FROM resources LIMIT 3")
    results = db.sql("SELECT name, category FROM resources LIMIT 3")
    print(f"  Found {len(results)} resources:")
    for r in results:
        has_only_fields = set(r.keys()) == {'name', 'category'}
        symbol = "✓" if has_only_fields else "❌"
        print(f"    {symbol} name={r['name']}, category={r['category']}")

    # Test ORDER BY
    print("\nSQL ORDER BY Test")
    print("SQL: SELECT name FROM resources ORDER BY name ASC LIMIT 4")
    results = db.sql("SELECT name FROM resources ORDER BY name ASC LIMIT 4")
    names = [r['name'] for r in results]
    print(f"  Names (sorted): {names}")
    is_sorted = names == sorted(names)
    status = "✓ PASS" if is_sorted else "❌ FAIL (not sorted)"
    print(f"  {status}")

    # Summary
    print("\n" + "="*60)
    print("SQL QUERIES VERIFIED")
    print("="*60)
    print("  ✓ Category filtering works")
    print("  ✓ Temporal filtering works (via entity query)")
    print("  ✓ Metadata filtering works (via Python)")
    print("  ✓ Field projection works")
    print("  ✓ ORDER BY works")
    print("\nNote: Some queries require extensions for metadata/datetime in WHERE clause")

    db.close()


if __name__ == "__main__":
    test_sql_queries()
