# Delivery Receipt Examples

Example delivery receipts for testing the po-receipt-matcher agent.

## Example 1: Perfect match - full delivery

```
===============================
DELIVERY NOTE
===============================
Greenfield Nurseries Ltd
Maidstone, Kent
Tel: +44 1622 456789

Your PO: PO-2024-045
Delivery Date: 28 October 2024
Driver: T. Morgan

ITEMS DELIVERED:
- PP-1001-SM  Monstera Deliciosa (Medium)    Qty: 20  @ £45.00
- PP-2015-SM  Snake Plant                    Qty: 30  @ £28.00

All plants in excellent condition.
Received by: Luis Rodriguez
Signature: [signed]
```

**Expected extraction**:
- receipt_id: REC-2024-089 (auto-generated)
- matched_po_id: PO-2024-045 (via search_knowledge_base)
- supplier_id: SUP-001 (via search_knowledge_base or lookup_entity)
- delivery_date: 2024-10-28
- items_delivered: [PP-1001-SM qty 20, PP-2015-SM qty 30]
- discrepancies: [] (perfect match)
- match_confidence: 1.0
- status: matched
- requires_employee_review: false

**Expected tool calls**:
1. `search_knowledge_base(query="supplier: Greenfield Nurseries", tenant_id="percolating-plants")` → find supplier:SUP-001
2. `search_knowledge_base(query="purchase_order:PO-2024-045", tenant_id="percolating-plants")` → PO details
3. `lookup_entity(entity_id="product:PP-1001-SM", tenant_id="percolating-plants")` → validate exists
4. `lookup_entity(entity_id="product:PP-2015-SM", tenant_id="percolating-plants")` → validate exists

## Example 2: Quantity discrepancy - partial delivery

```
===============================
DELIVERY NOTE
===============================
Rare Botanicals Europe B.V.
Amsterdam, Netherlands
Tel: +31 20 555 1234

Reference: PO-2024-078
Delivery: 01 November 2024

ITEMS:
- PP-3045-SM  Philodendron Pink Princess   Qty: 8  @ €110.00

NOTE FROM SUPPLIER:
Unfortunately 4 plants were damaged during transit due to temperature
drop in transport. Replacement shipment of 4 plants will be sent next
week at no additional charge.

Regards,
Daan van Bergen
```

**Expected extraction**:
- receipt_id: REC-2024-095
- matched_po_id: PO-2024-078
- supplier_id: SUP-003 (Rare Botanicals Europe)
- delivery_date: 2024-11-01
- items_delivered:
  - product_code: PP-3045-SM
  - quantity_delivered: 8
  - quantity_ordered: 12 (from PO)
  - condition: good
  - notes: "4 damaged in transit, replacement coming"
- discrepancies:
  - type: quantity_mismatch, expected: "12", actual: "8", severity: moderate
  - type: damaged_goods, expected: "12 good", actual: "4 damaged", severity: critical
- match_confidence: 1.0
- status: partial_match
- requires_employee_review: true

**Expected tool calls**:
1. `search_knowledge_base(query="supplier: Rare Botanicals Europe", tenant_id="percolating-plants")` → find supplier:SUP-003
2. `search_knowledge_base(query="purchase_order:PO-2024-078", tenant_id="percolating-plants")` → PO expecting 12 units
3. `lookup_entity(entity_id="product:PP-3045-SM", tenant_id="percolating-plants")` → get product details
4. Compare quantities: 8 vs 12 = discrepancy

## Example 3: New product with employee authorization

```
===============================
DELIVERY NOTE
===============================
Shipton Japanese Gardens
Henley-on-Thames, Oxfordshire

PO Reference: PO-2024-082
Delivered: 01 November 2024

ITEMS:
- PP-4012-LG  Japanese Maple (Acer palmatum)      Qty: 5  @ £145.00

ADDITIONAL ITEMS (as discussed with Elena):
- NEW ITEM: Dwarf Japanese Maple 'Crimson Queen'  Qty: 3  @ £95.00
  Catalog code: PP-4013-MD
  Size: Medium (60cm potted)

Note: Elena approved this new variety for our catalog. Beautiful compact form,
perfect for small gardens and containers. Limited availability - only 10
specimens from our autumn propagation.

Contact: Takeshi Nakamura
```

**Expected extraction**:
- receipt_id: REC-2024-096
- matched_po_id: PO-2024-082
- supplier_id: SUP-007
- delivery_date: 2024-11-01
- items_delivered:
  - PP-4012-LG: qty 5, condition: good
  - PP-4013-MD: qty 3, condition: good, notes: "New product - Elena approved"
- discrepancies:
  - type: extra_item, product_code: PP-4013-MD, expected: "0", actual: "3", severity: minor
- new_products_detected:
  - product_code: PP-4013-MD
  - name: "Dwarf Japanese Maple 'Crimson Queen'"
  - authorized_by: "Elena"
- status: matched
- requires_employee_review: true

**Expected tool calls**:
1. `search_knowledge_base(query="supplier: Shipton Japanese Gardens", tenant_id="percolating-plants")` → find supplier:SUP-007
2. `search_knowledge_base(query="purchase_order:PO-2024-082", tenant_id="percolating-plants")` → PO for PP-4012-LG only
3. `lookup_entity(entity_id="product:PP-4013-MD", tenant_id="percolating-plants")` → null (doesn't exist yet)
4. `search_knowledge_base(query="employee: Elena", tenant_id="percolating-plants")` → find EMP-001 (Elena Vasquez)
5. Agent detects new product with employee authorization

**Key behavior**: Agent should flag for employee review to create the new product entity

## Example 4: No matching PO

```
===============================
DELIVERY NOTE
===============================
Heritage Plants & Trees
Exeter, Devon

Delivery: 01 November 2024
Invoice: INV-2024-556

ITEMS:
- PP-1002-LG  Fiddle Leaf Fig  Qty: 10  @ £89.00

Note: This is a regular monthly stock order
```

**Expected extraction**:
- receipt_id: REC-2024-097
- matched_po_id: null (no PO found)
- supplier_id: SUP-002
- delivery_date: 2024-11-01
- items_delivered: [PP-1002-LG qty 10]
- discrepancies: []
- match_confidence: 0.0
- status: no_match
- requires_employee_review: true

**Expected tool calls**:
1. `search_knowledge_base(query="supplier: Heritage Plants & Trees", tenant_id="percolating-plants")` → find supplier:SUP-002
2. `search_knowledge_base(query="purchase_order:INV-2024-556", tenant_id="percolating-plants")` → null (not a PO reference)
3. `search_knowledge_base(query="purchase_order supplier:SUP-002 date:2024-10-15 to 2024-11-01", tenant_id="percolating-plants")` → no pending POs
4. Agent returns no_match status

## Testing commands

```bash
# Run po-receipt-matcher on example
percolate agent-run .testing/agents/po-receipt-matcher.json \
  --input ".testing/examples/delivery-receipt-example.md#example-1" \
  --tenant percolating-plants

# Verify discrepancy detection
percolate agent-run .testing/agents/po-receipt-matcher.json \
  --input ".testing/examples/delivery-receipt-example.md#example-2" \
  --expect discrepancies.length=2 \
  --expect status="partial_match"
```
