# Scrap Metal Suite - Project Guide

## Overview
Frappe/ERPNext application for scrap metal buying operations. Includes supplier registration, portal systems, and price management.

## Current Implementation Status

### Completed (Not Yet Tested)

#### 1. Supplier Registration Module
- **DocType**: `Supplier Registration` - Self-service registration form
- **Public Form**: `/supplier-registration-form` - Guest-accessible registration
- **Features**:
  - Auto-creates Supplier, Contact, User on approval
  - Links User -> Contact -> Supplier via Dynamic Links
  - Tracks registration source (Portal vs Manual)

#### 2. Supplier Portal (`/supplier`)
- **Theme**: Light blue (`#1976d2`)
- **Pages**:
  | Route | File | Purpose |
  |-------|------|---------|
  | `/supplier` | index.html/py | Dashboard |
  | `/supplier/price` | price.html/py | View prices |
  | `/supplier/sell` | sell.html/py | Create sales |
  | `/supplier/invoice` | invoice.html/py | View invoices |
  | `/supplier/dropoff` | dropoff.html/py | Schedule dropoffs |
- **Auth**: Requires login + "Supplier" role
- **Sidebar**: Reusable include at `includes/sidebar.html`

#### 3. Manager Portal (`/manager`) - NOT TESTED
- **Theme**: Green (`#2e7d32`)
- **Pages**:
  | Route | File | Purpose |
  |-------|------|---------|
  | `/manager` | index.html/py | Dashboard with KPIs |
  | `/manager/price` | price.html/py | Price announcement |
  | `/manager/world-price` | world-price.html/py | World metal prices |
- **KPIs**: Total suppliers, purchases, weight, pending registrations
- **Sidebar**: Reusable include at `includes/sidebar.html`

#### 4. POS Module - DocTypes Created (NOT TESTED)
- **DocTypes**:
  | DocType | Purpose |
  |---------|---------|
  | `POS Profile Scrap` | Configuration: items to show, price list, settings |
  | `POS Profile Item` | Child table for items in profile |
  | `POS Session` | Track operator sessions (open/close, totals) |
  | `Scrap Purchase` | Individual purchase transactions |
  | `Scrap Purchase Item` | Child table for items in purchase |
- **Design Doc**: See `POS_DESIGN.md` for full specification
- **Status**: Phase 1 complete, Phase 2 (APIs) pending

#### 5. Dropoff Module - COMPLETE
- **DocTypes**: 21 custom doctypes for dropoff management
- **APIs**: 34 endpoints (15 dropoff + 19 POS)
- **Features**:
  - Truck weighing (gross/tare/net)
  - Scrap weight recording per item
  - Dual variance tracking (truck vs scrap, indicated vs actual)
  - Status auto-transitions (Draft → Scheduled → In Progress → Completed)
  - Per-item fulfillment with FIFO allocation
- **Design Doc**: See `docs/DROPOFF_ARCHITECTURE.md`, `docs/PHASE_8_DROPOFF_REDESIGN.md`

#### 6. CCTV Camera Integration - REBUILT, NOT DEPLOYED
- **Purpose**: Capture stills from the fixed Hikvision weighbridge cameras and
  attach them to Truck Weight records
- **Branch**: `cam_integration_v0`
- **Status**: Verified against real hardware 2026-08-17; browser UI not yet
  exercised end-to-end; not deployed to production
- **Read first**: `docs/CAMERA_INTEGRATION_HANDOFF.md` — deployment steps,
  25 known failure modes, and how to extend to the other terminals

**Components**: `Camera` doctype, `camera/service.py` (reusable backend),
`api/v1/camera.py`, `public/js/camera_client.js`, `agent/` (on-site capture
agent), `/camera-test` verification page.

**Two transports**: the Frappe backend fetches directly (dev/on-prem), or an
on-site agent fetches on the camera LAN and uploads (cloud production, since the
cloud server cannot reach `192.168.1.x`). Same terminal code either way.

⚠️ **Three things are not in git** and must be set up per environment — most
importantly a `POS Operator` permission fix that repairs a bug affecting
reweighing and photo attachment on production today. See §3 of the handoff doc.

#### 7. Production Sorting Module - PLANNED
- **Purpose**: QA/QC operations after Dropoff - sort, grade, and verify materials
- **Status**: Planning complete, implementation pending
- **Design Doc**: See `docs/PRODUCTION_SORTING_PLAN.md`

**DocTypes to Create**:
| DocType | Type | Purpose |
|---------|------|---------|
| `Production Sorting Settings` | Single | Global config (threshold, allowed Item Groups) |
| `Production Sorting Item Group` | Child | Allowed Item Groups for sorting |
| `Production Sorting` | Main | Links to Dropoff, contains sorted items |
| `Production Sorting Source Item` | Child | Read-only reference from Dropoff |
| `Production Sorting Item` | Child | Editable sorted items with weights |

**Workflow**:
```
Dropoff (Completed) → Production Sorting → Verified/Needs Review
```

**Key Features**:
- Links 1:1 with completed Dropoff
- Shows source items from Dropoff as reference
- Workers add sorted items (filtered by allowed Item Groups)
- Variance validation: total sorted must match Dropoff total (within threshold)
- Verification status: Pending → Verified / Needs Review

**Implementation Phases**:
- [ ] Phase 1: Settings & child tables
- [ ] Phase 2: Main DocType structure
- [ ] Phase 3: Controller logic (validations, calculations)
- [ ] Phase 4: Client-side JS (filters, real-time variance)
- [ ] Phase 5: Testing & fixtures

### Pending Implementation

- [ ] Production Sorting module (Phase 1-5)
- [ ] Price management via ERPNext Price Lists (Standard/VIP/Premium)
- [ ] Live world price API integration (LME, Kitco)
- [ ] Supplier tier assignment
- [ ] Invoice display in supplier portal
- [ ] Portal authentication/permissions

---

## Directory Structure (Actual)

```
scrap_metal_suite/
├── api/v1/
│   └── __init__.py          # get_countries(), debug_supplier_link()
│
├── overrides/
│   └── supplier.py          # set_source_on_manual_create()
│
├── www/
│   ├── supplier/            # Supplier Portal (blue theme)
│   │   ├── includes/
│   │   │   └── sidebar.html
│   │   ├── index.html/py    # Dashboard
│   │   ├── price.html/py    # Prices
│   │   ├── sell.html/py     # Sell
│   │   ├── invoice.html/py  # Invoices
│   │   ├── dropoff.html/py  # Dropoffs
│   │   └── utils.py         # get_supplier_context(), get_supplier_for_user()
│   │
│   ├── manager/             # Manager Portal (green theme) - NOT TESTED
│   │   ├── includes/
│   │   │   └── sidebar.html
│   │   ├── index.html/py    # Dashboard + KPIs
│   │   ├── price.html/py    # Price announcement
│   │   └── world-price.html/py  # World prices
│   │
│   └── supplier-registration-form.html/py  # Public registration
│
├── public/css/
│   ├── supplier_registration.css  # Registration form styles
│   ├── supplier_portal.css        # Supplier portal (blue)
│   └── manager_portal.css         # Manager portal (green)
│
├── fixtures/
│   └── custom_field.json    # Custom fields for Supplier
│
└── hooks.py                 # Web CSS includes, doc_events, role_home_page
```

## Key Configuration (hooks.py)

```python
# CSS files loaded on web pages
web_include_css = [
    "/assets/scrap_metal_suite/css/supplier_registration.css",
    "/assets/scrap_metal_suite/css/supplier_portal.css",
    "/assets/scrap_metal_suite/css/manager_portal.css"
]

# Redirect suppliers to portal on login
role_home_page = {
    "Supplier": "supplier"
}

# Track how suppliers were created
doc_events = {
    "Supplier": {
        "before_insert": "scrap_metal_suite.overrides.supplier.set_source_on_manual_create"
    }
}
```

## Portal Design Patterns

### Sidebar Include Pattern
Each portal uses a reusable sidebar:
```html
{% include "scrap_metal_suite/www/manager/includes/sidebar.html" %}
```

Sidebar uses `active_page` variable set in Python:
```python
def get_context(context):
    context.active_page = "dashboard"  # Highlights nav item
```

### Color Themes
| Portal | Primary | Active BG | Sidebar BG |
|--------|---------|-----------|------------|
| Supplier | `#1976d2` | `#e3f2fd` | `#f8f9fa` |
| Manager | `#2e7d32` | `#e8f5e9` | `#f8faf8` |

## Common Commands

```bash
# Build CSS assets
bench build --app scrap_metal_suite

# Clear cache (required after template changes)
bench clear-cache

# Export fixtures
bench export-fixtures --app scrap_metal_suite

# Migrate database
bench migrate
```

## Testing Checklist

### Manager Portal (`/manager`) - NOT TESTED
- [ ] Dashboard loads without errors
- [ ] KPI cards display correctly
- [ ] Recent registrations table works
- [ ] Quick action buttons link correctly
- [ ] Price page loads with sample data
- [ ] World price page displays
- [ ] Sidebar navigation works
- [ ] Mobile responsive layout

### Supplier Portal (`/supplier`)
- [ ] Login redirects supplier to portal
- [ ] Sidebar navigation between pages
- [ ] Company info displays correctly
- [ ] Mobile bottom nav works

## Price Tier Strategy (Planned)

Use ERPNext Price Lists:
1. **Standard Buying** - Default for all suppliers
2. **VIP Buying** - Better rates for regulars
3. **Premium Buying** - Best rates for high-volume

Assign via `Supplier.default_price_list` field.

