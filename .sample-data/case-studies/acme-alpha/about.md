# ACME Alpha - Investment Alpha Extraction Case Study

## Domain

**Business**: Institutional investment management (real estate, energy & infrastructure, private credit, venture capital)

**User**: Felix Prime - Senior Asset Manager at ACME Capital Partners, New York

**Data sources**:
- Investment underwriting memos and term sheets
- Financial models and projections
- Internal email chains and analysis
- Deal documents (contracts, agreements, closing docs)
- Market research and industry reports
- Investor updates and board memos
- Property inspection reports
- Due diligence materials

**Operating context**:
- Felix manages a $450M multi-strategy allocation across real estate, energy infrastructure, and credit
- Portfolio includes: industrial warehouses, multifamily, renewable energy projects, bridge loans
- Deal flow: 60-80 opportunities per quarter, commits to 3-5 deals
- Felix uses AI agents to triage deal flow, extract alpha signals, and identify hidden risks
- Investment committee meets weekly to review top-ranked opportunities
- Focus on identifying mispriced assets, hidden value, and buried risks in routine documentation

## Agentic Framework

This case study includes specialized agent-lets that extract alpha signals from investment documents and automatically index entities, deals, and relationships in the REM database.

### Available Agents

#### 1. alpha-extraction (agentlets/alpha-extraction.json)

Extracts investment alpha signals from deal documents with forensic precision.

**What it does**:
- Classifies document type and asset class
- Extracts key financial metrics (NOI, DSCR, LTV, IRR, Cap Rate, etc.)
- Identifies positive alpha signals (hidden value, mispricing, embedded options)
- Identifies negative alpha signals (hidden risks, modeling errors, poor contract terms)
- Assesses execution, financial, market, and governance risks
- Scores deals from -10 (catastrophic) to +10 (exceptional hidden value)
- Provides quality rating and investment judgment

**MCP tools used** (generic Percolate tools):
- `search_knowledge_base`: Find similar deals, comparable metrics, historical performance
- `lookup_entity`: Resolve sponsors, properties, market sectors
- `create_entity`: Create deal entity with extracted metrics
- `create_moment`: Record analysis moment with timestamp

**Example**:
```
Input: Ironwood Office Park underwriting memo (PDF)

Output:
- document_classification: {
    document_type: "Underwriting Memo",
    asset_class: "Office Real Estate",
    transaction_type: "Bridge Loan Refinancing",
    deal_name: "Ironwood Office Park"
  }
- key_metrics: {
    noi: "$810K stabilized",
    dscr: "1.62× (modeling error - actual 1.08×)",
    ltv: "77% → 84% when corrected",
    irr: "8.5-10.6% realistic vs 13% modeled"
  }
- alpha_signals:
    positive_signals: []
    negative_signals: [
      {
        signal_type: "Modeling Error Overstating Returns",
        description: "DSCR calculated as 1.62× but test scenario shows 1.08×. Excel formula error copying test values into final model.",
        impact: "-3-5pp IRR reduction; covenant breach risk"
      },
      {
        signal_type: "Missing Reserve/Expense",
        description: "No maintenance reserves, TI budget only covers 50% of renewals",
        impact: "Adds $200K+ unfunded shortfall"
      }
    ]
- quality_rating: "Bad / Watchlist"
- alpha_score: -6
- overall_judgment: "Over-levered bridge loan with modeling errors masking poor DSCR; clear pass"
```

**Key principle**: Forensic analysis of financial details, tone vs. substance, buried contract clauses, and modeling errors.

#### 2. entity-extraction (agentlets/entity-extraction.json)

Extracts and normalizes investment entities from documents.

**What it does**:
- Extracts sponsors, developers, lenders, and other industry players
- Identifies properties, assets, and projects with locations
- Normalizes company names and entity references
- Extracts key entity attributes (location, role, track record)
- Creates entity relationships (sponsor → deal, property → market)
- Links entities to deals and moments

**MCP tools used** (generic Percolate tools):
- `search_knowledge_base`: Search for existing entities by name/alias
- `lookup_entity`: Verify entity exists before creating
- `create_entity`: Create new entity with properties
- `create_edge`: Link entities (sponsor → deal, property → market)

**Example**:
```
Input: "Greenline Wind Phase I" project memo

Output:
- entities_extracted: [
    {
      entity_id: "sponsor:GRN-001",
      entity_type: "sponsor",
      name: "Greenline Renewables LLC",
      aliases: ["Greenline", "GRN"],
      location: "Denver, CO",
      track_record: "2 prior wind projects, 850 MW operational"
    },
    {
      entity_id: "property:GLW-PH1",
      entity_type: "property",
      name: "Greenline Wind Phase I",
      asset_class: "Wind Energy",
      location: "Laramie County, Wyoming",
      capacity: "200 MW"
    },
    {
      entity_id: "market:US-WIND-WY",
      entity_type: "market_sector",
      name: "Wyoming Wind Market",
      asset_class: "Wind Energy",
      region: "US Mountain West"
    }
  ]
- edges_created: [
    "sponsor:GRN-001 -[SPONSORS]-> property:GLW-PH1",
    "property:GLW-PH1 -[LOCATED_IN]-> market:US-WIND-WY",
    "deal:GLW-PH1-001 -[ASSET]-> property:GLW-PH1"
  ]
```

**Key principle**: Entity normalization across informal references, relationship extraction, market sector classification.

#### 3. deal-scorer (agentlets/deal-scorer.json)

Scores and ranks deals for portfolio construction and investment committee review.

**What it does**:
- Aggregates alpha scores across multiple documents for a deal
- Weighs signals by document type (underwriting > email > pitch deck)
- Compares to portfolio benchmarks and asset class standards
- Flags critical risks and deal-breakers
- Generates investment committee summary

**MCP tools used** (generic Percolate tools):
- `search_knowledge_base`: Find all documents for a deal
- `lookup_entity`: Get deal entity with all linked analyses
- `traverse_graph`: Find related entities (sponsor track record, market comps)

**Example**:
```
Input: Request to score "Ironwood Office Park" deal

Output:
- deal_id: "deal:IRW-001"
- documents_analyzed: 3 (underwriting memo, email chain, inspection report)
- aggregated_alpha_score: -6.2
- risk_factors: [
    "Modeling error overstating DSCR by 50%",
    "Soft suburban office market with rising vacancy",
    "Sponsor over-extended across 4 concurrent projects"
  ]
- recommendation: "DECLINE - structural over-leverage with execution risk"
- ic_summary: "Bridge loan with catastrophic DSCR error (1.62× modeled vs 1.08× actual) in soft suburban office market. Sponsor track record weak. Clear pass."
```

### Natural Language Query Workflow

These agents enable natural language queries about indexed investment data:

**Query**: "What deals has Greenline Renewables sponsored and how did they perform?"

**Resolution**:
1. Search for sponsor: `search_knowledge_base(query="sponsor:Greenline Renewables", ...)`
2. Traverse edges: `sponsor:GRN-001 -[SPONSORS]-> deal:GLW-PH1-001, deal:GLW-PH2-002`
3. Lookup deals: `lookup_entity(entity_id="deal:GLW-PH1-001", include_relationships=true)`
4. Return: "Greenline Renewables sponsored 2 deals: Greenline Wind Phase I (alpha score +4.5, funded) and Phase II (alpha score +3.2, funded). Track record: 850 MW operational, strong execution."

**Query**: "Which office deals have alpha scores below -5 and why?"

**Resolution**:
1. Search deals: `search_knowledge_base(query="asset_class:Office alpha_score:<-5", ...)`
2. Lookup deals: `lookup_entity(entity_id="deal:IRW-001", include_relationships=true)`
3. Extract signals: Parse negative alpha signals from analysis
4. Return: "2 office deals scored below -5: Ironwood Office Park (-6.2, DSCR modeling error + over-leverage) and Fairview Plaza (-5.8, unleased with inflated exit cap rate)."

**Query**: "What's the geographic concentration in our wind portfolio?"

**Resolution**:
1. Search wind deals: `search_knowledge_base(query="asset_class:Wind status:funded", ...)`
2. Traverse edges: `deal -[ASSET]-> property -[LOCATED_IN]-> market_sector`
3. Aggregate: Group by market region
4. Return: "Wind portfolio: 45% Texas (3 projects, 600 MW), 30% Wyoming (2 projects, 400 MW), 25% Iowa (2 projects, 350 MW). Geographic diversification moderate."

### Agent Workflow

```
Investment Document → Agent-let → Structured Alpha Analysis + Entity Edges + Moments

Example: Underwriting memo arrives
├─> alpha-extraction agent processes it
├─> Extracts: {metrics, alpha_signals, risks, score, rating}
├─> Creates Deal entity: deal:IRW-001
├─> Creates Moment: MOM-2024-156 (deal_analysis, timestamp, analyst:Felix)
├─> entity-extraction agent runs
├─> Extracts: {sponsors, properties, lenders, markets}
├─> Creates edges: Sponsor -[SPONSORS]-> Deal, Deal -[ASSET]-> Property
└─> Indexed in REM database for natural language queries
```

## Custom Ontology

Agent-lets extract the following domain models from unstructured investment data:

### Deal Classification

```python
from pydantic import BaseModel, Field
from decimal import Decimal
from typing import Literal, Optional
from datetime import date

class DealClassification(BaseModel):
    """Structured deal information extracted from documents."""

    deal_id: str = Field(pattern=r"^deal:[A-Z]{3}-\d{3}$")
    deal_name: str
    asset_class: Literal[
        "Industrial Real Estate",
        "Multifamily",
        "Office Real Estate",
        "Retail",
        "Hospitality",
        "Senior Living",
        "Self Storage",
        "Solar Energy",
        "Wind Energy",
        "Battery Storage",
        "EV Charging",
        "Hydrogen",
        "Geothermal",
        "Data Center",
        "Venture - Clean Energy",
        "Venture - Financial Services",
        "Bridge Loan",
        "Construction Loan",
        "Credit Fund",
        "NPL Portfolio"
    ]
    transaction_type: Literal[
        "Acquisition Financing",
        "Construction Loan",
        "Bridge Loan",
        "Refinancing",
        "Mezzanine Debt",
        "Preferred Equity",
        "Series A Equity",
        "Series B Equity",
        "Growth Equity",
        "Project Finance",
        "Fund Investment",
        "NPL Acquisition"
    ]
    deal_size_usd: Decimal
    investment_amount_usd: Decimal
    status: Literal["Pipeline", "IC Review", "Funded", "Declined", "Watchlist"]
    analyst: str  # Felix, other team members
    date_received: date
```

### Financial Metrics

```python
class FinancialMetrics(BaseModel):
    """Key investment metrics extracted from deal documents."""

    # Real estate metrics
    noi: Optional[str] = None  # Net Operating Income
    dscr: Optional[str] = None  # Debt Service Coverage Ratio
    ltv: Optional[float] = None  # Loan-to-Value ratio
    ltc: Optional[float] = None  # Loan-to-Cost ratio
    cap_rate: Optional[str] = None  # Capitalization rate
    occupancy: Optional[str] = None

    # Return metrics
    irr_levered: Optional[str] = None
    irr_unlevered: Optional[str] = None
    equity_multiple: Optional[str] = None
    cash_yield: Optional[str] = None

    # Operating metrics
    revenue: Optional[str] = None
    ebitda: Optional[str] = None
    margin: Optional[str] = None

    # Energy metrics
    capacity_mw: Optional[float] = None
    merchant_exposure: Optional[str] = None
    ppa_rate: Optional[str] = None

    # Other
    cash_runway: Optional[str] = None
    reserves: Optional[str] = None
```

### Alpha Signal

```python
class AlphaSignal(BaseModel):
    """Identified alpha signal (positive or negative)."""

    signal_type: str  # e.g., "Hidden Yield-on-Cost Arbitrage", "Modeling Error"
    description: str
    impact: str  # Estimated impact on returns
    materiality: Literal["Low", "Moderate", "High", "Severe"]
    evidence: str  # Specific citation from document
```

### Entity Types

The ontology defines 6 core entity types:

#### 1. Deal
- **ID format**: `deal:XXX-NNN` (e.g., `deal:IRW-001`)
- **Properties**: deal_name, asset_class, transaction_type, size, status, alpha_score
- **Inference**: Created from underwriting memos, term sheets, investment committee docs

#### 2. Sponsor
- **ID format**: `sponsor:XXX-NNN` (e.g., `sponsor:GRN-001`)
- **Properties**: name, aliases, location, track_record, asset_classes
- **Inference**: Extracted from deal documents, prior deal history

#### 3. Property/Asset
- **ID format**: `property:XXX-NNN` (e.g., `property:GLW-PH1`)
- **Properties**: name, asset_class, location, capacity/size, condition
- **Inference**: Extracted from underwriting memos, inspection reports, appraisals

#### 4. Market Sector
- **ID format**: `market:XX-CLASS-REGION` (e.g., `market:US-WIND-WY`)
- **Properties**: region, asset_class, cap_rate_range, occupancy_range, trends
- **Inference**: Extracted from market research, deal comparables

#### 5. Lender/Investor
- **ID format**: `lender:XXX-NNN` (e.g., `lender:ABC-001`)
- **Properties**: name, institution_type, lending_focus, terms
- **Inference**: Extracted from term sheets, credit agreements

#### 6. Instrument
- **ID format**: `instrument:XXX-NNN` (e.g., `instrument:IRW-LOAN-001`)
- **Properties**: type (debt, equity), amount, terms, covenants, structure
- **Inference**: Extracted from term sheets, credit agreements, investment memos

## Edge Types

Entity relationships are extracted as typed edges:

### Deal structure edges
- `SPONSORS`: Sponsor → Deal (who's behind the deal)
- `ASSET`: Deal → Property (what's being financed)
- `FINANCED_BY`: Deal → Lender (who's providing capital)
- `COMPETES_WITH`: Deal → Deal (alternative investments)

### Geographic edges
- `LOCATED_IN`: Property → Market Sector (where the asset is)
- `OPERATES_IN`: Sponsor → Market Sector (sponsor's focus markets)

### Temporal edges
- `PRECEDED_BY`: Deal → Deal (sponsor's prior deals)
- `FOLLOWS`: Deal → Deal (follow-on investment)

### Performance edges
- `ANALYZED_BY`: Deal → Analyst (Felix or team)
- `FLAGGED_FOR`: Deal → Risk (identified red flags)
- `COMPARED_TO`: Deal → Deal (comparable transactions)

## Expected Entity Paths

Agent-lets should extract these relationship paths:

### Path 1: Sponsor track record
```
Sponsor(GRN-001) -[SPONSORS]->
Deal(GLW-PH1-001) -[ASSET]->
Property(GLW-PH1) -[LOCATED_IN]->
Market(US-WIND-WY)
```

**Query enabled**: "What's Greenline's track record in Wyoming wind?"

### Path 2: Market concentration
```
Deal(GLW-PH1-001) -[ASSET]->
Property(GLW-PH1) -[LOCATED_IN]->
Market(US-WIND-WY) <-[LOCATED_IN]-
Property(BLH-001) <-[ASSET]-
Deal(BLH-001)
```

**Query enabled**: "What's our exposure to Wyoming wind market?"

### Path 3: Comparable deals
```
Deal(IRW-001) -[LOCATED_IN]->
Market(US-OFFICE-SUBURBAN) <-[LOCATED_IN]-
Deal(FVW-001) -[ANALYZED_BY]->
Analyst(Felix)
```

**Query enabled**: "What suburban office deals have we seen and how do they compare?"

### Path 4: Risk propagation
```
Sponsor(XYZ-001) -[SPONSORS]->
Deal(ABC-001) -[FLAGGED_FOR]->
Risk(Over-Leverage) <-[FLAGGED_FOR]-
Deal(DEF-002) <-[SPONSORS]-
Sponsor(XYZ-001)
```

**Query enabled**: "Does this sponsor have recurring risk patterns across deals?"

## Entity Resolution Challenges

The case study tests entity normalization across informal references:

### Challenge 1: Sponsor name variations
- "Greenline Renewables LLC" → `Sponsor(GRN-001)`
- "Greenline" → Same entity
- "GRN" → Same entity
- "the sponsor" (in context) → Same entity

### Challenge 2: Property references
- "Ironwood Office Park" → `Property(IRW-001)`
- "Ironwood" → Same entity
- "the property" (in context) → Same entity
- "234 Corporate Blvd" (address) → Same entity

### Challenge 3: Market sectors
- "Wyoming wind" → `Market(US-WIND-WY)`
- "WY wind market" → Same entity
- "Mountain West wind" → Same or related entity

### Challenge 4: Deal references
- "Greenline Wind Phase I" → `Deal(GLW-PH1-001)`
- "GLW Phase 1" → Same entity
- "the project" (in context) → Same entity
- Deal code in subject line → Same entity

## Ground Truth Testing

The `entities.yaml` file defines representative entities:
- 24 deals (across multiple asset classes)
- 15 sponsors
- 24 properties/assets
- 8 market sectors
- 3 analysts (Felix + 2 team members)

**Extraction accuracy metrics**:
1. **Entity recall**: Did we extract all entities mentioned in documents?
2. **Entity precision**: Are extracted entities correctly normalized?
3. **Alpha signal detection**: Did we catch hidden value and buried risks?
4. **Score calibration**: Do alpha scores align with investment outcomes?
5. **Relationship accuracy**: Are entity edges correctly identified?

## Success Criteria

Agent-let training is successful when:

1. **Entity extraction**: ≥90% recall, ≥85% precision
2. **Alpha signal detection**: ≥80% recall on major signals (±7-10 score range)
3. **Scoring calibration**: Alpha scores correlate with actual deal outcomes
4. **Entity normalization**: ≥85% accuracy on informal references
5. **Relationship extraction**: ≥75% of expected edges identified

---

**Domain**: Institutional investment management (multi-strategy)
**User**: Felix Prime - Senior Asset Manager, ACME Capital Partners
**Complexity**: Medium-high (60-80 deals per quarter, 6 entity types, complex relationships)
**Input documents**: 77 deal documents (mix of underwriting memos, emails, term sheets, reports)
**Ground truth entities**: ~70 entities defined in `entities.yaml`
**Operating model**: Felix + AI agents triage deal flow, extract alpha, rank opportunities for investment committee
