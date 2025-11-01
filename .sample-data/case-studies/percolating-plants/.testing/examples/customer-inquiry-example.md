# Customer Inquiry Examples

Example customer messages for testing the customer-inquiry agent.

## Example 1: Product recommendation request

```
From: james.park@yahoo.com
To: hello@percolatingplants.co.uk
Date: 2024-11-01 10:30:00
Subject: Plant for my apartment

Hi,

I'm looking for a plant for my small London apartment. The living room gets
decent light (bright but not direct sunlight). I'm quite busy so need something
that's forgiving if I forget to water it occasionally. Budget is around £40-60.

Can you recommend something?

Thanks,
James
```

**Expected extraction**:
- inquiry_type: product_inquiry
- extracted_requirements:
  - location: living room
  - light_conditions: bright indirect
  - space_size: small apartment
  - care_level_preference: easy
  - budget_gbp: 60
- sentiment: positive
- requires_response: true
- Agent should use `search_knowledge_base` with query="product: low maintenance bright indirect light" to find matching plants

## Example 2: Specific product order

```
Customer: Priya Sharma (priya.sharma@outlook.com)
Channel: website chat
Timestamp: 2024-11-01 14:20:00

Message: "Hi! I saw your PP-3045 on Instagram and would love to order one.
Can you deliver to Bethnal Green next week?"
```

**Expected extraction**:
- inquiry_type: order_request
- products_mentioned:
  - raw_reference: "PP-3045"
  - resolved_product_code: "PP-3045-SM" (via search_knowledge_base or lookup_entity)
  - confidence: 0.95
- sentiment: positive
- requires_response: true
- Agent should use `search_knowledge_base(query="product:PP-3045")` or `lookup_entity(entity_id="product:PP-3045-SM")` to resolve

## Example 3: Care question

```
From: sophie.henderson@gmail.com
To: support@percolatingplants.co.uk
Date: 2024-11-01 09:15:00
Subject: Monstera leaves turning yellow

Hi Charlotte,

I bought a Monstera from you last month (my order was in mid-January) and I'm
worried because some of the leaves are turning yellow at the edges. I've been
watering it once a week and it's in my living room near the window.

Is this normal or am I doing something wrong?

Thanks,
Sophie
```

**Expected extraction**:
- inquiry_type: care_question
- products_mentioned:
  - raw_reference: "Monstera"
  - resolved_product_code: "PP-1001-SM" (via search_knowledge_base)
  - confidence: 0.85
- extracted_requirements:
  - location: living room near window
  - light_conditions: bright (inferred)
- sentiment: neutral
- requires_response: true
- Agent should use `search_knowledge_base(query="product: Monstera")` to find PP-1001-SM
- Agent could use `search_knowledge_base(query="customer: sophie.henderson@gmail.com")` then `lookup_entity(entity_id="customer:CUST-XXX", include_relationships=true)` to verify purchase history

## Example 4: Non-existent product (validation test)

```
Message: "Do you sell Blue Orchids (product code BO-5000)?"
```

**Expected extraction**:
- inquiry_type: product_inquiry
- products_mentioned:
  - raw_reference: "Blue Orchids (BO-5000)"
  - resolved_product_code: null (lookup_entity returns null)
  - confidence: 0.0
- sentiment: neutral
- requires_response: true
- **Key validation**: Agent must NOT invent product code. Should return null for resolved_product_code

## Testing commands

```bash
# Run customer-inquiry agent on example
percolate agent-run .testing/agents/customer-inquiry.json \
  --input ".testing/examples/customer-inquiry-example.md#example-1" \
  --tenant percolating-plants

# Expected tools called:
# 1. search_knowledge_base(query="product: low maintenance bright indirect light small apartment budget 60", tenant_id="percolating-plants", limit=10)
# 2. Results should include: [product:PP-1001-SM (Monstera £45), product:PP-2015-SM (Snake Plant £28)]
```
