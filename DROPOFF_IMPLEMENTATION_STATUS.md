# Drop-off Implementation - Consolidated Status

**Last Updated:** 2025-12-28 (Session 5)

## Quick Status Overview

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1: DocTypes & Controllers | ✅ COMPLETED | 1-truck design implemented |
| Phase 2: API Endpoints | ✅ COMPLETED | 23/23 tests passing |
| Phase 3: Terminal UI Updates | ✅ COMPLETED | Order→Dropoff rename, API calls updated |
| Phase 4: Manual Weight Entry | ✅ COMPLETED | WebSerial optional, scale required |
| Phase 5: Bug Fixes | ✅ COMPLETED | SQL sanitizer issue fixed, CSS fixes |
| Phase 6: Truck Terminal Scale | ✅ COMPLETED | WebSerial + Manual Entry like scrap terminal |
| Phase 7: Truck Terminal UI Redesign | ✅ COMPLETED | Discussion started, needs finalization |
| Phase 8: Per-Item Fulfillment | 📋 PLANNED | See docs/PHASE_8_DROPOFF_REDESIGN.md |

---

## KNOWN ISSUES

### 🔴 Issue 1: Reweight on Closed Dropoff Does Not Re-Allocate

**Problem:**
When a **Closed** dropoff is reweighed:
1. Scrap Weight items update correctly ✅
2. `is_reweight` flag is set on Scrap Weight ✅
3. **BUT** `allocated_weight` on Dropoff Orders does NOT update ❌
4. **AND** `is_reweighed` flag on Dropoff itself is NOT set ❌

**Root Cause:**
- `allocate_weights_if_closing()` only runs when transitioning TO Closed (not when already Closed)
- `_auto_transition_status()` ignores Closed status entirely

**Current Workaround:**
Desk user must manually change status from Closed → Verified → Closed to trigger reallocation.

**Potential Solutions:**
| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A | Add "Needs Reallocation" status | Clear audit trail | Extra step for operator |
| B | Auto-reallocate on reweight (stay Closed) | Simplest UX | Less visible change |
| C | Revert to "Verified" on reweight | Forces review | Extra click to re-close |

**Decision:** TBD - needs discussion

**Affected Files:**
- `api/v1/dropoff.py` - `record_scrap_weight()`, `_auto_transition_status()`
- `doctype/dropoff/dropoff.py` - `allocate_weights_if_closing()`

---

---

## COMPLETED: Truck Terminal UI Redesign

> **Status**: ✅ Completed

### Current Problems
1. **Weight UI shows Gross/Tare simultaneously** - Should select type first, then enter
2. **No confirmation after save** - User doesn't know if weight was saved
3. **Variance not displayed** - Backend calculates, UI doesn't show

### Design Questions (Need Discussion)

**1. UI Pattern - What to use instead of modal/popup?**
Options:
- **Tabs** - [Gross] [Tare] tabs at top, click to switch
- **Inline panel** - Expandable section in main view
- **Slide-in drawer** - Panel slides from side
- **Full-screen view** - Replaces current content entirely

**2. Photo per Weighing** - ✅ Confirmed
Store on Truck Weight document, not Dropoff.

**3. Variance Display**
- Show color-coded warning when scrap weight differs from net truck weight
- Logic exists in backend (`calculate_totals()` in dropoff.py)
- Need to show in UI with colors (green OK, yellow warning, red error)

**4. Reweight Strategy**
Current: Keep all Truck Weight records, use latest
Options:
- Keep all, mark old as "superseded"
- Show weighing history list
- Allow selecting which to use as "active"

---

## Session 5 Completed Work

### Weight Verification Consolidation
- Removed redundant "Weight Verification" panel from left side
- Kept right-side panel styled as dropoff card (ตรวจสอบน้ำหนัก)
- Dynamic threshold now uses variance_threshold_percent from Dropoff document (was hardcoded 2%)
- Added "threshold" translation (English/Thai)

### Photo Storage (Fixed)
- Photos now properly attach to Truck Weight document via Weight Photo child table
- Multi-photo support working
- Photo modal displays all attachments

---

## Session 4 Completed Work

### Truck Terminal Updates (truck.html)
- Added `scale_reader.js` include for WebSerial
- Renamed Order → Dropoff (HTML IDs, CSS classes, JS functions)
- Updated API calls: `pos.*` → `dropoff.*`
- Added Scale Selection Modal with two buttons:
  - "Confirm & Connect Scale" (WebSerial)
  - "Confirm Scale (Manual Entry)"
- Added Scale Connection Result Modal (connecting/success/fail states)
- Added full WebSerial connection flow matching scrap terminal
- Fixed `state.order` → `state.dropoff` in savePhoto()
- Added `isScaleConnected` state flag
- Updated `checkSessionScale()` to include serial settings

### New JavaScript Functions Added
- `confirmScaleManualMode()`
- `showScaleConnectionModal()`
- `showScaleConnectionResult()`
- `testScaleConnection()`
- `closeScaleConnectionModal()`
- `openScaleTestPage()`
- `completeScaleSelection()`
- `useManualEntryMode()`

---

## Previous Sessions Summary

### Session 3
- Terminal UI: Order→Dropoff rename, API calls updated
- Manual weight entry mode
- SQL sanitizer fix for `_count_dropoff_orders()`
- CSS fixes

### Session 2
- API endpoints implementation
- 23/23 edge case tests passing

### Session 1
- DocTypes created (Dropoff, Dropoff Order, Truck Weight)
- 1-truck-per-dropoff design decision
- Controller validations

---

## Architecture: 1-Truck-Per-Dropoff Design

### Design Decision
- **1 Dropoff = 1 Truck** (license_plate directly on Dropoff form)
- **Truck Weight DocType** for weighing history (standalone, links to Dropoff)

### Dropoff Status Flow
```
Draft → Scheduled → Weighing → Unloading → Verified/Needs Attention → Closed
                                                                    ↓
                                                               Cancelled
```

---

## Files Modified This Session

| File | Changes |
|------|---------|
| www/pos/truck.html | WebSerial scale flow, Scale Connection Modal |
| docs/IMPLEMENTATION_PLAN.md | Marked phases complete, added pending items |

---

*Reference: docs/DROPOFF_ARCHITECTURE.md for full design decisions*
*Reference: docs/IMPLEMENTATION_PLAN.md for implementation checklist*
*Reference: docs/PHASE_8_DROPOFF_REDESIGN.md for Phase 8 consolidated design*
