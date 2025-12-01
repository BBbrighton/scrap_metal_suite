# Scrap Metal Suite - Project Structure Guide

## Overview
This is a Frappe/ERPNext application for scrap metal management. The codebase follows a modular structure to keep code organized, maintainable, and scalable.

## Directory Structure

```
scrap_metal_suite/
├── scrap_metal_suite/          # Main application module
│   ├── api/                    # All API endpoints
│   │   ├── v1/                 # Versioned API (whitelisted methods)
│   │   │   ├── inventory.py    # Inventory endpoints
│   │   │   ├── pricing.py      # Pricing endpoints
│   │   │   ├── transactions.py # Transaction endpoints
│   │   │   └── reports.py      # Report endpoints
│   │   ├── webhooks/           # Incoming webhook handlers
│   │   │   ├── payment.py      # Payment gateway webhooks
│   │   │   └── shipping.py     # Shipping webhooks
│   │   └── integrations/       # Third-party integrations
│   │       ├── payment_gateway.py
│   │       └── market_data.py
│   │
│   ├── services/               # Business logic layer
│   │   ├── pricing/            # Pricing calculations
│   │   │   ├── calculator.py   # Price calculation logic
│   │   │   ├── market_rates.py # Market rate management
│   │   │   └── quotation.py    # Quotation generation
│   │   ├── inventory/          # Stock management
│   │   │   ├── stock.py        # Stock operations
│   │   │   ├── materials.py    # Material tracking
│   │   │   └── warehouse.py    # Warehouse operations
│   │   ├── reporting/          # Report generation
│   │   │   ├── generators.py   # Report builders
│   │   │   ├── analytics.py    # Data analytics
│   │   │   └── exporters.py    # PDF/Excel export
│   │   └── notifications/      # Notification handling
│   │       ├── email.py        # Email notifications
│   │       ├── sms.py          # SMS notifications
│   │       └── templates.py    # Message templates
│   │
│   ├── utils/                  # Shared utilities
│   │   ├── helpers.py          # General helpers
│   │   ├── validators.py       # Data validation
│   │   ├── formatters.py       # Data formatting
│   │   └── constants.py        # App constants
│   │
│   ├── overrides/              # DocType class overrides
│   │   ├── sales_invoice.py    # Custom Sales Invoice
│   │   └── purchase_order.py   # Custom Purchase Order
│   │
│   ├── tasks/                  # Scheduled/background tasks
│   │   ├── daily.py            # Daily scheduled tasks
│   │   ├── hourly.py           # Hourly scheduled tasks
│   │   ├── weekly.py           # Weekly scheduled tasks
│   │   └── queued.py           # Background job handlers
│   │
│   ├── fixtures/               # Data fixtures (JSON)
│   │   ├── custom_field.json   # Custom field definitions
│   │   ├── property_setter.json # Property setters
│   │   └── role.json           # Role definitions
│   │
│   ├── www/                    # Website pages (public)
│   │   ├── portal/             # Customer/supplier portal pages
│   │   ├── dashboard/          # Dashboard pages
│   │   └── reports/            # Public report pages
│   │
│   ├── templates/              # Jinja templates
│   │   ├── pages/              # Full page templates
│   │   └── includes/           # Partial templates
│   │
│   ├── public/                 # Static assets
│   │   ├── js/
│   │   │   ├── components/     # Reusable JS components
│   │   │   └── pages/          # Page-specific JS
│   │   ├── css/
│   │   │   ├── components/     # Component styles
│   │   │   └── pages/          # Page-specific styles
│   │   └── images/             # Image assets
│   │
│   ├── scrap_metal_suite/      # DocTypes module
│   │   └── doctype/            # DocType definitions
│   │
│   ├── hooks.py                # Frappe hooks configuration
│   ├── modules.txt             # Module list
│   └── patches.txt             # Migration patches
│
├── CLAUDE.md                   # This file
├── README.md                   # Project readme
├── pyproject.toml              # Python project config
└── license.txt                 # License
```

## Code Organization Guidelines

### 1. API Endpoints (`api/`)
- Use `@frappe.whitelist()` decorator for all public endpoints
- Keep endpoint functions thin - delegate to services
- Version APIs in subfolders (v1, v2) for backwards compatibility
- Group endpoints by domain (inventory, pricing, etc.)

```python
# api/v1/inventory.py
import frappe
from scrap_metal_suite.services.inventory import stock

@frappe.whitelist()
def get_stock_levels(warehouse=None):
    """Get current stock levels"""
    return stock.get_levels(warehouse)
```

### 2. Services (`services/`)
- Contains all business logic
- Services are called by API endpoints and DocType controllers
- Each service module handles one domain
- Keep files under 300 lines - split into multiple files if needed

```python
# services/inventory/stock.py
import frappe

def get_levels(warehouse=None):
    """Get stock levels, optionally filtered by warehouse"""
    filters = {}
    if warehouse:
        filters["warehouse"] = warehouse
    return frappe.get_all("Bin", filters=filters, fields=["item_code", "actual_qty"])
```

### 3. DocType Overrides (`overrides/`)
- Extend standard ERPNext DocTypes here
- Register in hooks.py under `override_doctype_class`
- Keep overrides focused - use services for complex logic

```python
# overrides/sales_invoice.py
from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice

class CustomSalesInvoice(SalesInvoice):
    def validate(self):
        super().validate()
        # Custom validation here
```

### 4. Scheduled Tasks (`tasks/`)
- Register in hooks.py under `scheduler_events`
- Use background jobs for long-running operations
- Keep task functions focused and idempotent

### 5. Website Pages (`www/`)
- Each `.html` or `.py` file creates a route
- Use subfolders to organize by feature
- Corresponding `.py` file provides context

### 6. Fixtures (`fixtures/`)
- Export with: `bench export-fixtures`
- Register in hooks.py under `fixtures`
- Use for Custom Fields, Property Setters, Roles, etc.

### 7. Utilities (`utils/`)
- Shared helper functions
- Constants and configuration
- Validators and formatters

## File Size Guidelines
- **Target**: < 200 lines per file
- **Maximum**: 400 lines per file
- If a file exceeds limits, split by:
  - Functionality (handlers, validators, formatters)
  - Entity (by DocType or domain)
  - Operation type (CRUD operations)

## Naming Conventions
- **Files**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **DocTypes**: Title Case with spaces

## Import Patterns
```python
# Standard library
import json
from datetime import datetime

# Frappe/ERPNext
import frappe
from frappe import _
from frappe.utils import nowdate, flt

# Local imports (relative)
from ..services.pricing import calculator
from ..utils.helpers import format_currency
```

## Testing
- Place tests in `scrap_metal_suite/tests/`
- Name test files: `test_<module>.py`
- Run with: `bench run-tests --app scrap_metal_suite`

## Common Commands
```bash
# Create new DocType
bench new-doctype "Metal Type" --module "Scrap Metal Suite"

# Export fixtures
bench export-fixtures --app scrap_metal_suite

# Run migrations
bench migrate

# Clear cache
bench clear-cache

# Build assets
bench build --app scrap_metal_suite
```
