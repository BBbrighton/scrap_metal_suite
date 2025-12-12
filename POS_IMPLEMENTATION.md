# Scrap Metal POS - Implementation Documentation

## Overview

A weighing-focused Point-of-Sale system for scrap metal buying operations. The system handles:
- **POS Orders**: Pre-scheduled supplier deliveries with expected items
- **Truck Weighing**: Gross/tare weight verification via weighbridge
- **Scrap Weighing**: Individual item weighing on platform scales
- **Weight Reconciliation**: Variance tracking between truck and scrap weights

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           POS ORDER FLOW                                │
└─────────────────────────────────────────────────────────────────────────┘

  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
  │  POS Order   │      │    Truck     │      │    Scrap     │
  │  (Created)   │ ───► │   Weighing   │ ───► │   Weighing   │
  │              │      │  (Optional)  │      │  (Terminal)  │
  └──────────────┘      └──────────────┘      └──────────────┘
         │                     │                     │
         │                     ▼                     ▼
         │              ┌──────────────┐      ┌──────────────┐
         │              │ Gross Weight │      │ Scrap Weight │
         │              │ Tare Weight  │      │   Records    │
         │              │ Net Weight   │      │   (Items)    │
         │              └──────────────┘      └──────────────┘
         │                     │                     │
         │                     └─────────┬───────────┘
         │                               ▼
         │                     ┌──────────────────┐
         └────────────────────►│ Weight Variance  │
                               │   Calculation    │
                               └──────────────────┘
```

---

## DocTypes

### 1. POS Order

The central document representing a supplier's delivery/transaction.

| Field | Type | Description |
|-------|------|-------------|
| `naming_series` | Select | ORD-.YYYY.- |
| `order_id` | Data | Unique searchable ID |
| `supplier` | Link: Supplier | Who is delivering |
| `supplier_name` | Data | Auto-fetched |
| `order_date` | Date | Order creation date |
| `dropoff_date` | Date | Scheduled delivery date |
| `license_plate` | Data | Vehicle plate number |
| `scrap_scale` | Link: Scale | Scale used (from session) |
| `purchase_order` | Data | Reference to PO |
| `notes` | Small Text | Additional notes |
| `status` | Select | Pending / Processed / Cancelled |
| `processed_by` | Link: User | Who processed |
| `processed_time` | Datetime | When processed |

**Truck Weight Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `gross_weight` | Float | Truck with load (kg) |
| `gross_weight_scale` | Link: Scale | Weighbridge used |
| `gross_weight_time` | Datetime | When weighed |
| `tare_weight` | Float | Empty truck (kg) |
| `tare_weight_scale` | Link: Scale | Weighbridge used |
| `tare_weight_time` | Datetime | When weighed |
| `net_truck_weight` | Float | Gross - Tare (calculated) |
| `total_scrap_weight` | Float | Sum from Scrap Weight records |
| `weight_variance` | Float | Net truck - Total scrap |
| `weight_variance_percent` | Percent | Variance as % |
| `truck_weight_remarks` | Small Text | Notes from truck operator |
| `truck_weight_photo` | Attach Image | Photo evidence |
| `is_truck_reweighed` | Check | Flag for reweigh |
| `is_scrap_reweighed` | Check | Flag for reweigh |

**Child Tables:**

- `order_items` → **POS Order Item**: Expected items from supplier
- `items` → **POS Order Weighed Item**: Actual weighed items (read-only, synced from Scrap Weight)

---

### 2. POS Order Item (Child Table)

Items expected/indicated by the supplier when order is created.

| Field | Type | Description |
|-------|------|-------------|
| `item_code` | Link: Item | Scrap metal item |
| `item_name` | Data | Auto-fetched |
| `uom` | Link: UOM | Unit of measure |
| `weight` | Float | Indicated weight (kg) |

---

### 3. POS Order Weighed Item (Child Table)

Actual weighed items, auto-populated from Scrap Weight records.

| Field | Type | Description |
|-------|------|-------------|
| `scrap_weight` | Link: Scrap Weight | Source record |
| `item_code` | Link: Item | Item weighed |
| `item_name` | Data | Item name |
| `weight` | Float | Actual weight (kg) |
| `uom` | Link: UOM | Unit of measure |

---

### 4. Scrap Weight

Individual weighing record for items from a POS Order.

| Field | Type | Description |
|-------|------|-------------|
| `naming_series` | Select | WGT-.YYYY.- |
| `pos_order` | Link: POS Order | Parent order |
| `supplier` | Link: Supplier | Supplier |
| `supplier_name` | Data | Auto-fetched |
| `posting_date` | Date | Weighing date |
| `posting_time` | Time | Weighing time |
| `license_plate` | Data | Fetched from order |
| `session` | Link: POS Session | Operator session |
| `operator` | Link: User | Auto from session |
| `pos_profile` | Link: POS Profile Scrap | Auto from session |
| `scale` | Link: Scale | Scale used |
| `total_weight` | Float | Sum of items (calculated) |
| `remarks` | Small Text | Notes |

**Reweight Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `is_reweight` | Check | Is this a reweight? |
| `reweight_reason` | Small Text | Why reweighed |
| `reweight_at` | Datetime | When reweighed |
| `reweight_by` | Link: User | Who reweighed |

**Child Table:**

- `items` → **Scrap Weight Item**: Individual item weights

**Server Logic (`scrap_weight.py`):**

```python
def before_insert(self):
    # Auto-fill operator and pos_profile from session

def validate(self):
    # Calculate total_weight from items

def on_update(self):
    # Sync items to POS Order.items child table

def on_trash(self):
    # Remove items from POS Order when deleted
```

---

### 5. Scrap Weight Item (Child Table)

Individual item in a Scrap Weight record.

| Field | Type | Description |
|-------|------|-------------|
| `item_code` | Link: Item | Scrap item |
| `item_name` | Data | Auto-fetched |
| `weight` | Float | Weight (kg) |
| `uom` | Link: UOM | Unit (default: Kg) |

---

### 6. POS Session

Operator work session for accountability and scale assignment.

| Field | Type | Description |
|-------|------|-------------|
| `naming_series` | Select | SES-.YYYY.- |
| `pos_profile` | Link: POS Profile Scrap | Profile used |
| `operator` | Link: User | Auto from login |
| `scale` | Link: Scale | Assigned scale |
| `status` | Select | Open / Closed |
| `opening_time` | Datetime | Auto on create |
| `closing_time` | Datetime | Set on close |
| `total_purchases` | Int | Count (calculated) |
| `total_amount` | Currency | Sum (calculated) |
| `total_weight` | Float | Sum (calculated) |

**Server Logic (`pos_session.py`):**

```python
def before_insert(self):
    # Set opening_time and operator

def validate(self):
    # Ensure operator has only one open session

def close_session(self):
    # Calculate totals, set closing_time, status = Closed

def on_update(self):
    # Release scale when session closes
```

---

### 7. Scale

Physical weighing equipment registry.

| Field | Type | Description |
|-------|------|-------------|
| `scale_name` | Data | Unique ID (e.g., SCALE-001) |
| `scale_type` | Select | Platform / Weighbridge / Hanging / Floor / Bench |
| `usage_type` | Select | **Scrap** (items) / **Truck** (weighbridge) |
| `location` | Data | Physical location |
| `is_active` | Check | Available for use |
| `in_use` | Check | Currently in use (auto) |
| `in_use_by_session` | Link: POS Session | Which session |
| `max_capacity_kg` | Float | Max weight capacity |
| `asset_link` | Link: Asset | ERPNext asset |
| `last_calibration_date` | Date | Calibration tracking |
| `calibration_certificate` | Attach | Certificate file |
| `next_calibration_date` | Date | Next calibration due |
| `notes` | Small Text | Notes |

---

### 8. POS Profile Scrap

Configuration for POS terminal behavior.

| Field | Type | Description |
|-------|------|-------------|
| `profile_name` | Data | Unique name |
| `is_active` | Check | Enable/disable |
| `price_list` | Link: Price List | Default price list |
| `warehouse` | Link: Warehouse | Stock destination |
| `show_price` | Check | Show prices to operator |
| `items` | Table: POS Profile Item | Items to display |

---

## API Endpoints

All endpoints in `scrap_metal_suite/api/v1/pos.py`

### Authentication

All endpoints call `check_pos_operator()` which requires:
- User is logged in (not Guest)
- User has role "POS Operator" OR "System Manager"

---

### Session Management

#### `get_active_session()`
Get current user's open session with scale info.

**Returns:**
```json
{
  "name": "SES-2025-00001",
  "pos_profile": "Main Counter",
  "opening_time": "2025-12-13 08:00:00",
  "scale": "SCALE-001",
  "scale_name": "Platform Scale 1",
  "scale_type": "Platform",
  "scale_usage_type": "Scrap",
  "scale_location": "Warehouse A"
}
```

#### `open_session(pos_profile)`
Start a new POS session.

**Args:** `pos_profile` - POS Profile Scrap name

**Returns:**
```json
{
  "session": "SES-2025-00001",
  "pos_profile": "Main Counter",
  "operator": "user@example.com",
  "opening_time": "2025-12-13 08:00:00"
}
```

**Errors:** Throws if user already has open session.

#### `close_session(session)`
Close session and calculate totals.

**Args:** `session` - POS Session name

**Returns:** Session totals

---

### Scale Management

#### `get_scales(usage_type=None, scale_type=None)`
List available scales with optional filters.

**Args:**
- `usage_type`: "Scrap" or "Truck"
- `scale_type`: "Platform", "Weighbridge", etc.

**Returns:**
```json
[
  {
    "name": "SCALE-001",
    "scale_name": "Platform 1",
    "scale_type": "Platform",
    "usage_type": "Scrap",
    "location": "Warehouse A",
    "is_active": 1,
    "in_use": 0,
    "in_use_by_session": null
  }
]
```

#### `get_scale_by_id(scale_id)`
Get scale by ID or QR code URL.

**Args:** `scale_id` - Scale name or URL (e.g., `https://site.com/scale/SCALE-001`)

**Returns:**
```json
{
  "scale": {
    "name": "SCALE-001",
    "scale_name": "Platform 1",
    "is_active": 1
  }
}
```

#### `set_session_scale(session, scale)`
Assign scale to session (once per session).

**Args:**
- `session`: POS Session name
- `scale`: Scale name

**Effects:**
- Sets `session.scale`
- Marks scale as `in_use = 1`, `in_use_by_session = session`

---

### Order Lookup

#### `lookup_order(query)`
Search POS Orders by name, order_id, or license_plate.

**Search Logic:**
1. Exact match on `name` (no date restriction)
2. Exact match on `order_id` (no date restriction)
3. Exact match on `license_plate` (no date restriction)
4. Partial match with `dropoff_date` within ±2 days of today

**Args:** `query` - Search string (min 2 chars)

**Returns:**
```json
[
  {
    "name": "ORD-2025-00001",
    "order_id": "ABC123",
    "supplier": "SUP-001",
    "supplier_name": "John's Scrap",
    "order_date": "2025-12-13",
    "dropoff_date": "2025-12-13",
    "license_plate": "ABC-1234",
    "status": "Pending"
  }
]
```

#### `get_order_details(order_id)`
Get full order details including truck weights and order items.

**Args:** `order_id` - POS Order name

**Returns:**
```json
{
  "order_id": "ORD-2025-00001",
  "supplier": "SUP-001",
  "supplier_name": "John's Scrap",
  "license_plate": "ABC-1234",
  "order_items": [
    {"item_code": "COPPER-001", "item_name": "Copper Wire", "weight": 100}
  ],
  "existing_scrap_weight": "WGT-2025-00001",
  "gross_weight": 5000,
  "tare_weight": 2000,
  "net_truck_weight": 3000,
  "total_scrap_weight": 2950,
  "weight_variance": 50,
  "weight_variance_percent": 1.67,
  "is_truck_reweighed": 0,
  "is_scrap_reweighed": 0
}
```

---

### Scrap Weighing

#### `create_scrap_weight(session, pos_order, items, remarks=None, existing_scrap_weight=None, reweight_reason=None)`
Create or update scrap weight record.

**Args:**
- `session`: POS Session name
- `pos_order`: POS Order name
- `items`: JSON array `[{"item_code": "...", "weight": 50, "uom": "Kg"}]`
- `remarks`: Optional notes
- `existing_scrap_weight`: If provided, updates existing record (reweight)
- `reweight_reason`: Required if reweighting

**Returns:**
```json
{
  "scrap_weight": "WGT-2025-00001",
  "total_weight": 150,
  "order_id": "ORD-2025-00001",
  "is_reweight": false,
  "total_scrap_weight": 150,
  "weight_variance": -50,
  "weight_variance_percent": -1.67
}
```

**Effects:**
- Creates/updates Scrap Weight record
- Updates POS Order status to "Processed"
- Syncs items to POS Order.items child table
- Calculates weight variance

#### `load_scrap_weight(scrap_weight_id)`
Load existing Scrap Weight for editing/reweight.

**Args:** `scrap_weight_id` - Scrap Weight name

**Returns:**
```json
{
  "name": "WGT-2025-00001",
  "pos_order": "ORD-2025-00001",
  "items": [
    {"item_code": "COPPER-001", "item_name": "Copper Wire", "weight": 50, "uom": "Kg"}
  ],
  "remarks": "Some notes",
  "is_reweight": 0
}
```

#### `get_session_weights(session)`
Get all scrap weights for a session.

**Args:** `session` - POS Session name

**Returns:** List of Scrap Weight summaries

#### `get_session_summary(session)`
Get session statistics.

**Returns:**
```json
{
  "session": { ... },
  "totals": {
    "weight_count": 5,
    "total_weight": 500
  }
}
```

---

### Truck Weighing

#### `record_truck_weight(pos_order, weight_type, weight, scale=None, remarks=None)`
Record gross or tare truck weight.

**Args:**
- `pos_order`: POS Order name
- `weight_type`: "gross" or "tare"
- `weight`: Weight in kg
- `scale`: Scale name (optional)
- `remarks`: Notes (optional)

**Effects:**
- Sets weight field + timestamp + scale
- Calculates `net_truck_weight` if both weights exist
- Calculates variance if scrap weight exists

**Returns:** Updated order weight data

#### `save_truck_remarks(pos_order, remarks)`
Save remarks for truck weighing.

#### `update_total_scrap_weight(pos_order)`
Recalculate total scrap weight from all Scrap Weight records.

#### `mark_reweighed(pos_order, reweight_type)`
Flag order as reweighed.

**Args:**
- `pos_order`: POS Order name
- `reweight_type`: "truck" or "scrap"

---

### Weight Verification

#### `get_weight_verification(pos_order)`
Get comprehensive weight verification summary.

**Returns:**
```json
{
  "name": "ORD-2025-00001",
  "gross_weight": 5000,
  "tare_weight": 2000,
  "net_truck_weight": 3000,
  "total_scrap_weight": 2950,
  "weight_variance": 50,
  "weight_variance_percent": 1.67,
  "scrap_records": [
    {"name": "WGT-001", "total_weight": 2950, "is_reweight": 0}
  ],
  "variance_threshold": 2.0,
  "variance_ok": true,
  "has_truck_weights": true,
  "has_scrap_weights": true
}
```

---

### Profile

#### `get_pos_profile(profile_name)`
Get POS profile configuration with items.

**Returns:**
```json
{
  "profile_name": "Main Counter",
  "warehouse": "Main Warehouse",
  "items": [
    {"item_code": "COPPER-001", "item_name": "Copper Wire", "display_order": 1}
  ]
}
```

---

## Frontend Pages

### `/pos/` - Index
Session start page. Select POS profile and open session.

### `/pos/terminal` - Weighing Terminal
Main scrap weighing interface:
- Scale selection (QR scan or manual)
- Order search (by ID, plate, or name)
- Item grid from POS profile
- Cart with weight entry
- Collapsible sections for order details
- Reweight capability
- "From Order" tab to load expected items

### `/pos/truck` - Truck Weighing
Weighbridge interface:
- Gross weight entry (truck with load)
- Tare weight entry (empty truck)
- Net weight calculation
- Remarks and photo capture
- Variance display

---

## Weight Variance Logic

```python
def _calculate_variance(order):
    if order.net_truck_weight and order.total_scrap_weight:
        order.weight_variance = net_truck_weight - total_scrap_weight
        order.weight_variance_percent = (weight_variance / net_truck_weight) * 100
```

**Interpretation:**
- **Positive variance**: Truck scale shows more weight (normal - moisture, debris)
- **Negative variance**: Scrap scale shows more weight (possible issue)
- **Threshold**: 2% tolerance considered acceptable

---

## Typical Workflow

### 1. Order Creation
Manager creates POS Order with:
- Supplier details
- Drop-off date
- License plate
- Expected items (optional)

### 2. Truck Arrival (Optional)
Truck operator at weighbridge:
1. Search order by plate/ID
2. Record gross weight (loaded truck)

### 3. Scrap Weighing
Terminal operator:
1. Open session, select scale
2. Search order
3. Add items to cart with weights
4. Submit → Creates Scrap Weight record

### 4. Truck Departure (Optional)
Truck operator at weighbridge:
1. Record tare weight (empty truck)
2. System calculates net weight and variance

### 5. Verification
Manager reviews:
- Weight variance within tolerance?
- Reweight if needed

---

## File Structure

```
scrap_metal_suite/
├── scrap_metal_suite/
│   └── doctype/
│       ├── pos_order/
│       ├── pos_order_item/
│       ├── pos_order_weighed_item/
│       ├── scrap_weight/
│       ├── scrap_weight_item/
│       ├── pos_session/
│       ├── pos_profile_scrap/
│       ├── pos_profile_item/
│       └── scale/
│
├── api/v1/
│   └── pos.py                    # All POS API endpoints
│
├── www/pos/
│   ├── index.html/py             # Session start
│   ├── terminal.html/py          # Scrap weighing
│   └── truck.html/py             # Truck weighing
│
└── public/
    ├── css/pos.css               # POS styling
    └── js/pos-translations.js    # i18n strings
```

---

## Permissions

| Role | Access |
|------|--------|
| System Manager | Full access to all DocTypes |
| POS Operator | Read Scale, API access via `check_pos_operator()` |

---

## Future Considerations

- Receipt printing
- Scale API integration (auto-read weight)
- Barcode scanning for items
- Stock Entry creation on order completion
- Payment/settlement tracking
- Reports and analytics
