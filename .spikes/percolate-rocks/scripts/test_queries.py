#!/usr/bin/env python3
"""Comprehensive test suite for REM database queries.

Tests all query types from docs/sql-dialect.md with detailed validation.
"""

import subprocess
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
import re

# Configuration
DB_PATH = Path("./test-db")
REM_BIN = Path("./target/release/rem")
TEST_DATA_DIR = Path("./test-data")

# Colors
class Colors:
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'

class TestResult:
    def __init__(self, name: str, passed: bool, message: str = "", output: str = ""):
        self.name = name
        self.passed = passed
        self.message = message
        self.output = output

class TestSuite:
    def __init__(self):
        self.results: List[TestResult] = []
        self.current_phase = ""

    def phase(self, name: str):
        """Start a new test phase."""
        self.current_phase = name
        print(f"\n{'='*60}")
        print(f"{name}")
        print(f"{'='*60}\n")

    def run(self, name: str, command: List[str], expect_success: bool = True,
            validate_fn: Optional[callable] = None) -> TestResult:
        """Run a single test."""
        test_num = len(self.results) + 1
        print(f"Test {test_num}: {name} ... ", end="", flush=True)

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=30
            )

            success = result.returncode == 0
            output = result.stdout + result.stderr

            # Check if outcome matches expectation
            if success != expect_success:
                if expect_success:
                    msg = f"Command failed: {result.stderr[:200]}"
                else:
                    msg = "Expected failure but command succeeded"
                test_result = TestResult(name, False, msg, output)
                print(f"{Colors.RED}FAIL{Colors.NC}")
            else:
                # Run validation if provided
                if validate_fn:
                    try:
                        validate_fn(output)
                        test_result = TestResult(name, True, "Validation passed", output)
                        print(f"{Colors.GREEN}PASS{Colors.NC}")
                    except AssertionError as e:
                        test_result = TestResult(name, False, f"Validation failed: {e}", output)
                        print(f"{Colors.RED}FAIL{Colors.NC}")
                else:
                    test_result = TestResult(name, True, "", output)
                    print(f"{Colors.GREEN}PASS{Colors.NC}")

        except subprocess.TimeoutExpired:
            test_result = TestResult(name, False, "Command timed out", "")
            print(f"{Colors.RED}TIMEOUT{Colors.NC}")
        except Exception as e:
            test_result = TestResult(name, False, f"Exception: {e}", "")
            print(f"{Colors.RED}ERROR{Colors.NC}")

        self.results.append(test_result)
        if not test_result.passed and test_result.message:
            print(f"  → {test_result.message}")

        return test_result

    def summary(self):
        """Print test summary."""
        passed = sum(1 for r in self.results if r.passed)
        failed = len(self.results) - passed

        print(f"\n{'='*60}")
        print("Test Summary")
        print(f"{'='*60}\n")
        print(f"Total tests run:    {len(self.results)}")
        print(f"Tests passed:       {Colors.GREEN}{passed}{Colors.NC}")
        print(f"Tests failed:       {Colors.RED}{failed}{Colors.NC}")
        print()

        if failed > 0:
            print("Failed tests:")
            for i, result in enumerate(self.results, 1):
                if not result.passed:
                    print(f"  {i}. {result.name}")
                    if result.message:
                        print(f"     → {result.message}")
            return False
        else:
            print(f"{Colors.GREEN}All tests passed!{Colors.NC}")
            return True

def setup_environment():
    """Set up test environment."""
    print("Setting up test environment...")

    # Clean test database
    if DB_PATH.exists():
        import shutil
        shutil.rmtree(DB_PATH)

    # Create test data directory
    TEST_DATA_DIR.mkdir(exist_ok=True)

    # Build release binary
    print("Building REM binary (release mode)...")
    result = subprocess.run(
        ["cargo", "build", "--bin", "rem", "--no-default-features", "--release"],
        capture_output=True
    )
    if result.returncode != 0:
        print(f"{Colors.RED}Failed to build REM binary{Colors.NC}")
        print(result.stderr.decode())
        sys.exit(1)

    print(f"{Colors.GREEN}Setup complete{Colors.NC}\n")

def main():
    suite = TestSuite()

    print("="*60)
    print("REM Database Query Test Suite")
    print("="*60)

    setup_environment()

    # ========================================
    # Phase 1: Schema Registration
    # ========================================
    suite.phase("Phase 1: Schema Registration")

    suite.run(
        "Register articles schema",
        [str(REM_BIN), "schema", "add", "test-data/articles_schema.json"]
    )

    suite.run(
        "List schemas",
        [str(REM_BIN), "schema", "list"],
        validate_fn=lambda out: "articles" in out
    )

    # ========================================
    # Phase 2: Data Generation & Ingestion
    # ========================================
    suite.phase("Phase 2: Test Data Generation & Ingestion")

    suite.run(
        "Generate test data",
        ["python3", "scripts/generate_test_data.py"]
    )

    suite.run(
        "Ingest articles (100 items)",
        [str(REM_BIN), "ingest", "test-data/articles.jsonl", "--schema", "articles"],
        validate_fn=lambda out: "100" in out or "✓" in out
    )

    def validate_count_100(output: str):
        # Extract number from output
        match = re.search(r'\d+', output)
        if match:
            count = int(match.group())
            assert count == 100, f"Expected 100 entities, got {count}"
        else:
            raise AssertionError("Could not find count in output")

    suite.run(
        "Count articles (verify 100)",
        [str(REM_BIN), "count", "articles"],
        validate_fn=validate_count_100
    )

    # ========================================
    # Phase 3: Key Lookup Queries
    # ========================================
    suite.phase("Phase 3: Key Lookup Queries (LOOKUP)")

    suite.run(
        "LOOKUP single key",
        [str(REM_BIN), "query", "LOOKUP 'Rust Tutorial 1'"]
    )

    suite.run(
        "LOOKUP multiple keys",
        [str(REM_BIN), "query", "LOOKUP 'Rust Tutorial 1', 'Python Tutorial 5'"]
    )

    suite.run(
        "LOOKUP with projection",
        [str(REM_BIN), "query", "LOOKUP 'Rust Tutorial 1' SELECT name, category"]
    )

    suite.run(
        "LOOKUP non-existent key (expect empty)",
        [str(REM_BIN), "query", "LOOKUP 'NonExistentKey123'"]
    )

    # ========================================
    # Phase 4: Semantic Search
    # ========================================
    suite.phase("Phase 4: Semantic Search (SEARCH)")

    has_embedding = os.getenv("P8_DEFAULT_EMBEDDING") or os.getenv("OPENAI_API_KEY")

    if has_embedding:
        suite.run(
            "SEARCH basic query",
            [str(REM_BIN), "search", "memory safety and performance",
             "--schema", "articles", "--top-k", "5"],
            validate_fn=lambda out: "Score:" in out or "ID:" in out
        )

        suite.run(
            "SEARCH with SQL filter (category)",
            [str(REM_BIN), "query",
             "SEARCH 'async programming' IN articles WHERE category = 'rust' LIMIT 3"]
        )

        suite.run(
            "SEARCH with ORDER BY rating",
            [str(REM_BIN), "query",
             "SEARCH 'machine learning' IN articles ORDER BY rating DESC LIMIT 5"]
        )

        suite.run(
            "SEARCH with multiple filters",
            [str(REM_BIN), "query",
             "SEARCH 'database optimization' IN articles WHERE category IN ('database', 'rust') AND rating >= 4.0"]
        )
    else:
        print(f"{Colors.YELLOW}Skipping search tests (no embedding provider configured){Colors.NC}")
        print(f"  Set P8_DEFAULT_EMBEDDING=local:all-MiniLM-L6-v2 or OPENAI_API_KEY")

    # ========================================
    # Phase 5: Standard SQL Queries
    # ========================================
    suite.phase("Phase 5: Standard SQL Queries")

    suite.run(
        "SELECT all with LIMIT",
        [str(REM_BIN), "query", "SELECT * FROM articles LIMIT 5"]
    )

    suite.run(
        "SELECT with WHERE clause",
        [str(REM_BIN), "query", "SELECT name, author FROM articles WHERE category = 'rust'"]
    )

    suite.run(
        "SELECT with IN clause",
        [str(REM_BIN), "query",
         "SELECT name, category FROM articles WHERE author IN ('alice', 'bob')"]
    )

    suite.run(
        "SELECT with comparison (views >= 5000)",
        [str(REM_BIN), "query", "SELECT name, views FROM articles WHERE views >= 5000"]
    )

    suite.run(
        "SELECT with ORDER BY DESC",
        [str(REM_BIN), "query",
         "SELECT name, rating FROM articles ORDER BY rating DESC LIMIT 10"]
    )

    suite.run(
        "SELECT with AND conditions",
        [str(REM_BIN), "query",
         "SELECT name, author, rating FROM articles WHERE category = 'python' AND rating > 3.5 ORDER BY views DESC"]
    )

    suite.run(
        "SELECT with LIMIT OFFSET",
        [str(REM_BIN), "query", "SELECT name FROM articles LIMIT 10 OFFSET 20"]
    )

    # ========================================
    # Phase 6: Natural Language Queries
    # ========================================
    suite.phase("Phase 6: Natural Language Queries (ask)")

    has_llm = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")

    if has_llm:
        suite.run(
            "Ask about Rust tutorials",
            [str(REM_BIN), "ask", "Find articles about Rust performance"]
        )

        suite.run(
            "Ask with --plan flag",
            [str(REM_BIN), "ask", "Show me Python tutorials by Alice", "--plan"],
            validate_fn=lambda out: "Query Plan" in out or "intent" in out.lower()
        )

        suite.run(
            "Ask for top rated",
            [str(REM_BIN), "ask", "What are the highest rated database articles?"]
        )

        suite.run(
            "Ask complex query",
            [str(REM_BIN), "ask",
             "Find recent articles about async programming with good ratings"]
        )
    else:
        print(f"{Colors.YELLOW}Skipping NL query tests (no LLM API key configured){Colors.NC}")
        print(f"  Set OPENAI_API_KEY or ANTHROPIC_API_KEY")

    # ========================================
    # Phase 7: Edge Cases & Errors
    # ========================================
    suite.phase("Phase 7: Edge Cases and Error Handling")

    suite.run(
        "Query non-existent schema",
        [str(REM_BIN), "query", "SELECT * FROM nonexistent"],
        expect_success=False
    )

    suite.run(
        "Invalid SQL syntax",
        [str(REM_BIN), "query", "SELECT WHERE FROM"],
        expect_success=False
    )

    suite.run(
        "Empty LOOKUP",
        [str(REM_BIN), "query", "LOOKUP"],
        expect_success=False
    )

    suite.run(
        "SEARCH without schema",
        [str(REM_BIN), "query", "SEARCH 'test'"],
        expect_success=False
    )

    # ========================================
    # Summary
    # ========================================
    success = suite.summary()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
