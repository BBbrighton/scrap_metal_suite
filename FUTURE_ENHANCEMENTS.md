# Future Enhancements

This document tracks planned improvements for the Scrap Metal Suite POS system.

---

## 1. Scale Info Propagation

**Priority**: Medium
**Status**: Planned

### Current State
- Scale is linked to `POS Session` only
- `POS Order` and `Scrap Weight` don't have direct scale reference

### Proposed Changes
- Add `scale` field to `POS Order` (set when order is processed)
- Add `scale` field to `Scrap Weight` (set when weight is recorded)
- Auto-populate from session when creating records

### Benefits
- Complete audit trail: Session → Order → Scrap Weight all linked to scale
- Easier reporting by scale
- Scale performance tracking

---

## 2. PDF Print Design

**Priority**: High
**Status**: Planned

### 2.1 ERPNext Print Formats
- Standard print format for `POS Order` (full details, official document)
- Standard print format for `Scrap Weight` (detailed weight record)
- Summary reports for sessions

### 2.2 Terminal Receipt Printing
- Quick thermal receipt for `Scrap Weight` after recording
- Compact format suitable for 80mm thermal printers
- Content:
  - Date/Time
  - Order ID
  - Supplier name
  - Scale used
  - Items with weights
  - Total weight
  - Operator name
  - QR code for verification

### Implementation Notes
- Use Frappe print format for ERPNext side
- Create lightweight HTML template for terminal receipts
- Consider using `window.print()` or direct ESC/POS commands

---

## 3. Reweight/Void Logic Redesign

**Priority**: High
**Status**: Planned

### Current Problem
- All `Scrap Weight` records are summed including re-weighs
- This inflates total weight when corrections are made
- `is_reweight` flag exists but doesn't exclude from totals

### Proposed Solution

#### Add `is_voided` field to `Scrap Weight`
```
Field: is_voided
Type: Check
Default: 0
Description: "Voided records are excluded from weight totals"
```

#### Add `voided_by` and `voided_reason` fields
```
Field: voided_by
Type: Link (User)
Description: "User who voided this record"

Field: voided_reason
Type: Small Text
Description: "Reason for voiding"

Field: voided_datetime
Type: Datetime
```

#### Workflow
1. Operator records weight → creates `Scrap Weight` record
2. If error discovered, operator can:
   - Void the incorrect record (sets `is_voided = 1`)
   - Record new correct weight
3. Summations exclude voided records:
   ```sql
   SELECT SUM(total_weight)
   FROM `tabScrap Weight`
   WHERE pos_order = 'XXX' AND is_voided = 0
   ```

#### Benefits
- Full audit trail preserved (voided records visible but flagged)
- Accurate totals for reporting
- Clear accountability (who voided, when, why)

### UI Changes Needed
- Add "Void" button in terminal for weight records
- Show voided records with strikethrough styling
- Confirmation dialog with reason input

---

## 4. Additional Considerations

### 4.1 Truck Weight Void Logic
- Similar void mechanism for truck weights (gross/tare)
- May need `truck_weight_voided` flag on `POS Order`
- Or separate `Truck Weight` DocType for full history

### 4.2 Manager Approval for Voids
- Optional: require manager approval for voiding records
- Workflow: Operator requests void → Manager approves
- Configurable per company/profile

### 4.3 Variance Recalculation
- When weights are voided, recalculate:
  - `total_scrap_weight` on `POS Order`
  - `weight_variance` and `weight_variance_percent`

---

## Implementation Order

1. **Phase 1**: Void logic for Scrap Weight (most impactful)
2. **Phase 2**: Scale propagation to Order and Scrap Weight
3. **Phase 3**: Terminal receipt printing
4. **Phase 4**: ERPNext print formats
5. **Phase 5**: Manager approval workflow (optional)

---

*Last updated: 2025-12-04*
