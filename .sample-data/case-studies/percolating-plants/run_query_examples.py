#!/usr/bin/env python3
"""Run 5 example queries and output plan + results as JSON."""

import os
import sys
import json
from pathlib import Path

# Set up environment
TENANT_ID = "percolating-plants"
DB_PATH = os.path.expanduser("~/.p8/percolating-plants-db")

os.environ["P8_DB_PATH"] = DB_PATH
os.environ["P8_TENANT_ID"] = TENANT_ID

try:
    from rem_db import Database
except ImportError:
    print(json.dumps({"error": "rem_db not available"}))
    sys.exit(1)


# 5 test queries
QUERIES = [
    {
        "id": 1,
        "natural_language": "product PP-1001-SM",
        "description": "Exact product code lookup",
        "schema": None
    },
    {
        "id": 2,
        "natural_language": "Monstera Deliciosa",
        "description": "Product name lookup",
        "schema": None
    },
    {
        "id": 3,
        "natural_language": "supplier SUP-001",
        "description": "Supplier ID lookup",
        "schema": None
    },
    {
        "id": 4,
        "natural_language": "Les Jardins de Provence",
        "description": "Supplier name lookup",
        "schema": None
    },
    {
        "id": 5,
        "natural_language": "all plants in stock",
        "description": "SQL query for all plants",
        "schema": "resources"
    },
]


def run_query_example(db: Database, query_def: dict) -> dict:
    """Run a single query and capture plan + results."""

    result = {
        "id": query_def["id"],
        "query": query_def["natural_language"],
        "description": query_def["description"],
        "plan": None,
        "execution": None,
        "error": None
    }

    try:
        # Step 1: Generate plan
        plan = db.plan_query(
            query_def["natural_language"],
            query_def["schema"]
        )
        result["plan"] = plan

        # Step 2: Execute query
        # Use ask() with execute=True to get results
        try:
            execution_result = db.ask(
                query_def["natural_language"],
                execute=True,
                schema_hint=query_def["schema"]
            )
            result["execution"] = execution_result
        except Exception as e:
            result["execution"] = {
                "error": str(e),
                "note": "Query plan succeeded but execution failed"
            }

    except Exception as e:
        result["error"] = str(e)

    return result


def main():
    """Run all queries and output JSON."""
    db = Database()

    output = {
        "database": DB_PATH,
        "tenant": TENANT_ID,
        "timestamp": "2025-11-01T17:50:00Z",
        "queries": []
    }

    for query_def in QUERIES:
        result = run_query_example(db, query_def)
        output["queries"].append(result)

    # Pretty print JSON
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
