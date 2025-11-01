# Market Data - External Time Series for ACME Alpha

## Overview

This directory contains external market data in CSV format that Felix Prime uses for benchmarking, market analysis, and deal evaluation. All datasets can be ingested into the REM database using the **trends** schema for unified querying alongside deal and entity data.

## Datasets

### 1. NCREIF Property Benchmarks
**File**: `ncreif-property-benchmarks.csv`

Commercial real estate performance benchmarks by property type (2020-Q1 to 2024-Q3).

**Property Types**:
- Apartment (multifamily)
- Industrial-Warehouse
- Office
- Retail
- Seniors Housing

**Metrics** (quarterly):
- `total_return_pct`: Total investment return
- `income_return_pct`: Income/dividend return component
- `appreciation_return_pct`: Capital appreciation component
- `cap_rate_pct`: Market capitalization rate
- `occupancy_pct`: Average occupancy rate
- `noi_growth_pct`: Year-over-year NOI growth

**Use Cases**:
- Compare deal underwriting to NCREIF benchmarks
- Identify cap rate compression/expansion trends
- Assess portfolio performance vs market indices

**Example Query**: "Is our 6.45% cap rate for industrial above or below NCREIF Industrial-Warehouse benchmarks?"

---

### 2. CBSA Market Metrics
**File**: `cbsa-market-metrics.csv`

Economic and demographic indicators for key metropolitan areas (2020-Q1 to 2024-Q3).

**Metropolitan Areas** (5 major markets):
- **19740**: Denver-Aurora-Lakewood, CO
- **12060**: Atlanta-Sandy Springs-Roswell, GA
- **36740**: Orlando-Kissimmee-Sanford, FL
- **12420**: Austin-Round Rock, TX
- **19100**: Dallas-Fort Worth-Arlington, TX

**Metrics** (quarterly):
- `population_thousands`: Total population
- `population_growth_yoy_pct`: Year-over-year population growth
- `employment_thousands`: Total employment
- `employment_growth_yoy_pct`: Year-over-year employment growth
- `unemployment_rate_pct`: Unemployment rate
- `median_household_income`: Median household income
- `gdp_billions`: Metropolitan GDP
- `gdp_growth_yoy_pct`: Year-over-year GDP growth

**Use Cases**:
- Assess demographic tailwinds for multifamily deals
- Evaluate employment trends for office exposure
- Identify high-growth markets for expansion

**Example Query**: "What's the population growth in Austin (CBSA 12420) where we have 2 multifamily deals?"

---

### 3. Energy Market PPA Rates
**File**: `energy-market-ppa-rates.csv`

Power Purchase Agreement (PPA) rates and operating metrics for renewable energy markets (2020-Q1 to 2024-Q3).

**Markets** (7 renewable energy markets):
- **wind-wyoming**: Wyoming wind (Mountain West)
- **wind-texas**: Texas wind (ERCOT)
- **wind-offshore-ne**: Offshore wind (US Northeast)
- **solar-southwest**: Southwest solar (AZ, NV, NM)
- **solar-california**: California solar
- **solar-texas**: Texas solar (ERCOT)

**Metrics** (quarterly):
- `ppa_rate_usd_mwh`: Average PPA contract rate ($/MWh)
- `capacity_factor_pct`: Average capacity factor
- `merchant_exposure_pct`: Percentage of generation sold at merchant rates
- `avg_project_size_mw`: Average project size in market
- `curtailment_rate_pct`: Average curtailment rate

**Use Cases**:
- Benchmark deal PPA rates against market averages
- Assess capacity factor assumptions
- Evaluate merchant exposure risk

**Example Query**: "Is our Greenline Wind Phase I PPA rate of $24.50/MWh competitive with Wyoming wind market rates?"

---

### 4. Financial Market Rates
**File**: `financial-market-rates.csv`

Interest rates and yield curves for debt structuring and cost of capital analysis (Jan 2020 to Sep 2024).

**Instruments** (2 key benchmarks):
- **SOFR**: Secured Overnight Financing Rate (overnight, 1-month, 3-month)
- **US-Treasury**: Treasury yield curve (1Y, 2Y, 5Y, 10Y)

**Metrics** (monthly):
- `overnight_rate_pct`: Overnight rate
- `one_month_rate_pct`: 1-month term rate
- `three_month_rate_pct`: 3-month term rate
- `six_month_rate_pct`: 6-month term rate (treasuries only)
- `one_year_rate_pct`: 1-year rate
- `two_year_rate_pct`: 2-year rate (treasuries only)
- `five_year_rate_pct`: 5-year rate (treasuries only)
- `ten_year_rate_pct`: 10-year rate (treasuries only)

**Use Cases**:
- Evaluate floating-rate loan terms (SOFR + spread)
- Assess cost of capital for capital stack modeling
- Understand interest rate environment for deal timing

**Example Query**: "What's the current SOFR 3-month rate for our bridge loan pricing?"

---

## Quick Start

### 1. Validate Data Quality

Before ingestion, validate all CSV files:

```bash
cd market-data
python3 validate_data.py
```

Expected output:
```
✓ All validation checks passed
Total rows validated: 418
Ready for ingestion: ./ingest_all_trends.sh felix-prime
```

### 2. Ingest All Market Data

Use the provided shell script to ingest all 4 datasets:

```bash
./ingest_all_trends.sh felix-prime
```

This will ingest:
- 95 NCREIF property benchmarks
- 95 CBSA market metrics
- 114 energy PPA rates
- 114 financial market rates

**Total**: 418 trend data points ready for querying.

### 3. Query Trends

Test queries are available in `test_query_trends.py`:

```bash
python3 test_query_trends.py
```

Validates:
- Latest cap rates by property type
- Population growth across markets
- Wind PPA rate comparisons
- SOFR rate trends
- Time series aggregation

---

## Data Schema: Trends

All market data is ingested into the REM database using the **trends** schema. See `schema-trends.md` for complete documentation.

### Key Structure

```
trend:{tenant_id}:{sub_category}:{key}:{date}
```

**Unique record** = `sub_category` + `key` + `date` (idempotent upserts)

### Ingestion

Use the unified `percolate ingest` command with `--schema trends`:

```bash
# NCREIF benchmarks
percolate ingest \
  --file market-data/ncreif-property-benchmarks.csv \
  --schema trends \
  --category property_benchmark \
  --sub-category-field property_type \
  --date-field quarter \
  --period-type quarter \
  --source NCREIF \
  --tenant felix-prime

# CBSA market metrics
percolate ingest \
  --file market-data/cbsa-market-metrics.csv \
  --schema trends \
  --category market_metric \
  --sub-category-field cbsa_code \
  --date-field quarter \
  --period-type quarter \
  --source "US Census Bureau" \
  --tenant felix-prime

# Energy PPA rates
percolate ingest \
  --file market-data/energy-market-ppa-rates.csv \
  --schema trends \
  --category energy_price \
  --sub-category-field market \
  --date-field quarter \
  --period-type quarter \
  --source ERCOT \
  --tenant felix-prime

# Financial rates
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

**Unified Ingestion**: The same `percolate ingest` command handles:
- Documents: `--file report.pdf` (default schema: resource chunking)
- Time Series: `--file data.csv --schema trends`
- Entities: `--file entities.yaml --schema entities`

## Query Examples

### Compare Deal to NCREIF Benchmark

```python
from datetime import date

# Get latest NCREIF Apartment cap rate
trends = db.query_trends(
    tenant_id="felix-prime",
    sub_category="Apartment",
    key="cap_rate_pct",
    start_date=date(2024, 9, 30),
    end_date=date(2024, 9, 30)
)
market_cap_rate = trends[0].value

# Compare to deal
deal_cap_rate = 5.45
spread_to_market = deal_cap_rate - market_cap_rate
print(f"Deal: {deal_cap_rate}%, Market: {market_cap_rate}%, Spread: {spread_to_market:.2f}pp")
```

### Track Population Growth in Target Markets

```python
# Austin multifamily markets
cbsa_markets = {
    "12420": "Austin",
    "36740": "Orlando",
    "16740": "Charlotte"
}

for cbsa_code, name in cbsa_markets.items():
    trends = db.query_trends(
        tenant_id="felix-prime",
        sub_category=f"CBSA-{cbsa_code}",
        key="population_growth_yoy_pct",
        start_date=date(2024, 6, 30),
        end_date=date(2024, 9, 30)
    )
    growth = trends[-1].value if trends else 0
    print(f"{name}: {growth}% population growth")
```

### Evaluate Wind PPA Pricing

```python
# Get Wyoming wind market PPA rates (last 8 quarters)
trends = db.query_trends(
    tenant_id="felix-prime",
    sub_category="wind-wyoming",
    key="ppa_rate_usd_mwh",
    start_date=date(2022, 9, 30),
    end_date=date(2024, 9, 30)
)

print("Wyoming Wind PPA Rate Trend:")
for t in trends:
    print(f"{t.date}: ${t.value}/MWh")

avg_rate = sum(t.value for t in trends) / len(trends)
print(f"2-year avg: ${avg_rate:.2f}/MWh")
```

### Get Current SOFR for Loan Pricing

```python
# Current 3-month SOFR for floating-rate bridge loan
trends = db.query_trends(
    tenant_id="felix-prime",
    sub_category="SOFR",
    key="three_month_rate_pct",
    start_date=date(2024, 9, 1),
    end_date=date(2024, 9, 30)
)
sofr_3m = trends[-1].value

# Example bridge loan pricing
spread = 4.50  # 450 bps over SOFR
all_in_rate = sofr_3m + spread
print(f"SOFR 3M: {sofr_3m}%, Spread: {spread}%, All-in Rate: {all_in_rate}%")
```

## Data Sources

- **NCREIF**: National Council of Real Estate Investment Fiduciaries (https://www.ncreif.org/)
- **US Census Bureau**: CBSA demographic and economic data (https://www.census.gov/)
- **BLS**: Bureau of Labor Statistics employment data (https://www.bls.gov/)
- **ERCOT**: Electric Reliability Council of Texas energy market data
- **Federal Reserve**: SOFR rates and economic indicators (https://www.federalreserve.gov/)
- **US Treasury**: Treasury yield curve (https://home.treasury.gov/)

## Update Frequency

- **NCREIF**: Quarterly (published ~45 days after quarter end)
- **CBSA metrics**: Quarterly (Census/BLS releases)
- **Energy PPA rates**: Quarterly (market reports)
- **SOFR**: Daily (use monthly averages in dataset)
- **Treasury yields**: Daily (use month-end values in dataset)

## Data Quality Notes

- All data in this case study is **simulated but realistic** based on actual market trends
- NCREIF property returns reflect actual 2020-2024 market dynamics (COVID impact, recovery, rate hikes)
- CBSA population growth reflects actual Sunbelt migration patterns
- Energy PPA rates reflect actual renewable energy market pricing trends
- SOFR/Treasury rates match actual Federal Reserve policy trajectory

For production use, replace with actual data from licensed sources.

## Scripts in This Directory

### `validate_data.py`
Validates all CSV files before ingestion:
- Checks required columns present
- Validates date formats (quarters and months)
- Verifies numeric ranges are reasonable
- Reports errors and warnings

**Usage**: `python3 validate_data.py`

### `ingest_all_trends.sh`
Bash script to ingest all 4 market data CSVs into REM database using the trends schema. Demonstrates proper command structure with category, sub-category, date fields, and metadata.

**Usage**: `./ingest_all_trends.sh [tenant_id]`

**Default tenant**: `felix-prime`

### `test_query_trends.py`
Query validation script that tests reading CSV data and demonstrates query patterns for each dataset. Uses mock database for testing without requiring actual REM instance.

**Usage**: `python3 test_query_trends.py`

**Tests**:
- Latest NCREIF cap rates by property type
- Population growth across Sunbelt markets
- Wind PPA rate comparisons
- SOFR 3-month rate trends
- Time series aggregation (apartment returns)

### `test_ingest_embeddings.py`
Ingestion pipeline test that validates:
- CSV parsing and data transformation
- Deterministic key generation (idempotent upserts)
- Temporal indexing
- Cross-sectional queries
- Date range filtering

**Usage**: `python3 test_ingest_embeddings.py`

**Validates**: Mock ingestion of 418+ trend data points with proper indexing.
