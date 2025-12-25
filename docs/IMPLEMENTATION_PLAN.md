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

## Phase 1: DocTypes & Controllers

### Phase 1A: Create New DocTypes

#### 1A.1 Create Drop-off Order (Child Table)
> Reference: [Part 2.1 - Drop-off Order](./DROPOFF_ARCHITECTURE.md#21-new-data-model), [Part 14.2](./DROPOFF_ARCHITECTURE.md#142-drop-off-order-child-table---final)

**File**: `doctype/dropoff_order/dropoff_order.json`

| Field | Type | Notes |
|-------|------|-------|
| `pos_order` | Link → POS Order | Required |
| `allocated_weight` | Float | Filled at close |

**Decision**: `contracted_weight` is NOT stored - fetched live from POS Order ([Part 13.9](./DROPOFF_ARCHITECTURE.md#139-drop-off-order-contracted_weight---live-fetch))

---

#### 1A.2 Create Drop-off Truck (Child Table)
> Reference: [Part 2.1 - Drop-off Truck](./DROPOFF_ARCHITECTURE.md#21-new-data-model)

**File**: `doctype/dropoff_truck/dropoff_truck.json`

| Field | Type | Notes |
|-------|------|-------|
| `license_plate` | Data | Required |
| `gross_weight` | Float | |
| `gross_weight_scale` | Link → Scale | |
| `gross_weight_time` | Datetime | |
| `gross_weight_operator` | Link → User | |
| `tare_weight` | Float | |
| `tare_weight_scale` | Link → Scale | |
| `tare_weight_time` | Datetime | |
| `tare_weight_operator` | Link → User | |
| `net_weight` | Float | Read-only, calculated |
| `is_reweighed` | Check | |
| `reweight_reason` | Small Text | |
| `reweight_by` | Link → User | |
| `reweight_at` | Datetime | |
| `remarks` | Small Text | |
| `photo` | Attach Image | |

---

#### 1A.3 Create Drop-off (Main DocType)
> Reference: [Part 2.1](./DROPOFF_ARCHITECTURE.md#21-new-data-model), [Part 11](./DROPOFF_ARCHITECTURE.md#part-11-drop-off-status-flow), [Part 14.1](./DROPOFF_ARCHITECTURE.md#141-drop-off-doctype-final)

**File**: `doctype/dropoff/dropoff.json`

| Section | Field | Type | Notes |
|---------|-------|------|-------|
| Core | `naming_series` | Select | `DROP-.YYYY.-` |
| Core | `dropoff_date` | Date | Required |
| Core | `dropoff_time` | Time | |
| Core | `supplier` | Link → Supplier | Set from first order |
| Core | `status` | Select | See status flow below |
| Orders | `orders` | Table → Drop-off Order | Child table |
| Trucks | `trucks` | Table → Drop-off Truck | Child table |
| Verification | `total_truck_weight` | Float | Read-only |
| Verification | `total_scrap_weight` | Float | Read-only |
| Verification | `truck_variance` | Float | Read-only |
| Verification | `truck_variance_percent` | Percent | Read-only |
| Verification | `variance_threshold_percent` | Percent | Default 0.01% |
| Verification | `variance_ok` | Check | Read-only, auto-set |
| Verification | `unallocated_weight` | Float | Read-only ([Part 13.1](./DROPOFF_ARCHITECTURE.md#131-unexpected-item-delivery-unallocated-bucket)) |
| Verification | `unallocated_items` | JSON | Read-only |
| Reweight | `is_reweighed` | Check | |
| Reweight | `reweight_reason` | Small Text | |
| Reweight | `reweight_by` | Link → User | |
| Reweight | `reweight_at` | Datetime | |
| Cancel | `cancellation_reason` | Small Text | Required if cancelled |
| Cancel | `cancelled_by` | Link → User | |
| Cancel | `cancelled_at` | Datetime | |
| | `remarks` | Small Text | |

**Status Options** ([Part 11](./DROPOFF_ARCHITECTURE.md#part-11-drop-off-status-flow)):
- Draft (Grey)
- Scheduled (Blue)
- Weighing (Orange)
- Unloading (Yellow)
- Verified (Purple)
- Closed (Green)
- Cancelled (Red)

**Settings**:
- `track_changes: 1` for audit trail
- `is_submittable: 0` (we use status field, not workflow)

---

### Phase 1B: Modify Existing DocTypes

#### 1B.1 Modify POS Order
> Reference: [Part 2.1 - POS Order modified](./DROPOFF_ARCHITECTURE.md#21-new-data-model), [Part 14.3](./DROPOFF_ARCHITECTURE.md#143-pos-order-modified---final)

**File**: `doctype/pos_order/pos_order.json`

**REMOVE Fields**:
| Field | Reason |
|-------|--------|
| `order_id` | Use document name (ORD-.YYYY.-) instead |
| `dropoff_date` | Moved to Drop-off |
| `license_plate` | Moved to Drop-off Truck |
| `scrap_scale` | Moved to Drop-off |
| `gross_weight` | Moved to Drop-off Truck |
| `gross_weight_scale` | Moved to Drop-off Truck |
| `gross_weight_time` | Moved to Drop-off Truck |
| `tare_weight` | Moved to Drop-off Truck |
| `tare_weight_scale` | Moved to Drop-off Truck |
| `tare_weight_time` | Moved to Drop-off Truck |
| `net_truck_weight` | Moved to Drop-off Truck |
| `weight_variance` | Moved to Drop-off |
| `weight_variance_percent` | Moved to Drop-off |
| `truck_weight_remarks` | Moved to Drop-off Truck |
| `truck_weight_photo` | Moved to Drop-off Truck |
| `is_truck_reweighed` | Moved to Drop-off Truck |
| `is_scrap_reweighed` | Moved to Drop-off |

**ADD Fields** (Fulfillment Section):
| Field | Type | Notes |
|-------|------|-------|
| `contracted_weight` | Float | Sum of order_items, read-only |
| `total_received` | Float | Sum from drop-offs, read-only |
| `fulfillment_percent` | Percent | Read-only |
| `fulfillment_status` | Select | Pending/Partial/Fulfilled/Over-delivered |
| `dropoff_status` | Select | No Drop-off/Scheduled/In Progress/Received ([Part 13.5](./DROPOFF_ARCHITECTURE.md#135-pos-order-drop-off-status)) |
| `variance_threshold_percent` | Percent | Default 0.01% |

---

#### 1B.2 Modify Scrap Weight
> Reference: [Part 2.1 - Scrap Weight modified](./DROPOFF_ARCHITECTURE.md#21-new-data-model), [Part 12](./DROPOFF_ARCHITECTURE.md#part-12-weight-allocation-for-mm-auto-by-item-type)

**File**: `doctype/scrap_weight/scrap_weight.json`

**REMOVE Fields**:
| Field | Reason |
|-------|--------|
| `pos_order` | Allocation happens at close, not at weighing ([Part 12](./DROPOFF_ARCHITECTURE.md#part-12-weight-allocation-for-mm-auto-by-item-type)) |

**ADD Fields**:
| Field | Type | Notes |
|-------|------|-------|
| `dropoff` | Link → Drop-off | Required |

---

### Phase 1C: Create Controllers

#### 1C.1 Drop-off Controller
**File**: `doctype/dropoff/dropoff.py`

**Validations to implement** (from [Part 13](./DROPOFF_ARCHITECTURE.md#part-13-edge-cases--validations)):

| Edge Case | Validation | Reference |
|-----------|------------|-----------|
| 13.3 | Single supplier per drop-off | [Link](./DROPOFF_ARCHITECTURE.md#133-single-supplier-per-drop-off-validation) |
| 13.10 | No duplicate license plates | [Link](./DROPOFF_ARCHITECTURE.md#1310-duplicate-license-plate-in-same-drop-off) |
| 13.12 | No duplicate orders | [Link](./DROPOFF_ARCHITECTURE.md#1312-duplicate-pos-order-in-same-drop-off) |
| 13.16 | Lock dropoff_date after weighing | [Link](./DROPOFF_ARCHITECTURE.md#1316-drop-off-date-changed-after-weighing-started-desk) |
| 13.21 | Cannot remove orders from Closed | [Link](./DROPOFF_ARCHITECTURE.md#1321-order-removed-from-drop-off-after-weighing-desk) |
| 13.22 | Cannot remove trucks with weights | [Link](./DROPOFF_ARCHITECTURE.md#1322-truck-removed-from-drop-off-after-weights-recorded-desk) |

```python
# dropoff.py structure
class Dropoff(Document):
    def validate(self):
        self.validate_single_supplier()      # 13.3
        self.validate_no_duplicate_plates()  # 13.10
        self.validate_no_duplicate_orders()  # 13.12
        self.validate_date_not_changed()     # 13.16
        self.validate_closed_immutable()     # 13.21, 13.22

    def before_save(self):
        self.set_supplier_from_orders()
        self.calculate_totals()

    def on_cancel(self):
        self.recalculate_order_fulfillment()  # 13.4
```

---

#### 1C.2 POS Order Controller Updates
**File**: `doctype/pos_order/pos_order.py`

**Add validation** ([Part 13.11](./DROPOFF_ARCHITECTURE.md#1311-pos-order-cancelled-after-drop-off-created)):
```python
def before_cancel(self):
    # Prevent cancellation if linked to active drop-off
    pass
```

---

#### 1C.3 Scrap Weight Controller Updates
**File**: `doctype/scrap_weight/scrap_weight.py`

**Add validation** ([Part 13.13](./DROPOFF_ARCHITECTURE.md#1313-scrap-weight-deleted-after-drop-off-closed)):
```python
def before_cancel(self):
    # Prevent deletion if linked to Closed drop-off
    pass
```

---

### Phase 1D: Migration & Desk Testing

```bash
# Run migration
bench migrate

# Test in Desk
1. Create POS Order
2. Create Drop-off, link order
3. Add truck to Drop-off
4. Verify validations work
```

---

## Phase 2: API Implementation

### Phase 2A: Core API Setup
> Reference: [Part 4.4](./DROPOFF_ARCHITECTURE.md#44-new-dropoffpy-api-complete)

**File**: `api/v1/dropoff.py`

#### 2A.1 Auth & Permission Check
```python
def check_pos_operator():
    """Same auth check as pos.py"""
```

#### 2A.2 lookup_dropoff(query)
> Reference: [Part 4.4](./DROPOFF_ARCHITECTURE.md#44-new-dropoffpy-api-complete)

Search by Drop-off ID or license plate.

#### 2A.3 get_dropoff_details(dropoff)
> Reference: [Part 4.4](./DROPOFF_ARCHITECTURE.md#44-new-dropoffpy-api-complete)

Return full drop-off details for terminal display.

---

### Phase 2B: Truck Weight APIs

#### 2B.1 record_truck_weight(dropoff, license_plate, weight_type, weight, scale)
> Reference: [Part 4.4](./DROPOFF_ARCHITECTURE.md#44-new-dropoffpy-api-complete)

**Validations to implement**:
| Edge Case | Validation | Reference |
|-----------|------------|-----------|
| 13.14 | Gross before tare | [Link](./DROPOFF_ARCHITECTURE.md#1314-tare-weight-recorded-before-gross-weight-terminal) |
| 13.20 | Tare < gross | [Link](./DROPOFF_ARCHITECTURE.md#1320-tare-weight-greater-than-or-equal-to-gross-weight-terminal) |
| 13.23 | Weight ≤ scale max | [Link](./DROPOFF_ARCHITECTURE.md#1323-weight-exceeds-scale-maximum-terminal) |

**Auto-transitions** ([Part 11](./DROPOFF_ARCHITECTURE.md#auto-transitions)):
- Scheduled → Weighing (first gross recorded)

#### 2B.2 mark_truck_reweighed(dropoff, license_plate, reason)

#### 2B.3 save_truck_remarks(dropoff, license_plate, remarks, photo)

---

### Phase 2C: Scrap Weight APIs

#### 2C.1 record_scrap_weight(session, dropoff, items, ...)
> Reference: [Part 4.4](./DROPOFF_ARCHITECTURE.md#44-new-dropoffpy-api-complete)

**Validations**:
| Edge Case | Validation | Reference |
|-----------|------------|-----------|
| 13.15 | Zero weight warning | [Link](./DROPOFF_ARCHITECTURE.md#1315-zero-weight-items-terminal) |
| 13.23 | Weight ≤ scale max | [Link](./DROPOFF_ARCHITECTURE.md#1323-weight-exceeds-scale-maximum-terminal) |

**Auto-transitions** ([Part 11](./DROPOFF_ARCHITECTURE.md#auto-transitions)):
- Weighing → Unloading (all trucks have gross, first scrap recorded)

#### 2C.2 load_scrap_weight(scrap_weight_id)

---

### Phase 2D: Verification & Completion APIs

#### 2D.1 get_dropoff_verification(dropoff)
> Reference: [Part 4.4](./DROPOFF_ARCHITECTURE.md#44-new-dropoffpy-api-complete)

#### 2D.2 complete_dropoff(dropoff)
> Reference: [Part 4.4](./DROPOFF_ARCHITECTURE.md#44-new-dropoffpy-api-complete), [Part 13.6](./DROPOFF_ARCHITECTURE.md#136-validation-before-complete-drop-off)

**Completion validations**:
1. At least one order linked
2. At least one truck
3. All trucks have gross AND tare
4. At least one scrap weight recorded
5. Variance warning (not blocking)

**Negative variance warning** ([Part 13.18](./DROPOFF_ARCHITECTURE.md#1318-negative-variance-scrap--truck))

---

### Phase 2E: Internal Functions

#### 2E.1 _auto_allocate_scrap_to_orders(dropoff_doc)
> Reference: [Part 12](./DROPOFF_ARCHITECTURE.md#part-12-weight-allocation-for-mm-auto-by-item-type)

Pro-rata allocation by item type. Unallocated items go to bucket ([Part 13.1](./DROPOFF_ARCHITECTURE.md#131-unexpected-item-delivery-unallocated-bucket)).

#### 2E.2 _sync_fulfillment_to_orders(dropoff_doc)
> Reference: [Part 13.2](./DROPOFF_ARCHITECTURE.md#132-multi-day-fulfillment-aggregation)

Sum `allocated_weight` from ALL non-cancelled drop-offs.

#### 2E.3 _calculate_dropoff_totals(dropoff_doc)
> Reference: [Part 13.18](./DROPOFF_ARCHITECTURE.md#1318-negative-variance-scrap--truck)

#### 2E.4 _update_order_dropoff_status(pos_order_name)
> Reference: [Part 13.5](./DROPOFF_ARCHITECTURE.md#135-pos-order-drop-off-status)

---

### Phase 2F: Hooks Integration

**File**: `hooks.py`

```python
doc_events = {
    "Drop-off": {
        "on_update": "scrap_metal_suite.api.v1.dropoff.on_dropoff_update",
        "on_cancel": "scrap_metal_suite.api.v1.dropoff.on_dropoff_cancel"
    },
    "Scrap Weight": {
        "after_insert": "scrap_metal_suite.api.v1.dropoff.on_scrap_weight_change",
        "on_update": "scrap_metal_suite.api.v1.dropoff.on_scrap_weight_change",
        "on_trash": "scrap_metal_suite.api.v1.dropoff.on_scrap_weight_delete"
    }
}
```

---

## Phase 3: API Testing & Security

### Phase 3A: Lookup & Details Tests

| Test | Expected |
|------|----------|
| lookup by DROP-ID | Returns matching drop-off |
| lookup by license plate | Returns drop-offs with that truck |
| lookup with no results | Returns empty list |
| get_dropoff_details valid | Returns full details |
| get_dropoff_details invalid | Throws error |

---

### Phase 3B: Truck Weight Tests

| Test | Expected | Reference |
|------|----------|-----------|
| Record gross weight | Success, status → Weighing | [Part 11](./DROPOFF_ARCHITECTURE.md#auto-transitions) |
| Record tare before gross | Error | [13.14](./DROPOFF_ARCHITECTURE.md#1314-tare-weight-recorded-before-gross-weight-terminal) |
| Record tare ≥ gross | Error | [13.20](./DROPOFF_ARCHITECTURE.md#1320-tare-weight-greater-than-or-equal-to-gross-weight-terminal) |
| Record weight > scale max | Error | [13.23](./DROPOFF_ARCHITECTURE.md#1323-weight-exceeds-scale-maximum-terminal) |
| Record for non-existent truck | Error | |
| Record for closed drop-off | Error | |

---

### Phase 3C: Scrap Weight Tests

| Test | Expected | Reference |
|------|----------|-----------|
| Record scrap weight | Success | |
| Record with zero weight item | Warning shown | [13.15](./DROPOFF_ARCHITECTURE.md#1315-zero-weight-items-terminal) |
| Record for closed drop-off | Error | |
| Delete scrap from closed drop-off | Error | [13.13](./DROPOFF_ARCHITECTURE.md#1313-scrap-weight-deleted-after-drop-off-closed) |

---

### Phase 3D: Completion & Allocation Tests

| Test | Expected | Reference |
|------|----------|-----------|
| Complete with missing orders | Error | [13.6](./DROPOFF_ARCHITECTURE.md#136-validation-before-complete-drop-off) |
| Complete with missing trucks | Error | [13.6](./DROPOFF_ARCHITECTURE.md#136-validation-before-complete-drop-off) |
| Complete with missing weights | Error | [13.6](./DROPOFF_ARCHITECTURE.md#136-validation-before-complete-drop-off) |
| Complete with negative variance | Warning, success | [13.18](./DROPOFF_ARCHITECTURE.md#1318-negative-variance-scrap--truck) |
| Allocation pro-rata | Correct distribution | [Part 12](./DROPOFF_ARCHITECTURE.md#part-12-weight-allocation-for-mm-auto-by-item-type) |
| Unallocated items | Goes to bucket | [13.1](./DROPOFF_ARCHITECTURE.md#131-unexpected-item-delivery-unallocated-bucket) |
| Fulfillment sync | Order updated correctly | [13.2](./DROPOFF_ARCHITECTURE.md#132-multi-day-fulfillment-aggregation) |

---

### Phase 3E: Edge Case Tests (All 23 Cases)

| Case | Test | Reference |
|------|------|-----------|
| 13.1 | Unexpected item → unallocated | [Link](./DROPOFF_ARCHITECTURE.md#131-unexpected-item-delivery-unallocated-bucket) |
| 13.2 | Multi-day aggregation | [Link](./DROPOFF_ARCHITECTURE.md#132-multi-day-fulfillment-aggregation) |
| 13.3 | Multiple suppliers blocked | [Link](./DROPOFF_ARCHITECTURE.md#133-single-supplier-per-drop-off-validation) |
| 13.4 | Cancel recalculates fulfillment | [Link](./DROPOFF_ARCHITECTURE.md#134-cancel-rollback-mechanism) |
| 13.5 | Order dropoff_status updates | [Link](./DROPOFF_ARCHITECTURE.md#135-pos-order-drop-off-status) |
| 13.6 | Completion validations | [Link](./DROPOFF_ARCHITECTURE.md#136-validation-before-complete-drop-off) |
| 13.7 | Empty drop-off blocked | [Link](./DROPOFF_ARCHITECTURE.md#137-empty-drop-off-validation) |
| 13.8 | Cancel & create new pattern | [Link](./DROPOFF_ARCHITECTURE.md#138-reopen-closed-drop-off-cancel--amend) |
| 13.9 | contracted_weight live fetch | [Link](./DROPOFF_ARCHITECTURE.md#139-drop-off-order-contracted_weight---live-fetch) |
| 13.10 | Duplicate plates blocked | [Link](./DROPOFF_ARCHITECTURE.md#1310-duplicate-license-plate-in-same-drop-off) |
| 13.11 | Cancel order with active drop-off blocked | [Link](./DROPOFF_ARCHITECTURE.md#1311-pos-order-cancelled-after-drop-off-created) |
| 13.12 | Duplicate orders blocked | [Link](./DROPOFF_ARCHITECTURE.md#1312-duplicate-pos-order-in-same-drop-off) |
| 13.13 | Delete scrap from closed blocked | [Link](./DROPOFF_ARCHITECTURE.md#1313-scrap-weight-deleted-after-drop-off-closed) |
| 13.14 | Tare before gross blocked | [Link](./DROPOFF_ARCHITECTURE.md#1314-tare-weight-recorded-before-gross-weight-terminal) |
| 13.15 | Zero weight warning | [Link](./DROPOFF_ARCHITECTURE.md#1315-zero-weight-items-terminal) |
| 13.16 | Date change after weighing blocked | [Link](./DROPOFF_ARCHITECTURE.md#1316-drop-off-date-changed-after-weighing-started-desk) |
| 13.17 | Truck added during weighing allowed | [Link](./DROPOFF_ARCHITECTURE.md#1317-truck-added-after-weighing-started-desk) |
| 13.18 | Negative variance warning | [Link](./DROPOFF_ARCHITECTURE.md#1318-negative-variance-scrap--truck) |
| 13.19 | Multi-session drop-off works | [Link](./DROPOFF_ARCHITECTURE.md#1319-drop-off-spans-multiple-sessions) |
| 13.20 | Tare ≥ gross blocked | [Link](./DROPOFF_ARCHITECTURE.md#1320-tare-weight-greater-than-or-equal-to-gross-weight-terminal) |
| 13.21 | Remove order from closed blocked | [Link](./DROPOFF_ARCHITECTURE.md#1321-order-removed-from-drop-off-after-weighing-desk) |
| 13.22 | Remove truck with weights blocked | [Link](./DROPOFF_ARCHITECTURE.md#1322-truck-removed-from-drop-off-after-weights-recorded-desk) |
| 13.23 | Weight > scale max blocked | [Link](./DROPOFF_ARCHITECTURE.md#1323-weight-exceeds-scale-maximum-terminal) |

---

### Phase 3F: Security Tests

| Test | Expected |
|------|----------|
| API without login | 403 Forbidden |
| API without POS Operator role | 403 Forbidden |
| Access other user's session | Error |
| SQL injection in lookup | Sanitized |
| XSS in remarks | Escaped |

---

## Phase 4: UI (Separate Phase - After API Complete)

> **NOT STARTED** - Will be planned after Phase 3 is complete

Reference: [Part 5](./DROPOFF_ARCHITECTURE.md#part-5-terminal-ui-changes)

---

## Checklist Summary

### Phase 1: DocTypes
- [ ] 1A.1 Create Drop-off Order child table
- [ ] 1A.2 Create Drop-off Truck child table
- [ ] 1A.3 Create Drop-off DocType
- [ ] 1B.1 Modify POS Order (remove truck, add fulfillment)
- [ ] 1B.2 Modify Scrap Weight (add dropoff, remove pos_order)
- [ ] 1C.1 Create Drop-off controller with validations
- [ ] 1C.2 Update POS Order controller
- [ ] 1C.3 Update Scrap Weight controller
- [ ] 1D Run bench migrate & test in Desk

### Phase 2: API
- [ ] 2A.1 Auth check function
- [ ] 2A.2 lookup_dropoff()
- [ ] 2A.3 get_dropoff_details()
- [ ] 2B.1 record_truck_weight()
- [ ] 2B.2 mark_truck_reweighed()
- [ ] 2B.3 save_truck_remarks()
- [ ] 2C.1 record_scrap_weight()
- [ ] 2C.2 load_scrap_weight()
- [ ] 2D.1 get_dropoff_verification()
- [ ] 2D.2 complete_dropoff()
- [ ] 2E.1 _auto_allocate_scrap_to_orders()
- [ ] 2E.2 _sync_fulfillment_to_orders()
- [ ] 2E.3 _calculate_dropoff_totals()
- [ ] 2E.4 _update_order_dropoff_status()
- [ ] 2F Add hooks.py doc_events

### Phase 3: Testing
- [ ] 3A Lookup & details tests
- [ ] 3B Truck weight tests
- [ ] 3C Scrap weight tests
- [ ] 3D Completion & allocation tests
- [ ] 3E All 23 edge case tests
- [ ] 3F Security tests

---

*Last updated: 2025-12-25*
