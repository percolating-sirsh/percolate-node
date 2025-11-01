# ACME Alpha - Investment Alpha Extraction Case Study

## Overview

This case study demonstrates Percolate's capabilities for institutional investment alpha extraction. Felix Prime, a Senior Asset Manager at ACME Capital Partners in New York, uses AI agents to analyze 60-80 investment opportunities per quarter and extract alpha signals from deal documents.

**Uses Official Industry Classification Codes**: This case study incorporates real-world industry standards including NCREIF property types, NAICS codes, CBSA market codes, and CFI instrument classifications for data integration and benchmarking.

## Key Files

- **profile.md**: Detailed case study profile including domain context, agent framework, and success criteria
- **entities.yaml**: Ground truth entities (13 deals, 10 sponsors, 13 properties, 8 markets, 5 lenders, 3 analysts)
- **agentlets/**: Three specialized agent-let schemas
  - `alpha-extraction.json`: Extracts investment alpha signals with forensic precision
  - `entity-extraction.json`: Normalizes entities (sponsors, properties, markets) across documents
  - `deal-scorer.json`: Aggregates multi-document analysis for IC recommendations
- **test-cases/**: 77 investment documents across asset classes
- **market-data/**: External time series data for benchmarking (see below)

## Domain

**User**: Felix Prime - Senior Asset Manager, ACME Capital Partners, New York
**Portfolio**: $450M multi-strategy (real estate, energy infrastructure, private credit)
**Deal Flow**: 60-80 opportunities/quarter → 3-5 investments
**Focus**: Hidden value detection, risk signal recognition, modeling error identification

## Entity Types

1. **Deals**: Investment opportunities with alpha scores
2. **Sponsors**: Developers and operators with track records
3. **Properties**: Physical assets (warehouses, wind farms, apartments, etc.)
4. **Market Sectors**: Geographic and asset class segments
5. **Lenders**: Financial institutions providing capital
6. **Analysts**: Felix and his team

## Industry Classification Codes

The case study uses official industry standards for data integration:

### NCREIF Property Types
- **Apartment**: Multifamily residential buildings
- **Industrial-Warehouse**: Logistics and distribution facilities
- **Office**: Commercial office buildings
- **Retail**: Shopping centers and retail properties
- **Seniors Housing**: Independent living and assisted care facilities

### NAICS Codes (6-digit)
- **221114**: Solar Electric Power Generation
- **221115**: Wind Electric Power Generation
- **531110**: Lessors of Residential Buildings and Dwellings (multifamily)
- **531120**: Lessors of Nonresidential Buildings (office, industrial, retail)
- **531130**: Lessors of Miniwarehouses and Self-Storage Units

### CBSA Codes (US Census Metropolitan Areas)
- **19740**: Denver-Aurora-Lakewood, CO
- **12060**: Atlanta-Sandy Springs-Roswell, GA
- **36740**: Orlando-Kissimmee-Sanford, FL
- **12420**: Austin-Round Rock, TX
- **19100**: Dallas-Fort Worth-Arlington, TX
- **26900**: Indianapolis-Carmel-Anderson, IN
- **16740**: Charlotte-Concord-Gastonia, NC-SC
- And more...

### Benefits
- **Benchmarking**: Compare portfolio performance against NCREIF Property Index
- **Market Analysis**: Link to BLS employment data, Census demographics, FRED economic indicators
- **Comparable Transactions**: Find similar deals by property type + geography + industry code
- **Data Integration**: Query external datasets using standardized codes

**Example Query**: "Show me apartment deals (NCREIF: Apartment, NAICS: 531110) in Sunbelt CBSAs with cap rates below market average"

## Agent-lets

### 1. Alpha Extraction
Analyzes investment documents to identify:
- **Positive alpha**: Hidden value, mispricing, embedded options, compound-yield structures
- **Negative alpha**: Modeling errors, missing reserves, catastrophic contract clauses, execution impossibility
- Scores deals from -10 (catastrophic) to +10 (exceptional hidden value)

### 2. Entity Extraction
Extracts and normalizes:
- Sponsors (with track records)
- Properties/Assets (with specifications)
- Market sectors (with benchmarks)
- Lenders (with typical terms)
- Creates relationship edges (SPONSORS, ASSET, LOCATED_IN, etc.)

### 3. Deal Scorer
Aggregates multi-document analysis:
- Weights signals by document type (underwriting memo 1.0×, email 0.6×, etc.)
- Compares to asset class benchmarks
- Generates IC summary with recommendation

## Sample Queries

**Query**: "What deals has Greenline Renewables sponsored and how did they perform?"

**Expected**: "Greenline Renewables sponsored Greenline Wind Phase I (alpha score +4.5, funded). Track record: 850 MW operational, strong execution."

---

**Query**: "Which office deals have alpha scores below -5 and why?"

**Expected**: "2 office deals scored below -5: Ironwood Office Park (-6.2, DSCR modeling error + over-leverage) and Fairview Plaza (-5.8, unleased with inflated exit cap rate)."

---

**Query**: "What's our exposure to the Wyoming wind market?"

**Expected**: "Wyoming wind exposure: Greenline Wind Phase I (200 MW, $95M equity). Market cap: ~800 MW total, transmission constraints limiting growth."

## Success Criteria

1. **Entity extraction**: ≥90% recall, ≥85% precision
2. **Alpha signal detection**: ≥80% recall on major signals (±7-10 score range)
3. **Scoring calibration**: Alpha scores correlate with actual investment outcomes
4. **Entity normalization**: ≥85% accuracy on informal references
5. **Relationship extraction**: ≥75% of expected edges identified

## Test Data

### Investment Documents (77 files)
- Industrial warehouses (Glenview, Horizon, Northgate)
- Multifamily apartments (Riverbend, Lakeside Manor, Summit Ridge)
- Office parks (Ironwood, Fairview)
- Senior living (Oakview)
- Retail (Maple Grove)
- Wind energy (Greenline, Blue Harbor)
- Solar + storage (High Mesa)

### Market Data (Time Series CSV)

The case study includes **4 external market datasets** for benchmarking and analysis:

1. **NCREIF Property Benchmarks** (95 data points, Q1 2020 - Q3 2024)
   - Returns, cap rates, occupancy by property type
   - 5 property types: Apartment, Industrial-Warehouse, Office, Retail, Seniors Housing

2. **CBSA Market Metrics** (95 data points, Q1 2020 - Q3 2024)
   - Population, employment, GDP growth by metro area
   - 5 markets: Denver, Atlanta, Orlando, Austin, Dallas-Fort Worth

3. **Energy Market PPA Rates** (114 data points, Q1 2020 - Q3 2024)
   - PPA rates, capacity factors, merchant exposure
   - 6 markets: Wyoming wind, Texas wind, Offshore NE wind, Southwest solar, California solar, Texas solar

4. **Financial Market Rates** (114 data points, Jan 2020 - Sep 2024)
   - SOFR rates (overnight, 1M, 3M) and Treasury yield curve
   - 2 instruments: SOFR, US-Treasury

**Trends Schema**: All market data is designed for ingestion into REM using a unified schema. See `market-data/schema-trends.md` for details on the data structure.

## Quick start

```bash
# Parse a deal document with alpha extraction agent
percolate parse test-deal-simple.txt \
  --agent agentlets/alpha-extraction.yaml \
  --tenant-id felix-prime \
  --project alpha-deals

# Ask the agent about alpha signals
percolate ask agentlets/alpha-extraction.yaml \
  "What are the key alpha signals in this deal?"

# Run agent evaluation
percolate agent-eval agentlets/alpha-extraction.yaml \
  "Analyze this investment opportunity: ..."

# Start API server with MCP endpoint
percolate serve
```

## Testing

Integration tests validate agent extraction accuracy against ground truth entities defined in `entities.yaml`:

```bash
# Run all integration tests
cd ../../../
uv run pytest percolate/tests/integration/

# Run agent-specific tests
uv run pytest percolate/tests/integration/agents/
```
