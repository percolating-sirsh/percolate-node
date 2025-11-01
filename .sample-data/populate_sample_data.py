#!/usr/bin/env python3
"""Populate REM database with ACME Alpha case study data."""

import os
import sys
import csv
import json
import yaml
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from urllib.parse import quote

# Set up environment for acme-alpha tenant
TENANT_ID = "felix-prime"
DB_PATH = os.path.expanduser("~/.p8/acme-alpha-db")

# Set environment variables before importing rem_db
os.environ["P8_DB_PATH"] = DB_PATH
os.environ["P8_TENANT_ID"] = TENANT_ID

try:
    from rem_db import Database
except ImportError:
    print("ERROR: percolate-rocks not installed. Run 'uv sync' first.")
    sys.exit(1)


def parse_quarter_date(quarter_str: str) -> datetime:
    """Convert 'YYYY-QN' to last day of quarter."""
    year, quarter = quarter_str.split("-Q")
    quarter_num = int(quarter)
    month = quarter_num * 3

    # Last day of each quarter
    if month == 3:
        return datetime(int(year), 3, 31)
    elif month == 6:
        return datetime(int(year), 6, 30)
    elif month == 9:
        return datetime(int(year), 9, 30)
    else:  # month == 12
        return datetime(int(year), 12, 31)


def ingest_ncreif_benchmarks(db: Database, csv_path: Path):
    """Ingest NCREIF property benchmarks."""
    print(f"Ingesting NCREIF property benchmarks from {csv_path.name}...")

    count = 0
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = parse_quarter_date(row['quarter'])
            property_type = row['property_type']

            # Insert each metric as a separate trend
            metrics = {
                'total_return_pct': row['total_return_pct'],
                'income_return_pct': row['income_return_pct'],
                'appreciation_return_pct': row['appreciation_return_pct'],
                'cap_rate_pct': row['cap_rate_pct'],
                'occupancy_pct': row['occupancy_pct'],
                'noi_growth_pct': row['noi_growth_pct'],
            }

            for key, value in metrics.items():
                # Resources schema required fields (URL-encode spaces)
                property_type_safe = property_type.replace(' ', '-')
                uri = f"ncreif://{property_type_safe}/{key}/{row['quarter']}"
                name = f"NCREIF {property_type} {key} ({row['quarter']})"
                content = f"{property_type} {key}: {value}% for {row['quarter']}"

                entity = {
                    "name": name,
                    "content": content,
                    "uri": uri,
                    "chunk_ordinal": 0,
                    # Additional metadata
                    "category": "property_benchmark",
                    "sub_category": property_type,
                    "key": key,
                    "date": date.strftime("%Y-%m-%d"),
                    "period_type": "quarter",
                    "value": float(value),
                    "value_unit": "percent",
                    "source": "NCREIF",
                }

                # Insert as resource (uses default schema)
                db.insert("resources", entity)
                count += 1

    print(f"  ✓ Inserted {count} NCREIF data points")
    return count


def ingest_cbsa_metrics(db: Database, csv_path: Path):
    """Ingest CBSA market metrics."""
    print(f"Ingesting CBSA market metrics from {csv_path.name}...")

    count = 0
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = parse_quarter_date(row['quarter'])
            cbsa_code = f"CBSA-{row['cbsa_code']}"

            metrics = {
                'population_thousands': row['population_thousands'],
                'population_growth_yoy_pct': row['population_growth_yoy_pct'],
                'employment_thousands': row['employment_thousands'],
                'employment_growth_yoy_pct': row['employment_growth_yoy_pct'],
                'unemployment_rate_pct': row['unemployment_rate_pct'],
                'median_household_income': row['median_household_income'],
                'gdp_billions': row['gdp_billions'],
                'gdp_growth_yoy_pct': row['gdp_growth_yoy_pct'],
            }

            for key, value in metrics.items():
                uri = f"cbsa://{cbsa_code}/{key}/{row['quarter']}"
                name = f"CBSA {cbsa_code} {key} ({row['quarter']})"
                content = f"{row['cbsa_name']} {key}: {value} for {row['quarter']}"

                entity = {
                    "name": name,
                    "content": content,
                    "uri": uri,
                    "chunk_ordinal": 0,
                    # Additional metadata
                    "category": "market_metric",
                    "sub_category": cbsa_code,
                    "key": key,
                    "date": date.strftime("%Y-%m-%d"),
                    "period_type": "quarter",
                    "value": float(value),
                    "source": "US Census Bureau",
                    "metadata": {
                        "cbsa_name": row['cbsa_name']
                    }
                }

                db.insert("resources", entity)
                count += 1

    print(f"  ✓ Inserted {count} CBSA data points")
    return count


def ingest_energy_ppa_rates(db: Database, csv_path: Path):
    """Ingest energy market PPA rates."""
    print(f"Ingesting energy PPA rates from {csv_path.name}...")

    count = 0
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = parse_quarter_date(row['quarter'])
            market = row['market']

            metrics = {
                'ppa_rate_usd_mwh': row['ppa_rate_usd_mwh'],
                'capacity_factor_pct': row['capacity_factor_pct'],
                'merchant_exposure_pct': row['merchant_exposure_pct'],
                'avg_project_size_mw': row['avg_project_size_mw'],
                'curtailment_rate_pct': row['curtailment_rate_pct'],
            }

            for key, value in metrics.items():
                uri = f"energy://{market}/{key}/{row['quarter']}"
                name = f"Energy {market} {key} ({row['quarter']})"
                content = f"{row['technology']} in {market}: {key} = {value} for {row['quarter']}"

                entity = {
                    "name": name,
                    "content": content,
                    "uri": uri,
                    "chunk_ordinal": 0,
                    # Additional metadata
                    "category": "energy_price",
                    "sub_category": market,
                    "key": key,
                    "date": date.strftime("%Y-%m-%d"),
                    "period_type": "quarter",
                    "value": float(value),
                    "source": "Market Data",
                    "metadata": {
                        "technology": row['technology']
                    }
                }

                db.insert("resources", entity)
                count += 1

    print(f"  ✓ Inserted {count} energy data points")
    return count


def ingest_financial_rates(db: Database, csv_path: Path):
    """Ingest financial market rates."""
    print(f"Ingesting financial rates from {csv_path.name}...")

    count = 0
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Parse month (YYYY-MM format)
            date = datetime.strptime(row['month'], "%Y-%m")
            instrument = row['instrument']

            metrics = {}
            for col_name, value in row.items():
                # Skip month/instrument columns and empty values
                if col_name not in ['month', 'instrument']:
                    # Skip if value is not a string or is empty
                    if isinstance(value, str) and value.strip():
                        try:
                            # Validate it's a number
                            float(value)
                            metrics[col_name] = value
                        except ValueError:
                            # Skip non-numeric values
                            pass

            for key, value in metrics.items():
                uri = f"rates://{instrument}/{key}/{row['month']}"
                name = f"Rates {instrument} {key} ({row['month']})"
                content = f"{instrument} {key}: {value}% for {row['month']}"

                entity = {
                    "name": name,
                    "content": content,
                    "uri": uri,
                    "chunk_ordinal": 0,
                    # Additional metadata
                    "category": "interest_rate",
                    "sub_category": instrument,
                    "key": key,
                    "date": date.strftime("%Y-%m-%d"),
                    "period_type": "monthly",
                    "value": float(value),
                    "value_unit": "percent",
                    "source": "Market Data",
                }

                db.insert("resources", entity)
                count += 1

    print(f"  ✓ Inserted {count} financial data points")
    return count


def ingest_entities(db: Database, yaml_path: Path):
    """Ingest entities from entities.yaml."""
    print(f"Ingesting entities from {yaml_path.name}...")

    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)

    count = 0

    # Insert analysts
    if 'analysts' in data:
        for analyst in data['analysts']:
            # Clean ID for URI (remove prefix)
            analyst_id = analyst['analyst_id'].replace('analyst:', '').replace(':', '-')
            entity = {
                "name": analyst['name'],
                "content": f"{analyst['name']} - {analyst.get('title', '')} at {analyst.get('firm', '')}",
                "uri": f"analyst://{analyst_id}",
                "chunk_ordinal": 0,
                **analyst  # Include all original fields
            }
            db.insert("resources", entity)
            count += 1

    # Insert sponsors
    if 'sponsors' in data:
        for sponsor in data['sponsors']:
            # Clean ID for URI (remove prefix)
            sponsor_id = sponsor['sponsor_id'].replace('sponsor:', '').replace(':', '-')
            entity = {
                "name": sponsor['name'],
                "content": f"{sponsor['name']} - {sponsor.get('track_record', '')}",
                "uri": f"sponsor://{sponsor_id}",
                "chunk_ordinal": 0,
                **sponsor  # Include all original fields
            }
            db.insert("resources", entity)
            count += 1

    # Insert other entity types
    for entity_type in ['lenders', 'markets', 'properties', 'deals']:
        if entity_type in data:
            for entity_data in data[entity_type]:
                # Get name from the entity or use ID
                entity_name = entity_data.get('name', entity_data.get(f'{entity_type.rstrip("s")}_id', 'Unknown'))
                entity_id_field = f'{entity_type.rstrip("s")}_id'
                entity_id = entity_data.get(entity_id_field, entity_name)
                # Clean ID for URI (remove prefix, URL-encode)
                entity_id_clean = str(entity_id).replace(f'{entity_type.rstrip("s")}:', '').replace(':', '-')
                entity_id_encoded = quote(entity_id_clean, safe='')

                entity = {
                    "name": entity_name,
                    "content": str(entity_data),  # Simple string representation
                    "uri": f"{entity_type}://{entity_id_encoded}",
                    "chunk_ordinal": 0,
                    **entity_data  # Include all original fields
                }
                db.insert("resources", entity)
                count += 1

    print(f"  ✓ Inserted {count} entities")
    return count




def main():
    """Populate database with ACME Alpha data."""
    print(f"\n{'='*70}")
    print(f"ACME Alpha Case Study - Database Population")
    print(f"{'='*70}")
    print(f"Tenant ID: {TENANT_ID}")
    print(f"Database Path: {DB_PATH}")
    print(f"{'='*70}\n")

    # Initialize database
    print("Initializing REM database...")
    db = Database()
    print(f"  ✓ Database initialized (using default 'resources' schema)\n")

    # Get paths
    case_study_dir = Path(__file__).parent / "case-studies" / "acme-alpha"
    market_data_dir = case_study_dir / "market-data"

    # Ingest market data
    total_trends = 0
    total_trends += ingest_ncreif_benchmarks(db, market_data_dir / "ncreif-property-benchmarks.csv")
    total_trends += ingest_cbsa_metrics(db, market_data_dir / "cbsa-market-metrics.csv")
    total_trends += ingest_energy_ppa_rates(db, market_data_dir / "energy-market-ppa-rates.csv")
    total_trends += ingest_financial_rates(db, market_data_dir / "financial-market-rates.csv")

    # Ingest entities
    total_entities = ingest_entities(db, case_study_dir / "entities.yaml")

    print(f"\n{'='*70}")
    print(f"Population Complete!")
    print(f"{'='*70}")
    print(f"Total trends ingested: {total_trends}")
    print(f"Total entities ingested: {total_entities}")
    print(f"\nDatabase ready for MCP server testing.")
    print(f"\nTo use this database with MCP server:")
    print(f"  export P8_DB_PATH={DB_PATH}")
    print(f"  export P8_TENANT_ID={TENANT_ID}")
    print(f"  percolate serve")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
