# Production Sorting Module - Design & Implementation Plan

## Executive Summary

This document defines the architecture for a new **Production Sorting** module within Scrap Metal Suite. The module handles QA/QC operations after materials are delivered via Dropoff - workers sort raw materials into granular categories, grade quality, and verify weights.

**Key Insight**: Production Sorting is the **verification layer** between Dropoff (receiving) and inventory (stock).
- **Dropoff** records what the supplier delivered (raw materials, claimed weights)
- **Production Sorting** records what was actually inside (sorted, graded, verified weights)
- **Variance tracking** ensures sorted weight matches dropoff weight within tolerance

---

## Part 1: Business Requirements

### 1.1 Workflow

```
Supplier Delivers    →    Dropoff Completed    →    Production Sorting    →    Verified Stock
(raw materials)           (weighed at gate)         (sorted, graded, QC)       (ready for use)
```

### 1.2 Example Scenario

**Dropoff DO-25.01.15-001** (what supplier claimed):
| Item | Weight |
|------|--------|
| Gold | 10 kg |
| Copper Grade A | 10 kg |
| **Total** | **20 kg** |

**Production Sorting SORT-25.01.16-001** (after sorting):
| Sorted Item | Item Group | Weight | Notes |
|-------------|------------|--------|-------|
| Gold | Scrap Metal | 9.98 kg | |
| Plastic Bag | Packaging | 0.02 kg | From gold container |
| Copper Grade A | Scrap Metal | 9.00 kg | |
| Copper Grade C | Scrap Metal | 0.80 kg | Downgraded due to contamination |
| Dirt | Waste | 0.20 kg | |
| **Total** | | **20.00 kg** | |

**Result**: Variance = 0 kg → **Verified** ✓

### 1.3 Design Decisions (Confirmed)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Item Classification | Use ERPNext Item Group | No new fields needed, leverages existing hierarchy |
| Weight Matching | Per Dropoff total | Simpler validation; items may transform during sorting |
| Sessions | One-to-one | 1 Dropoff = 1 Production Sorting document |
| Item Filter | Multiple Item Groups | Configurable in settings (Scrap Metal, Packaging, Waste) |
| Source Reference | Show Dropoff items | Workers can compare received vs sorted |
| Integration | None initially | Just record sorting; Stock Entry integration later |

---

## Part 2: Data Model

### 2.1 DocType Overview

```
Production Sorting Settings (Single)
├── variance_threshold_percent (Percent)
├── allowed_item_groups (Table)
│   └── Production Sorting Item Group
│       └── item_group (Link to Item Group)
└── require_supervisor_approval (Check) [Future]

Production Sorting (Main)
├── Header: naming_series, status, dropoff, sorting_date, sorted_by
├── Reference (read-only from Dropoff):
│   ├── dropoff_total_weight
│   ├── license_plate, supplier, supplier_name
│   └── source_items (Table) → Production Sorting Source Item
│       └── item_code, item_name, weight
├── Sorted Items (editable):
│   └── sorted_items (Table) → Production Sorting Item
│       └── item_code, item_name, item_group, weight, remarks
├── Verification (calculated):
│   ├── total_sorted_weight
│   ├── weight_variance, variance_percent
│   ├── variance_threshold_percent
│   ├── variance_ok (Check)
│   └── verification_status
└── Cancellation:
    └── cancellation_reason, cancelled_by, cancelled_at
```

### 2.2 Production Sorting Settings (Single DocType)

**Purpose**: Global configuration for the module

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `variance_threshold_percent` | Percent | 0.1 | Max allowed variance (%) |
| `allowed_item_groups` | Table | - | Which Item Groups can be selected |

**Child Table: Production Sorting Item Group**
| Field | Type | Options |
|-------|------|---------|
| `item_group` | Link | Item Group |

**Default Item Groups**:
- Scrap Metal
- Packaging (or "Bags")
- Waste (or "Debris")

### 2.3 Production Sorting (Main DocType)

**Naming Series**: `SORT-.YY.MM.DD.-`

#### Section: Header
| Field | Type | Notes |
|-------|------|-------|
| `naming_series` | Select | `SORT-.YY.MM.DD.-`, hidden |
| `status` | Select | Draft / In Progress / Completed / Cancelled |
| `dropoff` | Link (Dropoff) | Required, must be Completed |
| `sorting_date` | Date | Default: Today |
| `sorted_by` | Link (User) | Auto-set to session user |

#### Section: Dropoff Reference (Read-only)
| Field | Type | Notes |
|-------|------|-------|
| `dropoff_total_weight` | Float | Fetch from `dropoff.total_actual_weight` |
| `license_plate` | Data | Fetch from `dropoff.license_plate` |
| `supplier` | Link | Fetch from `dropoff.supplier` |
| `supplier_name` | Data | Fetch from supplier |

#### Section: Source Items (Read-only reference)
| Field | Type | Notes |
|-------|------|-------|
| `source_items` | Table | Populated from Dropoff `item_summary` |

**Child Table: Production Sorting Source Item**
| Field | Type | Notes |
|-------|------|-------|
| `item_code` | Link (Item) | Read-only |
| `item_name` | Data | Read-only, fetched |
| `weight` | Float | Read-only |

#### Section: Sorted Items (Editable)
| Field | Type | Notes |
|-------|------|-------|
| `sorted_items` | Table | Worker input |

**Child Table: Production Sorting Item**
| Field | Type | Notes |
|-------|------|-------|
| `item_code` | Link (Item) | Filtered by allowed Item Groups |
| `item_name` | Data | Fetched |
| `item_group` | Link (Item Group) | Fetched |
| `weight` | Float | Required |
| `remarks` | Small Text | Optional (e.g., "contaminated") |

#### Section: Verification (Calculated)
| Field | Type | Notes |
|-------|------|-------|
| `total_sorted_weight` | Float | SUM(sorted_items.weight), read-only |
| `weight_variance` | Float | dropoff_total - total_sorted, read-only |
| `variance_percent` | Percent | ABS(variance / dropoff_total) * 100, read-only |
| `variance_threshold_percent` | Percent | Copied from settings, editable override |
| `variance_ok` | Check | variance_percent <= threshold, read-only |
| `verification_status` | Data | Pending / Verified / Needs Review, read-only |

#### Section: Cancellation
| Field | Type | Notes |
|-------|------|-------|
| `cancellation_reason` | Small Text | Required if status = Cancelled |
| `cancelled_by` | Link (User) | Auto-set |
| `cancelled_at` | Datetime | Auto-set |

---

## Part 3: Controller Logic

### 3.1 Validations

```python
def validate(self):
    self.validate_dropoff_exists()
    self.validate_dropoff_completed()
    self.validate_unique_sorting()
    self.validate_item_groups()
    self.validate_sorted_items_exist()
```

| Validation | Rule | Error Message |
|------------|------|---------------|
| Dropoff exists | `dropoff` field is set | "Dropoff is required" |
| Dropoff completed | Dropoff.status == "Completed" | "Dropoff must be Completed before sorting" |
| Unique sorting | No existing Production Sorting for this Dropoff | "This Dropoff already has a Production Sorting record" |
| Item groups | Each sorted item belongs to allowed groups | "Item {item} is not in allowed Item Groups" |
| Items exist | `sorted_items` table not empty (for completion) | "Add at least one sorted item" |

### 3.2 Calculations (before_save)

```python
def before_save(self):
    self.set_defaults()
    self.populate_source_items()
    self.calculate_totals()
    self.calculate_variance()
    self.set_verification_status()
    self.auto_transition_status()
    self.handle_cancellation()
```

**Calculation Logic**:
```python
def calculate_totals(self):
    self.total_sorted_weight = sum(flt(row.weight) for row in self.sorted_items)

def calculate_variance(self):
    self.weight_variance = flt(self.dropoff_total_weight) - flt(self.total_sorted_weight)
    if flt(self.dropoff_total_weight) > 0:
        self.variance_percent = abs(self.weight_variance / self.dropoff_total_weight) * 100
    else:
        self.variance_percent = 0
    self.variance_ok = self.variance_percent <= flt(self.variance_threshold_percent)

def set_verification_status(self):
    if not self.sorted_items:
        self.verification_status = "Pending"
    elif self.variance_ok:
        self.verification_status = "Verified"
    else:
        self.verification_status = "Needs Review"
```

### 3.3 Status Transitions

```
Draft → In Progress    : When first sorted item is added
In Progress → Completed: Manual action (user clicks Complete button)
Any → Cancelled        : Manual action (requires cancellation_reason)
```

```python
def auto_transition_status(self):
    if self.status == "Cancelled":
        return  # Never auto-transition cancelled

    if self.status == "Draft" and self.sorted_items:
        self.status = "In Progress"
```

### 3.4 Populate Source Items

```python
def populate_source_items(self):
    """Copy item_summary from Dropoff as reference"""
    if not self.dropoff:
        return

    if self.source_items:
        return  # Already populated

    dropoff_doc = frappe.get_doc("Dropoff", self.dropoff)
    for item in dropoff_doc.item_summary:
        self.append("source_items", {
            "item_code": item.item,
            "item_name": item.item_name,
            "weight": item.total_weight
        })
```

---

## Part 4: Client-Side Logic (JS)

### 4.1 Field Triggers

```javascript
frappe.ui.form.on('Production Sorting', {
    dropoff: function(frm) {
        if (frm.doc.dropoff) {
            // Fetch dropoff fields
            frappe.db.get_doc('Dropoff', frm.doc.dropoff).then(dropoff => {
                frm.set_value('dropoff_total_weight', dropoff.total_actual_weight);
                frm.set_value('license_plate', dropoff.license_plate);
                frm.set_value('supplier', dropoff.supplier);
            });
        }
    }
});
```

### 4.2 Item Filter by Allowed Groups

```javascript
frappe.ui.form.on('Production Sorting Item', {
    item_code: function(frm, cdt, cdn) {
        // Get allowed item groups from settings
        frm.set_query('item_code', 'sorted_items', function() {
            return {
                filters: {
                    'item_group': ['in', frm.allowed_item_groups]
                }
            };
        });
    }
});
```

### 4.3 Real-time Variance Display

```javascript
frappe.ui.form.on('Production Sorting Item', {
    weight: function(frm) {
        calculate_totals(frm);
    },
    sorted_items_remove: function(frm) {
        calculate_totals(frm);
    }
});

function calculate_totals(frm) {
    let total = 0;
    (frm.doc.sorted_items || []).forEach(row => {
        total += flt(row.weight);
    });
    frm.set_value('total_sorted_weight', total);

    let variance = flt(frm.doc.dropoff_total_weight) - total;
    frm.set_value('weight_variance', variance);

    if (flt(frm.doc.dropoff_total_weight) > 0) {
        let pct = Math.abs(variance / frm.doc.dropoff_total_weight * 100);
        frm.set_value('variance_percent', pct);
    }
}
```

---

## Part 5: File Structure

```
scrap_metal_suite/scrap_metal_suite/doctype/
├── production_sorting_settings/
│   ├── production_sorting_settings.json
│   ├── production_sorting_settings.py
│   └── __init__.py
│
├── production_sorting_item_group/
│   ├── production_sorting_item_group.json
│   ├── production_sorting_item_group.py
│   └── __init__.py
│
├── production_sorting/
│   ├── production_sorting.json
│   ├── production_sorting.py
│   ├── production_sorting.js
│   └── __init__.py
│
├── production_sorting_source_item/
│   ├── production_sorting_source_item.json
│   ├── production_sorting_source_item.py
│   └── __init__.py
│
└── production_sorting_item/
    ├── production_sorting_item.json
    ├── production_sorting_item.py
    └── __init__.py
```

---

## Part 6: Implementation Phases

### Phase 1: Settings & Child Tables
- [ ] Create `Production Sorting Item Group` (child table)
- [ ] Create `Production Sorting Settings` (Single DocType)
- [ ] Configure default Item Groups

### Phase 2: Main DocType Structure
- [ ] Create `Production Sorting Source Item` (read-only child)
- [ ] Create `Production Sorting Item` (editable child)
- [ ] Create `Production Sorting` (main DocType JSON)

### Phase 3: Controller Logic
- [ ] Implement `production_sorting.py` validations
- [ ] Implement calculations (totals, variance)
- [ ] Implement status transitions
- [ ] Implement source item population

### Phase 4: Client-Side Logic
- [ ] Create `production_sorting.js`
- [ ] Implement dropoff field fetching
- [ ] Implement item filter by allowed groups
- [ ] Implement real-time variance calculation

### Phase 5: Testing & Polish
- [ ] Test: Dropoff must be Completed
- [ ] Test: Unique constraint (one sorting per dropoff)
- [ ] Test: Variance within/outside threshold
- [ ] Test: Status transitions
- [ ] Test: Cancellation flow
- [ ] Add fixtures for default settings

### Phase 6: Production Terminal
- [ ] CSS Refactor: Extract terminal-base.css + pos-theme.css from pos.css
- [ ] Create production-theme.css (orange theme)
- [ ] Create production-translations.js (EN/TH)
- [ ] Create Production Session DocType
- [ ] Add session field to Production Sorting
- [ ] Add check_production_operator() to auth.py
- [ ] Add "Production" to Scale usage_type
- [ ] Create Production API endpoints (api/v1/production.py)
- [ ] Create landing page (/production)
- [ ] Create sorting terminal (/production/terminal)
- [ ] Add idle session scheduler

### Phase 7: Roles & Access Control
- [ ] Create Production Worker + Production Manager roles
- [ ] Set DocType permissions
- [ ] Implement manager override for variance

### Phase 8: Workspace
- [ ] Create Production Sorting workspace JSON
- [ ] Add role_home_page redirect for Production Worker

### Phase 9: Print Formats (A4 + Thermal)
- [ ] Create Sorting Report print format — A4 (Jinja)
- [ ] Create Sorting Receipt print format — 80mm thermal (Jinja)
- [ ] Add print format selection to terminal UI

---

## Part 7: Edge Cases

| # | Case | Expected Behavior |
|---|------|-------------------|
| 1 | Dropoff not yet Completed | Block: "Dropoff must be Completed" |
| 2 | Dropoff already has sorting | Block: "Already has Production Sorting" |
| 3 | Item not in allowed groups | Block: "Item not in allowed Item Groups" |
| 4 | Variance within threshold | verification_status = "Verified" |
| 5 | Variance exceeds threshold | verification_status = "Needs Review" |
| 6 | No sorted items | verification_status = "Pending" |
| 7 | Cancel without reason | Block: "Cancellation reason required" |
| 8 | Delete sorted item | Recalculate totals and variance |
| 9 | Change dropoff after items added | Block: "Cannot change Dropoff with items" |

---

## Part 8: Future Enhancements (Out of Scope)

1. **Stock Entry Integration**: Auto-create Stock Entry on completion
2. **Supervisor Approval**: Require approval for "Needs Review" status
3. **Batch/Lot Tracking**: Assign batch numbers during sorting
4. **Photo Documentation**: Attach photos of sorted materials
5. **Scale Integration**: Direct scale reading like POS terminal
6. **Analytics**: Sorting efficiency reports, grade distribution

---

## Part 9: Testing Checklist

### Unit Tests
- [ ] Variance calculation with various inputs
- [ ] Status transition logic
- [ ] Validation rules

### Integration Tests
- [ ] Create sorting for completed Dropoff
- [ ] Block sorting for non-completed Dropoff
- [ ] Block duplicate sorting
- [ ] Item group filtering
- [ ] Source items population

### User Acceptance Tests
- [ ] Full workflow: Dropoff → Production Sorting → Verified
- [ ] Variance handling (within and outside threshold)
- [ ] Cancellation workflow
- [ ] Item selection from allowed groups only

---

---

## Part 10: Production Terminal (Phase 6)

### 10.1 Production Session DocType

**Naming Series:** `PSORT-SES-.YY.MM.DD.-`

| Field | Type | Notes |
|-------|------|-------|
| `naming_series` | Select | Hidden |
| `operator` | Link (User) | Required, auto-set |
| `scale` | Link (Scale) | Set on first entry |
| `status` | Select | Open / Closed |
| `opening_time` | Datetime | Auto-set on insert |
| `closing_time` | Datetime | Set on close |
| `last_activity` | Datetime | Heartbeat for idle timeout |
| `closed_by` | Link (User) | Auto-set |
| `total_sortings` | Int | Read-only, calculated on close |
| `total_weight_sorted` | Float | Read-only, calculated on close |

**Controller:** Mirror `pos_session.py` — one open session per operator, calculate totals on close, release scale.

**Modification to Production Sorting:** Add `session` (Link to Production Session) field.

### 10.2 Terminal Pages

**Landing Page:** `/production/index.html` + `index.py`
- Auth check (Production Worker/Manager role)
- Active session detection → resume or start new
- Orange theme gradient, language/theme toggle

**Sorting Terminal:** `/production/terminal.html` + `terminal.py`

```
Header: ← Back | X-DESK | Session badge | Operator | Scale badge | Clock | Lang | Theme | Summary | Close
Body:
  Left Panel:  Category tabs (Item Groups) → Item grid (allowed items from Settings)
  Right Panel: Dropoff search/scan → Dropoff details (source items) →
               Sorted items cart → Variance display → Save/Complete/Print buttons
```

**Modals:** Weight Input (live scale + manual), Scanner, Scale Selection (mandatory), Scale Connection, Session Summary, Close Session, Completion Confirmation

### 10.3 API Endpoints (`api/v1/production.py`)

| # | Endpoint | Purpose |
|---|----------|---------|
| 1 | `open_session()` | Create Production Session |
| 2 | `close_session(session)` | Close + calculate totals |
| 3 | `get_active_session()` | Get user's open session with scale config |
| 4 | `update_session_activity(session)` | Heartbeat |
| 5 | `get_session_summary(session)` | Stats for close modal |
| 6 | `lookup_dropoff(query)` | Search completed Dropoffs (exclude already-sorted) |
| 7 | `get_dropoff_for_sorting(dropoff)` | Dropoff details + item_summary |
| 8 | `get_allowed_items()` | Items from allowed Item Groups (from Settings) |
| 9 | `create_sorting(session, dropoff, items)` | Create Production Sorting doc |
| 10 | `update_sorting(sorting_name, items)` | Update sorted items |
| 11 | `complete_sorting(sorting_name)` | Set status to Completed |
| 12 | `get_sorting_for_dropoff(dropoff)` | Check if sorting exists |
| 13 | `set_session_scale(session, scale)` | Assign scale to session |

Every endpoint guarded by `check_production_operator()` from `api/v1/auth.py`.

### 10.4 CSS Architecture (3-Layer)

```
terminal-base.css       → Shared structural CSS (var(--t-*) custom properties)
pos-theme.css           → POS blue color overrides
production-theme.css    → Production orange (#e65100) color overrides + variance UI
```

**Orange Theme:**
- Primary: `#e65100`, Light: `#ff6d00`, Dark: `#bf360c`
- Dark gradient: `linear-gradient(135deg, #1a1a1e, #2e1800)`
- Light bg: `#fff3e0`
- Variance: green (Verified), amber (Pending), red (Needs Review)

### 10.5 Translation Architecture

**Dedicated file:** `production-translations.js` extends `POS_I18N` via `extend()` method.

- `pos-translations.js` — ~300 shared keys (session, scale, cart, dropoff, etc.)
- `production-translations.js` — ~40 production-specific keys (variance, sorting, verification)
- Full EN/TH coverage for both files

**Reused JS modules (no changes):** pos-core.js, scale_reader.js, pos-scanner.js

---

## Part 11: Roles & Access Control (Phase 7)

### Roles

| Role | Purpose |
|------|---------|
| Production Worker | Use terminal, create/edit sorting records, own sessions |
| Production Manager | Verify, override variance, view all records, manage settings |

### DocType Permissions

**Production Sorting:**
- Production Worker: Read, Write, Create
- Production Manager: Read, Write, Create, Delete, Submit, Cancel, Amend

**Production Sorting Settings:**
- Production Manager + System Manager: Read, Write

**Production Session:**
- Production Worker: Read, Write, Create (own only)
- Production Manager: Read, Write, Create, Delete (all)

### Manager Override

Add to Production Sorting: `manager_override` (Check), `manager_override_by` (Link to User).

In `complete_sorting()` API: if variance exceeds threshold, only Production Manager can complete.

---

## Part 12: Workspace (Phase 8)

**Frappe Workspace:** `Production Sorting`
- Module: Scrap Metal Suite
- Icon: factory
- Roles: Production Worker, Production Manager, System Manager
- **Shortcuts:** Sorting Terminal (`/production`), Production Sorting list, Production Sessions list
- **Links:** Production Sorting, Production Session, Production Sorting Settings

**Login redirect:** Production Worker → `/production`

---

## Part 13: Print Formats (Phase 9)

Two print formats for Production Sorting DocType — consistent with existing Weight Receipt pattern.

### 13.1 Sorting Report — A4 Format

**Name:** `Sorting Report` | **Format:** Jinja | **doc_type:** Production Sorting

**Structure** (mirrors Weight Receipt section-by-section):

| # | Section | Content |
|---|---------|---------|
| 1 | Header | Company logo (left) + QR code (right) — same as Weight Receipt |
| 2 | Company Address | Centered address, phone — same as Weight Receipt |
| 3 | Title | "SORTING REPORT" (uppercase, 18pt) |
| 4 | Info Grid | 2-column, 8 fields: Sorting ID, Date, Dropoff Ref, Sorted By, Supplier, License Plate, Status badge, Verification badge |
| 5 | Source Items Table | "#, Item, Unit, Weight" — from `doc.source_items` child table |
| 6 | Sorted Items Table | "#, Item, Item Group, Unit, Weight, Remarks" — from `doc.sorted_items` child table |
| 7 | Weight Verification | Dropoff Total vs Sorted Total, Variance (kg + %), Threshold, color-coded (green/red) |
| 8 | Manager Override | Conditional: shows override manager name + timestamp if `doc.manager_override` |
| 9 | Status | Status badge + processing timestamps |
| 10 | Notes | Cancellation reason, remarks |
| 11 | Signatures | 3 boxes: Worker, Supervisor, Manager |

**CSS:** Reuses Weight Receipt class names (`.receipt-header`, `.order-info`, `.items-table`, `.variance-section`, etc.) for visual consistency. Root class: `.sorting-report`. New classes: `.verification-badge`, `.manager-override-section`.

**Files:**
- `print_format/sorting_report/sorting_report.json`
- `print_format/sorting_report/sorting_report.html`
- `print_format/sorting_report/__init__.py`

### 13.2 Sorting Receipt — 80mm Thermal Format

**Name:** `Sorting Receipt` | **Format:** Jinja | **doc_type:** Production Sorting

**Design constraints:**
- Page: `@page { size: 80mm auto; margin: 3mm; }` (continuous roll)
- Font: Courier New / monospace, 9pt body, 12pt title
- Monochrome (no colors — bold/underline for emphasis)
- Single-column layout (no flexbox grids)
- No logo image (text-only company name)
- No signature boxes (copy label instead: "--- Worker Copy ---")

**Structure:**

| # | Section | Content |
|---|---------|---------|
| 1 | Header | Company name (bold, centered), address, phone |
| 2 | Title | "SORTING REPORT" (centered, 12pt) |
| 3 | Info Block | Sorting ID, Date, Operator, Dropoff ref, Supplier, Plate (key: value rows) |
| 4 | Source Items | Compact list: "Item Name ... Weight kg" + total |
| 5 | Sorted Items | Per-item: "#N Item Name" + "[Group] Weight kg" + total |
| 6 | Variance | Dropoff, Sorted, Diff (kg + %), Threshold, Status (checkmark text) |
| 7 | QR Code | Centered, 40×40mm |
| 8 | Footer | Print timestamp + "--- Worker Copy ---" |

**Files:**
- `print_format/sorting_receipt/sorting_receipt.json`
- `print_format/sorting_receipt/sorting_receipt.html`
- `print_format/sorting_receipt/__init__.py`

### 13.3 Terminal Integration

The terminal "Print" button offers format selection:
- Default: A4 Sorting Report (for office printers)
- Option: Thermal Sorting Receipt (for 80mm receipt printers)
- Uses `frappe.utils.print_format.download_pdf` with `format` parameter

---

## Appendix: Related Files

| File | Purpose |
|------|---------|
| `doctype/dropoff/dropoff.py` | Reference for controller patterns |
| `doctype/dropoff/dropoff.json` | Reference for field structure |
| `docs/DROPOFF_ARCHITECTURE.md` | Dropoff design reference |
| `docs/PHASE_8_DROPOFF_REDESIGN.md` | Variance calculation patterns |
| `api/v1/pos.py` | Reference for terminal API patterns |
| `www/pos/terminal.html` | Reference for terminal UI patterns |
| `public/css/pos.css` | Reference for CSS patterns (standalone production.css) |
| `public/js/pos-translations.js` | Base translation system (POS_I18N with extend()) |
| `public/js/pos-core.js` | Shared terminal utilities |
| `print_format/weight_receipt/weight_receipt.html` | Reference for A4 print format pattern |
| `print_format/weight_receipt/weight_receipt.json` | Reference for print format JSON metadata |
