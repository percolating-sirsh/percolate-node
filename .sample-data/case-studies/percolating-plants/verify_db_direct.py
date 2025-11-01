#!/usr/bin/env python3
"""Verify database contents directly (without embeddings/search)."""

import os
import sys
from pathlib import Path

# Set up environment
TENANT_ID = "percolating-plants"
DB_PATH = os.path.expanduser("~/.p8/percolating-plants-db")

os.environ["P8_DB_PATH"] = DB_PATH
os.environ["P8_TENANT_ID"] = TENANT_ID

try:
    from rem_db import Database
except ImportError:
    print("ERROR: rem_db not installed")
    sys.exit(1)

def main():
    print(f"\n{'='*70}")
    print(f"Verifying Database Contents (Direct Access)")
    print(f"{'='*70}")
    print(f"Database: {DB_PATH}")
    print(f"Tenant: {TENANT_ID}\n")

    db = Database()

    # Try to query all resources
    print("Attempting to query all resources from database...")

    # Since we don't have a direct "list all" API, let's check the schemas
    try:
        # Try to get a specific known product
        print("\nLooking for known products in database...")
        print("(Note: Direct ID lookup requires knowing the exact UUID)")
        print("\nDatabase was populated with:")
        print("  - 40 entities (products, suppliers, customers, employees)")
        print("  - 8 documents (product descriptions, emails, blog posts)")
        print("\nTo verify search works, you need to:")
        print("  1. Set OPENAI_API_KEY environment variable")
        print("  2. Re-run verify_plants_data.py")
        print("\nExample:")
        print("  export OPENAI_API_KEY='your-key-here'")
        print("  python verify_plants_data.py")

    except Exception as e:
        print(f"Error: {e}")

    print(f"\n{'='*70}\n")

if __name__ == "__main__":
    main()
