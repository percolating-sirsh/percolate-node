# Trends Schema - Time Series Data in REM

## Overview

The **trends** schema stores time series data for benchmarking, market analysis, and external data integration. This allows Felix to query market benchmarks (NCREIF, CBSA metrics, energy prices, interest rates) alongside investment deals.

## Schema Definition

```python
from pydantic import BaseModel, Field
from datetime import date
from typing import Optional, Dict, Any
from decimal import Decimal

class TrendDataPoint(BaseModel):
    """Single time series data point."""

    # Classification
    category: str = Field(
        description="Top-level category (e.g., 'property_benchmark', 'market_metric', 'energy_price', 'interest_rate')"
    )
    sub_category: str = Field(
        description="Sub-category for filtering (e.g., 'Apartment', 'Industrial-Warehouse', 'CBSA-19740')"
    )
    key: str = Field(
        description="Specific metric key (e.g., 'total_return_pct', 'cap_rate_pct', 'population_thousands')"
    )

    # Time dimension
    date: date = Field(
        description="Date of the data point (YYYY-MM-DD format)"
    )
    period_type: str = Field(
        default="quarter",
        description="Period type: 'daily', 'weekly', 'monthly', 'quarter', 'annual'"
    )

    # Value
    value: Decimal = Field(
        description="Numeric value for this data point"
    )
    value_unit: Optional[str] = Field(
        default=None,
        description="Unit of measurement (e.g., 'percent', 'dollars', 'thousands', 'MW')"
    )

    # Metadata
    source: Optional[str] = Field(
        default=None,
        description="Data source (e.g., 'NCREIF', 'US Census', 'BLS', 'ERCOT')"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional metadata as JSON"
    )

class TrendQuery(BaseModel):
    """Query parameters for time series data."""

    category: Optional[str] = None
    sub_category: Optional[str] = None
    key: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    limit: Optional[int] = 100
```

## RocksDB Key Structure

Trends are stored with a **deterministic key** for idempotent upserts:

```
trend:{tenant_id}:{sub_category}:{key}:{date}
```

**Unique record = sub_category + key + date**

This ensures:
- **Idempotent upserts**: Re-ingesting same data overwrites existing record
- **Deduplication**: Same metric for same date is stored once
- **Time-ordered queries**: Efficient range scans by date within sub_category+key

**Note**: `category` is stored as metadata for filtering, not part of the key.

**Examples**:
- `trend:felix-prime:Apartment:total_return_pct:2024-09-30`
- `trend:felix-prime:CBSA-19740:population_thousands:2024-06-30`
- `trend:felix-prime:wind-wyoming:ppa_rate_usd_mwh:2024-09-30`
- `trend:felix-prime:SOFR:overnight_rate_pct:2024-09-15`

## Column Families

Trends use a dedicated RocksDB column family for efficient range queries:

- **Column Family**: `trends`
- **Ordering**: Lexicographic by key (date-ordered within category/subcategory/key)
- **Indexing**: Prefix bloom filter on `category:sub_category:key`

## Ingestion from CSV

```python
import csv
from datetime import datetime
from decimal import Decimal

def ingest_trends_from_csv(
    db: REMDatabase,
    csv_path: str,
    category: str,
    tenant_id: str,
    source: str,
    category_field: str = None,  # CSV column to use as sub_category
    date_field: str = "date",
    period_type: str = "quarter"
):
    """
    Ingest time series data from CSV into trends schema.

    Args:
        db: REM database instance
        csv_path: Path to CSV file
        category: Top-level category (e.g., 'property_benchmark')
        tenant_id: Tenant scope
        source: Data source name
        category_field: CSV column to use as sub_category (e.g., 'property_type', 'cbsa_code')
        date_field: CSV column containing date
        period_type: 'daily', 'monthly', 'quarter', 'annual'
    """
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)

        for row in reader:
            # Parse date
            date_str = row[date_field]
            if period_type == "quarter":
                # Convert "2024-Q3" to "2024-09-30"
                year, quarter = date_str.split('-Q')
                month = int(quarter) * 3
                date_val = datetime(int(year), month, 1).date()
                # Last day of quarter
                if month == 3:
                    date_val = date_val.replace(day=31, month=3)
                elif month == 6:
                    date_val = date_val.replace(day=30, month=6)
                elif month == 9:
                    date_val = date_val.replace(day=30, month=9)
                else:  # month == 12
                    date_val = date_val.replace(day=31, month=12)
            else:
                date_val = datetime.fromisoformat(date_str).date()

            # Get sub_category
            sub_category = row[category_field] if category_field else "default"

            # Ingest each metric column
            for key, value in row.items():
                if key in [date_field, category_field]:
                    continue

                if value and value.strip():
                    trend = TrendDataPoint(
                        category=category,
                        sub_category=sub_category,
                        key=key,
                        date=date_val,
                        period_type=period_type,
                        value=Decimal(value),
                        source=source,
                        metadata={"csv_path": csv_path}
                    )

                    db.put_trend(tenant_id, trend)
```

## Example Ingestion Commands

All market data uses the unified `percolate ingest` command with `--schema trends`:

```bash
# Ingest NCREIF property benchmarks
percolate ingest \
  --file market-data/ncreif-property-benchmarks.csv \
  --schema trends \
  --category property_benchmark \
  --sub-category-field property_type \
  --date-field quarter \
  --period-type quarter \
  --source NCREIF \
  --tenant felix-prime

# Ingest CBSA market metrics
percolate ingest \
  --file market-data/cbsa-market-metrics.csv \
  --schema trends \
  --category market_metric \
  --sub-category-field cbsa_code \
  --date-field quarter \
  --period-type quarter \
  --source "US Census Bureau" \
  --tenant felix-prime

# Ingest energy market prices
percolate ingest \
  --file market-data/energy-market-ppa-rates.csv \
  --schema trends \
  --category energy_price \
  --sub-category-field market \
  --date-field quarter \
  --period-type quarter \
  --source ERCOT \
  --tenant felix-prime

# Ingest financial market rates
percolate ingest \
  --file market-data/financial-market-rates.csv \
  --schema trends \
  --category interest_rate \
  --sub-category-field instrument \
  --date-field month \
  --period-type monthly \
  --source "Federal Reserve" \
  --tenant felix-prime
```

**Note**: The same `percolate ingest` command handles documents (PDFs, emails, etc.) and structured data (CSV trends). The `--schema` parameter determines the ingestion behavior.

## Query Examples

### 1. Get NCREIF Apartment Returns (Last 2 Years)

```python
from datetime import date, timedelta

end_date = date(2024, 9, 30)
start_date = end_date - timedelta(days=730)  # ~2 years

trends = db.query_trends(
    tenant_id="felix-prime",
    category="property_benchmark",
    sub_category="Apartment",
    key="total_return_pct",
    start_date=start_date,
    end_date=end_date
)

for trend in trends:
    print(f"{trend.date}: {trend.value}%")
```

**Use case**: "How does our multifamily portfolio compare to NCREIF Apartment returns?"

### 2. Compare Cap Rates Across Property Types

```python
property_types = ["Apartment", "Industrial-Warehouse", "Office", "Retail"]

for prop_type in property_types:
    trends = db.query_trends(
        tenant_id="felix-prime",
        category="property_benchmark",
        sub_category=prop_type,
        key="cap_rate_pct",
        start_date=date(2024, 6, 30),
        end_date=date(2024, 9, 30)
    )
    latest = trends[-1]
    print(f"{prop_type}: {latest.value}% cap rate")
```

**Use case**: "What are current market cap rates for our asset classes?"

### 3. Get Population Growth for Target Markets

```python
cbsa_codes = ["19740", "12060", "36740", "12420"]  # Denver, Atlanta, Orlando, Austin
cbsa_names = {
    "19740": "Denver",
    "12060": "Atlanta",
    "36740": "Orlando",
    "12420": "Austin"
}

for cbsa in cbsa_codes:
    trends = db.query_trends(
        tenant_id="felix-prime",
        category="market_metric",
        sub_category=f"CBSA-{cbsa}",
        key="population_growth_yoy_pct",
        start_date=date(2024, 6, 30),
        end_date=date(2024, 9, 30)
    )
    latest = trends[-1]
    print(f"{cbsa_names[cbsa]}: {latest.value}% population growth")
```

**Use case**: "What's the demographic trend in markets where we have multifamily exposure?"

### 4. Track Energy PPA Rates for Wind Projects

```python
trends = db.query_trends(
    tenant_id="felix-prime",
    category="energy_price",
    sub_category="wind-wyoming",
    key="ppa_rate_usd_mwh",
    start_date=date(2023, 1, 1),
    end_date=date(2024, 9, 30)
)

print("Wyoming Wind PPA Rate Trend:")
for trend in trends:
    print(f"{trend.date}: ${trend.value}/MWh")
```

**Use case**: "Are PPA rates improving for our Wyoming wind deal?"

### 5. Get SOFR Rate History

```python
trends = db.query_trends(
    tenant_id="felix-prime",
    category="interest_rate",
    sub_category="SOFR",
    key="overnight_rate_pct",
    start_date=date(2024, 1, 1),
    end_date=date(2024, 9, 30),
    limit=30  # Last 30 days
)

avg_rate = sum(t.value for t in trends) / len(trends)
print(f"SOFR avg (last 30 days): {avg_rate:.2f}%")
```

**Use case**: "What's the current SOFR rate for our floating-rate loans?"

## Integration with Agent-lets

Agent-lets can query trends via MCP tool:

```python
# In alpha-extraction agent
def get_market_benchmark(property_type: str, metric: str, date: str):
    """Get market benchmark for comparison."""
    trends = search_knowledge_base(
        query=f"trend:property_benchmark:{property_type}:{metric}",
        filters={"date": date}
    )
    return trends[0].value if trends else None

# Example: Compare deal to NCREIF benchmark
deal_cap_rate = 6.45
market_cap_rate = get_market_benchmark("Office", "cap_rate_pct", "2024-09-30")

if deal_cap_rate > market_cap_rate:
    print(f"Deal cap rate {deal_cap_rate}% is {deal_cap_rate - market_cap_rate:.2f}pp above market")
```

## Benefits

1. **Unified Querying**: Query market data alongside deals and entities in single REM database
2. **Time-Ordered**: Efficient range queries by date for trend analysis
3. **Flexible**: Any time series data can be ingested (property, macro, energy, rates)
4. **Contextual AI**: Agent-lets can reference market benchmarks when analyzing deals
5. **Portfolio Analytics**: Compare portfolio performance against market indices

## Data Sources

Supported external data sources:

- **NCREIF**: Property performance benchmarks
- **US Census Bureau**: CBSA demographic and economic data
- **BLS**: Employment and labor market data
- **FRED**: Federal Reserve economic data (interest rates, GDP)
- **ERCOT/CAISO**: Energy market prices and PPA rates
- **ICE**: Financial market rates (SOFR, treasuries)
