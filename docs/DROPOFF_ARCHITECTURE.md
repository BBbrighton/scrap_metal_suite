# Drop-off Architecture - Complete Redesign

## Executive Summary

This document defines a new architecture to support M:M relationships between POS Orders and Drop-offs, enabling:
- One POS Order → Multiple Drop-offs (large order delivered over multiple days)
- One Drop-off → Multiple POS Orders (one truck carrying materials for multiple orders)
- One Drop-off → Multiple Trucks (convoy delivery)

**Key Insight**: The **Drop-off is the central operational unit**.
- **Desk Users (Managers)** create POS Orders first, then create Drop-offs linking to those orders
- **POS Operators** work with Drop-offs only - they search by Drop-off ID, not Order ID
- Operators don't need to know/care about the M:M relationships - they just process the Drop-off

---

## Part 1: Current State Analysis

### 1.1 Current Data Model

```
POS Order (current)
├── order_id, supplier, order_date, dropoff_date, license_plate
├── order_items[] (expected items from supplier)
├── items[] (weighed items - synced from Scrap Weight)
├── Truck Weight Fields (EMBEDDED - problem!)
│   ├── gross_weight, gross_weight_scale, gross_weight_time
│   ├── tare_weight, tare_weight_scale, tare_weight_time
│   ├── net_truck_weight
│   ├── weight_variance, weight_variance_percent
│   ├── truck_weight_remarks, truck_weight_photo
│   └── is_truck_reweighed, is_scrap_reweighed
├── total_scrap_weight (sum from Scrap Weight records)
└── status, processed_by, processed_time

Scrap Weight (current)
├── pos_order (Link) ← directly linked to POS Order
├── supplier, posting_date
├── session, operator, scale
├── items[] (item_code, weight, uom)
├── total_weight
├── is_reweight, reweight_reason, reweight_by, reweight_at
└── remarks
```

### 1.2 Current API Functions (pos.py)

| Function | Lines | Purpose | Impact |
|----------|-------|---------|--------|
| `check_pos_operator()` | 9-20 | Auth check | KEEP |
| `_calculate_variance()` | 23-39 | Calculate truck vs scrap variance | MODIFY - move to Drop-off |
| `get_pos_profile()` | 42-67 | Get profile config | KEEP |
| `get_active_session()` | 70-115 | Get user's open session | KEEP |
| `open_session()` | 118-154 | Open new session | KEEP |
| `close_session()` | 157-177 | Close session | KEEP |
| `lookup_order()` | 180-253 | Search orders | MODIFY - add drop-off info |
| `get_order_details()` | 256-333 | Get full order details | MODIFY - include drop-offs |
| `load_scrap_weight()` | 336-366 | Load scrap weight for reweight | MODIFY - link to drop-off |
| `create_scrap_weight()` | 369-540 | Record scrap weight | **MAJOR REWRITE** - link to drop-off |
| `get_session_weights()` | 543-575 | Get session's scrap weights | KEEP |
| `get_session_summary()` | 578-608 | Get session totals | KEEP |
| `record_truck_weight()` | 611-703 | Record gross/tare weight | **MAJOR REWRITE** - write to Drop-off |
| `save_truck_remarks()` | 706-731 | Save truck remarks | **REWRITE** - move to Drop-off |
| `update_total_scrap_weight()` | 734-770 | Recalc total scrap weight | MODIFY - sync to order via drop-off |
| `mark_reweighed()` | 773-803 | Mark truck/scrap reweighed | **REWRITE** - move to Drop-off |
| `get_scales()` | 806-840 | List scales | KEEP |
| `get_scale_by_id()` | 843-891 | Get scale by ID/QR | KEEP |
| `set_session_scale()` | 894-957 | Set scale for session | KEEP |
| `get_weight_verification()` | 960-1012 | Get weight verification | **REWRITE** - read from Drop-off |

### 1.3 Current Problems

1. **Truck weight embedded in POS Order** - Can't have multiple truck arrivals for one order
2. **One license plate per order** - Can't have multiple trucks
3. **No audit trail for truck weights** - Reweight overwrites original values
4. **Scrap Weight links directly to POS Order** - Can't link to specific drop-off event
5. **Hardcoded 2% variance threshold** - Not configurable
6. **No fulfillment tracking** - Can't track partial deliveries

---

## Part 2: New Architecture

### 2.1 New Data Model

```
POS Order (modified)
├── naming_series: ORD-.YYYY.- (this IS the order ID)
├── REMOVE: order_id (use document name instead)
├── supplier, order_date
├── order_items[] (expected items)
├── items[] (weighed items - aggregated from all drop-offs)
├── REMOVE: license_plate, dropoff_date (move to Drop-off)
├── REMOVE: all truck weight fields (move to Drop-off)
├── NEW: Fulfillment Tracking
│   ├── contracted_weight (sum of order_items)
│   ├── total_received (sum from drop-offs)
│   ├── fulfillment_percent
│   └── fulfillment_status (Pending/Partial/Fulfilled/Over-delivered)
├── NEW: variance_threshold_percent (configurable, default 0.01%)
├── total_scrap_weight (kept for backward compat, synced from drop-offs)
└── status, processed_by, processed_time

Drop-off (NEW DocType)
├── naming_series: DROP-.YYYY.-
├── dropoff_date, dropoff_time
├── supplier (denormalized for quick lookup)
├── status: Select (see Status Flow below)
│   ├── Draft (Grey) - Created but not ready
│   ├── Scheduled (Blue) - Ready for truck arrival
│   ├── Weighing (Orange) - Recording truck weights
│   ├── Unloading (Yellow) - Recording scrap weights
│   ├── Verified (Purple) - All weights recorded, pending review
│   ├── Closed (Green) - Complete, fulfillment synced
│   └── Cancelled (Red) - Voided, excluded from fulfillment
├── Linked Orders (child table: Drop-off Order)
│   ├── pos_order (Link)
│   ├── contracted_weight (fetched)
│   └── allocated_weight (filled after weighing)
├── Truck Weights (child table: Drop-off Truck)
│   ├── license_plate
│   ├── gross_weight, gross_weight_scale, gross_weight_time, gross_weight_operator
│   ├── tare_weight, tare_weight_scale, tare_weight_time, tare_weight_operator
│   ├── net_weight (calculated)
│   └── remarks, photo
├── Verification Section
│   ├── total_truck_weight (sum of net weights from all trucks, read-only)
│   ├── total_scrap_weight (sum from Scrap Weight linked to this drop-off, read-only)
│   ├── truck_variance (net truck - scrap, read-only)
│   ├── truck_variance_percent (read-only)
│   ├── variance_threshold_percent (configurable, default 0.01%)
│   └── variance_ok (Check, read-only, auto-set based on threshold)
├── Reweight Fields
│   ├── is_reweighed
│   ├── reweight_reason
│   ├── reweight_by
│   └── reweight_at
└── remarks

Drop-off Order (child table of Drop-off)
├── pos_order: Link → POS Order (required)
├── contracted_weight: Float (fetched from order)
└── allocated_weight: Float (what this drop-off delivers for this order)

Drop-off Truck (child table of Drop-off)
├── license_plate: Data (required)
├── gross_weight: Float
├── gross_weight_scale: Link → Scale
├── gross_weight_time: Datetime
├── gross_weight_operator: Link → User
├── tare_weight: Float
├── tare_weight_scale: Link → Scale
├── tare_weight_time: Datetime
├── tare_weight_operator: Link → User
├── net_weight: Float (calculated, read-only)
├── Reweight Fields (audit trail for truck weight corrections)
│   ├── is_reweighed: Check
│   ├── reweight_reason: Small Text
│   ├── reweight_by: Link → User
│   └── reweight_at: Datetime
├── remarks: Small Text
└── photo: Attach Image

NOTE: Parent Drop-off has `track_changes: 1` for full audit trail via Frappe's Version system.

Scrap Weight (modified)
├── dropoff: Link → Drop-off (required) ← ONLY link needed
├── REMOVE: pos_order ← not needed, allocation happens at close
├── supplier, posting_date
├── session, operator, scale
├── items[] (unchanged)
├── total_weight
├── is_reweight, reweight_reason, reweight_by, reweight_at
└── remarks
```

### 2.2 Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         POS Order                                │
│  - order_id, supplier, order_date                                │
│  - order_items[] (contracted)                                    │
│  - contracted_weight, total_received                             │
│  - fulfillment_percent, fulfillment_status                       │
│  - variance_threshold_percent                                    │
└─────────────────────────────────────────────────────────────────┘
          ▲
          │ M:M via Drop-off Order
          │
┌─────────────────────────────────────────────────────────────────┐
│                         Drop-off                                 │
│  - dropoff_date, supplier, status                                │
│  ┌─────────────────────────────────┐                            │
│  │ Drop-off Order (child table)    │──────────┘                  │
│  │  - pos_order                    │                             │
│  │  - contracted_weight            │                             │
│  │  - allocated_weight             │                             │
│  └─────────────────────────────────┘                            │
│  ┌─────────────────────────────────┐                            │
│  │ Drop-off Truck (child table)    │                            │
│  │  - license_plate                │                            │
│  │  - gross/tare/net weight        │                            │
│  │  - scale, operator, time        │                            │
│  └─────────────────────────────────┘                            │
│  - total_truck_weight (sum of trucks)                            │
│  - total_scrap_weight                                            │
│  - truck_variance, truck_variance_percent                        │
└─────────────────────────────────────────────────────────────────┘
          │
          │ 1:M
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Scrap Weight                               │
│  - dropoff (Link → Drop-off, required) ← ONLY link needed        │
│  - items[], total_weight                                         │
│  - (pos_order REMOVED - allocation at close)                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 3: User Workflows

### 3.1 Two Types of Users

| User | Role | What They Do |
|------|------|--------------|
| **Desk User (Manager)** | Planning & Setup | Create POS Orders, Create Drop-offs, Link orders to drop-offs |
| **POS Operator** | Execution | Process Drop-offs - weigh trucks, record scrap, verify |

### 3.2 Desk User Workflow (Manager)

**Step 1: Create POS Order(s)**
```
1. Go to Desk → POS Order → New
2. Select Supplier
3. Add order_items (contracted items & weights)
4. Save → ORD-2025-001 created
```

**Step 2: Create Drop-off**
```
1. Go to Desk → Drop-off → New
2. Select dropoff_date
3. In "Linked Orders" child table:
   └── Add ORD-2025-001
   └── (Add more orders if truck carries for multiple orders)
4. In "Trucks" child table:
   └── Add license plate(s) expected
5. Save → DROP-2025-001 created
6. Print/share Drop-off ticket for truck driver
```

**Complex Scenarios (all handled by Desk User):**

| Scenario | Desk User Action |
|----------|------------------|
| 1 Order, 1 Truck | Create 1 Drop-off with 1 order, 1 truck |
| 1 Order, Multiple Trucks (convoy) | Create 1 Drop-off with 1 order, multiple trucks |
| Multiple Orders, 1 Truck | Create 1 Drop-off with multiple orders, 1 truck |
| 1 Order, Multiple Days | Create separate Drop-offs for each delivery day |

### 3.3 POS Operator Workflow (Terminal)

**Operator ONLY works with Drop-off ID. They don't care about orders.**

```
1. Truck arrives with Drop-off ticket (DROP-2025-001)

2. Search/Scan Drop-off ID
   └── Terminal shows: Drop-off details, linked orders summary, truck list

3. Select truck from list (or scan license plate)
   └── Record Gross Weight → "15,000 kg ✓"

4. Unload & Record Scrap Weights
   └── Weigh each item, add to cart
   └── Submit scrap weight

5. Record Tare Weight for truck
   └── "Tare: 13,500 kg ✓, Net: 1,500 kg"

6. (If multiple trucks) Repeat steps 3-5 for each truck

7. Verify & Complete Drop-off
   └── System shows: Total truck weight vs Total scrap weight
   └── Variance calculation
   └── Complete → Drop-off closed, fulfillment synced to orders
```

**What Operator DOESN'T need to know:**
- How many POS Orders are linked (system handles allocation)
- Whether this is a partial delivery (system tracks fulfillment)
- Complex M:M relationships (just process what's in front of them)

### 3.4 Example: Multi-Day Delivery

**Desk User (Day 0):**
```
1. Create ORD-2025-001 (5000 kg contracted)
2. Create DROP-2025-001 for Day 1 delivery (link to ORD-2025-001)
```

**POS Operator (Day 1):**
```
1. Process DROP-2025-001 → delivers 2000 kg
2. System: ORD-2025-001 fulfillment = 40% (Partial)
```

**Desk User (Day 1 evening):**
```
1. Create DROP-2025-002 for Day 2 delivery (link to same ORD-2025-001)
```

**POS Operator (Day 2):**
```
1. Process DROP-2025-002 → delivers 3000 kg
2. System: ORD-2025-001 fulfillment = 100% (Fulfilled)
```

### 3.5 Example: One Truck, Multiple Orders

**Desk User:**
```
1. Create ORD-2025-001 (Supplier A, 2000 kg)
2. Create ORD-2025-002 (Supplier A, 1500 kg)  ← Same supplier!
3. Create DROP-2025-001, link BOTH orders, 1 truck
```

**POS Operator:**
```
1. Process DROP-2025-001
2. Record truck weight (one measurement)
3. Record scrap weights (items are tagged to orders in system)
4. Complete → System allocates weights to each order
```

**Weight Allocation (handled by system or Desk User):**
- Total scrap: 3,400 kg
- ORD-2025-001 allocated: 1,900 kg (95% fulfilled)
- ORD-2025-002 allocated: 1,500 kg (100% fulfilled)

---

## Part 4: API Changes

### 4.1 New API Structure (Drop-off Centric)

```
scrap_metal_suite/api/v1/
├── pos.py           # Session & scale management (keep existing)
└── dropoff.py       # Drop-off management (NEW - main operator API)
```

**Key Change**: Operators interact with `dropoff.py`, not `pos.py` for weighing operations.

### 4.2 Functions to KEEP in pos.py (Session/Scale Only)

| Function | Status | Notes |
|----------|--------|-------|
| `check_pos_operator()` | KEEP | No changes |
| `get_pos_profile()` | KEEP | No changes |
| `get_active_session()` | KEEP | No changes |
| `open_session()` | KEEP | No changes |
| `close_session()` | KEEP | No changes |
| `get_session_weights()` | MODIFY | Filter by drop-off instead of order |
| `get_session_summary()` | KEEP | No changes |
| `get_scales()` | KEEP | No changes |
| `get_scale_by_id()` | KEEP | No changes |
| `set_session_scale()` | KEEP | No changes |

### 4.3 Functions to REMOVE from pos.py (Move to dropoff.py)

| Function | Status | Notes |
|----------|--------|-------|
| `lookup_order()` | REMOVE | Replace with `lookup_dropoff()` |
| `get_order_details()` | REMOVE | Replace with `get_dropoff_details()` |
| `load_scrap_weight()` | MOVE | Now works with Drop-off |
| `create_scrap_weight()` | REMOVE | Replace with `record_scrap_weight()` |
| `record_truck_weight()` | REMOVE | Replace with `record_truck_weight()` in dropoff.py |
| `save_truck_remarks()` | REMOVE | Replace with `save_truck_remarks()` in dropoff.py |
| `update_total_scrap_weight()` | REMOVE | Now internal in dropoff.py |
| `mark_reweighed()` | REMOVE | Replace with `mark_truck_reweighed()` |
| `get_weight_verification()` | REMOVE | Replace with `get_dropoff_verification()` |
| `_calculate_variance()` | REMOVE | Now internal in dropoff.py |

### 4.4 New dropoff.py API (Complete)

```python
# =============================================================================
# DROP-OFF API - Operator Terminal Functions
# =============================================================================
# This is the main API for POS Operators. All weighing operations go through
# Drop-off, not POS Order directly.
# =============================================================================

import frappe
from frappe import _
from frappe.utils import flt, nowdate, now_datetime

def check_pos_operator():
    """Auth check - same as pos.py"""
    ...

# === SEARCH & LOOKUP ===

@frappe.whitelist()
def lookup_dropoff(query):
    """
    Search for Drop-offs by ID or license plate.
    This is the PRIMARY search for operators.

    Args:
        query: Search term (DROP-ID or license plate)

    Returns:
        list: Matching drop-offs with status, truck count, order count
    """

@frappe.whitelist()
def get_dropoff_details(dropoff):
    """
    Get full details of a Drop-off for terminal display.

    Args:
        dropoff: Drop-off name

    Returns:
        dict: {
            name, dropoff_date, status, supplier,
            trucks: [{license_plate, gross, tare, net, status}, ...],
            orders: [{order_id, supplier_name, contracted_weight}, ...],
            scrap_weights: [{name, total_weight, items}, ...],
            total_truck_weight,
            total_scrap_weight,
            variance, variance_percent, variance_ok
        }
    """

# === TRUCK WEIGHT RECORDING ===

@frappe.whitelist()
def record_truck_weight(dropoff, license_plate, weight_type, weight, scale=None):
    """
    Record gross or tare weight for a truck in a drop-off.

    Args:
        dropoff: Drop-off name
        license_plate: Truck license plate (must exist in drop-off trucks)
        weight_type: 'gross' or 'tare'
        weight: Weight in kg
        scale: Scale name (optional)

    Returns:
        dict: {
            truck: {license_plate, gross, tare, net, status},
            dropoff_status,
            total_truck_weight
        }
    """

@frappe.whitelist()
def mark_truck_reweighed(dropoff, license_plate, reason):
    """
    Mark a truck as reweighed and record the reason.

    Args:
        dropoff: Drop-off name
        license_plate: Truck license plate
        reason: Reason for reweight

    Returns:
        dict: Updated truck row
    """

@frappe.whitelist()
def save_truck_remarks(dropoff, license_plate, remarks=None, photo=None):
    """
    Save remarks/photo for a specific truck.

    Args:
        dropoff: Drop-off name
        license_plate: Truck license plate
        remarks: Optional text remarks
        photo: Optional photo attachment

    Returns:
        dict: {success: True}
    """

# === SCRAP WEIGHT RECORDING ===

@frappe.whitelist()
def record_scrap_weight(session, dropoff, items, remarks=None,
                        existing_scrap_weight=None, reweight_reason=None):
    """
    Record scrap weight for a drop-off.

    Args:
        session: POS Session name
        dropoff: Drop-off name
        items: JSON list of items [{item_code, weight, uom}]
        remarks: Optional remarks
        existing_scrap_weight: For reweight - update this doc instead
        reweight_reason: Required if reweighting

    Returns:
        dict: {
            scrap_weight: name,
            total_weight,
            dropoff_total_scrap,
            variance, variance_percent
        }
    """

@frappe.whitelist()
def load_scrap_weight(scrap_weight_id):
    """
    Load existing Scrap Weight for editing (reweight).

    Args:
        scrap_weight_id: Scrap Weight document name

    Returns:
        dict: {name, dropoff, items, remarks, is_reweight}
    """

# === VERIFICATION & COMPLETION ===

@frappe.whitelist()
def get_dropoff_verification(dropoff):
    """
    Get complete verification summary for a drop-off.

    Args:
        dropoff: Drop-off name

    Returns:
        dict: {
            trucks: [{license_plate, gross, tare, net, is_reweighed}, ...],
            total_truck_weight,
            scrap_records: [{name, total_weight, is_reweight}, ...],
            total_scrap_weight,
            variance,
            variance_percent,
            variance_threshold,
            variance_ok,
            linked_orders: [{
                order_id, supplier_name,
                contracted_weight, allocated_weight,
                fulfillment_percent, fulfillment_status
            }, ...]
        }
    """

@frappe.whitelist()
def complete_dropoff(dropoff):
    """
    Complete a drop-off - set status to Closed, sync fulfillment to orders.

    Args:
        dropoff: Drop-off name

    Returns:
        dict: {
            dropoff: name,
            status: "Closed",
            orders_updated: [{order_id, fulfillment_status}, ...]
        }
    """

# === INTERNAL FUNCTIONS ===

def _calculate_dropoff_totals(dropoff_doc):
    """
    Calculate total truck weight and variance.
    Called on truck weight save.
    """

def _sync_fulfillment_to_orders(dropoff_doc):
    """
    Sync allocated weights to linked POS Orders.
    Updates total_received, fulfillment_percent, fulfillment_status.
    Called on drop-off complete.
    """

def _get_truck_row(dropoff_doc, license_plate):
    """
    Find truck row by license plate in drop-off.
    """
```

### 4.5 Desk User APIs (Standard Frappe)

Desk users use standard Frappe CRUD for POS Order and Drop-off:
- `frappe.get_doc()`, `frappe.new_doc()`, etc.
- No custom API needed - just DocType forms

For convenience, we may add:

```python
# In dropoff.py - Desk helper functions

@frappe.whitelist()
def create_dropoff_for_orders(pos_orders, dropoff_date, trucks=None):
    """
    Quick create Drop-off linking multiple orders.
    Used by Desk users.

    Args:
        pos_orders: List of POS Order names
        dropoff_date: Date
        trucks: Optional list of license plates

    Returns:
        dict: {dropoff: name}
    """

@frappe.whitelist()
def get_pending_orders_for_supplier(supplier):
    """
    Get POS Orders not yet fully fulfilled for a supplier.
    Helps Desk user find orders to link to new drop-off.
    """
```

---

## Part 5: Terminal UI Changes

### 5.1 Drop-off Centric Terminal

The terminal is redesigned around **Drop-off**, not POS Order.

### 5.2 Terminal Screens

| Screen | Purpose | API Used |
|--------|---------|----------|
| **Search** | Search by Drop-off ID or license plate | `lookup_dropoff()` |
| **Drop-off Details** | Show trucks, linked orders, status | `get_dropoff_details()` |
| **Truck Weight** | Record gross/tare for selected truck | `record_truck_weight()` |
| **Scrap Weight** | Weigh items, link to drop-off | `record_scrap_weight()` |
| **Verification** | Show variance, complete drop-off | `get_dropoff_verification()`, `complete_dropoff()` |

### 5.3 Search Screen (Updated)

```
┌──────────────────────────────────────────────────┐
│ 🔍 Search Drop-off                               │
├──────────────────────────────────────────────────┤
│ [DROP-2025-001 or License Plate    ] [Search]   │
│                                                  │
│ Recent Drop-offs:                                │
│ ┌────────────────────────────────────────────┐  │
│ │ DROP-2025-003  ABC-1234  Weighing    2 ord │  │
│ │ DROP-2025-002  XYZ-5678  Unloading   1 ord │  │
│ │ DROP-2025-001  DEF-9012  Closed      1 ord │  │
│ └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

### 5.4 Drop-off Details Screen (New)

```
┌──────────────────────────────────────────────────┐
│ DROP-2025-003                     Status: Weighing│
├──────────────────────────────────────────────────┤
│ Date: 2025-12-25                                 │
│ Supplier: Metal Recyclers Ltd                    │
│                                                  │
│ TRUCKS (2)                                       │
│ ┌────────────────────────────────────────────┐  │
│ │ ABC-1234  Gross: 15,000kg  Tare: --  [Weigh]│  │
│ │ DEF-5678  Gross: --        Tare: --  [Weigh]│  │
│ └────────────────────────────────────────────┘  │
│                                                  │
│ LINKED ORDERS (2)                                │
│ ┌────────────────────────────────────────────┐  │
│ │ ORD-2025-001  Copper Wire    2,000 kg      │  │
│ │ ORD-2025-002  Aluminum Scrap 1,500 kg      │  │
│ └────────────────────────────────────────────┘  │
│                                                  │
│ [Record Scrap Weight]  [View Verification]       │
└──────────────────────────────────────────────────┘
```

### 5.5 Truck Weight Screen (Same UI, Different API)

```
┌──────────────────────────────────────────────────┐
│ Truck Weight - ABC-1234                          │
│ DROP-2025-003                                    │
├──────────────────────────────────────────────────┤
│                                                  │
│ Gross Weight:  [15,000    ] kg  ✓ Recorded      │
│ Tare Weight:   [          ] kg  ○ Pending       │
│ Net Weight:    -- kg                            │
│                                                  │
│ Scale: Truck Scale 01 (Weighbridge)             │
│                                                  │
│ [Record Tare]  [Reweigh Gross]                   │
│                                                  │
│ Remarks: [                                    ]  │
│ Photo: [📷 Take Photo]                          │
└──────────────────────────────────────────────────┘
```

### 5.6 Scrap Weight Screen (Same UI, Different API)

Same cart-based UI, but now calls `record_scrap_weight(dropoff=...)` instead of `create_scrap_weight(pos_order=...)`.

### 5.7 Verification Screen (Updated)

```
┌──────────────────────────────────────────────────┐
│ Verification - DROP-2025-003                     │
├──────────────────────────────────────────────────┤
│ TRUCK WEIGHTS                                    │
│ ┌────────────────────────────────────────────┐  │
│ │ ABC-1234  Net: 1,500 kg                    │  │
│ │ DEF-5678  Net: 1,200 kg                    │  │
│ ├────────────────────────────────────────────┤  │
│ │ TOTAL TRUCK:        2,700 kg               │  │
│ └────────────────────────────────────────────┘  │
│                                                  │
│ SCRAP WEIGHTS                                    │
│ ┌────────────────────────────────────────────┐  │
│ │ WGT-2025-001  1,480 kg                     │  │
│ │ WGT-2025-002  1,190 kg                     │  │
│ ├────────────────────────────────────────────┤  │
│ │ TOTAL SCRAP:        2,670 kg               │  │
│ └────────────────────────────────────────────┘  │
│                                                  │
│ VARIANCE: -30 kg (-1.1%)  ✓ Within tolerance    │
│                                                  │
│ [Complete Drop-off]                              │
└──────────────────────────────────────────────────┘
```

---

## Part 6: Data Migration

### 6.1 Development Phase - No Migration Needed

**We are in active development.** No production data exists yet.

- Old POS Order truck weight fields will be **removed** (not deprecated)
- Old Scrap Weight `pos_order` field will be **removed** (replaced with `dropoff`)
- No backward compatibility needed
- Fresh start with new architecture

### 6.2 Clean Slate Approach

```bash
# Remove old test data if any
bench execute scrap_metal_suite.utils.clear_test_data

# Migrate with new DocTypes
bench migrate

# Build assets
bench build --app scrap_metal_suite
```

---

## Part 7: Implementation Phases

### Phase 1: DocTypes

**Goal**: Create new DocTypes, modify existing ones

- [ ] Create `Drop-off` DocType with `track_changes: 1`
- [ ] Create `Drop-off Order` child table
- [ ] Create `Drop-off Truck` child table (with reweight fields)
- [ ] Modify `Scrap Weight`: add `dropoff` field, REMOVE `pos_order` (allocation at close)
- [ ] Modify `POS Order`:
  - [ ] Remove `order_id` field (use document name `ORD-.YYYY.-` instead)
  - [ ] Remove truck weight fields (gross, tare, net, scales, times, remarks, photo)
  - [ ] Remove `dropoff_date`, `license_plate` (move to Drop-off)
  - [ ] Add fulfillment fields (contracted_weight, total_received, fulfillment_percent, fulfillment_status)
  - [ ] Add `variance_threshold_percent`
- [ ] Run `bench migrate`
- [ ] Test in Desk: Create POS Order → Create Drop-off → Link them

### Phase 2: Drop-off API

**Goal**: Implement `dropoff.py` - the main operator API

- [ ] Create `api/v1/dropoff.py`
- [ ] Implement `lookup_dropoff(query)`
- [ ] Implement `get_dropoff_details(dropoff)`
- [ ] Implement `record_truck_weight(dropoff, license_plate, weight_type, weight, scale)`
- [ ] Implement `mark_truck_reweighed(dropoff, license_plate, reason)`
- [ ] Implement `save_truck_remarks(dropoff, license_plate, remarks, photo)`
- [ ] Implement `record_scrap_weight(session, dropoff, items, ...)`
- [ ] Implement `load_scrap_weight(scrap_weight_id)`
- [ ] Implement `get_dropoff_verification(dropoff)`
- [ ] Implement `complete_dropoff(dropoff)`
- [ ] Implement internal `_sync_fulfillment_to_orders()`
- [ ] Add doc_events in `hooks.py` for sync

### Phase 3: Clean Up pos.py

**Goal**: Remove order/truck functions from pos.py

- [ ] Remove `lookup_order()`
- [ ] Remove `get_order_details()`
- [ ] Remove `record_truck_weight()`
- [ ] Remove `save_truck_remarks()`
- [ ] Remove `create_scrap_weight()`
- [ ] Remove `load_scrap_weight()`
- [ ] Remove `update_total_scrap_weight()`
- [ ] Remove `mark_reweighed()`
- [ ] Remove `get_weight_verification()`
- [ ] Remove `_calculate_variance()`
- [ ] Keep session/scale functions only

### Phase 4: Terminal UI

**Goal**: Update terminal to be Drop-off centric

- [ ] Create new search screen (search by Drop-off ID / license plate)
- [ ] Create Drop-off details screen
- [ ] Update truck weight screen (pass dropoff + license_plate)
- [ ] Update scrap weight screen (pass dropoff instead of pos_order)
- [ ] Update verification screen (show drop-off level data)
- [ ] Test full operator workflow

### Phase 5: Testing & Documentation

**Goal**: End-to-end testing, update docs

- [ ] Test: 1 Order, 1 Truck, 1 Drop-off
- [ ] Test: 1 Order, Multiple Drop-offs (multi-day delivery)
- [ ] Test: Multiple Orders, 1 Drop-off
- [ ] Test: 1 Drop-off, Multiple Trucks (convoy)
- [ ] Test: Reweight scenarios
- [ ] Update CLAUDE.md
- [ ] Archive/remove old TRUCK_WEIGHT_DESIGN.md

---

## Part 8: Files to Create/Modify

### New Files

| File | Purpose |
|------|---------|
| `doctype/dropoff/dropoff.json` | Drop-off DocType definition |
| `doctype/dropoff/dropoff.py` | Drop-off Python controller |
| `doctype/dropoff/__init__.py` | Module init |
| `doctype/dropoff_order/dropoff_order.json` | Child table for M:M |
| `doctype/dropoff_order/__init__.py` | Module init |
| `doctype/dropoff_truck/dropoff_truck.json` | Child table for trucks |
| `doctype/dropoff_truck/__init__.py` | Module init |
| `api/v1/dropoff.py` | Main operator API (Drop-off centric) |

### Modified Files

| File | Changes |
|------|---------|
| `doctype/pos_order/pos_order.json` | Remove truck fields, add fulfillment fields |
| `doctype/scrap_weight/scrap_weight.json` | Add `dropoff`, REMOVE `pos_order` |
| `api/v1/pos.py` | Remove all order/truck functions |
| `www/pos/terminal.html` | Rewrite for Drop-off centric workflow |
| `www/pos/truck.html` | Update API calls |
| `hooks.py` | Add Drop-off doc_events for fulfillment sync |

### Files to Remove/Archive

| File | Reason |
|------|--------|
| `TRUCK_WEIGHT_DESIGN.md` | Superseded by this document |

---

## Part 9: Answered Questions

1. **License plate on POS Order?**
   - **Answer**: REMOVE from POS Order. Only on Drop-off Truck.

2. **Backward compatibility for Scrap Weight?**
   - **Answer**: Not needed (development phase). Remove `pos_order`, use only `dropoff`.

3. **Who handles complex scenarios (M:M)?**
   - **Answer**: Desk User creates the Drop-offs with linked orders. Operator just processes Drop-offs.

4. **Dedicated Drop-off terminal?**
   - **Answer**: NO. Same terminal, but search/process by Drop-off ID instead of Order ID.

---

## Part 10: Additional Answered Questions

1. **Fulfillment tolerance?**
   - **Answer**: Default 0.01%, configurable per profile/company
   - Both variance_threshold_percent AND fulfillment tolerance use same default

2. **Void/Cancel workflow for Drop-offs?**
   - **Answer**: Add `Cancelled` status to Drop-off
   - Cancelled Drop-offs are excluded from fulfillment calculations
   - Linked Scrap Weights are NOT deleted (audit trail preserved)
   - Cancellation requires reason field

3. **Drop-off status flow?**
   - **Answer**: Detailed flow with color coding (see below)

4. **Weight allocation for M:M?**
   - **Answer**: Auto-allocate by item type (scrap metal is fungible)
   - Operator just weighs items - NO order selection needed
   - At Drop-off close, system auto-allocates based on item types
   - See Part 12 for detailed allocation logic

---

## Part 11: Drop-off Status Flow

### Status Definitions

| Status | Color | Indicator | Meaning |
|--------|-------|-----------|---------|
| **Draft** | Grey | `grey` | Created but not ready for processing |
| **Scheduled** | Blue | `blue` | Orders and trucks added, ready for arrival |
| **Weighing** | Orange | `orange` | Truck arrived, recording gross/tare weights |
| **Unloading** | Yellow | `yellow` | Recording scrap weights |
| **Verified** | Purple | `purple` | All weights recorded, pending final review |
| **Closed** | Green | `green` | Complete, fulfillment synced to orders |
| **Cancelled** | Red | `red` | Voided, excluded from all calculations |

### State Transitions

```
                    ┌──────────────────────────────────────────┐
                    │                                          │
                    ▼                                          │
┌───────┐      ┌───────────┐      ┌──────────┐      ┌──────────┤
│ Draft │ ──▶  │ Scheduled │ ──▶  │ Weighing │ ──▶  │Unloading │
└───────┘      └───────────┘      └──────────┘      └──────────┘
    │               │                  │                  │
    │               │                  │                  │
    ▼               ▼                  ▼                  ▼
┌───────────────────────────────────────────────────────────────┐
│                         Cancelled                              │
└───────────────────────────────────────────────────────────────┘
                                                              │
                                                              ▼
                                      ┌──────────┐      ┌────────┐
                                      │ Verified │ ──▶  │ Closed │
                                      └──────────┘      └────────┘
```

### Auto-Transitions

| Trigger | From Status | To Status |
|---------|-------------|-----------|
| Desk User adds orders + trucks | Draft | Scheduled |
| First gross weight recorded | Scheduled | Weighing |
| All trucks have gross, first scrap weight recorded | Weighing | Unloading |
| All trucks have tare, all expected scrap recorded | Unloading | Verified |
| Operator clicks "Complete Drop-off" | Verified | Closed |
| Desk User cancels (any status except Closed) | Any | Cancelled |

### List View Indicator (pos_order_list.js style)

```javascript
frappe.listview_settings['Drop-off'] = {
    add_fields: ['status'],
    get_indicator: function(doc) {
        const status_map = {
            'Draft': ['Draft', 'grey', 'status,=,Draft'],
            'Scheduled': ['Scheduled', 'blue', 'status,=,Scheduled'],
            'Weighing': ['Weighing', 'orange', 'status,=,Weighing'],
            'Unloading': ['Unloading', 'yellow', 'status,=,Unloading'],
            'Verified': ['Verified', 'purple', 'status,=,Verified'],
            'Closed': ['Closed', 'green', 'status,=,Closed'],
            'Cancelled': ['Cancelled', 'red', 'status,=,Cancelled']
        };
        return status_map[doc.status] || ['Unknown', 'grey'];
    }
};
```

---

## Part 12: Weight Allocation for M:M (Auto by Item Type)

### Key Insight: Scrap Metal is Fungible

Copper from Order A is the same as copper from Order B. The system can auto-allocate based on item type - operator doesn't need to select orders.

### How It Works

1. **Operator just weighs items** - no order selection needed
2. **Scrap Weight links to Drop-off only** - no `pos_order` field
3. **At Drop-off close**, system auto-allocates weights to orders based on item types

### Allocation Logic

```python
def _auto_allocate_scrap_to_orders(dropoff_doc):
    """
    Auto-allocate scrap weights to orders based on item type.
    Called when Drop-off is completed.

    Logic:
    1. Sum all scrap weights by item_code
    2. For each order, allocate items it expects (up to contracted weight)
    3. If multiple orders expect same item, allocate pro-rata
    """
    # Step 1: Sum scrap by item type
    scrap_by_item = {}  # {item_code: total_weight}
    scrap_weights = frappe.get_all(
        "Scrap Weight",
        filters={"dropoff": dropoff_doc.name},
        fields=["name"]
    )
    for sw_name in scrap_weights:
        sw = frappe.get_doc("Scrap Weight", sw_name)
        for item in sw.items:
            scrap_by_item[item.item_code] = scrap_by_item.get(item.item_code, 0) + item.weight

    # Step 2: Build demand by item type (which orders want what)
    demand_by_item = {}  # {item_code: [{order, contracted}, ...]}
    for order_row in dropoff_doc.orders:
        order = frappe.get_doc("POS Order", order_row.pos_order)
        for order_item in order.order_items:
            if order_item.item_code not in demand_by_item:
                demand_by_item[order_item.item_code] = []
            demand_by_item[order_item.item_code].append({
                "order_row": order_row,
                "contracted": order_item.weight
            })

    # Step 3: Allocate
    for order_row in dropoff_doc.orders:
        order_row.allocated_weight = 0

    for item_code, available in scrap_by_item.items():
        if item_code not in demand_by_item:
            continue  # No order expects this item

        demands = demand_by_item[item_code]
        total_demand = sum(d["contracted"] for d in demands)

        for demand in demands:
            if total_demand > 0:
                # Pro-rata allocation
                share = demand["contracted"] / total_demand
                allocated = min(available * share, demand["contracted"])
                demand["order_row"].allocated_weight += allocated

    dropoff_doc.save()
```

### Example

```
DROP-2025-001 links to:
├── ORD-001 expects: Copper Wire 2,000 kg, Brass 500 kg
└── ORD-002 expects: Copper Wire 1,000 kg, Aluminum 1,500 kg

Operator weighs (doesn't select order):
├── Copper Wire: 2,800 kg total
├── Brass: 480 kg
└── Aluminum: 1,500 kg

System auto-allocates at close:
├── Copper: ORD-001 gets 1,867 kg (2000/3000 share), ORD-002 gets 933 kg (1000/3000 share)
├── Brass: ORD-001 gets 480 kg (only order expecting brass)
└── Aluminum: ORD-002 gets 1,500 kg (only order expecting aluminum)

Final:
├── ORD-001 allocated: 1,867 + 480 = 2,347 kg
└── ORD-002 allocated: 933 + 1,500 = 2,433 kg
```

### Scrap Weight DocType (Simplified)

```
Scrap Weight (modified)
├── dropoff: Link → Drop-off (required) ← ONLY link needed
├── REMOVE: pos_order ← not needed, allocation happens at close
├── supplier, posting_date
├── session, operator, scale
├── items[] (unchanged)
├── total_weight
├── is_reweight, reweight_reason, reweight_by, reweight_at
└── remarks
```

### Operator Workflow (Unchanged)

1. Search Drop-off
2. Record truck weight
3. Record scrap weights (just weigh items, no order selection)
4. Complete → System auto-allocates

---

## Part 13: Edge Cases & Validations

### 13.1 Unexpected Item Delivery (Unallocated Bucket)

**Scenario**: Operator weighs an item that NO linked order expects.
```
DROP-001 links to: ORD-001 (expects Copper), ORD-002 (expects Aluminum)
Operator weighs: Brass 500kg  ← Neither order expects this!
```

**Solution**: Create an "unallocated" bucket at Drop-off level.

```
Drop-off (add field)
├── unallocated_weight: Float (read-only)
└── unallocated_items: JSON or child table [{item_code, weight}]
```

**Allocation Logic Update**:
```python
def _auto_allocate_scrap_to_orders(dropoff_doc):
    # ... existing allocation logic ...

    # After allocation, check for unallocated items
    unallocated = {}
    for item_code, available in scrap_by_item.items():
        if item_code not in demand_by_item:
            unallocated[item_code] = available

    dropoff_doc.unallocated_weight = sum(unallocated.values())
    dropoff_doc.unallocated_items = json.dumps(unallocated)

    if unallocated:
        frappe.msgprint(
            f"Warning: {dropoff_doc.unallocated_weight} kg of items not expected by any order",
            indicator="orange"
        )
```

**UI**: Show warning on verification screen if unallocated items exist.

---

### 13.2 Multi-Day Fulfillment Aggregation

**How `total_received` is calculated on POS Order:**

```python
def _sync_fulfillment_to_orders(dropoff_doc):
    """Called when Drop-off is completed."""
    for order_row in dropoff_doc.orders:
        order = frappe.get_doc("POS Order", order_row.pos_order)

        # Sum allocated_weight from ALL non-cancelled Drop-offs for this order
        total_received = frappe.db.sql("""
            SELECT COALESCE(SUM(do.allocated_weight), 0)
            FROM `tabDrop-off Order` do
            JOIN `tabDrop-off` d ON d.name = do.parent
            WHERE do.pos_order = %s
            AND d.status != 'Cancelled'
        """, order.name)[0][0]

        order.total_received = total_received
        order.fulfillment_percent = (total_received / order.contracted_weight * 100) if order.contracted_weight else 0
        order.fulfillment_status = _get_fulfillment_status(order.fulfillment_percent)
        order.save()
```

---

### 13.3 Single Supplier per Drop-off (Validation)

**Constraint**: All orders linked to a Drop-off must have the same supplier.

**Validation in Drop-off controller:**
```python
def validate(self):
    if self.orders:
        suppliers = set()
        for row in self.orders:
            order = frappe.get_doc("POS Order", row.pos_order)
            suppliers.add(order.supplier)

        if len(suppliers) > 1:
            frappe.throw("All orders in a Drop-off must be from the same supplier")

        # Set Drop-off supplier from first order
        if suppliers:
            self.supplier = list(suppliers)[0]
```

**UI**: When adding orders to Drop-off, filter by supplier of first order.

---

### 13.4 Cancel Rollback Mechanism

**When Drop-off is cancelled:**
1. Set status = Cancelled
2. Record cancellation reason (required field)
3. Recalculate fulfillment for all linked orders

```python
def on_cancel(self):
    # Recalculate fulfillment for each linked order
    for order_row in self.orders:
        _recalculate_order_fulfillment(order_row.pos_order)

def _recalculate_order_fulfillment(pos_order_name):
    """Recalculate from source of truth (non-cancelled drop-offs)."""
    order = frappe.get_doc("POS Order", pos_order_name)

    total_received = frappe.db.sql("""
        SELECT COALESCE(SUM(do.allocated_weight), 0)
        FROM `tabDrop-off Order` do
        JOIN `tabDrop-off` d ON d.name = do.parent
        WHERE do.pos_order = %s
        AND d.status != 'Cancelled'
    """, pos_order_name)[0][0]

    order.total_received = total_received
    order.fulfillment_percent = (total_received / order.contracted_weight * 100) if order.contracted_weight else 0
    order.fulfillment_status = _get_fulfillment_status(order.fulfillment_percent)
    order.save()
```

**Note**: Cancelled Drop-offs are NOT deleted. Scrap Weights linked to cancelled Drop-offs remain for audit trail.

---

### 13.5 POS Order Drop-off Status

**New field on POS Order**: `dropoff_status`

| Status | Meaning | Color |
|--------|---------|-------|
| `No Drop-off` | Order created, no drop-off linked yet | Grey |
| `Scheduled` | At least one drop-off is Scheduled | Blue |
| `In Progress` | At least one drop-off is Weighing/Unloading | Orange |
| `Received` | At least one drop-off Closed for this order | Green |

**Calculation logic:**
```python
def _update_order_dropoff_status(pos_order_name):
    """Update dropoff_status based on linked drop-offs."""
    dropoffs = frappe.db.sql("""
        SELECT d.status
        FROM `tabDrop-off Order` do
        JOIN `tabDrop-off` d ON d.name = do.parent
        WHERE do.pos_order = %s
        AND d.status != 'Cancelled'
    """, pos_order_name, as_dict=True)

    if not dropoffs:
        return "No Drop-off"

    statuses = [d.status for d in dropoffs]

    if "Closed" in statuses:
        return "Received"
    elif any(s in ["Weighing", "Unloading", "Verified"] for s in statuses):
        return "In Progress"
    elif "Scheduled" in statuses:
        return "Scheduled"
    else:
        return "No Drop-off"
```

---

### 13.6 Validation Before Complete Drop-off

**Rules before `complete_dropoff()` can succeed:**

```python
def complete_dropoff(dropoff):
    doc = frappe.get_doc("Drop-off", dropoff)

    # Rule 1: At least one order linked
    if not doc.orders:
        frappe.throw("Cannot complete: No orders linked to this drop-off")

    # Rule 2: At least one truck
    if not doc.trucks:
        frappe.throw("Cannot complete: No trucks in this drop-off")

    # Rule 3: All trucks must have gross AND tare weights
    for truck in doc.trucks:
        if not truck.gross_weight:
            frappe.throw(f"Cannot complete: Truck {truck.license_plate} missing gross weight")
        if not truck.tare_weight:
            frappe.throw(f"Cannot complete: Truck {truck.license_plate} missing tare weight")

    # Rule 4: At least one scrap weight recorded
    scrap_count = frappe.db.count("Scrap Weight", {"dropoff": doc.name})
    if scrap_count == 0:
        frappe.throw("Cannot complete: No scrap weights recorded")

    # Rule 5: Variance within threshold (warning, not blocking)
    if not doc.variance_ok:
        frappe.msgprint(
            f"Warning: Variance {doc.truck_variance_percent}% exceeds threshold {doc.variance_threshold_percent}%",
            indicator="orange"
        )

    # Proceed with completion
    _auto_allocate_scrap_to_orders(doc)
    _sync_fulfillment_to_orders(doc)
    doc.status = "Closed"
    doc.save()
```

---

### 13.7 Empty Drop-off Validation

**Status transition rules:**

| From | To | Requirements |
|------|-----|--------------|
| Draft | Scheduled | At least 1 order, at least 1 truck |
| Scheduled | Weighing | (auto) First gross weight recorded |
| Weighing | Unloading | (auto) All trucks have gross, first scrap weight |
| Unloading | Verified | (auto) All trucks have tare |
| Verified | Closed | (manual) All validations pass |
| Any (except Closed) | Cancelled | Cancellation reason required |

---

### 13.8 Reopen Closed Drop-off (Cancel & Amend)

**ERPNext Standard Pattern:**

1. **Closed Drop-off cannot be edited** - it's like "Submitted"
2. **To fix mistakes**: Cancel the Drop-off
   - Requires cancellation reason
   - Triggers fulfillment rollback (13.4)
   - Original document preserved with status = Cancelled
3. **Create new Drop-off** with corrected data
   - Link same orders
   - Re-record weights
   - Complete again

**No "Amend" link needed** - just create a fresh Drop-off. The M:M relationship allows multiple drop-offs per order naturally.

---

### 13.9 Drop-off Order `contracted_weight` - Live Fetch

**Decision**: Fetch live from POS Order, don't store.

```
Drop-off Order (child table)
├── pos_order: Link → POS Order (required)
├── allocated_weight: Float (filled at close)
└── REMOVE: contracted_weight ← fetch live instead
```

**In API/UI**: Always fetch `contracted_weight` from `POS Order.contracted_weight`.

**Benefit**: No stale data if order items change.

---

### 13.10 Duplicate License Plate in Same Drop-off

**Scenario**: Desk user accidentally adds the same license plate twice to the trucks child table.
```
DROP-001:
├── Truck: ABC-123
└── Truck: ABC-123  ← Duplicate!
```

**Problem**:
- `record_truck_weight()` uses license plate to find the truck row
- With duplicates, which row gets updated?
- Could result in double-counting net weight

**Solution**: Add validation to prevent duplicate license plates within same Drop-off.

```python
def validate(self):
    # Check for duplicate license plates
    plates = [t.license_plate for t in self.trucks]
    if len(plates) != len(set(plates)):
        frappe.throw("Duplicate license plates not allowed in the same Drop-off")
```

---

### 13.11 POS Order Cancelled After Drop-off Created

**Scenario**:
```
1. Create ORD-001 (Pending)
2. Create DROP-001, link ORD-001
3. Manager cancels ORD-001
4. Operator tries to process DROP-001
```

**Problems**:
- Drop-off still references a cancelled order
- Allocation logic will try to allocate to cancelled order
- Fulfillment sync will update cancelled order

**Solution**: Prevent order cancellation if linked to active drop-off.

```python
# In POS Order controller
def before_cancel(self):
    active_dropoffs = frappe.db.sql("""
        SELECT d.name FROM `tabDrop-off` d
        JOIN `tabDrop-off Order` do ON d.name = do.parent
        WHERE do.pos_order = %s
        AND d.status NOT IN ('Cancelled', 'Closed')
    """, self.name)

    if active_dropoffs:
        names = [d[0] for d in active_dropoffs]
        frappe.throw(f"Cannot cancel: Order linked to active Drop-offs: {', '.join(names)}")
```

**Note**: If manager needs to cancel the order, they must first cancel the linked Drop-off(s).

---

### 13.12 Duplicate POS Order in Same Drop-off

**Scenario**: Desk user accidentally adds the same order twice to the orders child table.
```
DROP-001:
├── Order: ORD-001
└── Order: ORD-001  ← Duplicate!
```

**Problems**:
- Allocation logic will count this order's contracted weight twice
- Pro-rata calculation will be wrong
- `allocated_weight` written to both rows = double fulfillment

**Solution**: Validate no duplicate orders in same Drop-off.

```python
def validate(self):
    # Check for duplicate orders
    orders = [o.pos_order for o in self.orders]
    if len(orders) != len(set(orders)):
        frappe.throw("Same order cannot be linked multiple times to the same Drop-off")
```

---

### 13.13 Scrap Weight Deleted After Drop-off Closed

**Scenario**:
```
1. DROP-001 completed with WGT-001 (1000kg)
2. Fulfillment synced to ORD-001 (1000kg received)
3. Admin deletes WGT-001 from database
4. ORD-001 still shows 1000kg received (stale)
```

**Problem**: No trigger to recalculate fulfillment when Scrap Weight is deleted.

**Solution**: Prevent deletion of Scrap Weight linked to Closed drop-off.

```python
# In Scrap Weight controller
def before_cancel(self):
    if self.dropoff:
        dropoff_status = frappe.db.get_value("Drop-off", self.dropoff, "status")
        if dropoff_status == "Closed":
            frappe.throw("Cannot delete Scrap Weight linked to a Closed Drop-off. Cancel the Drop-off first.")
```

---

### 13.14 Tare Weight Recorded Before Gross Weight (Terminal)

**Scenario**: Operator tries to record tare weight first.
```
Truck ABC-123:
├── Gross: -- (not recorded)
└── Tare: 13,500 kg  ← Trying to record this first
```

**Problem**:
- Net weight = Gross - Tare would be negative or wrong
- Workflow assumes gross → tare order (truck arrives loaded, leaves empty)

**Solution**: API validates gross weight must be recorded before tare.

```python
# In dropoff.py
def record_truck_weight(dropoff, license_plate, weight_type, weight, scale=None):
    # ...
    truck_row = _get_truck_row(doc, license_plate)

    if weight_type == "tare" and not truck_row.gross_weight:
        frappe.throw("Cannot record tare weight before gross weight")

    # ... proceed with recording
```

**Terminal UI**: Disable "Record Tare" button until gross weight is recorded.

---

### 13.15 Zero Weight Items (Terminal)

**Scenario**: Operator records 0 kg for an item.
```
Scrap Weight WGT-001:
├── Copper: 500 kg
└── Brass: 0 kg  ← Zero!
```

**Question**: Is this intentional (item inspected but rejected) or data entry error?

**Solution**: Allow with warning - operator might legitimately record "inspected but rejected" items.

```python
# In dropoff.py
def record_scrap_weight(session, dropoff, items, ...):
    # ...
    zero_items = [i["item_code"] for i in items if flt(i["weight"]) == 0]
    if zero_items:
        frappe.msgprint(
            f"Warning: Zero weight recorded for: {', '.join(zero_items)}",
            indicator="orange"
        )
    # ... proceed with saving
```

**Terminal UI**: Show confirmation dialog if any item has 0 weight.

---

### 13.16 Drop-off Date Changed After Weighing Started (Desk)

**Scenario**:
```
1. Create DROP-001 for 2025-12-25
2. Start weighing on 2025-12-25
3. Desk user changes dropoff_date to 2025-12-20 (past)
```

**Problem**: Data integrity - weighing timestamps will be after the drop-off date.

**Solution**: Lock `dropoff_date` once status moves past Draft/Scheduled.

```python
def validate(self):
    if self.status not in ["Draft", "Scheduled"]:
        if self.has_value_changed("dropoff_date"):
            frappe.throw("Cannot change drop-off date after weighing has started")
```

---

### 13.17 Truck Added After Weighing Started (Desk)

**Scenario**:
```
1. DROP-001 has Truck ABC-123
2. Status = Weighing (ABC-123 gross recorded)
3. Desk user adds new Truck DEF-456
4. System now expects DEF-456 to also have weights
```

**Decision**: Allow adding trucks even during Weighing/Unloading (late truck arrival to convoy).

**Behavior**:
- New truck starts with no weights
- All trucks must still have gross+tare before completion
- Addition logged in audit trail (`track_changes: 1` handles this)

**No code change needed** - existing completion validation will catch missing weights.

---

### 13.18 Negative Variance (Scrap > Truck)

**Scenario**:
```
Total Truck Net: 1,500 kg
Total Scrap: 1,600 kg  ← More scrap than truck carried?
Variance: -100 kg (-6.7%)
```

**Problem**: Physically impossible unless scale calibration error. Could indicate fraud or error.

**Solution**:
- Calculate variance as absolute value for threshold check
- Show warning for negative variance
- Don't block completion - let manager review

```python
def _calculate_dropoff_totals(dropoff_doc):
    variance = dropoff_doc.total_truck_weight - dropoff_doc.total_scrap_weight
    dropoff_doc.truck_variance = variance
    dropoff_doc.truck_variance_percent = abs(variance / dropoff_doc.total_truck_weight * 100) if dropoff_doc.total_truck_weight else 0
    dropoff_doc.variance_ok = dropoff_doc.truck_variance_percent <= dropoff_doc.variance_threshold_percent

def complete_dropoff(dropoff):
    # ...
    if doc.truck_variance < 0:
        frappe.msgprint(
            "Warning: Scrap weight exceeds truck weight. Please verify scale readings.",
            indicator="red"
        )
    # ... proceed with completion
```

---

### 13.19 Drop-off Spans Multiple Sessions

**Scenario**:
```
1. Operator A opens session, starts processing DROP-001
2. Records WGT-001 (linked to session A)
3. Operator A closes session (end of shift)
4. Operator B opens new session
5. Continues processing DROP-001, records WGT-002
```

**Current Design**: This is handled correctly because:
- Scrap Weight links to Drop-off (primary) AND Session (for operator tracking)
- Drop-off aggregates from all Scrap Weights regardless of session
- Each session shows only its own weights in session summary

**No code change needed** - documenting expected behavior:
- Drop-offs CAN span multiple sessions (shift changes)
- Session summary shows that session's contribution only
- Drop-off verification shows total from all sessions
- Each Scrap Weight tracks which operator/session recorded it

---

### 13.20 Tare Weight Greater Than or Equal to Gross Weight (Terminal)

**Scenario**: Operator records tare weight that's higher than gross.
```
Truck ABC-123:
├── Gross: 13,000 kg
└── Tare: 14,000 kg  ← Higher than gross!
Net: -1,000 kg  ← Negative!
```

**Problem**: Physically impossible - empty truck can't weigh more than loaded truck.

**Solution**: Validate tare < gross when recording tare.

```python
# In dropoff.py
def record_truck_weight(dropoff, license_plate, weight_type, weight, scale=None):
    # ...
    truck_row = _get_truck_row(doc, license_plate)

    if weight_type == "tare":
        if not truck_row.gross_weight:
            frappe.throw("Cannot record tare weight before gross weight")
        if weight >= truck_row.gross_weight:
            frappe.throw(f"Tare weight ({weight} kg) cannot be >= gross weight ({truck_row.gross_weight} kg)")

    # ... proceed with recording
```

---

### 13.21 Order Removed from Drop-off After Weighing (Desk)

**Scenario**:
```
1. DROP-001 links ORD-001, ORD-002
2. Operator records scrap weights
3. Desk user removes ORD-002 from Drop-off
4. Allocation at close only has ORD-001
```

**Behavior**:
- Allow removal during Weighing/Unloading (manager decision)
- Items meant for removed order go to unallocated bucket
- **Cannot remove orders once Drop-off is Closed**

**Solution**: Validate orders cannot be removed from Closed Drop-off.

```python
def validate(self):
    if self.status == "Closed":
        old_doc = self.get_doc_before_save()
        if old_doc:
            old_orders = {o.pos_order for o in old_doc.orders}
            new_orders = {o.pos_order for o in self.orders}
            removed = old_orders - new_orders
            if removed:
                frappe.throw(f"Cannot remove orders from a Closed Drop-off: {', '.join(removed)}")
```

---

### 13.22 Truck Removed from Drop-off After Weights Recorded (Desk)

**Scenario**:
```
1. DROP-001 has ABC-123 (gross: 15000, tare: 13500)
2. Desk user removes ABC-123 from trucks
3. Total truck weight drops, variance changes, recorded data lost
```

**Problem**: Weights already recorded would be lost.

**Solution**: Prevent removal if truck has any weights recorded.

```python
def validate(self):
    old_doc = self.get_doc_before_save()
    if old_doc:
        old_trucks = {t.license_plate: t for t in old_doc.trucks}
        new_plates = {t.license_plate for t in self.trucks}

        for plate, truck in old_trucks.items():
            if plate not in new_plates:
                if truck.gross_weight or truck.tare_weight:
                    frappe.throw(f"Cannot remove truck {plate} - weights already recorded. Cancel the Drop-off instead.")
```

---

### 13.23 Weight Exceeds Scale Maximum (Terminal)

**Scenario**: Operator enters weight that exceeds the scale's capacity.
```
Scale: Truck Scale 01 (max_weight: 50,000 kg)
Operator enters: 60,000 kg  ← Exceeds scale max!
```

**Problem**:
- Impossible reading - scale can't measure beyond its capacity
- Could be typo or data entry error

**Solution**: Validate weight against scale's `max_weight` field.

```python
# In dropoff.py
def record_truck_weight(dropoff, license_plate, weight_type, weight, scale=None):
    # ...
    if scale:
        scale_doc = frappe.get_doc("Scale", scale)
        if scale_doc.max_weight and weight > scale_doc.max_weight:
            frappe.throw(
                f"Weight {weight} kg exceeds scale capacity ({scale_doc.max_weight} kg). "
                f"Please verify the reading."
            )

    # ... proceed with recording
```

**Note**: Same validation applies to scrap scale when recording scrap weights.

---

## Part 14: Updated Data Model (Final)

### 14.1 Drop-off DocType (Final)

```
Drop-off
├── naming_series: DROP-.YYYY.-
├── dropoff_date: Date (required)
├── dropoff_time: Time
├── supplier: Link → Supplier (required, set from first order)
├── status: Select [Draft, Scheduled, Weighing, Unloading, Verified, Closed, Cancelled]
│
├── Section: Linked Orders
│   └── orders: Table → Drop-off Order
│
├── Section: Trucks
│   └── trucks: Table → Drop-off Truck
│
├── Section: Verification
│   ├── total_truck_weight: Float (read-only, sum of truck net weights)
│   ├── total_scrap_weight: Float (read-only, sum from Scrap Weight)
│   ├── truck_variance: Float (read-only, truck - scrap)
│   ├── truck_variance_percent: Percent (read-only)
│   ├── variance_threshold_percent: Percent (default 0.01%)
│   ├── variance_ok: Check (read-only, auto-set)
│   ├── unallocated_weight: Float (read-only) ← NEW
│   └── unallocated_items: JSON (read-only) ← NEW
│
├── Section: Reweight (collapsible)
│   ├── is_reweighed: Check
│   ├── reweight_reason: Small Text
│   ├── reweight_by: Link → User
│   └── reweight_at: Datetime
│
├── Section: Cancellation (collapsible, depends_on: status == Cancelled)
│   ├── cancellation_reason: Small Text (required if cancelled) ← NEW
│   ├── cancelled_by: Link → User ← NEW
│   └── cancelled_at: Datetime ← NEW
│
└── remarks: Small Text
```

### 14.2 Drop-off Order (Child Table - Final)

```
Drop-off Order
├── pos_order: Link → POS Order (required)
└── allocated_weight: Float (filled at close)

Note: contracted_weight fetched live from POS Order
```

### 14.3 POS Order (Modified - Final)

```
POS Order
├── naming_series: ORD-.YYYY.-
├── supplier: Link → Supplier (required)
├── order_date: Date
├── order_items[]: Table → POS Order Item
│
├── Section: Fulfillment Tracking
│   ├── contracted_weight: Float (sum of order_items, read-only)
│   ├── total_received: Float (sum from drop-offs, read-only)
│   ├── fulfillment_percent: Percent (read-only)
│   ├── fulfillment_status: Select [Pending, Partial, Fulfilled, Over-delivered] (read-only)
│   └── dropoff_status: Select [No Drop-off, Scheduled, In Progress, Received] (read-only) ← NEW
│
├── variance_threshold_percent: Percent (default 0.01%)
├── status: Select [Pending, Processed, Cancelled]
└── ...
```

---

*Last updated: 2025-12-25*
*Branch: dev_2*


---

## Part 15: 1-Truck-Per-Dropoff Design Update (2025-12-26)

### 15.1 Design Decision

**Changed from multi-truck (child table) to 1-truck-per-dropoff design:**

| Aspect | Old Design | New Design |
|--------|------------|------------|
| Truck storage | Drop-off Truck child table | Inline fields on Dropoff |
| Convoy handling | 1 Dropoff, many trucks | Many Dropoffs, 1 truck each |
| Truck Weight history | In child table reweight fields | Standalone Truck Weight DocType |
| API complexity | Need license_plate param | Simpler - direct on dropoff |

**Rationale:**
- Simpler data model
- Cleaner API (no license_plate lookups)
- Better audit trail via standalone Truck Weight DocType
- Desk users can create separate Dropoffs for convoy trucks

### 15.2 Updated Data Model

**Dropoff (1-truck design):**
- naming_series: DO-.YY.MM.DD.-
- dropoff_date, dropoff_time
- license_plate: Data (required) - INLINE, not child table
- variance_threshold_percent: Percent (default 0.01%)
- status: Draft/Scheduled/Weighing/Unloading/Verified/Closed/Cancelled
- supplier, supplier_name (auto-set from orders)
- orders: Table -> Dropoff Order (M:M to POS Orders)
- expected_items: Table -> Dropoff Expected Item
- actual_items, item_summary: Tables (read-only, synced)
- Truck Weight Section (INLINE):
  - gross_weight, gross_weight_scale, gross_weight_time, gross_weight_operator
  - tare_weight, tare_weight_scale, tare_weight_time, tare_weight_operator
  - net_weight (calculated), truck_photo, truck_remarks
- Verification: total_truck_weight, total_scrap_weight, truck_variance, variance_ok
- Reweight: is_reweighed, reweight_reason, reweight_by, reweight_at
- Cancellation: cancellation_reason, cancelled_by, cancelled_at

**Truck Weight (standalone audit trail):**
- dropoff: Link -> Dropoff (required)
- license_plate, supplier_name: fetch from dropoff
- weight_type: Gross/Tare
- weight, weighed_at, scale, operator, remarks
- session, pos_profile (Session Info section)

**Scrap Weight (updated):**
- dropoff: Link -> Dropoff (required)
- supplier_name: fetch from dropoff.supplier_name
- NO supplier field (removed)
- NO pos_order field (allocation at close)

### 15.3 Updated API Specification (1-truck design)

**lookup_dropoff(query):**
- Search by ID or license plate
- Returns: list of matching dropoffs with status, order_count

**get_dropoff_details(dropoff):**
- Full details for terminal
- Returns: dropoff info, truck weights (inline), orders, scrap_weights, verification

**record_truck_weight(dropoff, weight_type, weight, scale, session):**
- No license_plate param (1-truck design)
- Creates Truck Weight audit record
- Returns: updated weights, status, truck_weight_record name

**mark_truck_reweighed(dropoff, reason):**
- Sets is_reweighed, records reason
- Returns: success

**save_truck_remarks(dropoff, remarks, photo):**
- Updates truck_remarks, truck_photo
- Returns: success

**record_scrap_weight(session, dropoff, items, ...):**
- Creates/updates Scrap Weight linked to dropoff
- Returns: scrap_weight name, totals, variance

**load_scrap_weight(scrap_weight_id):**
- Load for reweight editing
- Returns: items, remarks, dropoff

**get_dropoff_verification(dropoff):**
- Verification summary
- Returns: truck info, scrap records, variance, orders, can_complete, blockers

**complete_dropoff(dropoff):**
- Sets status=Closed, triggers allocation
- Returns: dropoff, status, orders_updated



### 15.4 Controller Methods (Already Implemented in dropoff.py)

- validate() - Edge cases 13.3, 13.12, 13.16, 13.20, 13.21, 13.22
- calculate_net_weight() - gross - tare
- sync_actual_items() - Sync from Scrap Weight records
- calculate_totals() - total_truck, total_scrap, variance
- allocate_weights_if_closing() - Pro-rata allocation by contracted_weight
- update_pos_orders_if_closed() - Sync fulfillment after save
- _recalculate_order_fulfillment() - Source of truth recalc

### 15.5 Files Summary (1-truck design)

| File | Status | Purpose |
|------|--------|---------|
| doctype/dropoff/dropoff.json | Done | Inline license_plate, truck weights |
| doctype/dropoff/dropoff.py | Done | Controller with validations & allocation |
| doctype/dropoff_order/ | Done | M:M link to POS Orders |
| doctype/dropoff_expected_item/ | Done | Supplier expected items |
| doctype/dropoff_actual_item/ | Done | Synced from Scrap Weight |
| doctype/dropoff_item_summary/ | Done | Aggregated by item |
| doctype/truck_weight/ | Done | Standalone audit trail |
| doctype/dropoff_truck/ | DEPRECATED | Was child table, not used |
| doctype/scrap_weight/ | Updated | dropoff link, fetch supplier_name |
| doctype/pos_order/ | Updated | Fulfillment fields, Links |
| api/v1/dropoff.py | Creating | 1-truck API |

---

*Updated: 2025-12-26 for 1-truck-per-dropoff design*


---

## Part 16: Final Implementation Plan (2025-12-26)

### 16.1 Status Flow with Auto-Transitions

| Status | Color | Trigger | Next Status |
|--------|-------|---------|-------------|
| Draft | Grey | Created | - |
| Scheduled | Blue | Orders linked, ready | - |
| Weighing | Orange | First truck weight recorded | auto from Draft/Scheduled |
| Unloading | Yellow | First scrap weight recorded | auto from Weighing |
| Verified | Green | All weights done, variance OK | auto |
| Needs Attention | Red | All weights done, variance NOT OK | auto |
| Closed | Purple | complete_dropoff() from Verified | manual |
| Cancelled | Dark Grey | User cancels | manual |

### 16.2 Session Management

**New Fields on POS Session:**
- last_activity: Datetime - updated on each API call
- closed_by: Link to User - who closed (or "Administrator" for auto-close)

**Cron Job (every 15 mins):**
- Find sessions: status=Open AND last_activity < now() - 60 mins
- Close them with closed_by=Administrator

### 16.3 Photo Naming Convention

Format: {doc_name}/{field}_{timestamp}.{ext}

Examples:
- DO-251226-00001/truck_photo_20251226_091500.jpg
- WGT-251226-00001/scrap_photo_20251226_093000.jpg

### 16.4 Final API Structure

**api/v1/pos.py (Session/Scale - KEEP):**
- check_pos_operator()
- get_pos_profile(profile_name)
- get_active_session()
- open_session(pos_profile)
- close_session(session)
- update_session_activity(session) - NEW for heartbeat
- get_scales(usage_type, scale_type)
- get_scale_by_id(scale_id)
- set_session_scale(session, scale)
- get_session_weights(session)
- get_session_summary(session)

**api/v1/dropoff.py (NEW - Dropoff operations):**
- lookup_dropoff(query) - search by ID or plate
- get_dropoff_by_qr(qr_data) - parse URL, return dropoff
- get_dropoff_details(dropoff) - full details for terminal
- record_truck_weight(dropoff, weight_type, weight, scale, session)
  - Auto-transitions: Draft/Scheduled -> Weighing
  - Creates Truck Weight audit record
- record_scrap_weight(session, dropoff, items, remarks, existing, reweight_reason)
  - Auto-transitions: Weighing -> Unloading
  - Auto-checks variance -> Verified or Needs Attention
- load_scrap_weight(scrap_weight_id) - for reweight
- get_dropoff_verification(dropoff) - summary + can_complete + blockers
- complete_dropoff(dropoff) - Verified -> Closed, allocates weights
- save_truck_photo(dropoff, photo) - with naming convention
- save_truck_remarks(dropoff, remarks)
- mark_truck_reweighed(dropoff, reason)

**scheduler.py (NEW - Cron jobs):**
- close_idle_sessions() - close sessions idle > 60 mins

### 16.5 Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| doctype/dropoff/dropoff.json | DONE | Added "Needs Attention" status |
| doctype/dropoff/dropoff_list.js | DONE | Color coding for statuses |
| doctype/pos_session/pos_session.json | DONE | Added last_activity, closed_by |
| api/v1/dropoff.py | CREATE | Dropoff-centric API |
| api/v1/pos.py | MODIFY | Add update_session_activity() |
| scheduler.py | CREATE | Cron job for session cleanup |
| hooks.py | MODIFY | Add scheduler_events |

---

*Updated: 2025-12-26*

---

## Part 17: Next Session Notes (2025-12-26)

### Priority 1: Test All APIs
Before proceeding to UI work, test all Phase 2 API endpoints:
1. Run  to apply DocType changes
2. Test api/v1/dropoff.py endpoints via Postman/curl
3. Test api/v1/pos.py session heartbeat
4. Verify scheduler cron job (close_idle_sessions)

### Priority 2: Terminal Manual Weight Mode
**Requirement:** Terminal should work without WebSocket scale connection

Currently, the terminal requires a WebSocket connection to the scale server.
For testing and fallback scenarios, we need:

1. **Manual Weight Entry Mode**
   - Option in session setup to skip scale connection
   - Manual input field for weight values
   - Useful for: testing, scale offline, remote operators

2. **Implementation Options:**
   - Add  field to POS Session: connected | manual
   - Terminal UI shows weight input field when mode = manual
   - APIs accept weight values regardless of scale connection

3. **Scale Integration Remains Optional:**
   - If scale configured: show live weight, auto-fill
   - If no scale: manual entry works fine
   - Terminal should not block if scale unavailable

---

*Updated: 2025-12-26*


---

## Part 17: Next Session Notes (2025-12-26)

### Priority 1: Test All APIs
Before proceeding to UI work, test all Phase 2 API endpoints:
1. Run bench migrate to apply DocType changes
2. Test api/v1/dropoff.py endpoints via Postman/curl
3. Test api/v1/pos.py session heartbeat
4. Verify scheduler cron job (close_idle_sessions)

### Priority 2: Terminal Manual Weight Mode
**Requirement:** Terminal should work without WebSocket scale connection

Currently, the terminal requires a WebSocket connection to the scale server.
For testing and fallback scenarios, we need:

1. **Manual Weight Entry Mode**
   - Option in session setup to skip scale connection
   - Manual input field for weight values
   - Useful for: testing, scale offline, remote operators

2. **Implementation Options:**
   - Add scale_mode field to POS Session: "connected" | "manual"
   - Terminal UI shows weight input field when mode = "manual"
   - APIs accept weight values regardless of scale connection

3. **Scale Integration Remains Optional:**
   - If scale configured: show live weight, auto-fill
   - If no scale: manual entry works fine
   - Terminal should not block if scale unavailable

---

*Updated: 2025-12-26*
