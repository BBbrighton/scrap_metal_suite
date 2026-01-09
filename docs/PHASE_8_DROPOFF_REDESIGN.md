# Phase 8: Dropoff System Redesign

**Created:** 2025-12-28
**Updated:** 2026-01-10
**Status:** ✅ COMPLETED (All core phases done: 8A, 8B, 8C, 8D, 8E)

---

## Prerequisites ✅ COMPLETED

**DateTime Migration (2026-01-09):** Migrated from separate date/time fields to datetime fields.
- **Old:** `dropoff_date` (Date) + `dropoff_start_time` (Time) + `dropoff_end_time` (Time)
- **New:** `dropoff_scheduled_start` (Datetime) + `dropoff_scheduled_end` (Datetime)
- **See:** [DROPOFF_DATETIME_MIGRATION.md](./DROPOFF_DATETIME_MIGRATION.md)

This enables calendar view with time slots and better date range queries.

---

## Overview

This phase consolidates several improvements to the Dropoff system:
1. **Simplified Status Flow** - Reduce from 8 to 5 statuses with auto-transitions
2. **Dual Variance Tracking** - Truck vs Scrap AND Indicated vs Actual
3. **Auto-populate Expected Items** - Instant population from linked POS Orders
4. **Re-allocation Fix** - Fix Issue #1 (reweight on completed dropoff)
5. **Weight Entry Method Tracking** - Manual vs Scale (Auto)
6. **Related Data Consolidation** - Notes and photos from child documents
7. **Per-Item Fulfillment** - Track fulfillment by item, not just total

---

## Decisions Made (Session 5-6)

| Question | Decision |
|----------|----------|
| Variance thresholds | Both default to **0.01%**, configurable per dropoff |
| Status simplification | **5 statuses**: Draft, Scheduled, In Progress, Completed, Cancelled |
| Verification display | Read-only `verification_status` field (Pending/Verified/Needs Review) |
| Auto-populate trigger | **Hybrid**: Client script (instant) + Controller (safety net) |
| Re-allocation | Run on **every save** when Completed (fixes Issue #1) |
| Completed dropoff edits | **Allowed** - weights can be adjusted, re-allocation happens automatically |
| Cannot modify orders | Once Completed, orders cannot be removed (validation enforced) |

---

## 1. Simplified Status Flow

### New Status Flow (5 statuses)

```
Draft ──→ Scheduled ──→ In Progress ──→ Completed
  │           │              │
  │           │              └── Auto: all weights recorded
  │           └── Auto: first weight recorded
  └── Auto: license_plate + dropoff_date set
              │
              └──→ Cancelled (manual, requires reason)
```

| Status | Color | Trigger | Meaning |
|--------|-------|---------|---------|
| **Draft** | Grey | Default | Created, incomplete |
| **Scheduled** | Blue | Auto: has license_plate AND dropoff_date | Ready for truck arrival |
| **In Progress** | Orange | Auto: first weight (gross/tare/scrap) recorded | Weighing happening |
| **Completed** | Green | Auto: has gross + tare + scrap weights | Done, allocations synced |
| **Cancelled** | Dark Grey | Manual (requires reason) | Voided |

### New Read-Only Field: `verification_status`

Computed on every save, shows variance status without affecting workflow:

| Value | Condition | Color |
|-------|-----------|-------|
| `Pending` | Missing gross OR tare OR scrap | Grey |
| `Verified` | All weights AND `truck_variance_ok` AND `indicated_variance_ok` | Green |
| `Needs Review` | All weights AND (variance NOT ok) | Red |

**Key insight:** Status controls workflow, `verification_status` is informational only.

### Auto-Transition Logic (in Controller)

```python
def auto_transition_status(self):
    """Auto-transition status based on data. Runs on before_save."""
    if self.status == "Cancelled":
        return  # Never auto-transition cancelled

    has_gross = self.gross_weight and self.gross_weight > 0
    has_tare = self.tare_weight and self.tare_weight > 0
    has_scrap = self.total_scrap_weight and self.total_scrap_weight > 0

    # Draft → Scheduled: when has license_plate AND dropoff_date
    if self.status == "Draft":
        if self.license_plate and self.dropoff_date:
            self.status = "Scheduled"

    # Scheduled → In Progress: when first weight recorded
    if self.status == "Scheduled":
        if has_gross or has_tare or has_scrap:
            self.status = "In Progress"

    # In Progress → Completed: when all weights done
    if self.status == "In Progress":
        if has_gross and has_tare and has_scrap:
            self.status = "Completed"
```

---

## 2. Dual Variance Tracking

### Two Variance Types

| Variance | Formula | Purpose | Default Threshold |
|----------|---------|---------|-------------------|
| **Truck vs Scrap** | `net_weight - total_scrap_weight` | Detect loss during unloading | 0.01% |
| **Indicated vs Actual** | `total_indicated_weight - total_actual_weight` | Detect supplier over/under-delivery | 0.01% |

### Fields on Dropoff

```
# Truck vs Scrap Variance (rename existing)
variance_threshold_percent: Percent (default 0.01%)
truck_variance: Float (kg) - renamed from truck_variance
truck_variance_percent: Percent
truck_variance_ok: Check - renamed from variance_ok

# Indicated vs Actual Variance (NEW)
indicated_variance_threshold_percent: Percent (default 0.01%)
indicated_variance: Float (kg)
indicated_variance_percent: Percent
indicated_variance_ok: Check

# Combined verification (NEW)
verification_status: Data (read-only) - Pending / Verified / Needs Review
```

### Verification Status Logic

```python
def calculate_verification_status(self):
    """Compute verification_status based on weights and both variances."""
    has_gross = self.gross_weight and self.gross_weight > 0
    has_tare = self.tare_weight and self.tare_weight > 0
    has_scrap = self.total_scrap_weight and self.total_scrap_weight > 0

    if not (has_gross and has_tare and has_scrap):
        self.verification_status = "Pending"
    elif self.truck_variance_ok and self.indicated_variance_ok:
        self.verification_status = "Verified"
    else:
        self.verification_status = "Needs Review"
```

### UI Display in Desk Form

```
┌─────────────────────────────────────────────────────────────────┐
│ Weight Verification (updates on save)                           │
├─────────────────────────────────────────────────────────────────┤
│ Verification Status: [Needs Review]                             │
├─────────────────────────────────────────────────────────────────┤
│ 1. Truck vs Scrap Weight                 Threshold: 0.01%       │
│    Net Truck: 1,500.00 kg  |  Scrap: 1,485.00 kg               │
│    Variance: -15.00 kg (1.0%) ⚠️ Exceeds threshold              │
├─────────────────────────────────────────────────────────────────┤
│ 2. Indicated vs Actual Weight            Threshold: 0.01%       │
│    Indicated: 550.00 kg  |  Actual: 485.00 kg                  │
│    Variance: -65.00 kg (11.8%) ⚠️ Under-delivery                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Auto-populate Expected Items

### Hybrid Approach (Instant + Safety Net)

| Trigger | Implementation | Purpose |
|---------|----------------|---------|
| **Client Script** | On `Dropoff Order.pos_order` change | Instant UI feedback in Desk |
| **Controller** | On `before_save` | Safety net for API/imports |

### Client Script (dropoff.js)

```javascript
frappe.ui.form.on('Dropoff Order', {
    pos_order: function(frm, cdt, cdn) {
        // Triggered INSTANTLY when pos_order field changes
        let row = locals[cdt][cdn];
        if (!row.pos_order) return;

        frappe.call({
            method: 'frappe.client.get',
            args: {
                doctype: 'POS Order',
                name: row.pos_order
            },
            callback: function(r) {
                if (r.message && r.message.order_items) {
                    let existing = frm.doc.expected_items.map(e => e.item);

                    r.message.order_items.forEach(item => {
                        if (!existing.includes(item.item_code)) {
                            let child = frm.add_child('expected_items');
                            child.item = item.item_code;
                            child.item_name = item.item_name;
                            child.indicated_weight = item.weight;
                            child.from_order = row.pos_order;
                        }
                    });

                    frm.refresh_field('expected_items');
                }
            }
        });
    }
});
```

### Controller Safety Net (dropoff.py)

```python
def ensure_expected_items_populated(self):
    """Safety net - ensure expected_items are populated from orders."""
    if not self.orders:
        return

    existing_items = {row.item for row in self.expected_items if row.item}

    for order_row in self.orders:
        if not order_row.pos_order:
            continue

        order_items = frappe.get_all(
            "POS Order Item",
            filters={"parent": order_row.pos_order},
            fields=["item_code", "item_name", "weight"]
        )

        for item in order_items:
            if item.item_code not in existing_items:
                self.append("expected_items", {
                    "item": item.item_code,
                    "item_name": item.item_name,
                    "indicated_weight": item.weight,
                    "from_order": order_row.pos_order
                })
                existing_items.add(item.item_code)
```

### New Field on Dropoff Expected Item

| Field | Type | Description |
|-------|------|-------------|
| `from_order` | Link → POS Order | Tracks which order this item came from (read-only) |

---

## 4. Re-allocation Fix (Issue #1)

### Problem
When a Completed dropoff is reweighed, allocations don't update.

### Solution
Run allocation on **every save** when status is Completed (not just on transition).

### Updated Logic

```python
def allocate_weights_if_completed(self):
    """
    Allocate weights when status is Completed.
    CHANGED: Now runs on EVERY save when Completed (not just transition).
    This fixes Issue #1 (reweight doesn't re-allocate).
    """
    if self.status != "Completed":
        return

    if not self.orders:
        return

    total_scrap = flt(self.total_scrap_weight)
    if not total_scrap:
        return

    # Pro-rata allocation by contracted weight
    total_contracted = 0
    order_contracts = {}

    for order_row in self.orders:
        if order_row.pos_order:
            contracted = flt(frappe.db.get_value(
                "POS Order", order_row.pos_order, "contracted_weight"
            ))
            order_contracts[order_row.pos_order] = contracted
            total_contracted += contracted

    for order_row in self.orders:
        if order_row.pos_order:
            if total_contracted > 0:
                ratio = order_contracts[order_row.pos_order] / total_contracted
                order_row.allocated_weight = flt(total_scrap * ratio, 2)
            else:
                order_row.allocated_weight = flt(total_scrap / len(self.orders), 2)
```

### Also Update Fulfillment on Every Save

```python
def on_update(self):
    """After save, update linked POS Orders if Completed."""
    if self.status == "Completed":
        for order_row in self.orders:
            if order_row.pos_order:
                _recalculate_order_fulfillment(order_row.pos_order)
```

---

## 5. Terminal UI Updates

### Both Terminals Need Updates

| Terminal | File | Changes |
|----------|------|---------|
| Scrap Terminal | `www/pos/terminal.html` | Status CSS classes, pass entry_method |
| Truck Terminal | `www/pos/truck.html` | Status CSS classes, pass entry_method, dual variance display |

### Status CSS Class Updates

Old classes to remove/replace:
- `.status-weighing` → `.status-in-progress`
- `.status-unloading` → `.status-in-progress`
- `.status-verified` → `.status-completed`
- `.status-closed` → `.status-completed`
- `.status-needs-attention` → (remove, use verification_status instead)

New classes to add:
- `.status-in-progress` (orange)
- `.status-completed` (green)

### Truck Terminal - Dual Variance Display

Update the verification panel to show both variances:

```html
<div class="verification-panel dropoff-card" id="variancePanel">
    <div class="verification-panel-header">
        <span class="verification-panel-title" data-i18n="weightVerification">Weight Verification</span>
        <span class="verification-status" id="verificationStatus">Pending</span>
    </div>

    <!-- Truck vs Scrap -->
    <div class="variance-section">
        <div class="variance-header">
            <span data-i18n="truckVsScrap">Truck vs Scrap</span>
            <span class="variance-threshold" id="truckThreshold">0.01%</span>
        </div>
        <div class="variance-row">
            <span>Net: <span id="varNet">--</span></span>
            <span>Scrap: <span id="varScrap">--</span></span>
        </div>
        <div class="variance-result" id="truckVarianceResult">--</div>
    </div>

    <!-- Indicated vs Actual -->
    <div class="variance-section">
        <div class="variance-header">
            <span data-i18n="indicatedVsActual">Indicated vs Actual</span>
            <span class="variance-threshold" id="indicatedThreshold">0.01%</span>
        </div>
        <div class="variance-row">
            <span>Indicated: <span id="varIndicated">--</span></span>
            <span>Actual: <span id="varActual">--</span></span>
        </div>
        <div class="variance-result" id="indicatedVarianceResult">--</div>
    </div>
</div>
```

---

## 6. Weight Entry Method Tracking

### New Fields

| DocType | Field | Options |
|---------|-------|---------|
| Truck Weight | `entry_method` | Scale (Auto) / Manual Entry |
| Scrap Weight | `entry_method` | Scale (Auto) / Manual Entry |

### Terminal Changes

Pass `entry_method` when recording weights:

```javascript
// In recordTruckWeight() and recordScrapWeight()
frappe.call({
    method: 'scrap_metal_suite.api.v1.dropoff.record_truck_weight',
    args: {
        // ... existing args ...
        entry_method: state.isScaleConnected ? 'Scale (Auto)' : 'Manual Entry'
    }
});
```

---

## Implementation Phases

### Phase 8A: Status Simplification + Re-allocation Fix ✅ COMPLETED (2026-01-09)
1. ✅ Update `dropoff.json` - new status options (5 statuses), add `verification_status`
2. ✅ Update `dropoff.py` - `auto_transition_status()`, `calculate_verification_status()`, fix allocation
3. ✅ Update `dropoff_list.js` - color indicators for new statuses
4. ✅ Update `api/v1/dropoff.py` - status checks updated
5. ✅ Migration script - migrated existing dropoffs to new status flow
6. ✅ Update terminal CSS - `.status-in-progress`, `.status-completed` classes
7. ✅ Update terminal.html - status handling for "In Progress" (space in name)

**Key Changes:**
- Status options: Draft → Scheduled → In Progress → Completed | Cancelled
- Auto-transitions on weight recording (first weight → In Progress, all weights → Completed)
- Read-only `verification_status` field (Pending/Verified/Needs Review)
- Re-allocation now runs on EVERY save when Completed (fixes reweight issue)

### Phase 8B: Dual Variance ✅ COMPLETED (2026-01-10)
1. ✅ Add indicated variance fields to `dropoff.json`:
   - `truck_variance_threshold_percent` (default 0.001 = 0.1%)
   - `indicated_variance_threshold_percent` (default 0.001 = 0.1%)
   - `total_indicated_weight` (calculated from expected_items)
   - `indicated_variance`, `indicated_variance_percent`, `indicated_variance_ok`
2. ✅ Update `dropoff.py` - `calculate_indicated_variance()` method
3. ✅ Update `api/v1/dropoff.py` - return all variance fields including `total_indicated_weight`
4. ✅ Update terminal UI for dual variance display:
   - Truck terminal shows TWO variance sections
   - Client-side real-time calculation using document thresholds
   - Proper translation support (EN/TH)
   - No inline CSS, uses dedicated CSS classes
5. ✅ Add POS Order status auto-transition - "Pending" → "Processing" → "Processed"

**Key Changes:**
- **Truck Variance**: Net Truck Weight vs Total Scrap Weight (detects unloading loss)
- **Indicated Variance**: Supplier Indicated vs Actual Weighed (detects over/under-delivery)
- Both variances have separate thresholds (configurable per dropoff)
- Variances are WARNINGS ONLY (informational, not blockers)
- Client-side calculation in terminals for real-time feedback
- Verification panel hidden on initial load (no dropoff selected)
- Translation keys added: `truckVarianceTitle`, `indicatedVarianceTitle`, `truckVariance`, `indicatedVariance`, `totalActualWeight`
- POS Order now auto-transitions status based on fulfillment progress

### Phase 8C: Auto-populate Expected Items ✅ COMPLETED (2026-01-10)
1. ✅ Create `dropoff.js` client script - auto-populate on POS Order selection
2. ✅ Add server-side validation in `dropoff.py` - validate expected items match orders
3. ✅ Create custom whitelisted API `api/v1/dropoff.py::get_items_from_orders()` - bypass child table permissions
4. ✅ Set `in_list_view: 1` on child table fields for grid visibility

**Key Decisions:**
- **NO `from_order` field** - User rejected, keeping fields minimal (item, item_name, indicated_weight only)
- **Auto-populate items ONLY** - Weights NOT auto-populated, user must enter `indicated_weight` manually
- **Dual validation rules**:
  1. All expected items must exist in at least one linked order (subset validation)
  2. Each linked order must have at least one item in expected items (coverage validation)
- **Simple trigger** - Client script triggers on `pos_order` field change (not status-dependent)
- **User control** - User can add/edit/delete expected items freely
- **Permissions workaround** - Child tables with empty permissions array block `frappe.client.get_list`, even for System Manager
  - Solution: Created custom whitelisted API with explicit `frappe.has_permission()` checks
  - API method: `scrap_metal_suite.api.v1.dropoff.get_items_from_orders(order_names)`
- **Modal editing** - Child tables open modal for editing (normal Frappe behavior), inline editing not required

### Phase 8D: Entry Method Tracking ✅ COMPLETED (2026-01-10)
1. ✅ Add `entry_method` field to `truck_weight.json` and `scrap_weight.json`
2. ✅ Update API endpoints to accept `entry_method` parameter
3. ✅ Update terminals to pass `entry_method` based on scale connection status

**Implementation:**
- Field: Select field with options "Scale (Auto)" / "Manual Entry"
- Default: "Manual Entry"
- In list view: Yes (`in_list_view: 1`)
- Terminal logic: `state.isScaleConnected ? 'Scale (Auto)' : 'Manual Entry'`
- APIs updated: `record_truck_weight()` and `record_scrap_weight()`

### Phase 8E: Terminal UI Updates ✅ COMPLETED (Already Done)
1. ✅ Status CSS classes in `pos.css` - completed in Phase 8A/8B
2. ✅ `terminal.html` status handling - completed in Phase 8A
3. ✅ `truck.html` dual variance panel - completed in Phase 8B

**Note:** This phase was already completed as part of Phase 8A and 8B implementation.

### Phase 8F: Notes & Photos Consolidation 🅿️ PARKED
1. Add `consolidated_notes` field
2. Add `get_all_photos()` virtual method
3. Copy notes on complete

### Phase 8G: Per-Item Fulfillment 🅿️ PARKED
1. Create new child table DocTypes
2. Update allocation logic for per-item
3. Update POS Order fulfillment display

**Note:** Phases 8F and 8G are parked for future consideration.

---

## Files to Modify

| # | File | Changes |
|---|------|---------|
| 1 | `doctype/dropoff/dropoff.json` | Status options, variance fields, verification_status |
| 2 | `doctype/dropoff/dropoff.py` | auto_transition, calculate_verification, fix allocation, auto_populate |
| 3 | `doctype/dropoff/dropoff.js` | NEW - Client script for auto-populate |
| 4 | `doctype/dropoff/dropoff_list.js` | Color indicators for new statuses |
| 5 | `doctype/dropoff_expected_item/dropoff_expected_item.json` | Add from_order field |
| 6 | `doctype/truck_weight/truck_weight.json` | Add entry_method |
| 7 | `doctype/scrap_weight/scrap_weight.json` | Add entry_method |
| 8 | `api/v1/dropoff.py` | Update status checks, accept entry_method |
| 9 | `www/pos/terminal.html` | Status CSS, entry_method |
| 10 | `www/pos/truck.html` | Status CSS, entry_method, dual variance panel |
| 11 | `public/css/pos.css` | Status color classes |
| 12 | `public/js/pos-translations.js` | New translation keys |

---

## Migration Script

```python
def migrate_dropoff_statuses():
    """Migrate old statuses to new simplified statuses."""
    status_map = {
        'Draft': 'Draft',
        'Scheduled': 'Scheduled',
        'Weighing': 'In Progress',
        'Unloading': 'In Progress',
        'Verified': 'Completed',
        'Needs Attention': 'Completed',  # Will show as Needs Review via verification_status
        'Closed': 'Completed',
        'Cancelled': 'Cancelled'
    }

    for old_status, new_status in status_map.items():
        frappe.db.sql("""
            UPDATE `tabDropoff`
            SET status = %s
            WHERE status = %s
        """, (new_status, old_status))

    frappe.db.commit()
```

---

## Summary

This redesign simplifies the Dropoff workflow while adding more useful verification information:

- ✅ **Fewer statuses** (8 → 5) with clear auto-transitions
- ✅ **Dual variance** tracking for both truck/scrap and indicated/actual
- ✅ **Fixed reweight issue** - re-allocation happens on every save
- ✅ **POS Order status** - auto-transitions based on fulfillment
- 🔜 **Instant expected items** population when orders are linked
- 🔜 **Entry method tracking** for audit trail
- 🔜 **Cleaner terminals** with updated status displays

---

## Completed Implementation Summary (2026-01-10)

### Files Modified

#### Backend
1. **`dropoff.json`** - Added dual variance fields, updated status options
2. **`dropoff.py`** - Added `calculate_indicated_variance()`, auto-transitions
3. **`pos_order.py`** - Added `update_status()` auto-transition logic
4. **`api/v1/dropoff.py`** - Return `total_indicated_weight` in API responses

#### Frontend
5. **`truck.html`** - Dual variance verification panel, client-side calculations, translation support
6. **`terminal.html`** - Status CSS handling for "In Progress"
7. **`pos-translations.js`** - Added variance translation keys (EN/TH)
8. **`pos.css`** - Variance section styles

### Technical Highlights

**Percentage Representation:**
- UI displays: 0.1% (user-friendly)
- Database stores: 0.001 (decimal)
- JavaScript converts: `(doc.threshold || 0.001) * 100` for display

**Client-Side Variance Calculation:**
- Uses `state.dropoff.truck_variance_threshold_percent` from document
- Uses `state.dropoff.indicated_variance_threshold_percent` from document
- Real-time calculation before save (no server round-trip)
- Conditional display (indicated variance only shown if data exists)

**Translation Architecture:**
- All labels use `data-i18n` attributes
- JavaScript uses `POS_I18N.t('key')` helper
- Supports EN/TH out of the box

**Status Auto-Transitions:**
- Dropoff: Draft → Scheduled → In Progress → Completed
- POS Order: Pending → Processing → Processed
- Both update automatically on save

---

## Phase 8C Implementation Details (2026-01-10)

### Files Modified

1. **`dropoff.js`** (NEW) - Client script for auto-populating expected items
2. **`dropoff.py`** - Added `validate_expected_items_match_orders()` method
3. **`api/v1/dropoff.py`** - Added `get_items_from_orders()` whitelisted API
4. **`pos_order.json`** - Removed redundant `dropoff_status` field

### Implementation Summary

**Auto-Population Logic:**
- Triggers when POS Order selected in Dropoff Orders child table
- Calls custom API `get_items_from_orders(order_names)`
- Populates `item` and `item_name` only (NOT `indicated_weight`)
- User manually enters weights after auto-population
- Avoids duplicates using Set tracking

**Validation Rules:**
1. **Subset validation**: All expected items must exist in at least one linked order
2. **Coverage validation**: Each linked order must have at least one item in expected items

**Permissions Workaround:**
- Problem: Child tables with `"permissions": []` block `frappe.client.get_list` even for System Manager
- Solution: Created custom whitelisted API with explicit `frappe.has_permission()` checks
- API path: `scrap_metal_suite.api.v1.dropoff.get_items_from_orders`

**Key Code Snippets:**

Client script trigger:
```javascript
frappe.ui.form.on('Dropoff Order', {
    pos_order: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.pos_order) {
            populate_expected_items_from_orders(frm);
        }
    }
});
```

Custom API with security:
```python
@frappe.whitelist()
def get_items_from_orders(order_names):
    # Security check
    for order_name in order_names:
        if not frappe.has_permission("POS Order", "read", order_name):
            frappe.throw(_("No permission to read POS Order: {0}").format(order_name))

    # Fetch items from POS Order Item child table
    items = frappe.get_all(
        "POS Order Item",
        filters={"parent": ["in", order_names]},
        fields=["item_code", "item_name", "parent"]
    )
    return items
```

**Build & Cache Management:**
- Ran `bench clear-cache && bench build --app scrap_metal_suite`
- Ran `bench migrate` to reload DocType metadata
- Required bench restart to serve new JavaScript assets

---

## Phase 8D Implementation Details (2026-01-10)

### Files Modified

1. **`truck_weight.json`** - Added `entry_method` Select field
2. **`scrap_weight.json`** - Added `entry_method` Select field
3. **`api/v1/dropoff.py`** - Updated `record_truck_weight()` and `record_scrap_weight()` to accept `entry_method` parameter
4. **`truck.html`** - Track actual weight source (button vs manual input)
5. **`terminal.html`** - Track actual weight source per item (button vs manual input)

### Implementation Summary

**Field Specification:**
```json
{
  "default": "Manual Entry",
  "fieldname": "entry_method",
  "fieldtype": "Select",
  "in_list_view": 1,
  "label": "Entry Method",
  "options": "Scale (Auto)\nManual Entry",
  "description": "How this weight was recorded"
}
```

**Truck Terminal Integration:**
```javascript
// Track when weight is captured from scale button
function captureAndSaveWeight() {
    const weight = parseFloat(liveWeightValue.textContent);
    if (weight && weight > 0) {
        document.getElementById('weightInput').value = weight.toFixed(2);
        state.weightCapturedFromScale = true;  // Flag as scale capture
        saveWeight();
    }
}

// Clear flag when user manually types
<input oninput="state.weightCapturedFromScale = false" />

// Use flag to determine entry_method
entry_method: state.weightCapturedFromScale ? 'Scale (Auto)' : 'Manual Entry'
```

**Scrap Terminal Integration:**
```javascript
// Track when weight is captured from scale button
function useLiveWeight() {
    if (state.liveWeight !== null) {
        document.getElementById('weightInput').value = state.liveWeight.toFixed(2);
        state.currentItemWeightFromScale = true;  // Flag as scale capture
        addToCart();
    }
}

// Clear flag when user manually types
<input oninput="state.currentItemWeightFromScale = false" />

// Track source per cart item
state.cart.push({
    item_code: item.code,
    weight: weight,
    fromScale: state.currentItemWeightFromScale || false
});

// entry_method = "Scale (Auto)" ONLY if ALL items from scale
const allFromScale = state.cart.every(item => item.fromScale);
entry_method: allFromScale ? 'Scale (Auto)' : 'Manual Entry'
```

**API Changes:**
- `record_truck_weight(...)` - Added optional `entry_method` parameter, defaults to "Manual Entry"
- `record_scrap_weight(...)` - Added optional `entry_method` parameter, defaults to "Manual Entry"

**Critical Fix Applied:**
Initial implementation incorrectly used `state.isScaleConnected` (connection status) to determine entry method. This was wrong because users can manually type/edit weight even when scale is connected.

**Correct Logic:**
- **"Scale (Auto)"** = Weight captured via "Capture Weight" / "Use Live Weight" button
- **"Manual Entry"** = User typed/edited the value OR mixed sources (scrap terminal)

**Benefits:**
- Accurate audit trail for manual vs automated weight capture
- Quality control - flag manual entries for review
- Analytics - track actual scale usage rates (not just connection)
- Compliance - regulatory requirement tracking with correct data

---

## Next Phases (Future Work)

### Phase 9: Print Forms (DRAFT - To Be Discussed)

**Goal:** Create complete print formats for each document, tailored for different audiences.

**Documents to Cover:**
- Dropoff (supplier-facing, internal)
- POS Order
- Truck Weight
- Scrap Weight
- Other weight-related documents

**Considerations:**
- Different versions for different audiences (supplier vs internal)
- Branding and styling requirements
- Required fields for each audience
- Legal/compliance requirements

**Status:** Draft phase, to be discussed and planned.

---

### Phase 10: Scale Integration RE-work

**Goal:** Fix WebSocket reliability and scale connection stability.

**Current Issues:**
- ✅ Scale works initially
- ❌ After terminal refresh, WebSocket connection is lost
- ❌ Need to unplug/replug USB to reconnect
- ❌ Not completely stable/reliable

**Planned Fixes:**
- Implement WebSocket reconnection logic
- Handle terminal refresh gracefully (persist connection or auto-reconnect)
- Auto-reconnect on connection loss
- Better error handling and recovery
- Keep connection alive across page refreshes
- Improve scale connection status indicators

**Benefits:**
- More reliable scale operation
- Better user experience (no manual USB replug)
- Reduced downtime
- Better error recovery

**Status:** Queued for future work.

---

*Updated: 2026-01-10 - Phase 8 COMPLETED (8A, 8B, 8C, 8D, 8E). Phases 8F & 8G parked. Phases 9 & 10 queued.*
