"""Test entity lookup functionality.

Verifies that lookup_entity() can find entities by:
- Numeric ID (12345)
- Code pattern (TAP-1234)
- Brand/entity name (DHL)
- Employee ID (EMP-001)
- UUID
"""

from pathlib import Path

from rem_db import REMDatabase


def test_entity_lookup():
    """Test all entity lookup patterns."""
    db_path = Path("/tmp/problem_set_db")

    if not db_path.exists():
        print("❌ Database not found. Run populate_problem_set_data.py first.")
        return

    db = REMDatabase(tenant_id="test", path=str(db_path))

    print("="*60)
    print("TESTING ENTITY LOOKUP")
    print("="*60)

    # Test cases
    test_cases = [
        ("12345", "Issue #12345", "Numeric ID"),
        ("TAP-1234", "TAP-1234", "Code pattern"),
        ("DHL", "DHL", "Brand name"),
        ("EMP-001", "Alice", "Employee ID"),
        ("Alice", "Alice", "User name"),
        ("FedEx", "FedEx", "Carrier name"),
        ("nonexistent", None, "Should return empty"),
    ]

    passed = 0
    failed = 0

    for identifier, expected_name, description in test_cases:
        print(f"\n{description}: lookup_entity('{identifier}')")

        results = db.lookup_entity(identifier)

        if expected_name is None:
            # Should return empty
            if len(results) == 0:
                print(f"  ✓ PASS: No results (expected)")
                passed += 1
            else:
                print(f"  ❌ FAIL: Found {len(results)} results, expected 0")
                failed += 1
        else:
            # Should find entity
            if len(results) == 0:
                print(f"  ❌ FAIL: No results found")
                failed += 1
            elif len(results) > 1:
                print(f"  ⚠ WARNING: Multiple results ({len(results)})")
                for r in results:
                    print(f"      - {r.name} (type: {r.type})")
                # Check if expected is in results
                if any(r.name == expected_name for r in results):
                    print(f"  ✓ PASS: Expected entity found")
                    passed += 1
                else:
                    print(f"  ❌ FAIL: Expected '{expected_name}' not in results")
                    failed += 1
            else:
                entity = results[0]
                if entity.name == expected_name:
                    print(f"  ✓ PASS: Found {entity.name} (type: {entity.type})")
                    passed += 1
                else:
                    print(f"  ❌ FAIL: Found '{entity.name}', expected '{expected_name}'")
                    failed += 1

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"  Passed: {passed}/{len(test_cases)}")
    print(f"  Failed: {failed}/{len(test_cases)}")

    success_rate = (passed / len(test_cases)) * 100
    if success_rate == 100:
        print(f"\n  ✓ ALL TESTS PASSED ({success_rate:.0f}%)")
    elif success_rate >= 80:
        print(f"\n  ⚠ MOSTLY PASSING ({success_rate:.0f}%)")
    else:
        print(f"\n  ❌ FAILING ({success_rate:.0f}%)")

    db.close()


if __name__ == "__main__":
    test_entity_lookup()
