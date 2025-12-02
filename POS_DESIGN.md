# Scrap Metal POS - Design Document

## Overview

A Point-of-Sale system for scrap metal buying operations with weighing scale integration, barcode/ID scanning, and manager-configurable item display.

---

## User Flows

### Flow 1: Operator Using POS

```
┌─────────────────────────────────────────────────────────────────┐
│                     OPERATOR WORKFLOW                           │
└─────────────────────────────────────────────────────────────────┘

1. LOGIN & START SESSION
   ┌──────────────────┐
   │ Operator logs in │ → System checks role "POS Operator"
   └────────┬─────────┘
            ↓
   ┌──────────────────┐
   │ Select POS       │ → Choose which POS Profile to use
   │ Profile          │    (e.g., "Main Counter", "Branch A")
   └────────┬─────────┘
            ↓
   ┌──────────────────┐
   │ Start Session    │ → Creates POS Session record
   └────────┬─────────┘    (status: Open, operator: current user)
            ↓

2. FIND SUPPLIER (Two Options)

   Option A: Search by Name/ID
   ┌──────────────────┐
   │ Type "John" or   │ → API: search_supplier(query)
   │ "SUP-00012"      │ → Returns matching suppliers
   └────────┬─────────┘
            ↓
   ┌──────────────────┐
   │ Select from list │ → Supplier loaded with tier info
   └────────┬─────────┘

   Option B: Scan Barcode
   ┌──────────────────┐
   │ Scan supplier    │ → API: lookup_supplier(barcode)
   │ barcode/QR       │ → Auto-loads supplier
   └────────┬─────────┘
            ↓

3. ADD ITEMS TO CART
   ┌──────────────────┐
   │ Tap "Copper      │ → Item selected
   │ Wire" button     │ → Shows default rate from price list
   └────────┬─────────┘    (based on supplier tier)
            ↓
   ┌──────────────────┐
   │ Enter weight:    │ → Manual input OR from scale
   │ 12.5 kg          │
   └────────┬─────────┘
            ↓
   ┌──────────────────┐
   │ Rate: ฿280/kg    │ → Can override if needed
   │ [Change Rate]    │
   └────────┬─────────┘
            ↓
   ┌──────────────────┐
   │ [ADD TO CART]    │ → Item added to cart
   └────────┬─────────┘    Amount = 12.5 × 280 = ฿3,500
            ↓
   (Repeat for more items)
            ↓

4. COMPLETE PURCHASE
   ┌──────────────────┐
   │ Review Cart:     │
   │ - Copper: ฿3,500 │
   │ - Alum:   ฿574   │
   │ ─────────────────│
   │ TOTAL:   ฿4,074  │
   └────────┬─────────┘
            ↓
   ┌──────────────────┐
   │ [COMPLETE]       │ → API: submit_purchase(data)
   └────────┬─────────┘ → Creates Scrap Purchase record
            ↓
   ┌──────────────────┐
   │ Success!         │
   │ Order: PUR-00001 │ → Ready for next supplier
   └──────────────────┘

5. END SESSION
   ┌──────────────────┐
   │ [Close Session]  │ → API: close_session()
   └────────┬─────────┘ → Calculates totals
            ↓
   ┌──────────────────┐
   │ Session Summary: │
   │ Purchases: 15    │
   │ Total: ฿45,000   │
   │ Weight: 180 kg   │
   └──────────────────┘
```

---

### Flow 2: Manager Configuring POS

```
┌─────────────────────────────────────────────────────────────────┐
│                     MANAGER WORKFLOW                            │
└─────────────────────────────────────────────────────────────────┘

1. ACCESS POS SETTINGS
   ┌──────────────────┐
   │ /manager/pos-    │ → Or via ERPNext Desk
   │ settings         │
   └────────┬─────────┘
            ↓

2. CREATE/EDIT POS PROFILE
   ┌──────────────────────────────────────┐
   │ POS Profile: "Main Counter"          │
   │                                      │
   │ Price List: [Standard Buying ▼]      │
   │                                      │
   │ Show Price to Operator: [✓]          │
   │                                      │
   │ Items to Display:                    │
   │ ┌────────────────────────────────┐   │
   │ │ [✓] Copper Wire         [↑↓]  │   │
   │ │ [✓] Aluminum Scrap      [↑↓]  │   │
   │ │ [✓] Steel/Iron          [↑↓]  │   │
   │ │ [ ] Brass               [↑↓]  │   │
   │ │ [✓] Stainless Steel     [↑↓]  │   │
   │ └────────────────────────────────┘   │
   │                                      │
   │ Default Warehouse: [Main Store ▼]    │
   │                                      │
   │              [SAVE]                  │
   └──────────────────────────────────────┘
```

---

## POS Interface Layout

```
+--------------------------------------------------+
| SCRAP METAL POS              [Operator: John]    |
+--------------------------------------------------+
| Supplier: [____________] [SCAN]    Session #5    |
| Selected: John Smith (VIP)                       |
+--------------------------------------------------+
|                                                  |
|  +--------+  +--------+  +--------+  +--------+  |
|  | Copper |  | Alum.  |  | Steel  |  | Brass  |  |
|  | Wire   |  | Scrap  |  |        |  |        |  |
|  +--------+  +--------+  +--------+  +--------+  |
|                                                  |
|  +--------+  +--------+  +--------+  +--------+  |
|  | Stain- |  | Lead   |  | Mixed  |  | E-Waste|  |
|  | less   |  |        |  | Metal  |  |        |  |
|  +--------+  +--------+  +--------+  +--------+  |
|                                                  |
+--------------------------------------------------+
| CURRENT ITEM: Copper Wire                        |
| Weight: [____] kg   (or from scale: 12.5 kg)     |
| Rate: ฿280/kg  [Edit]    Amount: ฿3,500          |
|                              [ADD TO CART]       |
+--------------------------------------------------+
| CART                                             |
| 1. Copper Wire    12.5 kg    ฿3,500        [x]  |
| 2. Aluminum       8.2 kg     ฿574          [x]  |
|                              ---------------     |
|                   TOTAL:     ฿4,074              |
+--------------------------------------------------+
|        [CLEAR]        [COMPLETE PURCHASE]        |
+--------------------------------------------------+
```

---

## Database Schema

### DocType: POS Profile Scrap

| Field | Type | Description |
|-------|------|-------------|
| name | Data (PK) | Auto-generated |
| profile_name | Data | Display name (e.g., "Main Counter") |
| price_list | Link: Price List | Default price list for this POS |
| show_price | Check | Show prices to operator? |
| warehouse | Link: Warehouse | Where purchased stock goes |
| is_active | Check | Enable/disable profile |

**Child Table: POS Profile Item**

| Field | Type | Description |
|-------|------|-------------|
| item_code | Link: Item | Item to display |
| item_name | Data | Auto-fetched |
| display_order | Int | Sort order in grid |

---

### DocType: POS Session

| Field | Type | Description |
|-------|------|-------------|
| name | Data (PK) | SES-YYYY-XXXXX |
| pos_profile | Link: POS Profile Scrap | Which profile |
| operator | Link: User | Who opened session |
| opening_time | Datetime | When opened |
| closing_time | Datetime | When closed (null if open) |
| status | Select | Open / Closed |
| total_purchases | Int | Count of purchases |
| total_amount | Currency | Sum of all purchases |
| total_weight | Float | Sum of all weights |

---

### DocType: Scrap Purchase

| Field | Type | Description |
|-------|------|-------------|
| name | Data (PK) | PUR-YYYY-XXXXX |
| session | Link: POS Session | Parent session |
| supplier | Link: Supplier | Who we bought from |
| posting_date | Date | Transaction date |
| posting_time | Time | Transaction time |
| operator | Link: User | Auto from session |
| pos_profile | Link: POS Profile Scrap | Auto from session |
| total_weight | Float | Sum of item weights |
| total_amount | Currency | Sum of item amounts |
| remarks | Text | Optional notes |

**Child Table: Scrap Purchase Item**

| Field | Type | Description |
|-------|------|-------------|
| item_code | Link: Item | What was purchased |
| item_name | Data | Auto-fetched |
| weight | Float | Net weight in kg |
| uom | Link: UOM | Usually "Kg" |
| rate | Currency | Price per unit |
| amount | Currency | weight × rate |

---

## API Endpoints

### Session Management

```python
@frappe.whitelist()
def get_pos_profiles()
    # Returns: [{"name", "profile_name", "price_list"}]

@frappe.whitelist()
def start_session(pos_profile)
    # Creates POS Session, returns session details + items

@frappe.whitelist()
def get_active_session()
    # Returns current open session or None

@frappe.whitelist()
def close_session(session_id)
    # Closes session, returns summary
```

### Supplier Lookup

```python
@frappe.whitelist()
def search_supplier(query)
    # Partial match on name/ID/phone
    # Returns: [{name, supplier_name, tier}]

@frappe.whitelist()
def lookup_supplier(barcode)
    # Exact match on barcode
    # Returns: {name, supplier_name, tier, price_list}
```

### Pricing

```python
@frappe.whitelist()
def get_item_rate(item_code, supplier=None, price_list=None)
    # Resolution: supplier tier → provided price_list → "Standard Buying"
    # Returns: {rate, price_list_used}
```

### Purchase

```python
@frappe.whitelist()
def submit_purchase(session_id, supplier, items, remarks=None)
    # Creates Scrap Purchase record
    # Items: [{"item_code", "weight", "rate"}]
    # Returns: {purchase_id, total_amount, total_weight}
```

---

## Price Resolution Logic

```python
def get_rate_for_item(item_code, supplier=None, price_list=None):
    """
    Rate resolution order:
    1. If supplier has a tier → use tier's price list
    2. Else if price_list provided → use that
    3. Else → use "Standard Buying" price list
    """

    resolved_price_list = None

    # Step 1: Check supplier tier
    if supplier:
        supplier_doc = frappe.get_doc("Supplier", supplier)
        if supplier_doc.default_price_list:
            resolved_price_list = supplier_doc.default_price_list

    # Step 2: Fallback to provided price_list
    if not resolved_price_list and price_list:
        resolved_price_list = price_list

    # Step 3: Default to Standard
    if not resolved_price_list:
        resolved_price_list = "Standard Buying"

    # Get rate from Item Price
    rate = frappe.db.get_value(
        "Item Price",
        {
            "item_code": item_code,
            "price_list": resolved_price_list,
            "buying": 1
        },
        "price_list_rate"
    )

    return {
        "rate": rate or 0,
        "price_list": resolved_price_list
    }
```

---

## Implementation Phases

### Phase 1: DocTypes ✅
- [ ] POS Profile Scrap + child table POS Profile Item
- [ ] POS Session
- [ ] Scrap Purchase + child table Scrap Purchase Item

### Phase 2: Backend APIs
- [ ] Session management (start, close, get active)
- [ ] Supplier lookup (search, barcode)
- [ ] Pricing (get rate with tier logic)
- [ ] Purchase submission

### Phase 3: Frontend POS
- [ ] `/pos` - Main POS interface
- [ ] Session start flow
- [ ] Supplier search/scan
- [ ] Item grid + cart
- [ ] Submit purchase

### Phase 4: Manager Settings
- [ ] `/manager/pos-settings` - Configure profiles
- [ ] Item selection UI
- [ ] Price list selection

### Phase 5: Enhancements (Future)
- [ ] Barcode scanner integration (JS)
- [ ] Weighing scale API integration
- [ ] Receipt printing
- [ ] Purchase history view

---

## File Structure

```
scrap_metal_suite/
├── scrap_metal_suite/
│   └── doctype/
│       ├── pos_profile_scrap/
│       │   ├── pos_profile_scrap.json
│       │   └── pos_profile_scrap.py
│       ├── pos_profile_item/           # Child table
│       │   └── pos_profile_item.json
│       ├── pos_session/
│       │   ├── pos_session.json
│       │   └── pos_session.py
│       ├── scrap_purchase/
│       │   ├── scrap_purchase.json
│       │   └── scrap_purchase.py
│       └── scrap_purchase_item/        # Child table
│           └── scrap_purchase_item.json
│
├── api/v1/
│   └── pos.py                          # POS API endpoints
│
├── www/
│   ├── pos/
│   │   ├── index.html
│   │   ├── index.py
│   │   └── history.html/py
│   └── manager/
│       └── pos-settings.html/py
│
└── public/
    ├── css/
    │   └── pos.css
    └── js/
        └── pos.js
```

---

## Design Decisions

1. **Rate Override**: Operators can override the default rate (from price list) for flexibility
2. **Supplier Required**: Every purchase must have a supplier (no walk-ins)
3. **Net Weight Only**: No tare/gross weight tracking
4. **No Stock Movement**: Purchases don't auto-create Stock Entry (can add later)
5. **No Payment Tracking**: Focus on recording what was bought, payment handled separately
6. **Session-Based**: All purchases grouped by operator session for accountability
