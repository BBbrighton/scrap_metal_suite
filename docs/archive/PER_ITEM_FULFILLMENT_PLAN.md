# Per-Item Fulfillment Tracking - Implementation Plan

**Date:** 2025-12-27
**Status:** PLANNING - Needs Discussion

---

## Overview

Currently, fulfillment tracking on POS Order is **aggregated only**:
- `contracted_weight` = sum of all items
- `total_received` = sum of all allocated weights from drop-offs
- `fulfillment_percent` = total_received / contracted_weight

**Problem:** We cannot track which specific items were fulfilled vs. which are still outstanding.

**Goal:** Track fulfillment **per-item** on POS Order, and auto-populate expected items on Dropoff when orders are linked.

---

## Current Data Model

### POS Order
```
POS Order (parent)
├── order_items: Table (POS Order Item)  ← Contracted/expected items
│   ├── item_code: Link → Item
│   ├── weight: Float                     ← Indicated/promised weight
│   └── uom: Link → UOM
│
├── items: Table (POS Order Weighed Item) ← Currently unused/broken
│   ├── scrap_weight: Link
│   ├── item_code, weight
│
├── contracted_weight: Float              ← Sum of order_items
├── total_received: Float                 ← Sum from all drop-offs (aggregated)
├── fulfillment_percent: Percent
└── fulfillment_status: Select            ← Pending/Partial/Fulfilled/Over-delivered
```

### Dropoff
```
Dropoff (parent)
├── orders: Table (Dropoff Order)         ← Links to POS Orders
│   ├── pos_order: Link → POS Order
│   └── allocated_weight: Float           ← Total allocated (aggregated)
│
├── expected_items: Table (Dropoff Expected Item)  ← Manual entry, NOT linked to orders
│   ├── item: Link → Item
│   └── indicated_weight: Float
│
├── actual_items: Table (Dropoff Actual Item)     ← From Scrap Weight (read-only)
│   ├── item, actual_weight
│
└── item_summary: Table                   ← Aggregated totals by item
```

---

## Proposed Changes

### 1. New Child Table: POS Order Item Fulfillment

Track per-item fulfillment on POS Order.

**DocType:** `POS Order Item Fulfillment` (child table)

| Field | Type | Description |
|-------|------|-------------|
| `item_code` | Link → Item | The item being tracked |
| `item_name` | Data (fetch) | Item name |
| `contracted_weight` | Float | From order_items (read-only) |
| `received_weight` | Float | Sum of allocations (read-only) |
| `remaining_weight` | Float | contracted - received (computed) |
| `fulfillment_percent` | Percent | received/contracted * 100 |
| `status` | Select | Pending/Partial/Fulfilled/Over-delivered |

**On POS Order:**
- Add new field: `item_fulfillment` (Table → POS Order Item Fulfillment)
- This table is auto-synced from `order_items` and updated when drop-offs close

### 2. Enhance Dropoff Order Child Table

Track per-item allocation, not just total.

**DocType:** `Dropoff Order` (modify existing)

Current fields:
- `pos_order`: Link → POS Order
- `allocated_weight`: Float

**New fields to add:**
- `allocated_items`: Table (Dropoff Order Item) - NEW child table

**DocType:** `Dropoff Order Item` (new child table)

| Field | Type | Description |
|-------|------|-------------|
| `item_code` | Link → Item | Item allocated |
| `item_name` | Data | Item name |
| `contracted_weight` | Float | From order's order_items (read-only) |
| `remaining_before` | Float | Remaining before this dropoff (read-only) |
| `allocated_weight` | Float | Weight allocated in this dropoff |

### 3. Auto-Populate Expected Items from Orders

When orders are linked to Dropoff, auto-populate `expected_items` from the orders' `order_items`.

**Logic (in Dropoff controller):**
```python
def auto_populate_expected_items(self):
    """When orders change, sync expected_items from linked order_items."""
    self.expected_items = []

    # Aggregate items across all linked orders
    item_totals = {}  # {item_code: {"item_name": str, "contracted": float, "remaining": float}}

    for order_row in self.orders:
        order_items = frappe.get_all("POS Order Item",
            filters={"parent": order_row.pos_order},
            fields=["item_code", "item_name", "weight"]
        )

        for item in order_items:
            if item.item_code not in item_totals:
                # Get remaining unfulfilled from POS Order
                remaining = _get_item_remaining(order_row.pos_order, item.item_code)
                item_totals[item.item_code] = {
                    "item_name": item.item_name,
                    "contracted": item.weight,
                    "remaining": remaining
                }
            else:
                item_totals[item.item_code]["contracted"] += item.weight
                item_totals[item.item_code]["remaining"] += _get_item_remaining(...)

    # Populate expected_items with remaining to fulfill
    for item_code, data in item_totals.items():
        self.append("expected_items", {
            "item": item_code,
            "item_name": data["item_name"],
            "indicated_weight": data["remaining"]  # User can edit this
        })
```

### 4. Enhance Dropoff Expected Item

**DocType:** `Dropoff Expected Item` (modify existing)

Current fields:
- `item`: Link → Item
- `item_name`: Data
- `indicated_weight`: Float (editable)

**New fields to add:**
- `from_order`: Link → POS Order (read-only) - which order this came from
- `contracted_weight`: Float (read-only) - original contracted amount
- `remaining_unfulfilled`: Float (read-only) - what's left to fulfill
- `indicated_weight`: Float (editable) - user's indicated weight for THIS dropoff

**UI Display:**
```
| Item          | Contracted | Remaining | Indicated (edit) |
|---------------|------------|-----------|------------------|
| Copper Wire   | 500 kg     | 350 kg    | [____] kg        |
| Aluminum Cans | 200 kg     | 200 kg    | [____] kg        |
```

### 5. Per-Item Allocation at Dropoff Close

When Dropoff closes, allocate weights per-item (not just total).

**Current logic (aggregated):**
```python
def allocate_weights_if_closing(self):
    # Pro-rata based on total contracted
    for order_row in self.orders:
        ratio = contracted / total_contracted
        order_row.allocated_weight = total_scrap * ratio
```

**New logic (per-item):**
```python
def allocate_weights_if_closing(self):
    # Get actual items from Scrap Weight records
    actual_by_item = self._get_actual_items_aggregated()  # {item_code: weight}

    # For each actual item, allocate to orders that expected it
    for item_code, actual_weight in actual_by_item.items():
        # Find orders that have this item in order_items
        orders_with_item = []
        for order_row in self.orders:
            order_item = self._get_order_item(order_row.pos_order, item_code)
            if order_item:
                orders_with_item.append({
                    "order": order_row,
                    "contracted": order_item.weight,
                    "remaining": self._get_item_remaining(order_row.pos_order, item_code)
                })

        # Allocate pro-rata among orders that expected this item
        total_remaining = sum(o["remaining"] for o in orders_with_item)
        for order_data in orders_with_item:
            if total_remaining > 0:
                ratio = order_data["remaining"] / total_remaining
            else:
                ratio = 1 / len(orders_with_item)

            allocated = actual_weight * ratio
            self._record_item_allocation(order_data["order"], item_code, allocated)
```

### 6. Update POS Order Fulfillment Per-Item

After Dropoff closes, update `item_fulfillment` on POS Order.

**Logic:**
```python
def update_pos_order_fulfillment(pos_order_name):
    order = frappe.get_doc("POS Order", pos_order_name)

    # Clear and rebuild item_fulfillment from allocations
    order.item_fulfillment = []

    for order_item in order.order_items:
        item_code = order_item.item_code
        contracted = order_item.weight

        # Sum allocations for this item from all closed dropoffs
        received = get_total_allocated_for_item(pos_order_name, item_code)
        remaining = max(0, contracted - received)
        percent = (received / contracted * 100) if contracted else 0

        order.append("item_fulfillment", {
            "item_code": item_code,
            "item_name": order_item.item_name,
            "contracted_weight": contracted,
            "received_weight": received,
            "remaining_weight": remaining,
            "fulfillment_percent": percent,
            "status": _get_item_fulfillment_status(percent)
        })

    order.save()
```

---

## Implementation Steps

### Phase A: New DocTypes

1. **Create `POS Order Item Fulfillment`** (child table)
   - Fields: item_code, item_name, contracted_weight, received_weight, remaining_weight, fulfillment_percent, status

2. **Create `Dropoff Order Item`** (child table for per-item allocation)
   - Fields: item_code, item_name, contracted_weight, remaining_before, allocated_weight

3. **Modify `Dropoff Expected Item`** (add read-only fields)
   - Add: from_order, contracted_weight, remaining_unfulfilled

4. **Modify `POS Order`**
   - Add: item_fulfillment (Table → POS Order Item Fulfillment)

5. **Modify `Dropoff Order`**
   - Add: allocated_items (Table → Dropoff Order Item)

### Phase B: Controller Logic

1. **Dropoff controller - `auto_populate_expected_items()`**
   - On orders change, populate expected_items from order's order_items
   - Show contracted weight and remaining unfulfilled (read-only)
   - User only edits `indicated_weight`

2. **Dropoff controller - `allocate_weights_if_closing()` update**
   - Change from aggregated to per-item allocation
   - Populate `Dropoff Order Item` entries
   - Maintain backward compatibility with `allocated_weight` total

3. **POS Order controller - `update_item_fulfillment()`**
   - After allocation, rebuild `item_fulfillment` table
   - Calculate per-item status

### Phase C: API Updates

1. **`get_dropoff_details()`** - Include per-item remaining from orders
2. **`complete_dropoff()`** - Return per-item allocation results
3. New: **`get_order_item_fulfillment(pos_order)`** - Get per-item fulfillment status

### Phase D: UI Updates (Deferred)

- Dropoff form: Show expected items with contracted/remaining columns
- POS Order form: Show item_fulfillment table
- Terminal UI: Display per-item progress

---

## Data Flow Diagram

```
POS Order Created
├── order_items populated (contracted per item)
└── item_fulfillment initialized (all Pending)

                    ↓

Dropoff Created, Orders Linked
├── auto_populate_expected_items() runs
├── expected_items populated from order_items
│   └── Shows: item, contracted, remaining, indicated_weight (editable)
└── User enters indicated_weight for each item

                    ↓

Scrap Weighing (Terminal)
├── actual_items recorded per Scrap Weight
└── item_summary aggregated on Dropoff

                    ↓

Dropoff Closed
├── allocate_weights_if_closing() (per-item)
│   ├── Creates Dropoff Order Item entries
│   └── Updates Dropoff Order.allocated_weight (total)
└── update_pos_orders_if_closed()
    └── Updates POS Order.item_fulfillment (per item)

                    ↓

POS Order Updated
├── item_fulfillment shows per-item status
├── total_received = sum of item received_weight
└── fulfillment_status computed from worst item status
```

---

## Questions for Discussion

### Q1: Handling Items Not in Original Order

**Scenario:** Supplier delivers Copper Wire (in order) + Aluminum Cans (NOT in order)

**Options:**
- A) Reject: Only allow items from linked orders
- B) Accept as "Unallocated": Goes to unallocated_items
- C) Accept and add to order: Auto-add new line to order_items

**Recommendation:** Option B - Accept as unallocated, allow manager to decide later.

### Q2: Over-Delivery Per Item

**Scenario:** Order has 100kg Copper. Dropoff delivers 150kg Copper.

**Options:**
- A) Allow over-allocation, mark item as "Over-delivered"
- B) Cap at contracted, excess goes to unallocated
- C) Allow with warning

**Recommendation:** Option A - Allow, track with status.

### Q3: Multiple Orders with Same Item

**Scenario:**
- Order A: 100kg Copper
- Order B: 50kg Copper
- Dropoff delivers: 120kg Copper

**Question:** How to allocate?

**Options:**
- A) Pro-rata by contracted (80kg to A, 40kg to B)
- B) Pro-rata by remaining unfulfilled
- C) FIFO (fill Order A first, then B)
- D) User chooses allocation

**Recommendation:** Option B - Pro-rata by remaining unfulfilled.

### Q4: Reweight Impact

**Scenario:** After dropoff closes, truck is reweighed.

**Question:** Should per-item allocations be recalculated?

**Current Issue:** `allocate_weights_if_closing()` only runs when transitioning TO Closed, not when already Closed.

**This ties into Known Issue #1 from DROPOFF_IMPLEMENTATION_STATUS.md**

---

## Files to Modify

| File | Changes |
|------|---------|
| New: `doctype/pos_order_item_fulfillment/` | New child table DocType |
| New: `doctype/dropoff_order_item/` | New child table DocType |
| `doctype/dropoff_expected_item/dropoff_expected_item.json` | Add from_order, contracted, remaining fields |
| `doctype/pos_order/pos_order.json` | Add item_fulfillment table |
| `doctype/dropoff_order/dropoff_order.json` | Add allocated_items table |
| `doctype/dropoff/dropoff.py` | auto_populate_expected_items(), update allocate_weights_if_closing() |
| `api/v1/dropoff.py` | Update get_dropoff_details(), complete_dropoff() |

---

## Migration Considerations

Existing data:
- POS Orders with `order_items` → Auto-populate `item_fulfillment` (all Pending initially)
- Existing Dropoffs with allocations → Leave as aggregated (no per-item breakdown)
- Future dropoffs → Use new per-item logic

---

*This plan requires discussion before implementation. Key decision points marked in "Questions for Discussion" section.*
