# Phase 8: Dropoff System Redesign

**Created:** 2025-12-28
**Updated:** 2025-12-29
**Status:** READY FOR IMPLEMENTATION

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

### Phase 8A: Status Simplification + Re-allocation Fix
1. Update `dropoff.json` - new status options, add `verification_status`
2. Update `dropoff.py` - `auto_transition_status()`, `calculate_verification_status()`, fix allocation
3. Update `dropoff_list.js` - color indicators
4. Update `api/v1/dropoff.py` - status checks
5. Migration script for existing data

### Phase 8B: Dual Variance
1. Add indicated variance fields to `dropoff.json`
2. Update `dropoff.py` - `calculate_indicated_variance()`
3. Update terminal UI for dual variance display

### Phase 8C: Auto-populate Expected Items
1. Add `from_order` field to `dropoff_expected_item.json`
2. Create `dropoff.js` client script
3. Add safety net in `dropoff.py`

### Phase 8D: Entry Method Tracking
1. Add `entry_method` to `truck_weight.json` and `scrap_weight.json`
2. Update APIs to accept entry_method
3. Update terminals to pass entry_method

### Phase 8E: Terminal UI Updates
1. Update status CSS classes in `pos.css`
2. Update `terminal.html` status handling
3. Update `truck.html` status handling + dual variance panel

### Phase 8F: Notes & Photos Consolidation (Lower Priority)
1. Add `consolidated_notes` field
2. Add `get_all_photos()` virtual method
3. Copy notes on complete

### Phase 8G: Per-Item Fulfillment (Lower Priority)
1. Create new child table DocTypes
2. Update allocation logic for per-item
3. Update POS Order fulfillment display

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

- **Fewer statuses** (8 → 5) with clear auto-transitions
- **Dual variance** tracking for both truck/scrap and indicated/actual
- **Instant expected items** population when orders are linked
- **Fixed reweight issue** - re-allocation happens on every save
- **Entry method tracking** for audit trail
- **Cleaner terminals** with updated status displays

---

*Updated: 2025-12-29 - Consolidated all decisions from Session 5-6 discussion*
