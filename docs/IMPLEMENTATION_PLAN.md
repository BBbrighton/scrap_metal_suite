# Drop-off Implementation Plan

> **Reference**: See [DROPOFF_ARCHITECTURE.md](./DROPOFF_ARCHITECTURE.md) for full design decisions

---

## Overview

This plan implements the Drop-off centric architecture in 3 main phases:
1. **Phase 1**: DocTypes & Controllers (database layer)
2. **Phase 2**: API Implementation (business logic)
3. **Phase 3**: API Testing & Security (validation)

**UI Phase is separate** - only starts after API is complete and tested.

---

## Phase 1: DocTypes & Controllers ✅ COMPLETED

### Phase 1A: Create New DocTypes

#### 1A.1 Create Drop-off Order (Child Table) ✅
> Reference: [Part 2.1 - Drop-off Order](./DROPOFF_ARCHITECTURE.md#21-new-data-model), [Part 14.2](./DROPOFF_ARCHITECTURE.md#142-drop-off-order-child-table---final)

**File**: `doctype/dropoff_order/dropoff_order.json`

| Field | Type | Notes |
|-------|------|-------|
| `pos_order` | Link → POS Order | Required |
| `allocated_weight` | Float | Filled at close |

**Decision**: `contracted_weight` is NOT stored - fetched live from POS Order ([Part 13.9](./DROPOFF_ARCHITECTURE.md#139-drop-off-order-contracted_weight---live-fetch))

---

#### 1A.2 ~~Create Drop-off Truck (Child Table)~~ → **1-Truck Design** ✅
> **DESIGN CHANGE**: Instead of child table, we use 1-truck-per-dropoff design with `license_plate` directly on Dropoff form.
> Truck Weight DocType added for weighing history/audit trail.

**Files Created**:
- `doctype/dropoff/dropoff.json` - has `license_plate`, `gross_weight`, `tare_weight` fields
- `doctype/truck_weight/truck_weight.json` - audit record per weighing event

---

#### 1A.3 Create Drop-off (Main DocType) ✅
> Reference: [Part 2.1](./DROPOFF_ARCHITECTURE.md#21-new-data-model), [Part 11](./DROPOFF_ARCHITECTURE.md#part-11-drop-off-status-flow), [Part 14.1](./DROPOFF_ARCHITECTURE.md#141-drop-off-doctype-final)

**File**: `doctype/dropoff/dropoff.json`

**Status Options** ([Part 11](./DROPOFF_ARCHITECTURE.md#part-11-drop-off-status-flow)):
- Draft (Grey)
- Scheduled (Blue)
- Weighing (Orange)
- Unloading (Yellow)
- Verified (Purple)
- Needs Attention (Red)
- Closed (Green)
- Cancelled (Red)

---

### Phase 1B: Modify Existing DocTypes ✅

#### 1B.1 Modify POS Order ✅
Added fulfillment fields: `contracted_weight`, `total_received`, `fulfillment_percent`, `fulfillment_status`, `dropoff_status`

#### 1B.2 Modify Scrap Weight ✅
Added `dropoff` link field.

---

### Phase 1C: Create Controllers ✅

#### 1C.1 Drop-off Controller ✅
**File**: `doctype/dropoff/dropoff.py`

**Validations implemented**:
| Edge Case | Validation | Status |
|-----------|------------|--------|
| 13.3 | Single supplier per drop-off | ✅ |
| 13.12 | No duplicate orders | ✅ |
| 13.16 | Lock dropoff_date after weighing | ✅ |
| 13.20 | Tare < gross validation | ✅ |
| 13.21 | Cannot remove orders from Closed | ✅ |
| 13.22 | Cannot remove license plate with weights | ✅ |

**Additional methods**:
- `allocate_weights_if_closing()` - Pro-rata weight allocation
- `update_pos_orders_if_closed()` - Syncs fulfillment to orders
- `sync_actual_items()` - Populates actual_items from Scrap Weight records
- `calculate_totals()` - Variance calculation

---

### Phase 1D: Migration & Desk Testing ✅

---

## Phase 2: API Implementation ✅ COMPLETED

### Phase 2A: Core API Setup ✅
**File**: `api/v1/dropoff.py`

| Function | Status |
|----------|--------|
| `check_pos_operator()` | ✅ |
| `lookup_dropoff(query)` | ✅ (with `.strip()` fix for tabs) |
| `get_dropoff_by_qr(qr_data)` | ✅ |
| `get_dropoff_details(dropoff)` | ✅ (added `expected_items`, `existing_scrap_weight`) |

---

### Phase 2B: Truck Weight APIs ✅

| Function | Status |
|----------|--------|
| `record_truck_weight(dropoff, weight_type, weight, scale, session)` | ✅ |
| `mark_truck_reweighed(dropoff, reason)` | ✅ |
| `save_truck_remarks(dropoff, remarks)` | ✅ |
| `save_truck_photo(dropoff, photo_url)` | ✅ |

---

### Phase 2C: Scrap Weight APIs ✅

| Function | Status |
|----------|--------|
| `record_scrap_weight(session, dropoff, items, ...)` | ✅ |
| `load_scrap_weight(scrap_weight_id)` | ✅ |

---

### Phase 2D: Verification & Completion APIs ✅

| Function | Status |
|----------|--------|
| `get_dropoff_verification(dropoff)` | ✅ |
| `complete_dropoff(dropoff)` | ✅ |

---

### Phase 2E: Internal Functions ✅

| Function | Status |
|----------|--------|
| `_auto_transition_status(doc)` | ✅ |
| `_count_dropoff_orders(dropoff)` | ✅ (SQL sanitizer fix) |
| `_update_session_activity(session)` | ✅ |

---

### Phase 2F: Session Management ✅

**File**: `api/v1/pos.py`
- `update_session_activity(session)` - heartbeat for timeout tracking

**File**: `scheduler.py`
- `close_idle_sessions()` - runs every 15 mins, closes sessions idle > 90 mins

---

## Phase 3: API Testing & Security ✅ COMPLETED (23/23 tests passing)

All edge cases from Part 13 tested and passing.

---

## Phase 4: UI Implementation ✅ MOSTLY COMPLETED

### Scrap Terminal (terminal.html) ✅
| Item | Status |
|------|--------|
| Order → Dropoff rename | ✅ |
| API calls updated (pos.* → dropoff.*) | ✅ |
| WebSerial scale connection | ✅ |
| Manual entry mode | ✅ |
| Scale selection modal | ✅ |
| Scale connection result modal | ✅ |
| Dropoff card with expected items | ✅ |
| Truck Weight (Gross) display | ✅ |

### Truck Terminal (truck.html) ✅ MOSTLY COMPLETE
| Item | Status |
|------|--------|
| Order → Dropoff rename | ✅ |
| API calls updated | ✅ |
| WebSerial scale connection | ✅ |
| Manual entry mode | ✅ |
| Scale selection modal | ✅ |
| Dropoff card with expected items | ✅ |
| Scrap Weight Records panel (collapsible) | ✅ |
| Weight Verification panel | ✅ |
| Variance display (color-coded) | ✅ |
| Panel widths matching | ✅ |
| Photo attached to Truck Weight | ✅ Fixed (Weight Photo child table) |
| Confirmation modal after save | ⏳ Low priority |

---

## Phase 7: Truck Terminal UI Redesign ✅ COMPLETED

> **Status**: Completed
> **Reference**: Apply [pos_refactor_plan.md](./archive/pos_refactor_plan.md) (archived) principles

### Completed ✅

1. **Dropoff Card Redesign**
   - Shows: Supplier, Date, License Plate, Status
   - Expected Items section (collapsible)
   - Consistent styling

2. **Weight Verification Panel**
   - Net Truck Weight vs Total Scrap Weight
   - Variance calculation with percentage
   - Color-coded status (green ≤2%, yellow 2-5%, red >5%)

3. **Scrap Weight Records Panel**
   - Collapsible with smooth animation
   - Shows individual scrap weight documents
   - Total weight display
   - Same width as dropoff card

4. **Scrap Terminal - Truck Weight Display**
   - Shows "Truck Weight (Gross)" / "น้ำหนักรถ (ขาเข้า)"
   - Green highlight for easy reference

5. **Panel Layout**
   - All panels (Dropoff, Variance, Scrap Records) same width
   - Moved inside dropoff-section container

### Remaining Tasks

| Task | Priority |
|------|----------|
| Photo storage - save to Truck Weight | Medium |
| Confirmation banner after weight save | Low |
| Replace dropoff_time with start/end times | Low (calendar feature) |

### Design Decisions (Updated)

| Decision | Choice | Status |
|----------|--------|--------|
| Variance display | Color-coded panel | ✅ Done |
| Scrap records | Collapsible panel | ✅ Done |
| Expected items | Collapsible in dropoff card | ✅ Done |
| Photo storage | Frappe File attachments on Truck Weight (multiple photos) | ✅ Done |
| Confirmation | Inline banner (not modal) | ⚠️ Pending |

### 7E: Checklist (Updated)

- [x] Add variance display with color coding
- [x] Add scrap weight records panel
- [x] Make scrap panel collapsible
- [x] Match panel widths
- [x] Add expected items to dropoff card
- [x] Add truck gross weight to scrap terminal
- [x] Fix expected items API field name (item vs item_code)
- [x] Add null-safety to updateWeightDisplay()
- [x] Photo storage: Use Frappe File attachments (removed dedicated photo field)
- [x] Update save_truck_photo() API for multiple attachments
- [x] Update savePhoto() to show attachment count
- [x] Dynamic variance threshold from Dropoff document
- [ ] Implement inline confirmation banner (low priority)
- [ ] Replace dropoff_time with dropoff_start_time/end_time (for calendar)
- [ ] E2E testing

---

## Known Issues

### 🔴 Reweight on Closed Dropoff Does Not Re-Allocate
- **Root Cause**: `allocate_weights_if_closing()` only runs when transitioning TO Closed
- **Workaround**: Manually change status Closed → Verified → Closed
- **Decision**: TBD

---

## Checklist Summary

### Phase 1: DocTypes ✅
- [x] 1A.1 Create Drop-off Order child table
- [x] 1A.2 ~~Create Drop-off Truck child table~~ → 1-truck design + Truck Weight DocType
- [x] 1A.3 Create Drop-off DocType
- [x] 1B.1 Modify POS Order (add fulfillment fields)
- [x] 1B.2 Modify Scrap Weight (add dropoff link)
- [x] 1C.1 Create Drop-off controller with validations
- [x] 1D Run bench migrate & test in Desk

### Phase 2: API ✅
- [x] 2A.1 Auth check function
- [x] 2A.2 lookup_dropoff()
- [x] 2A.3 get_dropoff_details()
- [x] 2B.1 record_truck_weight()
- [x] 2B.2 mark_truck_reweighed()
- [x] 2B.3 save_truck_remarks()
- [x] 2C.1 record_scrap_weight()
- [x] 2C.2 load_scrap_weight()
- [x] 2D.1 get_dropoff_verification()
- [x] 2D.2 complete_dropoff()

### Phase 3: Testing ✅
- [x] 3A Lookup & details tests
- [x] 3B Truck weight tests
- [x] 3C Scrap weight tests
- [x] 3D Completion & allocation tests
- [x] 3E All 23 edge case tests
- [x] 3F Security tests

### Phase 4: UI ✅ MOSTLY COMPLETE
- [x] Scrap Terminal updates
- [x] Truck Terminal basic updates
- [x] Truck Terminal UI redesign (variance, scrap records, panel layout)
- [x] Expected items in dropoff cards
- [x] Truck gross weight in scrap terminal
- [x] Photo storage: Frappe File attachments (multiple photos per weighing)
- [ ] Confirmation banner
- [ ] E2E testing

---

*Last updated: 2025-12-28 (Phase 7 complete)*
