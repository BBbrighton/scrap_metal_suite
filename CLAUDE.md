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

### Pending Implementation

- [ ] POS API endpoints (Phase 2)
- [ ] POS web interface `/pos` (Phase 3)
- [ ] Manager POS settings page (Phase 4)
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

---

## Session Notes - Dec 2, 2025

### POS Terminal Issues to Fix

#### 1. Remove `order_id` Field
- **Decision**: Remove `order_id` field from POS Order DocType
- **Reason**: Using document `name` (e.g., `ORD-2025-.00002`) for lookups instead
- **Files to update**:
  - `scrap_metal_suite/doctype/pos_order/pos_order.json` - Remove `order_id` field
  - `api/v1/pos.py` - Update `lookup_order` to search by document `name`
  - `api_test/setup.py` - Remove `order_id` from test order creation
  - `api_test/test_api.py` - Update tests to use document `name`
  - `api_test/test_config.py` - Remove `TEST_ORDER_ID`

#### 2. API Lookup Not Working in Browser
- `lookup_order` API passes bench tests but fails in browser terminal
- **Debug steps**:
  - Check browser console/network tab for errors
  - Verify CSRF token is being sent correctly
  - Test API directly via curl or browser dev tools

#### 3. Terminal Buttons Not Working
- **Remarks button** - Not saving/working
- **Photo button** - Camera/capture issues
- **Record Weight button** - API call failing
- **Debug**: Check `create_scrap_weight` API and browser console errors

#### 4. Pending Tasks
- [ ] Add POS Operator role check to `terminal.py`
- [ ] Display logged-in operator name in terminal header
- [ ] CSS may need hard refresh (Ctrl+Shift+R) to load

### Files Modified Today
- `pos_order.json` - Added `set_only_once: 1` to `order_id` (will be removed next session)
- Ran `bench migrate` and `bench build`
