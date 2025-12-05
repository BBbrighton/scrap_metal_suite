# Truck Weight Terminal Redesign Plan

## Problem Statement
Currently, truck weighing is embedded within the scrap weighing terminal as a fullscreen overlay. This causes:
1. UI overcrowding - too much functionality in one screen
2. Confusion between scrap weight flow and truck weight flow
3. Complex state management with overlapping concerns
4. The current overlay approach breaks the scrap weighing workflow

## Proposed Solution: Separate Truck Scale Terminal

Create a **completely separate page** (`/pos/truck`) for truck weighing, independent of the scrap weighing terminal.

### Architecture Overview

```
/pos                    → POS Landing (profile selection, session management)
  ├── /pos/terminal     → Scrap Weight Terminal (existing, simplified)
  └── /pos/truck        → NEW: Truck Scale Terminal (dedicated page)
```

### Navigation Flow

From `/pos` landing page:
- **"Start Scrap Session"** → Opens `/pos/terminal` (scrap weighing only)
- **"Truck Scale"** → Opens `/pos/truck` (truck weighing only)

Both share the same POS Session, but operate independently.

---

## Implementation Plan

### Phase 1: Create New Truck Scale Page

#### 1.1 Create `/pos/truck.html` - New dedicated page
- Fullscreen truck scale interface
- Clean, focused UI for truck weighing only
- Order search with QR scanning
- Gross/Tare/Net weight cards
- Variance display
- Scrap weight summary (read-only reference)

#### 1.2 Create `/pos/truck.py` - Context provider
- Same session validation as terminal.py
- Load operator info, session data
- No scrap items needed (not used here)

### Phase 2: Simplify Existing Terminal

#### 2.1 Remove truck weight code from `terminal.html`
- Remove "Weight Truck" button from header
- Remove fullscreen truck weight screen HTML
- Remove truck scanner modal
- Remove truck weight input modal
- Remove all truck weight JavaScript functions (~400 lines)

#### 2.2 Keep terminal focused on scrap weighing
- Order search → Select items → Record weight
- Clean, simple flow

### Phase 3: Update POS Landing Page

#### 3.1 Add Truck Scale button to `/pos/index.html`
Two options for navigation:

**Option A: Prominent button on landing page**
```
┌─────────────────────────────────────────┐
│     🏭 Scrap Metal POS                  │
│                                          │
│  ┌──────────────┐  ┌──────────────┐     │
│  │   📋 Main    │  │   🚚 Truck   │     │
│  │   Profile    │  │    Scale     │     │
│  │              │  │              │     │
│  │ Start Session│  │  Open Scale  │     │
│  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────┘
```

**Option B: Tab/toggle on active session** (Preferred)
```
When session is active, show:
┌─────────────────────────────────────────┐
│     Active Session: POS-00001           │
│                                          │
│  ┌──────────────┐  ┌──────────────┐     │
│  │  ⚖️ Scrap    │  │  🚚 Truck   │     │
│  │   Weighing   │  │    Scale    │     │
│  │              │  │              │     │
│  │    Enter     │  │    Enter    │     │
│  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────┘
```

### Phase 4: API Updates (Minor)

No significant API changes needed. All truck weight APIs already exist:
- `record_truck_weight` ✓
- `get_weight_verification` ✓
- `lookup_order` ✓

---

## File Changes Summary

### New Files
| File | Purpose |
|------|---------|
| `www/pos/truck.html` | Truck scale terminal UI |
| `www/pos/truck.py` | Truck scale context |

### Modified Files
| File | Changes |
|------|---------|
| `www/pos/terminal.html` | Remove all truck weight UI and JS (~500 lines removed) |
| `www/pos/index.html` | Add truck scale entry point |
| `public/css/pos.css` | Move truck styles to separate section, may need adjustments |

### Files Unchanged
| File | Reason |
|------|--------|
| `api/v1/pos.py` | All APIs already support both workflows |

---

## UI Design: Truck Scale Terminal (`/pos/truck`)

```
┌─────────────────────────────────────────────────────────────┐
│ 🚚 Truck Scale                          John Doe  [← Back]  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌───────────────────────────────────────────────────┐     │
│   │  Search Order                                      │     │
│   │  [________________________] [📷 Scan]              │     │
│   │                                                    │     │
│   │  ┌─────────────────────────────────────────────┐  │     │
│   │  │ ORD-2025-00001                              │  │     │
│   │  │ ABC Suppliers | ABC 123                     │  │     │
│   │  └─────────────────────────────────────────────┘  │     │
│   └───────────────────────────────────────────────────┘     │
│                                                              │
│   (After order selected)                                     │
│                                                              │
│   ┌────────────────────────────────────────────────────┐    │
│   │ Order: ORD-2025-00001            [Change Order]    │    │
│   │ Supplier: ABC Suppliers  |  Plate: ABC 123         │    │
│   └────────────────────────────────────────────────────┘    │
│                                                              │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│   │ GROSS       │  │ TARE        │  │ NET         │        │
│   │   --        │  │   --        │  │   --        │        │
│   │             │  │             │  │ (calculated)│        │
│   │[Record Gross│  │[Record Tare]│  │             │        │
│   └─────────────┘  └─────────────┘  └─────────────┘        │
│                                                              │
│   ┌────────────────────────────────────────────────────┐    │
│   │ Weight Verification                                │    │
│   │ Net Truck: 1500.00 Kg  |  Scrap: 1485.00 Kg       │    │
│   │ Variance: 15.00 Kg (1.0%) ✓ Within tolerance      │    │
│   └────────────────────────────────────────────────────┘    │
│                                                              │
│   ┌────────────────────────────────────────────────────┐    │
│   │ Scrap Weight Records (3)                           │    │
│   │ SW-00001  450.00 Kg                               │    │
│   │ SW-00002  535.00 Kg                               │    │
│   │ SW-00003  500.00 Kg                               │    │
│   │ ──────────────────────                            │    │
│   │ Total: 1485.00 Kg                                 │    │
│   └────────────────────────────────────────────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Benefits of This Approach

1. **Clean separation of concerns** - Each terminal does one thing well
2. **Simpler code** - ~500 lines removed from terminal.html
3. **Better UX** - Operators go to the right screen for their task
4. **Easier maintenance** - Changes to truck scale don't affect scrap weighing
5. **Parallel operation** - Different operators can use different terminals
6. **Mobile-friendly** - Simpler pages load faster, work better on tablets

---

## Implementation Order

1. ✅ Create `truck.html` and `truck.py` (new files)
2. ✅ Update `index.html` to add truck scale entry
3. ✅ Remove truck code from `terminal.html`
4. ✅ Test both workflows independently
5. ✅ Build assets and verify CSS

---

## Questions for User

1. **Session requirement**: Should truck scale require an active POS session, or work independently?
   - **Recommendation**: Keep session required for audit trail consistency

2. **Back navigation**: Where should "Back" button go?
   - **Option A**: Back to `/pos` landing (recommended)
   - **Option B**: Back to `/pos/terminal`

3. **Operator display**: Show full name or username in header?
   - **Recommendation**: Full name (already implemented)
