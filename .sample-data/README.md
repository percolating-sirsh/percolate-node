# Sample data for REM Dreaming

This directory contains synthetic data for testing **REM Dreaming**: Percolate's framework for training agent-lets to extract structured knowledge from unstructured documents using custom customer ontologies.

## Quick start

### Using the CLI with sample data

```bash
# Parse a document with an agent
percolate parse \
  .sample-data/case-studies/acme-alpha/test-deal-simple.txt \
  --agent .sample-data/case-studies/acme-alpha/agentlets/alpha-extraction.yaml \
  --tenant-id acme-corp \
  --project alpha-deals

# Ask an agent a question
percolate ask \
  .sample-data/case-studies/acme-alpha/agentlets/alpha-extraction.yaml \
  "What are the key alpha signals in venture capital deals?"

# Start the API server (includes MCP endpoint)
percolate serve
```

### Running tests

Integration tests use this sample data:

```bash
# Run all integration tests
uv run pytest percolate/tests/integration/

# Run specific test suite
uv run pytest percolate/tests/integration/agents/
```

## What is REM Dreaming?

REM Dreaming transforms unstructured business documents into queryable knowledge graphs.

**Input**: Emails, PDFs, transcripts, spreadsheets
**Output**: Structured entities, relationships, and searchable indexes

The system extracts three types of structured knowledge:

1. **Resources**: Chunked documents with embeddings for semantic search
2. **Entities**: Globally unique identifiers, names, and their relationships
3. **Moments**: Temporal classifications tied to user interaction (not document narratives)

Agent-lets are trained extractors that convert unstructured content into this REM model according to a customer's custom ontology.

## Why "REM Dreaming"?

Like REM sleep consolidates daily experiences into long-term memory, REM Dreaming consolidates unstructured business data into structured knowledge. The system "dreams" through documents to extract meaningful patterns and relationships.

**REM** = **R**esources-**E**ntities-**M**oments (the three-layer knowledge model)
**Dreaming** = The iterative process of extracting and refining knowledge from unstructured data

### Agent-lets as extractors

Agent-lets are JSON schema-defined AI skills that extract structure from unstructured data. They operate in two modes:

1. **Schema extraction**: Convert documents to customer-defined Pydantic models (e.g., `ProductSpec`, `CustomerOrder`, `SupplierContract`)
2. **Index extraction**: Extract entity relationships as graph paths for multi-stage querying

Example entity path extraction:
```
Document: "Elena contacted Daan at Rare Botanicals to order Pink Princess philodendrons"

Extracted path:
Employee(Elena, EMP-001) -[CONTACTED, 2024-03-15, weight=1.0]->
Supplier(Daan van Bergen, SUP-003) -[SUPPLIES, ongoing, weight=0.8]->
Product(Pink Princess, PP-3045-SM)
```

This path becomes queryable: "Who supplies rare plants?" or "What's Elena's supplier network?"

### Multi-stage indexing

Unlike simple keyword or vector search, REM Dreaming creates **indexes** that enable complex queries:

- **Entity index**: `entity:{tenant_id}:{entity_id}` → entity properties
- **Edge index**: `edge:{tenant_id}:{src_id}:{dst_id}:{type}` → relationship metadata
- **Path index**: Store paths of length N (e.g., Employee→Supplier→Product)
- **Moment index**: `moment:{tenant_id}:{timestamp}:{moment_id}` → user interaction events

Indexes are extracted by specialized agent-lets alongside custom schema extraction.

### Moments vs document narratives

**Moments** are temporal classifications of **user interaction**, not document content:

- ✅ User uploads supplier contracts → Moment: "supplier_onboarding"
- ✅ User searches for customer history → Moment: "customer_support_research"
- ✅ User has chat session about sustainability → Moment: "sustainability_planning"

- ❌ Document describes historical events (stored as Resource chunks)
- ❌ Email discusses past orders (entities extracted, not moments)
- ❌ Transcript covers project timeline (not a moment)

Moments create narrative structure around **how users interact with their data**, enabling questions like: "What was I researching last week?" or "Show me all my supplier onboarding sessions."

## Case study: Percolating Plants

A London-based sustainable plant retailer operating since 2018. The company sells plants online and through four physical locations, working with UK and European suppliers.

## Data Structure

Current structure with the Percolating Plants case study:

```
.sample-data/
├── case-studies/
│   └── percolating-plants/
│       ├── about.md                   # Case study description and ontology
│       ├── entities.yaml              # Ground truth entities (for testing)
│       ├── agents/                    # Agent-let schemas
│       │   ├── customer-inquiry.yaml      # Customer message extraction
│       │   ├── po-receipt-matcher.yaml    # PO/receipt reconciliation
│       │   └── README.md
│       ├── mcp-tools/                 # MCP tool definitions
│       │   ├── product-tools.yaml         # Product search/lookup
│       │   └── entity-tools.yaml          # Entity management
│       ├── tests/                     # Agent test cases
│       │   ├── customer-inquiry-test.md
│       │   └── po-receipt-test.md
│       ├── documents/                 # Documents to ingest
│       │   ├── email-commercial-wework-order.md
│       │   ├── email-customer-service-monstera.md
│       │   ├── email-supplier-order-pink-princess.md
│       │   ├── product-japanese-maple.md
│       │   ├── product-monstera-deliciosa.md
│       │   ├── product-pink-princess.md
│       │   ├── article-sustainable-plant-sourcing.md
│       │   └── blog-indoor-plants-london-apartments.md
│       └── transcripts/               # Audio transcription simulations
│           ├── customer-call-hoxton-hotel-2024-01.md
│           └── team-meeting-supplier-review-2024-02.md
└── README.md
```

### Case study structure

Each case study contains:

1. **about.md**: Description of the business domain and custom ontology (e.g., `ProductSpec`, `CommercialOrder`, `SupplierContract`)
2. **entities.yaml**: Ground truth entities (used for testing entity resolution and path extraction)
3. **agents/**: Agent-let schemas (YAML) for specialized extraction tasks
4. **mcp-tools/**: MCP tool definitions for entity operations
5. **tests/**: Test cases with expected outputs for validation
6. **documents/**: Unstructured documents to ingest (emails, product specs, articles, etc.)
7. **transcripts/**: Audio transcription simulations (meetings, calls)

### Testing workflow

```bash
# Parse documents with agent-lets
cd .sample-data/case-studies/percolating-plants

# Parse a document with an agent
percolate parse documents/email-customer-service-monstera.md \
  --agent agents/customer-inquiry.yaml \
  --tenant-id percolating-plants

# Ask an agent a question
percolate ask agents/customer-inquiry.yaml \
  "What products would you recommend for low maintenance?"

# Run agent evaluation tests
percolate agent-eval agents/customer-inquiry.yaml \
  "Extract customer inquiry from: I want a plant for my living room"
```

**Note**: Integration tests in `percolate/tests/integration/` use this sample data to validate agent extraction accuracy against ground truth entities defined in `entities.yaml`.

## How It Works

### Specialist agents scan and index

Agent-lets are JSON schema-defined specialists that automatically scan unstructured data and index it in the REM database. Each agent:

1. **Receives** unstructured input (email, PDF, transcript)
2. **Extracts** structured information using LLM + MCP tools
3. **Resolves** entities (product codes, customer names, supplier references)
4. **Creates** relationships (entity edges)
5. **Indexes** for natural language queries

**Example**: Customer inquiry agent
```
Input:  "I want a plant for my living room, low maintenance, budget £50"
↓
Extract: {intent: "product_inquiry", requirements: {care: "easy", budget: 50}}
↓
Resolve: product_search("low maintenance") → [PP-1001-SM, PP-2015-SM]
↓
Index:  Moment(customer_inquiry) + Edge(Customer→Product)
↓
Query:  "What did this customer inquire about?" → traverses graph
```

### Agent-lets extract dual outputs

Agent-lets process documents to extract both **structured schemas** and **entity relationships**:

**Schema extraction**: Documents → Pydantic models (e.g., `ProductSpec`, `CommercialOrder`)
**Index extraction**: Documents → Entity paths (e.g., Employee→Supplier→Product edges)

This dual extraction enables both **structured queries** ("Show all orders over £1000") and **graph traversal** ("Which customers buy from European suppliers?").

### Multi-stage indexing

The system creates multiple index types for complex queries:

- **Entity index**: `entity:{tenant_id}:{entity_id}` → Properties (name, type, metadata)
- **Edge index**: `edge:{tenant_id}:{src}:{dst}:{type}` → Relationship metadata (weight, timestamp)
- **Path index**: Store N-hop paths for graph traversal
- **Resource index**: Chunked documents with embeddings for semantic search

These indexes work together to answer questions that require multiple reasoning steps.

## Testing & Validation

These scenarios test agent-let extraction capabilities across Resources, Entities, and Moments.

### Test 1: Entity path extraction
**Input documents**:
- `email-supplier-order-pink-princess.md`
- `product-pink-princess.md`

**Expected entity paths**:
```
Employee(Elena Vasquez, EMP-001)
  -[NEGOTIATED_WITH, 2024-03-12, weight=1.0]->
Supplier(Daan van Bergen, SUP-003)
  -[SUPPLIES, ongoing, weight=0.8]->
Product(Pink Princess, PP-3045-SM)
  -[PURCHASED_BY, 2024-01-20, weight=0.6]->
Customer(Priya Sharma, CUST-1005)
```

**Multi-stage queries enabled**:
- "Who are Elena's supplier contacts?" (traverse Employee→Supplier edges)
- "What rare plants do we source from Europe?" (filter Supplier.location + Product.category)
- "Which customers buy rare plants?" (traverse Product←Customer edges where category='rare')

### Test 2: Custom ontology extraction
**Input document**: `email-commercial-wework-order.md`

**Customer ontology**: Commercial order schema
```python
class CommercialOrder(BaseModel):
    order_id: str
    customer_id: str
    account_manager: str
    order_date: date
    total_value: Decimal
    items: list[OrderItem]
    delivery_address: str
    payment_terms: str
```

**Expected extraction**: Agent-let converts unstructured email into typed `CommercialOrder` instance

**Indexes created**:
- Entity: Customer(WeWork Moorgate, CUST-2002)
- Entity: Employee(Aisha Patel, EMP-003)
- Edge: `Customer(CUST-2002) -[MANAGED_BY]-> Employee(EMP-003)`
- Edge: `Order(ORD-2024-156) -[PLACED_BY]-> Customer(CUST-2002)`

### Test 3: Multi-document entity resolution
**Input documents**:
- `email-customer-service-monstera.md` (mentions "Sophie")
- `product-monstera-deliciosa.md` (review by "Sophie H.")
- `entities.yaml` (formal: Sophie Henderson, CUST-1001)

**Expected entity resolution**:
- "Sophie" → normalize to `Customer(Sophie Henderson, CUST-1001)`
- "Sophie H." → normalize to same entity
- Create unified entity graph:

```
Customer(Sophie Henderson, CUST-1001)
  -[PURCHASED, 2024-01-15, weight=1.0]->
Product(Monstera Deliciosa, PP-1001-SM)
  -[SUPPORT_REQUEST, 2024-01-28, weight=0.7]->
Employee(Charlotte Mills, EMP-007)
```

### Test 4: Moment classification (user interaction)
**User action**: Uploads `company-backstory.md` and searches "sustainability"

**Expected moment extraction**:
```yaml
moment_id: MOM-2024-001
timestamp: 2024-11-01T14:23:00Z
tenant_id: tenant-001
type: knowledge_organization
classification: sustainability_research
context:
  - action: document_upload
  - query: "sustainability"
  - documents: [company-backstory.md, article-sustainable-plant-sourcing.md]
  - entities_engaged: [SUP-001, SUP-010]  # Suppliers related to sustainability
```

**NOT a moment**: Historical events described in documents (those are Resource chunks)

### Test 5: Hybrid search with path traversal
**Query**: "Find customers who bought products from European suppliers"

**Search strategy**:
1. Entity lookup: `Supplier` where `location.country != 'UK'`
2. Path traversal: `Supplier -[SUPPLIES]-> Product -[PURCHASED_BY]-> Customer`
3. Result fusion: Rank by purchase frequency + recency

**Expected results**:
- Priya Sharma (bought Pink Princess from SUP-003 Netherlands)
- Sophie Henderson (if she bought any Europe-sourced products)

**Indexes used**:
- `edge:{tenant_id}:SUP-003:PP-3045-SM:SUPPLIES`
- `edge:{tenant_id}:PP-3045-SM:CUST-1005:PURCHASED_BY`

## Usage

### Running a case study

```bash
# Navigate to case study
cd .sample-data/case-studies/percolating-plants

# Review the ontology
cat about.md

# Parse documents with agents
percolate parse documents/email-customer-service-monstera.md \
  --agent agents/customer-inquiry.yaml \
  --tenant-id percolating-plants

# Ask agents questions
percolate ask agents/customer-inquiry.yaml \
  "What products would you recommend for low maintenance?"

# Run integration tests with ground truth validation
cd ../../../
uv run pytest percolate/tests/integration/agents/
```

### Creating a new case study

```bash
# 1. Create case study directory structure
mkdir -p .sample-data/case-studies/my-business/{documents,agents}

# 2. Define the business domain and ontology
cat > .sample-data/case-studies/my-business/about.md <<'EOF'
# My Business Case Study

## Domain
[Description of the business and what data it generates]

## Custom Ontology
[Pydantic models for domain-specific extraction]
EOF

# 3. Create ground truth entities for testing
cat > .sample-data/case-studies/my-business/entities.yaml <<'EOF'
products:
  - product_id: "PROD-001"
    name: "Example Product"
EOF

# 4. Add sample documents
# Add .md, .pdf, .xlsx files to documents/

# 5. Create agent-let schemas
# Add YAML agent definitions to agents/

# 6. Test your agents
percolate parse documents/sample.md \
  --agent agents/my-agent.yaml \
  --tenant-id my-business
```

### Agent-let training

Use case study data to train agent-lets for:
- **Schema extraction**: Convert unstructured documents to Pydantic models
- **Entity normalization**: Resolve "Sophie" → "Sophie Henderson (CUST-1001)"
- **Path extraction**: Extract entity relationships as graph edges
- **Moment classification**: Identify user interaction patterns

---

## Appendix: Detailed Entity Listings

The following sections provide detailed entity information for the Percolating Plants case study.

### Entity Types

#### Products (10 entries)
- Indoor plants (statement, low-maintenance, rare varieties)
- Outdoor plants (perennials, ornamental trees)
- Accessories (plant food, pots)
- Format: `PP-XXXX-YY` product codes

#### Suppliers (10 entries)
- UK nurseries (Kent, Devon, Cornwall, etc.)
- European specialists (Netherlands)
- Packaging and accessories suppliers
- IDs: `SUP-001` through `SUP-010`

#### Customers (10 entries)
- Retail customers (individual buyers)
- Commercial clients (hotels, co-working spaces, property developers)
- IDs: `CUST-1001` through `CUST-2004`

#### Employees (10 entries)
- Leadership (founders)
- Operations (managers, coordinators)
- Retail (store managers)
- Specialists (horticulturists, marketing)
- IDs: `EMP-001` through `EMP-010`

### Document Types

#### Product Specifications
Detailed product descriptions including:
- Pricing and availability
- Supplier information
- Care requirements
- Customer reviews
- Related products

**Files**:
- `product-monstera-deliciosa.md` (PP-1001-SM)
- `product-pink-princess.md` (PP-3045-SM)
- `product-japanese-maple.md` (PP-4012-LG)

#### Email Correspondence
Business communications showing relationships:
- Supplier orders and negotiations
- Customer service interactions
- Commercial client quotes

**Files**:
- `email-supplier-order-pink-princess.md` (Elena → Daan at SUP-003)
- `email-customer-service-monstera.md` (Charlotte → Sophie CUST-1001)
- `email-commercial-wework-order.md` (Aisha → WeWork CUST-2002)

#### Content Marketing
Blog posts and industry articles:
- Plant care guides
- Sustainability thought leadership
- London-specific advice

**Files**:
- `blog-indoor-plants-london-apartments.md`
- `article-sustainable-plant-sourcing.md`

#### Company Documentation
- `company-backstory.md`: Full company profile and history

### Relationship Network

The data is designed to test relationship inference across documents:

#### Supplier Relationships
- **Greenfield Nurseries (SUP-001)** → supplies PP-1001-SM (Monstera), PP-2015-SM (Snake Plant)
- **Rare Botanicals Europe (SUP-003)** → supplies PP-3045-SM (Pink Princess)
- **Shipton Japanese Gardens (SUP-007)** → supplies PP-4012-LG (Japanese Maple)

#### Customer Interactions
- **Sophie Henderson (CUST-1001)** → purchased Monstera, received customer service
- **WeWork Moorgate (CUST-2002)** → commercial client, bulk orders
- **Berkeley Homes (CUST-2004)** → show homes, plant rehoming

#### Employee Roles
- **Elena Vasquez (EMP-001)** → supplier negotiations, content creation
- **Charlotte Mills (EMP-007)** → customer service
- **Aisha Patel (EMP-003)** → commercial sales, operations

#### Product References
Documents cross-reference products:
- Care guides recommend specific products
- Emails quote product codes
- Customer reviews mention products

### Data Characteristics

- **Realistic complexity**: Names, prices, locations based on actual London geography
- **Cross-references**: Documents cite each other naturally
- **Temporal markers**: Dates, order histories, seasonal references
- **Relationship types**:
  - Commercial (B2B, B2C)
  - Supply chain (supplier → company → customer)
  - Organizational (employees, departments)
  - Product (categories, recommendations, alternatives)

## Case study patterns

### Pattern 1: E-commerce retail (Percolating Plants)
**Domain**: Product catalog, supplier network, customer orders, employee roles

**Ontology**:
- `Product`, `Supplier`, `Customer`, `Employee`, `Order`
- Edge types: `SUPPLIES`, `PURCHASED_BY`, `MANAGED_BY`, `CONTACTED`

**Test scenarios**:
- Entity resolution across informal mentions
- Supply chain path traversal
- Customer journey reconstruction
- Commercial relationship tracking

### Pattern 2: Professional services (future)
**Domain**: Clients, projects, deliverables, consultants

**Ontology**:
- `Client`, `Project`, `Deliverable`, `Consultant`, `Meeting`
- Edge types: `ASSIGNED_TO`, `DELIVERED_TO`, `ATTENDED_BY`, `DEPENDS_ON`

### Pattern 3: Research organization (future)
**Domain**: Publications, researchers, grants, collaborations

**Ontology**:
- `Publication`, `Researcher`, `Grant`, `Institution`, `Dataset`
- Edge types: `AUTHORED_BY`, `FUNDED_BY`, `CITES`, `COLLABORATES_WITH`

### Adding new case studies

When creating new case studies:
1. Define 3-5 core entity types for the domain
2. Identify 5-10 edge types that connect entities
3. Create 10-20 input documents with natural cross-references
4. Define ground truth `entities.yaml` with expected extractions
5. Document custom Pydantic schemas in `about.md`

---

**Purpose**: REM Dreaming framework testing
**Status**: Synthetic data for development use only
**License**: MIT (for testing only)
