#!/bin/bash
# Comprehensive test script for REM database queries
# Tests all query types from docs/sql-dialect.md

set -e  # Exit on error

DB_PATH="./test-db"
REM="./target/debug/rem"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

echo "=========================================="
echo "REM Database Query Test Suite"
echo "=========================================="
echo ""

# Function to run a test
run_test() {
    local test_name="$1"
    local command="$2"
    local expect_success="${3:-true}"

    TESTS_RUN=$((TESTS_RUN + 1))
    echo -n "Test $TESTS_RUN: $test_name ... "

    if eval "$command" > /tmp/rem_test_output.txt 2>&1; then
        if [ "$expect_success" = "true" ]; then
            echo -e "${GREEN}PASS${NC}"
            TESTS_PASSED=$((TESTS_PASSED + 1))
        else
            echo -e "${RED}FAIL${NC} (expected failure but succeeded)"
            TESTS_FAILED=$((TESTS_FAILED + 1))
            cat /tmp/rem_test_output.txt
        fi
    else
        if [ "$expect_success" = "false" ]; then
            echo -e "${GREEN}PASS${NC} (expected failure)"
            TESTS_PASSED=$((TESTS_PASSED + 1))
        else
            echo -e "${RED}FAIL${NC}"
            TESTS_FAILED=$((TESTS_FAILED + 1))
            cat /tmp/rem_test_output.txt
        fi
    fi
}

# Setup: Clean and rebuild
echo "Setting up test environment..."
rm -rf "$DB_PATH"
mkdir -p test-data

# Build release binary
echo "Building REM binary..."
cargo build --bin rem --no-default-features --release > /dev/null 2>&1
REM="./target/release/rem"

echo ""
echo "=========================================="
echo "Phase 1: Schema Registration"
echo "=========================================="
echo ""

run_test "Register articles schema" \
    "$REM schema add test-data/articles_schema.json"

run_test "List schemas" \
    "$REM schema list | grep -q articles"

echo ""
echo "=========================================="
echo "Phase 2: Test Data Generation & Ingestion"
echo "=========================================="
echo ""

run_test "Generate test data" \
    "python3 scripts/generate_test_data.py"

run_test "Ingest articles" \
    "$REM ingest test-data/articles.jsonl --schema articles"

run_test "Count articles" \
    "$REM count articles | grep -q '100'"

echo ""
echo "=========================================="
echo "Phase 3: Key Lookup Queries (LOOKUP)"
echo "=========================================="
echo ""

run_test "LOOKUP single key" \
    "$REM query \"LOOKUP 'Rust Tutorial 1'\""

run_test "LOOKUP multiple keys" \
    "$REM query \"LOOKUP 'Rust Tutorial 1', 'Python Tutorial 5'\""

run_test "LOOKUP with projection" \
    "$REM query \"LOOKUP 'Rust Tutorial 1' SELECT name, category\""

run_test "LOOKUP non-existent key" \
    "$REM query \"LOOKUP 'NonExistent'\""

echo ""
echo "=========================================="
echo "Phase 4: Semantic Search (SEARCH)"
echo "=========================================="
echo ""

# Note: These require embeddings to be generated
echo -e "${YELLOW}Note: Search tests require P8_DEFAULT_EMBEDDING or P8_OPENAI_API_KEY${NC}"

if [ -n "$P8_DEFAULT_EMBEDDING" ] || [ -n "$OPENAI_API_KEY" ]; then
    run_test "SEARCH basic semantic query" \
        "$REM search 'memory safety and performance' --schema articles --top-k 5"

    run_test "SEARCH with SQL filter" \
        "$REM query \"SEARCH 'async programming' IN articles WHERE category = 'rust' LIMIT 3\""

    run_test "SEARCH with ORDER BY" \
        "$REM query \"SEARCH 'machine learning' IN articles ORDER BY rating DESC LIMIT 5\""

    run_test "SEARCH with multiple filters" \
        "$REM query \"SEARCH 'database optimization' IN articles WHERE category IN ('database', 'rust') AND rating >= 4.0\""
else
    echo -e "${YELLOW}Skipping search tests (no embedding provider configured)${NC}"
fi

echo ""
echo "=========================================="
echo "Phase 5: Standard SQL Queries"
echo "=========================================="
echo ""

run_test "SELECT all articles" \
    "$REM query \"SELECT * FROM articles LIMIT 5\""

run_test "SELECT with WHERE clause" \
    "$REM query \"SELECT name, author FROM articles WHERE category = 'rust'\""

run_test "SELECT with IN clause" \
    "$REM query \"SELECT name, category FROM articles WHERE author IN ('alice', 'bob')\""

run_test "SELECT with comparison operators" \
    "$REM query \"SELECT name, views FROM articles WHERE views >= 5000\""

run_test "SELECT with ORDER BY" \
    "$REM query \"SELECT name, rating FROM articles ORDER BY rating DESC LIMIT 10\""

run_test "SELECT with multiple conditions" \
    "$REM query \"SELECT name, author, rating FROM articles WHERE category = 'python' AND rating > 3.5 ORDER BY views DESC\""

run_test "SELECT with LIMIT and OFFSET" \
    "$REM query \"SELECT name FROM articles LIMIT 10 OFFSET 20\""

echo ""
echo "=========================================="
echo "Phase 6: Natural Language Queries (ask)"
echo "=========================================="
echo ""

if [ -n "$OPENAI_API_KEY" ] || [ -n "$ANTHROPIC_API_KEY" ]; then
    run_test "Ask about Rust tutorials" \
        "$REM ask 'Find articles about Rust performance'"

    run_test "Ask with --plan flag" \
        "$REM ask 'Show me Python tutorials by Alice' --plan | grep -q 'Query Plan'"

    run_test "Ask for top rated articles" \
        "$REM ask 'What are the highest rated database articles?'"

    run_test "Ask with complex intent" \
        "$REM ask 'Find recent articles about async programming with good ratings'"
else
    echo -e "${YELLOW}Skipping NL query tests (no LLM API key configured)${NC}"
fi

echo ""
echo "=========================================="
echo "Phase 7: Edge Cases and Error Handling"
echo "=========================================="
echo ""

run_test "Query non-existent schema" \
    "$REM query \"SELECT * FROM nonexistent\"" \
    "false"

run_test "Invalid SQL syntax" \
    "$REM query \"SELECT WHERE FROM\"" \
    "false"

run_test "Empty LOOKUP" \
    "$REM query \"LOOKUP\"" \
    "false"

run_test "SEARCH without schema" \
    "$REM query \"SEARCH 'test'\"" \
    "false"

echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo ""
echo "Total tests run:    $TESTS_RUN"
echo -e "Tests passed:       ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests failed:       ${RED}$TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed.${NC}"
    exit 1
fi
