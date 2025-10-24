#!/bin/bash
# Test complete user flow with new CLI pattern

set -e

REM_DB="../percolate-rocks/target/release/rem-db"

echo "======================================================================"
echo "Testing Complete REM Database Flow (New CLI Pattern)"
echo "======================================================================"
echo

# Clean up previous test databases
rm -rf ~/.p8/db/demo-local ~/.p8/db/demo-openai ~/.p8/config.json

# Test 1: Default (Local) Embeddings
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 1: Default Flow (Local Embeddings)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo

# Step 1: Init with database name
echo "→ Step 1: Initialize database 'demo-local' (uses ~/.p8/db/demo-local)"
$REM_DB init demo-local
echo

# Step 2: List all databases
echo "→ Step 2: List all databases"
$REM_DB list
echo

# Step 3: Query (SQL)
echo "→ Step 3: Query with SQL"
$REM_DB query -d demo-local "SELECT * FROM resources"
echo

# Step 4: Search (Natural Language)
echo "→ Step 4: Search with natural language (semantic)"
$REM_DB search -d demo-local "vector embeddings database" --min-score 0.3
echo

# Step 5: List schemas
echo "→ Step 5: List schemas"
$REM_DB schemas -d demo-local
echo

echo "✅ Test 1 Complete: Local embeddings working with new CLI!"
echo

# Test 2: OpenAI Embeddings (only if API key is set)
if [ -n "$OPENAI_API_KEY" ]; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Test 2: OpenAI Flow"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo

    # Set OpenAI embedding
    export P8_DEFAULT_EMBEDDING="text-embedding-3-small"
    echo "→ Using: $P8_DEFAULT_EMBEDDING"
    echo

    # Step 1: Init
    echo "→ Step 1: Initialize database 'demo-openai' with OpenAI embeddings"
    $REM_DB init demo-openai
    echo

    # Step 2: List all databases
    echo "→ Step 2: List all databases"
    $REM_DB list
    echo

    # Step 3: Query (SQL)
    echo "→ Step 3: Query with SQL"
    $REM_DB query -d demo-openai "SELECT * FROM resources"
    echo

    # Step 4: Search (Natural Language)
    echo "→ Step 4: Search with natural language (semantic)"
    $REM_DB search -d demo-openai "vector embeddings database" --min-score 0.3
    echo

    # Step 5: List schemas
    echo "→ Step 5: List schemas"
    $REM_DB schemas -d demo-openai
    echo

    echo "✅ Test 2 Complete: OpenAI embeddings working with new CLI!"
else
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Test 2: Skipped (OPENAI_API_KEY not set)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
    echo "To test OpenAI embeddings, run:"
    echo "  export OPENAI_API_KEY='sk-...'"
    echo "  export P8_DEFAULT_EMBEDDING='text-embedding-3-small'"
    echo "  ./test_complete_flow.sh"
fi

echo
echo "======================================================================"
echo "✅ All Tests Complete!"
echo "======================================================================"
echo
echo "New CLI Pattern Summary:"
echo "  • rem-db init <name>          - Create database at ~/.p8/db/<name>"
echo "  • rem-db list                 - List all databases"
echo "  • rem-db query -d <name> ...  - Query database by name"
echo "  • rem-db search -d <name> ... - Search database by name"
echo "  • rem-db schemas -d <name>    - List schemas in database"
echo
echo "Benefits:"
echo "  ✓ No --path or --tenant arguments needed"
echo "  ✓ Database names instead of paths"
echo "  ✓ Centralized config at ~/.p8/config.json"
echo "  ✓ Default storage at ~/.p8/db/"
echo
echo "Embedding providers tested:"
echo "  ✓ Local (all-MiniLM-L6-v2, 384 dims)"
if [ -n "$OPENAI_API_KEY" ]; then
    echo "  ✓ OpenAI (text-embedding-3-small, 1536 dims)"
else
    echo "  ⊘ OpenAI (skipped - no API key)"
fi
