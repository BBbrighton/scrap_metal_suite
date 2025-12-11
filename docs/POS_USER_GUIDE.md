# Scrap Metal POS - User Guide

## Table of Contents

1. [Overview](#overview)
2. [Functionality](#functionality)
   - [System Architecture](#system-architecture)
   - [Core Features](#core-features)
   - [Terminals](#terminals)
3. [Controls & DocTypes](#controls--doctypes)
   - [POS Profile Scrap](#pos-profile-scrap)
   - [POS Session](#pos-session)
   - [POS Order](#pos-order)
   - [Scrap Weight](#scrap-weight)
   - [Scale](#scale)
4. [Setup Guide](#setup-guide)
   - [Prerequisites](#prerequisites)
   - [Step 1: Create Scales](#step-1-create-scales)
   - [Step 2: Create POS Profile](#step-2-create-pos-profile)
   - [Step 3: Create User Roles](#step-3-create-user-roles)
   - [Step 4: Create Test Data](#step-4-create-test-data)
5. [How to Use](#how-to-use)
   - [Operator Workflow](#operator-workflow)
   - [Scrap Weighing Terminal](#scrap-weighing-terminal)
   - [Truck Scale Terminal](#truck-scale-terminal)
6. [API Reference](#api-reference)
   - [Session Management](#session-management-apis)
   - [Order Operations](#order-operations-apis)
   - [Weight Recording](#weight-recording-apis)
   - [Scale Management](#scale-management-apis)

---

## Overview

The Scrap Metal POS is a Point-of-Sale system designed for scrap metal buying operations. It features:

- **Dual Terminal Design**: Separate interfaces for scrap weighing and truck weighing
- **Scale Integration**: Track which scale is used for each weighing operation
- **Weight Verification**: Compare truck weights vs. scrap weights with variance calculation
- **Multi-language Support**: English and Thai (EN/TH)
- **Responsive Design**: Works on desktop, tablet, and mobile devices
- **Session Management**: Track operator shifts with totals

---

## Functionality

### System Architecture

```
                          +------------------+
                          |   /pos (Landing) |
                          |   - Login        |
                          |   - Select Scale |
                          +--------+---------+
                                   |
              +--------------------+--------------------+
              |                                         |
    +---------v---------+                    +----------v----------+
    |  Scrap Terminal   |                    |   Truck Terminal    |
    |  /pos/terminal    |                    |   /pos/truck        |
    |                   |                    |                     |
    | - Item Selection  |                    | - Order Lookup      |
    | - Weight Entry    |                    | - Gross Weight      |
    | - Cart Management |                    | - Tare Weight       |
    +---------+---------+                    | - Photo Capture     |
              |                              +----------+----------+
              |                                         |
              +--------------------+--------------------+
                                   |
                          +--------v---------+
                          |    POS Order     |
                          |  (Central Record)|
                          +------------------+
```

### Core Features

| Feature | Description |
|---------|-------------|
| **Session-Based Operations** | All transactions grouped by operator session |
| **Scale Binding** | Each session locks to a specific scale |
| **QR/Barcode Scanning** | Scan order IDs or scale QR codes |
| **Weight Variance** | Auto-calculates difference between truck and scrap weights |
| **Re-weigh Support** | Allow re-weighing of previously processed orders |
| **Category Tabs** | Items grouped by category for quick selection |
| **Dark/Light Theme** | User-selectable interface theme |

### Terminals

#### Scrap Weighing Terminal (`/pos/terminal`)
- Used for weighing individual scrap items
- Category-based item grid
- Weight input with cart management
- Links weights to POS Orders

#### Truck Scale Terminal (`/pos/truck`)
- Used for truck gross/tare weighing
- Order search and selection
- Weight variance calculation
- Photo capture capability
- Remarks for truck operators

---

## Controls & DocTypes

### POS Profile Scrap

Configuration profile that controls POS behavior.

| Field | Type | Description |
|-------|------|-------------|
| `profile_name` | Data | Unique display name (e.g., "Main Counter") |
| `is_active` | Check | Enable/disable this profile |
| `price_list` | Link | Default Price List for pricing |
| `warehouse` | Link | Where purchased stock goes |
| `show_price` | Check | Show prices to operator (default: Yes) |
| `items` | Table | List of items to display on POS |

**Child Table: POS Profile Item**

| Field | Type | Description |
|-------|------|-------------|
| `item_code` | Link | Item to display |
| `item_name` | Data | Auto-fetched from Item |
| `display_order` | Int | Sort order in grid |
| `category` | Data | Category for grouping |

---

### POS Session

Tracks operator work sessions.

| Field | Type | Description |
|-------|------|-------------|
| `naming_series` | Select | Auto: `SES-.YYYY.-` |
| `pos_profile` | Link | Which POS Profile is used |
| `operator` | Link | User who opened session |
| `scale` | Link | Scale bound to this session |
| `status` | Select | `Open` or `Closed` |
| `opening_time` | Datetime | When session started |
| `closing_time` | Datetime | When session ended |
| `total_purchases` | Int | Count of transactions |
| `total_amount` | Currency | Sum of all transaction amounts |
| `total_weight` | Float | Sum of all weights (kg) |

---

### POS Order

Central record for truck-based scrap purchases.

| Field | Type | Description |
|-------|------|-------------|
| `naming_series` | Select | Auto: `ORD-.YYYY.-` |
| `order_id` | Data | Unique identifier for operators |
| `supplier` | Link | Supplier selling scrap |
| `supplier_name` | Data | Auto-fetched |
| `order_date` | Date | Transaction date |
| `license_plate` | Data | Truck license plate |
| `status` | Select | `Pending`, `Processed`, `Cancelled` |

**Truck Weight Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `gross_weight` | Float | Truck + scrap weight (kg) |
| `gross_weight_scale` | Link | Scale used for gross |
| `gross_weight_time` | Datetime | When gross was recorded |
| `tare_weight` | Float | Empty truck weight (kg) |
| `tare_weight_scale` | Link | Scale used for tare |
| `tare_weight_time` | Datetime | When tare was recorded |
| `net_truck_weight` | Float | Gross - Tare (calculated) |

**Variance Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `total_scrap_weight` | Float | Sum from Scrap Weight records |
| `weight_variance` | Float | Net truck - Total scrap (kg) |
| `weight_variance_percent` | Percent | Variance as % of net truck |
| `is_truck_reweighed` | Check | Flag if truck was re-weighed |
| `is_scrap_reweighed` | Check | Flag if scrap was re-weighed |

---

### Scrap Weight

Records individual scrap weighing events.

| Field | Type | Description |
|-------|------|-------------|
| `naming_series` | Select | Auto: `WGT-.YYYY.-` |
| `pos_order` | Link | Parent POS Order |
| `supplier` | Link | Supplier (inherited from order) |
| `posting_date` | Date | When weighed |
| `posting_time` | Time | Time of weighing |
| `is_reweight` | Check | True if re-weighing processed order |
| `session` | Link | POS Session |
| `pos_profile` | Link | Profile used |
| `scale` | Link | Scale used for weighing |
| `items` | Table | Weighted items (Scrap Weight Item) |
| `total_weight` | Float | Sum of item weights |

---

### Scale

Defines weighing scales in the system.

| Field | Type | Description |
|-------|------|-------------|
| `scale_name` | Data | Unique identifier (e.g., `SCALE-001`) |
| `scale_type` | Select | `Platform`, `Weighbridge`, `Hanging`, `Floor`, `Bench` |
| `usage_type` | Select | `Scrap` or `Truck` |
| `location` | Data | Physical location |
| `is_active` | Check | Available for selection |
| `in_use` | Check | Currently being used (auto-set) |
| `in_use_by_session` | Link | Session using this scale |
| `max_capacity_kg` | Float | Maximum weight capacity |
| `last_calibration_date` | Date | Last calibration |
| `next_calibration_date` | Date | Next calibration due |
| `calibration_certificate` | Attach | Uploaded certificate |

---

## Setup Guide

### Prerequisites

1. ERPNext installed and running
2. Scrap Metal Suite app installed
3. Items created for scrap types (Copper, Aluminum, Steel, etc.)
4. Price List created with item prices
5. Suppliers created

### Step 1: Create Scales

Navigate to: **Scrap Metal Suite > Scale > New**

Create at least one scale of each usage type:

**Example Scrap Scale:**
```
Scale Name: SCALE-001
Scale Type: Platform
Usage Type: Scrap
Location: Main Yard
Is Active: Yes
Max Capacity: 500 (kg)
```

**Example Truck Scale:**
```
Scale Name: WEIGHBRIDGE-001
Scale Type: Weighbridge
Usage Type: Truck
Location: Entrance Gate
Is Active: Yes
Max Capacity: 50000 (kg)
```

### Step 2: Create POS Profile

Navigate to: **Scrap Metal Suite > POS Profile Scrap > New**

```
Profile Name: Main Counter
Default Price List: Standard Buying
Warehouse: Stores - YC
Show Price to Operator: Yes

Items to Display:
| Item Code          | Display Order | Category      |
|--------------------|---------------|---------------|
| Copper Wire        | 1             | Copper        |
| Copper Pipe        | 2             | Copper        |
| Aluminum Scrap     | 3             | Aluminum      |
| Aluminum Cans      | 4             | Aluminum      |
| Steel/Iron         | 5             | Ferrous       |
| Stainless Steel    | 6             | Stainless     |
```

### Step 3: Create User Roles

**Create POS Operator Role:**
1. Go to **Setup > Role > New**
2. Name: `POS Operator`
3. Save

**Assign Role to Users:**
1. Go to **Setup > User > [Select User]**
2. Add role: `POS Operator`
3. Save

### Step 4: Create Test Data

**Create a Test POS Order:**

Navigate to: **Scrap Metal Suite > POS Order > New**

```
Order ID: TEST-001
Supplier: [Select a supplier]
Order Date: [Today]
License Plate: ABC-1234
Status: Pending
```

---

## How to Use

### Operator Workflow

```
1. LOGIN
   └── Navigate to /pos
   └── Login with POS Operator account

2. SELECT PROFILE (if multiple exist)
   └── Choose POS Profile from dropdown

3. SELECT TERMINAL
   └── Click "Scrap Weighing" or "Truck Scale" card
   └── Select scale from list (QR scan or click)

4. PROCESS ORDERS
   └── Search for order by ID/license plate
   └── Record weights
   └── Complete transaction

5. CLOSE SESSION
   └── Click "Close Session" button
   └── Review session summary
```

### Scrap Weighing Terminal

**Opening the Terminal:**
1. Go to `/pos`
2. Select "Scrap Weighing"
3. Choose a Scrap-type scale
4. Session opens automatically

**Processing an Order:**

1. **Find Order**
   - Type order ID in search box, OR
   - Click QR icon to scan order barcode

2. **Select Items**
   - Click category tabs to filter items
   - Click item button to select

3. **Enter Weight**
   - Type weight in input field
   - Click "Add to Cart"

4. **Review & Submit**
   - Review items in cart
   - Remove items if needed (X button)
   - Click "Complete" to save

**Session Summary:**
- Click "Summary" button in header
- View total weights and transaction count
- Close session when shift ends

### Truck Scale Terminal

**Opening the Terminal:**
1. Go to `/pos`
2. Select "Truck Scale"
3. Choose a Truck-type scale (weighbridge)
4. Session opens automatically

**Recording Truck Weights:**

1. **Find Order**
   - Search by order ID or license plate
   - Select from results list

2. **Record Gross Weight** (truck enters with scrap)
   - Enter weight in "Gross Weight" field
   - Click "Save Gross"
   - Timestamp recorded automatically

3. **Record Tare Weight** (truck exits empty)
   - Enter weight in "Tare Weight" field
   - Click "Save Tare"
   - Net weight calculated automatically

4. **Review Variance**
   - System shows weight variance
   - Green = within 2% tolerance
   - Red = exceeds tolerance (may need re-weigh)

5. **Add Remarks/Photo** (optional)
   - Enter notes in remarks field
   - Click camera icon to capture photo

---

## API Reference

All APIs require `POS Operator` or `System Manager` role.

Base URL: `/api/method/scrap_metal_suite.api.v1.pos.`

### Session Management APIs

#### `get_active_session`
Get current user's open session.

**Request:**
```python
frappe.call({
    method: "scrap_metal_suite.api.v1.pos.get_active_session"
})
```

**Response:**
```json
{
    "name": "SES-2025-00001",
    "pos_profile": "Main Counter",
    "opening_time": "2025-12-08 09:00:00",
    "scale": "SCALE-001",
    "scale_name": "Platform Scale 1",
    "scale_usage_type": "Scrap"
}
```

---

#### `open_session`
Open a new POS session.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `pos_profile` | String | Yes | POS Profile name |

**Request:**
```python
frappe.call({
    method: "scrap_metal_suite.api.v1.pos.open_session",
    args: {
        pos_profile: "Main Counter"
    }
})
```

**Response:**
```json
{
    "session": "SES-2025-00001",
    "pos_profile": "Main Counter",
    "operator": "operator@example.com",
    "opening_time": "2025-12-08 09:00:00"
}
```

---

#### `close_session`
Close a POS session and get totals.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `session` | String | Yes | Session name |

**Request:**
```python
frappe.call({
    method: "scrap_metal_suite.api.v1.pos.close_session",
    args: {
        session: "SES-2025-00001"
    }
})
```

**Response:**
```json
{
    "total_purchases": 15,
    "total_weight": 1500.5,
    "total_amount": 45000.00
}
```

---

### Order Operations APIs

#### `lookup_order`
Search for POS Orders.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `query` | String | Yes | Search term (order ID, license plate) |

**Search Logic:**
1. Exact match on `name`, `order_id`, or `license_plate` (no date restriction)
2. If no exact match: partial match on today's orders
3. If no results: expand to +/- 2 days

**Request:**
```python
frappe.call({
    method: "scrap_metal_suite.api.v1.pos.lookup_order",
    args: {
        query: "ABC-1234"
    }
})
```

**Response:**
```json
[
    {
        "name": "ORD-2025-00001",
        "order_id": "TEST-001",
        "supplier": "SUP-00001",
        "supplier_name": "John's Scrap",
        "order_date": "2025-12-08",
        "license_plate": "ABC-1234",
        "status": "Pending"
    }
]
```

---

#### `get_order_details`
Get full order details including weights.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `order_id` | String | Yes | POS Order name |

**Request:**
```python
frappe.call({
    method: "scrap_metal_suite.api.v1.pos.get_order_details",
    args: {
        order_id: "ORD-2025-00001"
    }
})
```

**Response:**
```json
{
    "order_id": "ORD-2025-00001",
    "supplier": "SUP-00001",
    "supplier_name": "John's Scrap",
    "order_date": "2025-12-08",
    "license_plate": "ABC-1234",
    "status": "Processed",
    "gross_weight": 15000,
    "gross_weight_time": "2025-12-08 09:30:00",
    "tare_weight": 5000,
    "tare_weight_time": "2025-12-08 10:15:00",
    "net_truck_weight": 10000,
    "total_scrap_weight": 9850,
    "weight_variance": 150,
    "weight_variance_percent": 1.5,
    "is_truck_reweighed": false,
    "is_scrap_reweighed": false
}
```

---

### Weight Recording APIs

#### `create_scrap_weight`
Record scrap weight for an order.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `session` | String | Yes | POS Session name |
| `pos_order` | String | Yes | POS Order name |
| `items` | JSON | Yes | Array of items |
| `remarks` | String | No | Optional notes |

**Items Format:**
```json
[
    {"item_code": "Copper Wire", "weight": 100.5, "uom": "Kg"},
    {"item_code": "Aluminum Scrap", "weight": 50.0, "uom": "Kg"}
]
```

**Request:**
```python
frappe.call({
    method: "scrap_metal_suite.api.v1.pos.create_scrap_weight",
    args: {
        session: "SES-2025-00001",
        pos_order: "ORD-2025-00001",
        items: JSON.stringify([
            {item_code: "Copper Wire", weight: 100.5, uom: "Kg"}
        ]),
        remarks: "First batch"
    }
})
```

**Response:**
```json
{
    "scrap_weight": "WGT-2025-00001",
    "total_weight": 100.5,
    "order_id": "ORD-2025-00001",
    "is_reweight": false,
    "total_scrap_weight": 100.5,
    "weight_variance": null,
    "weight_variance_percent": null
}
```

---

#### `record_truck_weight`
Record truck gross or tare weight.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `pos_order` | String | Yes | POS Order name |
| `weight_type` | String | Yes | `gross` or `tare` |
| `weight` | Float | Yes | Weight in kg |
| `scale` | String | No | Scale name |
| `remarks` | String | No | Optional notes |

**Request:**
```python
frappe.call({
    method: "scrap_metal_suite.api.v1.pos.record_truck_weight",
    args: {
        pos_order: "ORD-2025-00001",
        weight_type: "gross",
        weight: 15000,
        scale: "WEIGHBRIDGE-001"
    }
})
```

**Response:**
```json
{
    "order_id": "ORD-2025-00001",
    "gross_weight": 15000,
    "gross_weight_time": "2025-12-08 09:30:00",
    "gross_weight_scale": "WEIGHBRIDGE-001",
    "tare_weight": null,
    "net_truck_weight": null
}
```

---

#### `get_session_weights`
Get all scrap weights for a session.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `session` | String | Yes | POS Session name |

**Request:**
```python
frappe.call({
    method: "scrap_metal_suite.api.v1.pos.get_session_weights",
    args: {
        session: "SES-2025-00001"
    }
})
```

**Response:**
```json
[
    {
        "name": "WGT-2025-00001",
        "supplier": "SUP-00001",
        "supplier_name": "John's Scrap",
        "pos_order": "ORD-2025-00001",
        "total_weight": 100.5,
        "posting_date": "2025-12-08",
        "posting_time": "09:45:00"
    }
]
```

---

#### `get_session_summary`
Get session statistics.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `session` | String | Yes | POS Session name |

**Request:**
```python
frappe.call({
    method: "scrap_metal_suite.api.v1.pos.get_session_summary",
    args: {
        session: "SES-2025-00001"
    }
})
```

**Response:**
```json
{
    "session": {
        "name": "SES-2025-00001",
        "pos_profile": "Main Counter",
        "operator": "operator@example.com",
        "opening_time": "2025-12-08 09:00:00",
        "status": "Open"
    },
    "totals": {
        "weight_count": 5,
        "total_weight": 1500.5
    }
}
```

---

#### `get_weight_verification`
Get weight verification summary for an order.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `pos_order` | String | Yes | POS Order name |

**Request:**
```python
frappe.call({
    method: "scrap_metal_suite.api.v1.pos.get_weight_verification",
    args: {
        pos_order: "ORD-2025-00001"
    }
})
```

**Response:**
```json
{
    "name": "ORD-2025-00001",
    "gross_weight": 15000,
    "tare_weight": 5000,
    "net_truck_weight": 10000,
    "total_scrap_weight": 9850,
    "weight_variance": 150,
    "weight_variance_percent": 1.5,
    "scrap_records": [
        {
            "name": "WGT-2025-00001",
            "total_weight": 9850,
            "is_reweight": false
        }
    ],
    "variance_threshold": 2.0,
    "variance_ok": true,
    "has_truck_weights": true,
    "has_scrap_weights": true
}
```

---

### Scale Management APIs

#### `get_scales`
Get list of available scales.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `usage_type` | String | No | Filter: `Scrap` or `Truck` |
| `scale_type` | String | No | Filter: `Platform`, `Weighbridge`, etc. |

**Request:**
```python
frappe.call({
    method: "scrap_metal_suite.api.v1.pos.get_scales",
    args: {
        usage_type: "Scrap"
    }
})
```

**Response:**
```json
[
    {
        "name": "SCALE-001",
        "scale_name": "SCALE-001",
        "scale_type": "Platform",
        "usage_type": "Scrap",
        "location": "Main Yard",
        "max_capacity_kg": 500,
        "is_active": true,
        "in_use": false,
        "in_use_by_session": null
    }
]
```

---

#### `get_scale_by_id`
Get scale details by ID (for QR scan).

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `scale_id` | String | Yes | Scale name or URL with scale name |

**Request:**
```python
frappe.call({
    method: "scrap_metal_suite.api.v1.pos.get_scale_by_id",
    args: {
        scale_id: "SCALE-001"
        // or: "https://yoursite.com/scale/SCALE-001"
    }
})
```

**Response:**
```json
{
    "scale": {
        "name": "SCALE-001",
        "scale_name": "SCALE-001",
        "scale_type": "Platform",
        "usage_type": "Scrap",
        "location": "Main Yard",
        "max_capacity_kg": 500,
        "is_active": true
    }
}
```

---

#### `set_session_scale`
Bind a scale to a session.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `session` | String | Yes | POS Session name |
| `scale` | String | Yes | Scale name |

**Request:**
```python
frappe.call({
    method: "scrap_metal_suite.api.v1.pos.set_session_scale",
    args: {
        session: "SES-2025-00001",
        scale: "SCALE-001"
    }
})
```

**Response:**
```json
{
    "session": "SES-2025-00001",
    "scale": "SCALE-001",
    "scale_name": "SCALE-001",
    "scale_type": "Platform",
    "usage_type": "Scrap",
    "location": "Main Yard"
}
```

---

#### `mark_reweighed`
Mark an order as reweighed.

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `pos_order` | String | Yes | POS Order name |
| `reweight_type` | String | Yes | `truck` or `scrap` |

**Request:**
```python
frappe.call({
    method: "scrap_metal_suite.api.v1.pos.mark_reweighed",
    args: {
        pos_order: "ORD-2025-00001",
        reweight_type: "truck"
    }
})
```

**Response:**
```json
{
    "order_id": "ORD-2025-00001",
    "is_truck_reweighed": true,
    "is_scrap_reweighed": false
}
```

---

## Running API Tests

To test the POS APIs:

```bash
bench execute scrap_metal_suite.api_test.test_pos_api.run_all_tests
```

This will run all API tests and report results.

---

## Troubleshooting

### Common Issues

**1. "Session already exists" error**
- Close existing session before opening new one
- Or ask System Manager to close stuck sessions

**2. "Scale already in use" error**
- Scale is bound to another session
- Wait for other operator to close session
- Or ask System Manager to release scale

**3. "POS Operator role required" error**
- User doesn't have POS Operator role
- Add role via Setup > User

**4. Orders not appearing in search**
- Check order date (default searches today +/- 2 days)
- Use exact order ID for older orders

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-08 | Initial release with dual terminal design |
