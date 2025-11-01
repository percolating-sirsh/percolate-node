#!/usr/bin/env python3
"""Populate REM database with Percolating Plants case study data."""

import os
import sys
import yaml
from pathlib import Path
from urllib.parse import quote

# Set up environment for percolating-plants tenant
TENANT_ID = "percolating-plants"
DB_PATH = os.path.expanduser("~/.p8/percolating-plants-db")

# Set environment variables before importing rem_db
os.environ["P8_DB_PATH"] = DB_PATH
os.environ["P8_TENANT_ID"] = TENANT_ID

try:
    from rem_db import Database
except ImportError:
    print("ERROR: percolate-rocks not installed. Run 'uv sync' first.")
    sys.exit(1)


def ingest_entities(db: Database, yaml_path: Path):
    """Ingest entities from entities.yaml."""
    print(f"Ingesting entities from {yaml_path.name}...")

    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)

    count = 0

    # Insert products
    if 'products' in data:
        for product in data['products']:
            uri = f"product://{quote(product['product_code'])}"
            content = f"{product['name']} - {product['category']} - {product.get('care_level', 'N/A')} care, {product.get('light_requirement', 'N/A')} light"

            entity = {
                "name": product['name'],
                "content": content,
                "uri": uri,
                "chunk_ordinal": 0,
                **product  # Include all original fields
            }
            db.insert("resources", entity)
            count += 1

    # Insert other entity types
    for entity_type in ['suppliers', 'customers', 'employees', 'locations']:
        if entity_type in data:
            for entity_data in data[entity_type]:
                # Determine ID field
                if entity_type == 'suppliers':
                    id_field = 'supplier_id'
                    name_field = 'name'
                elif entity_type == 'customers':
                    id_field = 'customer_id'
                    name_field = 'name'
                elif entity_type == 'employees':
                    id_field = 'employee_id'
                    name_field = 'name'
                elif entity_type == 'locations':
                    id_field = 'location_id'
                    name_field = 'name'

                entity_id = entity_data.get(id_field, '')
                entity_name = entity_data.get(name_field, entity_id)
                uri = f"{entity_type}://{quote(entity_id)}"

                entity = {
                    "name": entity_name,
                    "content": str(entity_data),
                    "uri": uri,
                    "chunk_ordinal": 0,
                    **entity_data
                }
                db.insert("resources", entity)
                count += 1

    print(f"  ✓ Inserted {count} entities")
    return count


def ingest_documents(db: Database, docs_dir: Path):
    """Ingest documents from documents/ directory."""
    print(f"Ingesting documents from {docs_dir.name}/...")

    count = 0
    for doc_file in docs_dir.glob("*.md"):
        with open(doc_file, 'r') as f:
            content = f.read()

        # Use filename as URI
        uri = f"doc://{quote(doc_file.stem)}"
        name = doc_file.stem.replace('-', ' ').replace('_', ' ').title()

        entity = {
            "name": name,
            "content": content,
            "uri": uri,
            "chunk_ordinal": 0,
            "document_type": "markdown",
            "source_file": str(doc_file.name)
        }

        db.insert("resources", entity)
        count += 1

    print(f"  ✓ Inserted {count} documents")
    return count


def main():
    """Populate database with Percolating Plants data."""
    print(f"\n{'='*70}")
    print(f"Percolating Plants Case Study - Database Population")
    print(f"{'='*70}")
    print(f"Tenant ID: {TENANT_ID}")
    print(f"Database Path: {DB_PATH}")
    print(f"{'='*70}\n")

    # Initialize database
    print("Initializing REM database...")
    db = Database()
    print(f"  ✓ Database initialized (using default 'resources' schema)\n")

    # Get paths
    case_study_dir = Path(__file__).parent
    docs_dir = case_study_dir / "documents"

    # Ingest entities
    total_entities = ingest_entities(db, case_study_dir / "entities.yaml")

    # Ingest documents
    total_docs = ingest_documents(db, docs_dir)

    print(f"\n{'='*70}")
    print(f"Population Complete!")
    print(f"{'='*70}")
    print(f"Total entities ingested: {total_entities}")
    print(f"Total documents ingested: {total_docs}")
    print(f"\nDatabase ready for MCP server testing.")
    print(f"\nTo use this database with MCP server:")
    print(f"  export P8_DB_PATH={DB_PATH}")
    print(f"  export P8_TENANT_ID={TENANT_ID}")
    print(f"  percolate mcp")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
