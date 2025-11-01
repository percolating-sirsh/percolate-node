# Percolating Plants - REM Dreaming Case Study

## Domain

**Business**: Boutique sustainable plant shop based in Paris, France

**Owner**: Phillipe Poirot - Small business owner who manages most operations himself with the help of AI agents

**Data sources**:
- Product specifications and descriptions
- Email correspondence (suppliers, customers, occasional contractors)
- Business documentation (backstory, policies, procedures)
- Content notes (social media posts, product descriptions)
- Audio transcripts (supplier calls, customer interactions, personal notes)

**Operating context**:
- Single shop location in Le Marais district, Paris
- Small e-commerce presence (website with online ordering)
- Phillipe manages operations solo with 2-3 part-time contractors for busy periods
- AI agents handle customer inquiries, inventory reconciliation, and knowledge management
- Supply network: 7 suppliers (French and broader European)
- Customer base: Mostly retail customers, occasional small business orders (cafés, boutique hotels)

## Agentic Framework

This case study includes specialized agent-lets that scan unstructured data and automatically index it in the REM database. Each agent is an expert in a specific domain task.

### Available Agents

#### 1. customer-inquiry (.testing/agents/customer-inquiry.json)

Extracts structured information from customer emails and messages.

**What it does**:
- Classifies customer intent (product inquiry, order request, care question)
- Resolves product references ("Monstera" → PP-1001-SM or "PP-3045" → PP-3045-SM)
- Extracts customer requirements (location, light, budget, care level)
- Creates Moment for this interaction
- Links customer to products via entity edges

**MCP tools used** (generic Percolate tools):
- `search_knowledge_base`: Find entities by query (e.g., "product: low maintenance bright indirect")
- `lookup_entity`: Resolve exact entity IDs (e.g., "product:PP-1001-SM", "customer:CUST-1001")

**Example**:
```
Input: "Je cherche une grande plante pour mon salon, lumière indirecte, peu d'entretien, budget 50-80€"
(Translation: "I want a large plant for my living room, bright indirect light, low maintenance, budget €50-80")

Output:
- inquiry_type: product_inquiry
- requirements: {location: "living room", light: "bright indirect", care: "easy", budget: 80}
- suggested_products: [PP-1001-SM, PP-2015-SM]
- moment_created: MOM-2024-001 (type: customer_inquiry)
```

**Key rule**: Customers cannot invent new products. Agent always uses search/lookup to find existing products.

#### 2. po-receipt-matcher (.testing/agents/po-receipt-matcher.json)

Compares purchase orders to delivery receipts and creates relationships.

**What it does**:
- Extracts delivery receipt information
- Finds matching purchase order (by reference or supplier+date)
- Validates line items (quantities, prices, condition)
- Flags discrepancies (quantity mismatch, damaged goods, missing items)
- Creates receipt entity and links to PO
- Updates PO status

**MCP tools used** (generic Percolate tools):
- `search_knowledge_base`: Search for entities by query (e.g., "purchase_order:PO-2024-045", "supplier: Greenfield Nurseries")
- `lookup_entity`: Look up specific entities (e.g., "product:PP-1001-SM", "supplier:SUP-001", "employee:EMP-001")

**Example**:
```
Input: Delivery receipt from SUP-001 for PO-2024-045

Output:
- receipt_id: REC-2024-089
- matched_po_id: PO-2024-045
- items: 20x PP-1001-SM, 30x PP-2015-SM
- discrepancies: [] (perfect match)
- edges_created:
  - REC-2024-089 -[FULFILLS]-> PO-2024-045
  - REC-2024-089 -[DELIVERED_BY]-> SUP-001
  - REC-2024-089 -[CONTAINS]-> PP-1001-SM, PP-2015-SM
```

**Key rule**: Only Phillipe (the owner) can authorize new products via PO comments. Agent checks for owner authorization before creating products.

### Natural Language Query Workflow

These agents enable natural language queries about indexed data:

**Query**: "What product did customer CUST-1005 inquire about and how much does it cost?"

**Resolution**:
1. Find customer inquiry moment: `search_knowledge_base(query="customer:CUST-1005 inquiry", ...)`
2. Traverse edges: `CUST-1005 -[INQUIRED_ABOUT]-> PP-3045-SM`
3. Lookup product: `lookup_entity(entity_id="product:PP-3045-SM", include_relationships=true)`
4. Return: "Customer inquired about Pink Princess Philodendron (PP-3045-SM), €125.00"

**Query**: "What was the order document corresponding to purchase order PO-2024-045?"

**Resolution**:
1. Lookup PO: `search_knowledge_base(query="purchase_order:PO-2024-045", ...)`
2. Traverse edges: `PO-2024-045 <-[FULFILLS]- REC-2024-089`
3. Lookup receipt: `lookup_entity(entity_id="receipt:REC-2024-089")`
4. Return: "Delivery receipt REC-2024-089 delivered on 2024-10-28 from Greenfield Nurseries"

### Agent Workflow

```
Unstructured Document → Agent-let → Structured Output + Entity Edges + Moments

Example: Customer email arrives
├─> customer-inquiry agent processes it
├─> Extracts: {inquiry_type, products, requirements, sentiment}
├─> Creates Moment: MOM-2024-001 (customer_inquiry)
├─> Creates edges: Customer -[INQUIRED_ABOUT]-> Product
└─> Indexed in REM database for natural language queries
```

## Custom Ontology

Agent-lets extract the following domain models from unstructured data:

### Product specification

```python
from pydantic import BaseModel, Field
from decimal import Decimal
from typing import Literal

class ProductSpec(BaseModel):
    """Structured product information extracted from documents."""

    product_code: str = Field(pattern=r"^PP-\d{4}-[A-Z]{2}$")
    name: str
    category: Literal[
        "Indoor - Statement",
        "Indoor - Low Maintenance",
        "Indoor - Specialty",
        "Indoor - Rare",
        "Outdoor - Perennial",
        "Outdoor - Ornamental Tree",
        "Accessories - Care",
        "Accessories - Pots"
    ]
    price_eur: Decimal
    stock_level: int
    supplier_id: str = Field(pattern=r"^SUP-\d{3}$")
    size: str
    care_level: Literal["Easy", "Moderate", "Challenging", "N/A"]
    light_requirement: str
```

### Commercial order

```python
from datetime import date
from typing import Optional

class OrderItem(BaseModel):
    product_code: str
    quantity: int
    unit_price: Decimal

class CommercialOrder(BaseModel):
    """Commercial B2B order extracted from emails or documents."""

    order_id: Optional[str] = None
    customer_id: str
    customer_name: str
    managed_by: str  # Usually "Phillipe" (owner handles most orders)
    order_date: date
    total_value: Decimal
    items: list[OrderItem]
    delivery_address: str
    payment_terms: str
    notes: Optional[str] = None
```

### Supplier relationship

```python
class SupplierContact(BaseModel):
    """Supplier information and relationship metadata."""

    supplier_id: str
    name: str
    location: str  # City, Country
    contact_person: str
    email: str
    phone: str
    specialty: str
    payment_terms: str
    certification: Optional[str] = None
    products_supplied: list[str]  # Product codes
```

### Customer interaction

```python
from datetime import datetime

class CustomerInteraction(BaseModel):
    """Customer service or sales interaction."""

    customer_id: str
    customer_name: str
    interaction_type: Literal["support_request", "sales_inquiry", "complaint", "feedback"]
    interaction_date: datetime
    handled_by: str  # Usually "Phillipe" or "agent" (AI agents handle initial triage)
    products_mentioned: list[str]
    issue_description: Optional[str] = None
    resolution: Optional[str] = None
    sentiment: Literal["positive", "neutral", "negative"]
```

## Entity Types

The ontology defines 5 core entity types:

### 1. Product
- **ID format**: `PP-XXXX-YY` (e.g., `PP-1001-SM`)
- **Properties**: name, category, price, stock, supplier, care requirements
- **Inference**: Extract from product specs, emails, orders, reviews

### 2. Supplier
- **ID format**: `SUP-XXX` (e.g., `SUP-001`)
- **Properties**: name, location, contact person, specialty, certifications
- **Inference**: Extract from supplier emails, product sources, company docs

### 3. Customer
- **ID format**:
  - Retail: `CUST-1XXX` (e.g., `CUST-1001`)
  - Commercial: `CUST-2XXX` (e.g., `CUST-2002`)
- **Properties**: name, email, address, customer type, purchase history
- **Inference**: Extract from emails, orders, reviews, mentions

### 4. Contractor
- **ID format**: `CON-XXX` (e.g., `CON-001`)
- **Properties**: name, role (e.g., "weekend help", "delivery"), availability, contact
- **Note**: Phillipe (owner) is `EMP-001`, contractors are CON-XXX
- **Inference**: Extract from scheduling notes, email signatures, payment records

### 5. Order
- **ID format**: `ORD-YYYY-XXX` (e.g., `ORD-2024-156`)
- **Properties**: customer, items, total, date, status, account manager
- **Inference**: Extract from commercial emails, order confirmations

## Edge Types

Entity relationships are extracted as typed edges:

### Supply chain edges
- `SUPPLIES`: Supplier → Product (who provides what)
- `PURCHASED_BY`: Product → Customer (purchase history)
- `RECOMMENDED_FOR`: Product → Product (related/alternative products)

### Organizational edges
- `MANAGED_BY`: Customer → Owner (Phillipe handles key accounts)
- `ASSISTED_BY`: Order → Contractor (part-time help with fulfillment)
- `DELEGATED_TO`: Task → Agent (AI agents handle specific workflows)

### Communication edges
- `CONTACTED`: Owner/Contractor ↔ Supplier (correspondence)
- `INTERACTED_WITH`: Owner/Agent ↔ Customer (support, sales)
- `MENTIONED_IN`: Product → Document (product references)

### Temporal edges
- `ORDERED`: Customer → Product @ timestamp (purchase events)
- `RESTOCKED`: Supplier → Product @ timestamp (inventory events)
- `REVIEWED`: Customer → Product @ timestamp (customer feedback)

## Expected Entity Paths

Agent-lets should extract these relationship paths:

### Path 1: Supply chain
```
Supplier(SUP-003) -[SUPPLIES]->
Product(PP-3045-SM) -[PURCHASED_BY]->
Customer(CUST-1005)
```

**Query enabled**: "Which customers buy products from European suppliers?"

### Path 2: Business operations
```
Customer(CUST-2002) -[MANAGED_BY]->
Owner(EMP-001/Phillipe) -[CONTACTED]->
Supplier(SUP-001)
```

**Query enabled**: "What suppliers does Phillipe work with for commercial clients?"

### Path 3: Customer journey
```
Customer(CUST-1001) -[PURCHASED]->
Product(PP-1001-SM) -[SUPPORT_REQUEST]->
Agent(customer-inquiry) -[ESCALATED_TO]-> Owner(Phillipe)
```

**Query enabled**: "What's Sophie's interaction history and did it need Phillipe's attention?"

### Path 4: Product recommendations
```
Product(PP-1001-SM) -[RECOMMENDED_FOR]->
Product(PP-2015-SM) -[SUPPLIED_BY]->
Supplier(SUP-001)
```

**Query enabled**: "Find alternative products from the same supplier"

## Entity Resolution Challenges

The case study tests entity normalization across informal references:

### Challenge 1: Name variations
- "Sophie" → `Customer(Sophie Henderson, CUST-1001)`
- "Sophie H." → Same entity
- "Ms. Henderson" → Same entity

### Challenge 2: Supplier references
- "Daan" → `Supplier(Daan van Bergen, SUP-003)`
- "Rare Botanicals" → Same entity
- "Our Amsterdam supplier" → Same entity

### Challenge 3: Product mentions
- "Monstera" → `Product(Monstera Deliciosa, PP-1001-SM)`
- "PP-1001" → Same entity
- "Swiss cheese plant" → Same entity (common name)

### Challenge 4: Owner and contractor references
- "Phillipe" → `Owner(Phillipe Poirot, EMP-001)`
- "The owner" → Same entity
- "Boss" → Same entity
- "Marie" → `Contractor(Marie Dubois, CON-001)` (weekend shop assistant)

## Ground Truth Testing

The `entities.yaml` file defines 30 entities:
- 10 products
- 7 suppliers
- 10 customers (8 retail, 2 small commercial)
- 3 people (1 owner + 2 contractors)

**Extraction accuracy metrics**:
1. **Entity recall**: Did we extract all entities from `entities.yaml`?
2. **Entity precision**: Are extracted entities correctly normalized?
3. **Edge accuracy**: Are relationships correctly identified?
4. **Path completeness**: Can we traverse expected multi-hop paths?

## Quick start

```bash
# Navigate to case study directory
cd .sample-data/case-studies/percolating-plants

# Parse a document with customer inquiry agent
percolate parse documents/email-customer-service-monstera.md \
  --agent agents/customer-inquiry.yaml \
  --tenant-id percolating-plants

# Ask the agent a question
percolate ask agents/customer-inquiry.yaml \
  "What products would you recommend for low maintenance?"

# Test agent evaluation
percolate agent-eval agents/customer-inquiry.yaml \
  "Extract customer inquiry: I want a plant for my living room"

# Start API server with MCP endpoint
percolate serve
```

## Testing workflow

Integration tests validate agent extraction against ground truth entities:

```bash
# Run all integration tests
cd ../../..
uv run pytest percolate/tests/integration/

# Run agent-specific tests
uv run pytest percolate/tests/integration/agents/
```

**Ground truth validation**: The `entities.yaml` file defines known entities that should be extracted from documents. Integration tests measure extraction accuracy (recall, precision) against these ground truth entities.

## Success Criteria

Agent-let training is successful when:

1. **Entity extraction**: ≥95% recall, ≥90% precision
2. **Entity normalization**: ≥85% accuracy on informal references
3. **Edge extraction**: ≥80% of expected relationships identified
4. **Path traversal**: All multi-hop queries return correct results
5. **Schema conversion**: Extracted Pydantic models pass validation

---

**Domain**: Small boutique plant shop (sustainable, Paris-based)
**Owner**: Phillipe Poirot (solo operator with AI agents)
**Complexity**: Small-medium (30 entities, 5 types, ~60 relationships)
**Input documents**: 12 files (~35KB text)
**Ground truth entities**: 30 defined in `entities.yaml`
**Operating model**: Owner-operated with AI agents handling customer triage, inventory reconciliation, and knowledge retrieval
