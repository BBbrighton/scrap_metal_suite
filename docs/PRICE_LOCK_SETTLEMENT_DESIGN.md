# Scrap Metal Suite — PO & PO Final Design

**Status:** Reviewed — ready for implementation
**Author:** Engineering
**Last updated:** 2026-04-15

> **Terminology note:** Throughout this document, **PO** refers to the initial purchase commitment (the price lock), and **PO Final** refers to the accountant's reconciliation document that closes out one or more POs against actual deliveries. These are custom doctypes (`SMT Price Lock`, `SMT Purchase Order`) — they are *not* the standard ERPNext Purchase Order. We chose "PO" because it matches the language the client already uses with suppliers.

---

## 1. Background & Problem

Scrap metal is a fungible commodity business with two unusual properties that break the standard ERPNext Purchase Order flow:

1. **Price is locked at commitment time, but fulfillment happens later.** A supplier calls in the morning and says "lock me in 10kg of copper at 300 THB/kg." They drop off the material days or weeks later.
2. **Delivered material rarely matches the PO exactly.** Quantities are off (re-weighed at the yard), grades get downgraded after sorting, and suppliers may want to apply a single delivery against multiple prior POs — or vice versa, multiple deliveries against one PO.

Standard ERPNext Purchase Order + Purchase Receipt + Purchase Invoice assumes a tight, near-1:1 relationship between order and receipt. That doesn't fit. We need a model where **price commitments and physical deliveries are decoupled**, and a human (the accountant) reconciles them at PO Final time.

This document proposes two custom DocTypes — `SMT Price Lock` and `SMT Purchase Order` — and walks through the complete lifecycle.

---

## 2. Core Concepts

| Concept | Meaning |
|---|---|
| **SMT Price Lock** (the initial PO) | A commitment from us to buy a specific item, in a specific quantity, at a specific rate, from a specific supplier. Created up-front. Terms are immutable after submit. |
| **Drop-off** | The physical event of a supplier delivering material. Captured in the existing Drop-off module. No prices. |
| **Drop-off Final** | (Built by another team) A finalized, re-weighed and re-graded version of a Drop-off. The authoritative record of what was actually received. |
| **SMT Purchase Order** | The accountant's reconciliation document. Links one or more Drop-off Finals to one or more POs (and/or spot prices), produces the Purchase Invoice, and pays the supplier. |
| **Spot** | A fallback rate set by the accountant at PO Final time, when no PO covers the material (e.g. downgraded material). |

**Key invariant:** A supplier is *only* paid through a PO Final. There is no other path from material-in-yard to money-out.

---

## 3. Use Cases

### UC-1 — Simple PO and fulfill
Supplier opens a PO for 10kg copper @ 300. Drops off exactly 10kg. Accountant closes it with a PO Final: 10kg × 300 = 3,000 THB. PO status → Fully Settled.

### UC-2 — Partial fulfillment, remainder still open
Supplier opens a PO for 10kg copper @ 300. Drops off 6kg. Accountant settles 6kg @ 300 in a PO Final. PO status → Partially Settled, 4kg remaining. Supplier delivers the rest two weeks later, closed in a second PO Final.

### UC-3 — Two POs at different rates, single delivery
Supplier opens PO-001 (10kg copper @ 300) and PO-002 (3kg copper @ 310). Delivers 13kg in one drop-off. Accountant splits the drop-off line: 10kg → PO-001, 3kg → PO-002.

### UC-4 — Downgrade after sorting
Supplier opens a PO for 10kg Copper Grade A @ 300. Drop-off Final shows 9kg Grade A + 1kg Grade B (downgraded by sorters). Accountant settles 9kg @ 300 against the PO; the remaining 1kg becomes a Spot line at the accountant's chosen Grade B rate (e.g. 285).

### UC-5 — Over-delivery
Supplier opens a PO for 10kg copper @ 300. Delivers 12kg. Accountant settles 10kg @ 300 against the PO (PO fully consumed); the extra 2kg becomes a Spot line at the accountant's discretion.

### UC-6 — Multi-item drop-off
A single drop-off contains 9kg copper and 15kg aluminum, against two separate POs (PO-A copper, PO-B aluminum). One PO Final covers both.

### UC-7 — Cross-PO fungibility (accountant discretion)
Supplier has three open copper POs. A delivery comes in. The accountant chooses which PO(s) to draw down — there is no automatic FIFO. This is intentional: it's a business judgment.

### UC-8 — Batch PO Final
Supplier dropped off material on three different days last week. Accountant closes all three Drop-off Finals in one PO Final document.

### UC-9 — Correction before payment
Accountant submits a PO Final, notices a wrong allocation. Cancels the PO Final (which cancels the Purchase Invoice), amends, re-submits.

### UC-10 — Correction after payment
Payment has already cleared the bank. The original PO Final is locked. Accountant creates a corrective PO Final (out of scope for v1 — see §10).

### UC-11 — PO expiry
PO has a 30-day expiry. Supplier never delivers. On expiry, status → Expired automatically; remaining qty no longer available for PO Final.

---

## 4. Data Model

### 4.1 `SMT Price Lock` (parent)

| Field | Type | Notes |
|---|---|---|
| `naming_series` | Select | `PL-.YYYY.-` |
| `supplier` | Link → Supplier | Required |
| `supplier_name` | Data | Fetched, read-only |
| `po_date` | Date | Defaults to today |
| `expiry_date` | Date | Optional. If set, scheduler auto-expires |
| `status` | Select | Open / Partially Settled / Fully Settled / Expired / Cancelled. **System-managed.** |
| `created_by_role` | Select | Manager / Supplier Portal / Accountant |
| `notes` | Small Text | Free-form |
| `items` | Table → SMT Price Lock Item | At least one row required |
| `total_po_value` | Currency | Sum of qty × rate, read-only |
| `total_settled_value` | Currency | Rolled up, read-only |
| `amended_from` | Link → SMT Price Lock | Standard Frappe |

**Submit semantics:** Once submitted (`docstatus=1`), the supplier-facing terms (`items.item_code`, `items.po_qty`, `items.po_rate`, `supplier`) are frozen. System-managed fields (`status`, `items.settled_qty`) are updated via `db_set()` from the PO Final controller — no user edits.

### 4.2 `SMT Price Lock Item` (child)

| Field | Type | Notes |
|---|---|---|
| `item_code` | Link → Item | Must exist in ERPNext Item master |
| `item_name` | Data | Fetched |
| `uom` | Link → UOM | Default kg |
| `po_qty` | Float | The committed quantity |
| `po_rate` | Currency | THB per UOM (the locked price) |
| `po_amount` | Currency | qty × rate, read-only |
| `settled_qty` | Float | **System-managed**, rolled up from PO Finals |
| `remaining_qty` | Float | `po_qty − settled_qty`, read-only |

### 4.3 `SMT Purchase Order` (parent)

| Field | Type | Notes |
|---|---|---|
| `naming_series` | Select | `SMTPL-.YYYY.-` |
| `supplier` | Link → Supplier | Required |
| `final_date` | Date | Defaults to today |
| `status` | Select | Draft / Submitted / Paid / Cancelled |
| `drop_off_finals` | Table → SMT Purchase Order Drop-off | Which Drop-off Finals are being closed |
| `allocations` | Table → SMT Purchase Order Allocation | The reconciliation lines |
| `total_po_value` | Currency | Sum of allocations where source = PO |
| `total_spot_value` | Currency | Sum of allocations where source = Spot |
| `total_amount` | Currency | Grand total |
| `purchase_invoice` | Link → Purchase Invoice | Generated on submit, read-only |
| `amended_from` | Link → SMT Purchase Order | Standard |

### 4.4 `SMT Purchase Order Drop-off` (child)

| Field | Type | Notes |
|---|---|---|
| `drop_off_final` | Link → Drop-off Final | The doc being closed |
| `drop_off_date` | Date | Fetched |
| `total_weight` | Float | Fetched, informational |

### 4.5 `SMT Purchase Order Allocation` (child)

| Field | Type | Notes |
|---|---|---|
| `drop_off_final` | Link → Drop-off Final | Which drop-off this line draws from |
| `item_code` | Link → Item | Must match drop-off line |
| `qty` | Float | Allocated quantity |
| `source_type` | Select | PO / Spot |
| `po` | Link → SMT Price Lock | Required if source = PO |
| `po_item_row` | Data | Which child row in the PO |
| `rate` | Currency | Auto-filled & locked if PO; manual if Spot |
| `amount` | Currency | qty × rate |
| `notes` | Small Text | e.g. "downgraded from Grade A" |

---

## 5. Validation & Controller Logic

### 5.1 PO controller

**`validate`:**
- At least one item row
- `po_qty > 0`, `po_rate > 0`
- Item exists in Item master
- Roll up `total_po_value`

**`on_submit`:**
- Set `status = Open`

**`on_cancel`:**
- Reject if any `settled_qty > 0` on any item row → "Cannot cancel a PO with settled quantity. Cancel related PO Finals first."

**Scheduler hook (daily):**
- Find POs where `expiry_date < today` and `status == "Open"` → set status `Expired`
- **Note:** Partially Settled POs are never auto-expired — supplier has already delivered material against them. Manager must handle these manually.

### 5.2 PO Final controller

**`validate`:**
- Supplier consistency: every referenced Drop-off Final and PO must belong to `self.supplier`
- Each allocation row:
  - `qty > 0`
  - `item_code` matches a line in the referenced Drop-off Final
  - If `source_type == "PO"`:
    - `po` is set, status in (Open, Partially Settled)
    - `po_item_row.item_code == allocation.item_code`
    - `qty <= po_item_row.remaining_qty` (accounting for other allocations in the same PO Final to the same PO)
    - `rate == po_item_row.po_rate` (force exact match — no override)
  - If `source_type == "Spot"`:
    - `rate > 0`, manually entered
- For each Drop-off Final referenced: sum of allocations per item must equal the drop-off's final qty for that item. (No partial drop-offs — close the whole thing.)
- Roll up totals.

**`on_submit`:**
- For each allocation against a PO:
  - `db_set` increment `settled_qty` on the PO item row
  - Recompute PO status: `Fully Settled` if all items consumed, else `Partially Settled`
- For each Drop-off Final: mark `status = Settled`, link back to this PO Final
- Generate **Purchase Invoice** (as Draft — accountant reviews and submits separately):
  - Supplier = `self.supplier`
  - Items = allocation rows (item_code, qty, rate)
  - Accountant sets warehouse and submits the PI themselves
- Store PI reference

**`on_cancel`:**
- Reject if linked Purchase Invoice is still submitted → "Cancel the linked Purchase Invoice first."
- Frappe's built-in link-based cancellation cascade handles payment protection: if a Payment Entry exists against the PI, the PI cannot be cancelled until the PE is cancelled first. No additional `is_locked` mechanism needed.
- For each allocation: decrement `settled_qty` on the PO item, recompute PO status
- For each Drop-off Final: revert `status = Unsettled`, clear back-link

---

## 6. Accountant Walkthrough (the UX that matters most)

This is the screen the accountant lives in. Imagine end of day, supplier "ACME Metals" has dropped off material this morning, the yard team has finalized the Drop-off Final.

### Step 1 — New PO Final
Accountant clicks **New SMT Purchase Order**. Picks supplier: ACME Metals. Date defaults to today.

### Step 2 — Pull Drop-off Finals
A panel **"Unsettled Drop-off Finals"** auto-populates with all of ACME's drop-offs in `status = Unsettled`:

```
☐ DOF-2026-0411 — 2026-04-07 — 13.0 kg total
    • Copper Wire Grade A — 9.0 kg
    • Copper Wire Grade B — 1.0 kg
    • Aluminum Sheet     — 3.0 kg
```

Accountant ticks the ones to close. The system loads all line items into the **allocation working area** below.

### Step 3 — See open POs
A read-only panel **"Open POs for ACME Metals"** lists everything available:

```
PO-2026-0034   Cu Wire Grade A    10 kg @ 300    remaining: 10 kg
PO-2026-0041   Cu Wire Grade A     3 kg @ 310    remaining:  3 kg
PO-2026-0052   Aluminum Sheet     20 kg @  75    remaining: 20 kg
```

This is reference info — accountant uses it to plan allocation.

### Step 4 — Allocate

The allocation table is the heart of the screen. Initially it's seeded with one row per drop-off line:

| # | Drop-off       | Item       | Qty | Source     | PO         | Rate | Amount |
|---|----------------|------------|-----|------------|------------|------|--------|
| 1 | DOF-2026-0411  | Cu Grade A | 9.0 | _select_   | _select_   |      |        |
| 2 | DOF-2026-0411  | Cu Grade B | 1.0 | _select_   | _select_   |      |        |
| 3 | DOF-2026-0411  | Aluminum   | 3.0 | _select_   | _select_   |      |        |

Accountant works row by row.

**Row 1 — 9kg Cu A:** picks Source = PO. Dropdown filters to copper-A POs → PO-2026-0034 and PO-2026-0041 appear. Picks PO-0034. Rate auto-fills to 300, becomes read-only. Amount → 2,700.

**Row 2 — 1kg Cu B:** no Cu B PO exists. Picks Source = Spot. Manually enters rate 285. Amount → 285. Adds note "downgraded from Grade A".

**Row 3 — 3kg Aluminum:** picks Source = PO → PO-2026-0052. Rate → 75. Amount → 225.

**Splitting a row** (UC-3 / UC-5): if a single drop-off line needs to span two POs, accountant clicks **+ Split** on that row. The qty splits in two, accountant adjusts proportions. Validator ensures sum == original drop-off qty.

Final state:

| # | Drop-off | Item | Qty | Source | PO | Rate | Amount |
|---|---|---|---|---|---|---|---|
| 1 | DOF-...0411 | Cu A | 9.0 | PO | PO-0034 | 300 | 2,700 |
| 2 | DOF-...0411 | Cu B | 1.0 | Spot | — | 285 | 285 |
| 3 | DOF-...0411 | Al | 3.0 | PO | PO-0052 | 75 | 225 |

### Step 5 — Review totals

```
PO total:    2,925 THB
Spot total:    285 THB
─────────────────────────
Grand total: 3,210 THB
```

### Step 6 — Submit
Accountant clicks **Submit**. System:
- Validates everything (§5.2)
- Increments `settled_qty` on PO-0034 (now 9/10, status → Partially Settled) and PO-0052 (3/20, Partially Settled)
- Marks DOF-2026-0411 as Settled
- Generates Purchase Invoice PI-2026-1234 as **Draft** for 3,210 THB, links back
- PO Final status → Submitted

### Step 7 — Review PI & Pay
Accountant opens the linked Draft PI, reviews it, sets the warehouse, and submits it. Then clicks Make Payment Entry — Frappe handles the rest. Frappe's built-in cancellation cascade protects the chain: PO Final → PI → Payment Entry must be unwound in reverse order.

---

## 7. Visual: complete flow

```
┌─────────────┐
│  Supplier   │ "Open a PO for 10kg Cu @ 300"
└──────┬──────┘
       │
       ▼
┌──────────────────────┐
│  SMT Price Lock              │  status: Open
│  PO-2026-0034        │  Cu A: 10kg @ 300, remaining 10
└──────────────────────┘
       │
       │  (days/weeks later)
       │
       ▼
┌─────────────┐
│  Drop-off   │  9kg Cu (operator records, no price)
└──────┬──────┘
       ▼
┌─────────────────┐
│ Drop-off Final  │  9kg Cu A + 1kg Cu B (re-weighed, sorted)
│ DOF-2026-0411   │  status: Unsettled
└────────┬────────┘
         │
         ▼
┌──────────────────────────────┐
│  SMT Purchase Order                │  Accountant reconciles
│  POF-2026-0078               │
│  ┌────────────────────────┐  │
│  │ Allocations:           │  │
│  │  9kg Cu A → PO-0034    │  │
│  │  1kg Cu B → Spot @285  │  │
│  └────────────────────────┘  │
└──────────┬───────────────────┘
           │ on_submit
           ├─────────► PO-0034: settled_qty=9, status=Partial
           ├─────────► DOF-0411: status=Settled
           └─────────► Purchase Invoice PI-2026-1234
                            │
                            ▼
                      Payment Entry
                            │
                            ▼
                      Bank reconciled
                            │
                            ▼
                  PO Final.is_locked = True
```

---

## 8. Cancellation & Correction Cascade

Frappe enforces: you cannot cancel a submitted doc if another submitted doc links to it. So unwinding a PO Final requires reverse-order:

```
Payment Entry (cancel)      ← must cancel first if it exists
    ↓
Purchase Invoice (cancel)   ← stock entries reverse automatically
    ↓
SMT Purchase Order (cancel)       ← decrements PO settled_qty,
    ↓                         reverts Drop-off Final status
SMT Price Lock                      ← status recomputed automatically
```

**No `is_locked` needed.** Frappe's built-in link-based cancellation cascade handles this natively. If a Payment Entry is submitted against the PI, the PI cannot be cancelled. If the PI is submitted, the PO Final's `on_cancel` blocks. The accountant must unwind in reverse order — Frappe enforces this automatically for all submitted doctypes (custom or standard).

**Frappe amend flow** is the supported correction path: cancel → amend (creates `POF-...-1`) → fix → submit. Audit trail preserved via `amended_from`.

---

## 9. Roles & Permissions

### 9.1 Custom Roles

Two new roles, identical permissions for v1. The distinction exists so we can differentiate later (approval workflows, rate thresholds, audit access).

| Role | Purpose |
|------|---------|
| **SMT Accountant** | Day-to-day settlement — creates POs, builds PO Finals, generates PI drafts |
| **SMT Accounting Manager** | Same as SMT Accountant in v1. Future: oversight, approvals, higher-value operations |

### 9.2 Permission Matrix

**Full access (Create, Read, Write, Submit, Cancel):**

| DocType | SMT Accountant | SMT Accounting Manager | System Manager |
|---------|---------------|----------------------|----------------|
| SMT Price Lock | Full | Full | Full |
| SMT Purchase Order | Full | Full | Full |

**Read-only access across all other SMT doctypes:**

| DocType | SMT Accountant | SMT Accounting Manager |
|---------|---------------|----------------------|
| Dropoff Final | Read | Read |
| Dropoff | Read | Read |
| Production Sorting | Read | Read |
| Production Session | Read | Read |
| Truck Weight | Read | Read |
| Scrap Weight | Read | Read |
| Scrap Purchase | Read | Read |
| POS Order | Read | Read |
| POS Session | Read | Read |
| Scale | Read | Read |

**Rationale:** The accountant reconciles money against physical deliveries. They need to trace the full chain (PO → Dropoff → Sorting → Weights) to verify quantities and resolve discrepancies.

**v1 note:** Supplier portal access is out of scope. Deferred to Phase D.

### 9.3 SMT Accounting Workspace

A dedicated workspace for the accounting team, following the `SMT Production` workspace pattern.

**Workspace name:** `SMT Accounting`
**Restricted to roles:** SMT Accountant, SMT Accounting Manager

**Shortcuts:**
- New SMT Price Lock
- New SMT Purchase Order
- SMT Price Lock List
- SMT Purchase Order List

**Link Cards:**
- **Settlement:** SMT Price Lock, SMT Purchase Order
- **Reference (read-only):** Dropoff Final, Dropoff, Production Sorting, Scrap Purchase, Truck Weight

The workspace gives accountants a single entry point to their workflow without navigating the full Frappe sidebar. Reference cards provide quick access to the read-only doctypes they need for verification.

---

## 10. Out of Scope for v1

- **Corrective PO Finals after payment.** v1 relies on Frappe's cancel → amend flow. v2 may introduce an `SMT Purchase Order Adjustment` doctype that posts a debit/credit note.
- **Supplier portal access.** Suppliers cannot view or create POs in v1. Manager creates all POs. Portal read-only access deferred to Phase D.
- **Automatic FIFO allocation.** Accountant always chooses. We may add a "suggest allocation" button later that proposes FIFO as a starting point.
- **Multi-currency.** THB only.
- **Tax handling.** Assume PI tax templates handle this — no PO-Final-side tax logic.
- **Partial drop-off settlement.** A Drop-off Final is closed in full, in one PO Final, or not at all. No "settle 8 of 10 kg now, the rest later" within a single Drop-off Final.
- **Warehouse configuration.** PI is created as Draft — accountant sets the warehouse before submitting the PI.

---

## 11. Resolved Questions

1. **Portal-created POs:** ~~does the supplier portal allow creating POs directly?~~ **Decision:** No. Manager creates all POs in v1. Supplier portal deferred to Phase D.
2. **PO expiry policy:** ~~default expiry days?~~ **Decision:** No expiry by default (open-ended). Manager optionally sets `expiry_date`. Only `Open` POs are auto-expired; `Partially Settled` POs are never auto-expired.
3. **Spot rate authority:** ~~manager approval step?~~ **Decision:** Accountant is fully trusted for v1. Add audit reports later.
4. **Drop-off Final coordination:** ~~what fields?~~ **Decision:** Already built. Dropoff Final has `status` (Unsettled/Settled), `po_final`, `settled_by`, `settled_at`. Child table `Dropoff Final Good Item` has `item_code`, `weight`, `uom`. No changes needed.
5. **Item master discipline:** ~~who owns it?~~ **Decision:** Production Manager role. Taxonomy governance is a process concern, not a code concern.
6. **Reporting needs:** **Decision:** Deferred to Phase D. Planned: Open PO Exposure by Supplier, Settlement History, Spot vs PO Rate Comparison.
7. **Payment reconciliation trigger:** ~~manual checkbox or bank import?~~ **Decision:** Neither. Dropped `is_locked` entirely. Frappe's built-in cancellation cascade (PE → PI → PO Final) handles payment protection natively.
8. **Naming clash:** ~~SMT Price Lock vs Purchase Order?~~ **Decision:** `SMT Price Lock` is fine. The `SMT` prefix disambiguates from standard ERPNext Purchase Order.

---

## 12. Dropoff Final Integration — Controller Patterns

The SMT Purchase Order controller manages the Dropoff Final status lifecycle. These are the exact patterns to use:

### On `on_submit` — Mark Dropoff Finals as Settled

```python
# For each Dropoff Final being settled
frappe.db.set_value("Dropoff Final", dof_name, {
    "status": "Settled",
    "po_final": self.name,
    "settled_by": frappe.session.user,
    "settled_at": now_datetime()
})
```

### On `on_cancel` — Revert Dropoff Finals to Unsettled

```python
# Revert Dropoff Final
frappe.db.set_value("Dropoff Final", dof_name, {
    "status": "Unsettled",
    "po_final": None,
    "settled_by": None,
    "settled_at": None
})
```

### Querying Unsettled Dropoff Finals (for the PO Final form)

```python
frappe.get_all("Dropoff Final",
    filters={"supplier": supplier, "status": "Unsettled"}
)
```

This powers the **"Unsettled Drop-off Finals"** panel in Step 2 of the accountant walkthrough (§6), ensuring only unlinked Dropoff Finals are available for selection.

### Required Fields on `Dropoff Final` DocType

These fields must exist on Dropoff Final for the integration to work:

| Field | Type | Notes |
|---|---|---|
| `status` | Select | Must include: `Unsettled`, `Settled` |
| `po_final` | Link → SMT Purchase Order | Back-link to the settling document |
| `settled_by` | Link → User | Who submitted the PO Final |
| `settled_at` | Datetime | When it was settled |

---

## 13. Integration Test Plan

Extends the existing `test_full_workflow.py` suite. Same patterns: `TestResult` class, shared `ctx` dict, `cleanup_test_data()`, sequential test groups. Run via:

```
bench --site metal execute scrap_metal_suite.api_test.test_full_workflow.run
```

### 13.1 Test Data Setup (extends existing test_01, test_02)

**New test user:**
- `_test_wf_accountant@test.local` — roles: `SMT Accountant` (also gets read on all SMT doctypes)

**New test data (added to ctx):**
- SMT Price Lock items reuse existing test items (`_TEST_WF_Copper Wire`, `_TEST_WF_Aluminum Sheet`)
- Test supplier reuses existing `_TEST_WF_ACME Metals`

### 13.2 Test Groups

Tests numbered 200+ to avoid collision with existing 01–140 range.

**test_200_smt_price_lock_create — Create and submit PO (happy path)**
1. As accountant, create SMT Price Lock: 10kg Copper Wire @ 300, 5kg Aluminum @ 75
2. Assert `total_po_value == 3,375`
3. Submit → assert `status == "Open"`
4. Assert `settled_qty == 0`, `remaining_qty == po_qty` on each row
5. Store PO name in ctx

**test_201_smt_price_lock_validation — PO validation guards**
1. Try create PO with `po_qty = 0` → expect throw
2. Try create PO with `po_rate = -1` → expect throw
3. Try create PO with no items → expect throw

**test_202_smt_price_lock_expiry — Auto-expire only Open POs**
1. Create PO with `expiry_date = yesterday`, submit
2. Call `expire_open_pos()` scheduler function
3. Assert `status == "Expired"`
4. Create another PO, partially settle it (via PO Final in later test), set `expiry_date = yesterday`
5. Call `expire_open_pos()` again
6. Assert `status` still `"Partially Settled"` (NOT expired)

**test_210_full_loop_dropoff_to_unsettled — Walk through existing flow to produce Unsettled Dropoff Final**

This test reuses the existing chain but ensures the Dropoff Final ends at `status = "Unsettled"`:
1. Open POS Session (as operator)
2. Create Dropoff for test supplier
3. Record truck weights (gross/tare)
4. Record scrap weights (10kg Copper, 5kg Aluminum)
5. Complete the Dropoff
6. Open Production Session (as production worker)
7. Create Production Sorting linked to Dropoff
8. Add sorted items (9kg Copper Grade A, 1kg Copper Grade B, 5kg Aluminum)
9. Submit Production Sorting
10. Verify Dropoff Final auto-populates with good items
11. Assert Dropoff Final `status == "Unsettled"`
12. Store Dropoff Final name in ctx

**test_220_smt_purchase_order_simple — Simple full settlement (UC-1)**
1. As accountant, create SMT Purchase Order for test supplier
2. Add Dropoff Final to `drop_off_finals` child table
3. Add allocation rows:
   - 9kg Copper → source PO, link to test PO → rate auto 300
   - 1kg Copper Grade B → source Spot, rate 285
   - 5kg Aluminum → source PO, link to test PO → rate auto 75
4. Submit PO Final
5. Assert:
   - PO `settled_qty` updated (9 on Copper, 5 on Aluminum)
   - PO `remaining_qty` correct (1 on Copper, 0 on Aluminum)
   - PO `status == "Partially Settled"` (Copper not fully consumed)
   - Dropoff Final `status == "Settled"`, `po_final` links back
   - Draft Purchase Invoice created with correct line items and totals
   - PO Final `total_po_value == 9×300 + 5×75 = 3,075`
   - PO Final `total_spot_value == 1×285 = 285`
   - PO Final `total_amount == 3,360`

**test_230_smt_purchase_order_cancel — Cancel cascade**
1. Cancel the PO Final from test_220
2. Assert:
   - PO `settled_qty` reverted to 0
   - PO `status` reverted to `"Open"`
   - Dropoff Final `status` reverted to `"Unsettled"`, `po_final` cleared
   - Draft Purchase Invoice deleted or cancelled

**test_240_partial_settlement — Partial PO settlement (UC-2)**
1. Re-settle Dropoff Final but only allocate 6kg Copper against PO (not full 9kg available)
2. Remaining 3kg Copper + 1kg Grade B as Spot
3. Submit → PO `status == "Partially Settled"`, `settled_qty == 6` on Copper row
4. Create a second Dropoff (via new dropoff flow) with 4kg Copper
5. Create second PO Final, allocate 4kg Copper → same PO
6. Submit → PO Copper row now `settled_qty == 10`, `remaining_qty == 0`
7. Assert PO `status == "Fully Settled"` (all items consumed)

**test_250_multi_po_single_dropoff — Two POs, one delivery (UC-3)**
1. Create PO-A: 5kg Copper @ 300
2. Create PO-B: 5kg Copper @ 310
3. Create Dropoff Final with 10kg Copper
4. PO Final: split allocation — 5kg → PO-A @ 300, 5kg → PO-B @ 310
5. Submit → both POs fully settled
6. Assert PI has two line items at different rates

**test_260_over_delivery — More material than PO covers (UC-5)**
1. Create PO: 5kg Copper @ 300
2. Dropoff Final has 8kg Copper
3. Allocate 5kg → PO, 3kg → Spot @ 290
4. Submit → PO fully settled, spot amount correct

**test_270_over_allocation_blocked — Cannot exceed PO remaining**
1. Create PO: 5kg Copper @ 300
2. Try to allocate 6kg against it → expect validation error

**test_280_supplier_consistency — Cross-supplier blocked**
1. Create PO for Supplier A
2. Create Dropoff Final for Supplier B
3. Try to create PO Final mixing them → expect validation error

**test_290_po_cancel_with_settlement — Cannot cancel PO with settled qty**
1. Create PO, settle partially via PO Final
2. Try to cancel the PO → expect throw "Cannot cancel: settled qty exists"

**test_300_accountant_read_access — Read-only access to other SMT doctypes**
1. As accountant user, verify can read: Dropoff, Dropoff Final, Production Sorting, POS Order, Truck Weight, Scrap Weight, POS Session, Production Session, Scale, Scrap Purchase
2. Verify cannot create/write/delete any of the above

**test_310_po_rate_locked — PO rate cannot be overridden in allocation**
1. Create PO with rate 300
2. In PO Final allocation with source = PO, try to set rate = 350
3. Assert rate is forced back to 300 (or validation error)

**test_320_dropoff_final_full_coverage — All items must be allocated**
1. Dropoff Final has 10kg Copper + 5kg Aluminum
2. PO Final only allocates the Copper, skips Aluminum
3. Submit → expect validation error: "All items in Dropoff Final must be allocated"

### 13.3 Cleanup

Extends `cleanup_test_data()` to also delete:
- SMT Purchase Order (cancel first if submitted) → in reverse dependency order
- SMT Price Lock (cancel first if submitted)
- Draft Purchase Invoices created by tests
- Test accountant user

### 13.4 Test Numbering Convention

| Range | Module |
|-------|--------|
| 01–09 | Setup (users, master data, permissions) |
| 10–50 | POS flow (session, dropoff, weights) |
| 60–99 | Production flow (sorting, variance, permissions) |
| 100–140 | Edge cases (lifecycle, security, reweight, variance) |
| **200–209** | **SMT Price Lock (create, validate, expiry)** |
| **210–219** | **Dropoff → Unsettled Dropoff Final (setup for settlement tests)** |
| **220–239** | **SMT Purchase Order (happy path, cancel, partial)** |
| **240–269** | **Multi-PO, over-delivery, complex allocation** |
| **270–299** | **Validation guards (over-allocation, cross-supplier, rate lock)** |
| **300–319** | **Permission checks (accountant read access)** |
| **320+** | **Coverage checks (full allocation required)** |

---

## 14. Implementation Phasing (proposed)

**Phase A — SMT Price Lock**
- DocType + child table
- Validation, submit, cancel, expiry scheduler
- Accountant UI for create/list/view
- Basic report: open PO exposure per supplier

**Phase B — SMT Purchase Order core**
- DocType + child tables
- Allocation validation logic
- PO Final walkthrough UI (the screen in §6)
- Cancel cascade

**Phase C — ERPNext integration**
- Draft PI generation on PO Final submit
- Accountant reviews and submits PI manually

**Phase D — Portal, workspace & polish**
- SMT Accounting workspace
- Supplier portal: view own POs, view own PO Finals (deferred from v1)
- Manager dashboard: exposure, aging, top suppliers
- Reports

**Phase E — v2 (later)**
- Corrective adjustment doctype
- FIFO suggestion
- Approval workflows

---

## 15. Design Decisions Log (2026-04-15)

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Keep `SMT Purchase Order Drop-off` child table | UX convenience — gives accountant a clear summary panel. Negligible cost (3 read-only fields, no logic). |
| 2 | Drop `is_locked` field and payment hooks | Frappe's built-in link-based cancellation cascade (PE → PI → PO Final) already prevents cancellation after payment. Redundant protection. |
| 3 | Auto-expire only `Open` POs | Partially Settled POs have delivered material — auto-expiring them is dangerous. Manager handles these manually. |
| 4 | No supplier portal in v1 | Reduces scope. Manager creates all POs. Portal read-only access deferred to Phase D. |
| 5 | PI created as Draft, not auto-submitted | Gives accountant a review step — they set warehouse and verify before submitting the PI. |
| 6 | No warehouse configuration | PI is Draft — accountant sets warehouse on the PI before submission. No settings doctype needed. |
| 7 | Use `flt(qty * rate, 2)` for all amounts | Prevents Float × Currency rounding issues. Amounts computed in Python, not stored blindly. |
| 8 | Race condition guard on `settled_qty` | Use atomic SQL `UPDATE SET settled_qty = settled_qty + %s` with post-write validation, not read-then-write. |
| 9 | Two accounting roles: SMT Accountant + SMT Accounting Manager | Identical permissions in v1, but the split exists for future differentiation (approvals, rate thresholds). |
| 10 | Accountants get read-only access to all SMT doctypes | They need to trace the full chain (Dropoff → Sorting → Weights) to verify and reconcile. |
| 11 | Dedicated SMT Accounting workspace | Gives accountants a focused entry point, following the SMT Production workspace pattern. |

---

## 16. v2 — Partial Dropoff Final Settlement (2026-08-26)

**Status:** Implemented
**Supersedes:** the §10 bullet "Partial drop-off settlement" (out of scope in v1)

### 16.1 What changed and why

v1 held that a Dropoff Final is closed *in full, in one PO Final, or not at all*.
That forced a 1000 kg delivery to be settled by a single document even when the
business wanted to pay for it in instalments — a **timing** constraint, not a
pricing one. (Pricing complexity was always handled *within* one PO Final by
allocating across several Price Locks and Spot rates; that has not changed.)

v2 makes the Dropoff Final a **drawdown account**, symmetric with the Price
Lock: many PO Finals may draw from one Dropoff Final, and one PO Final may still
draw from many Dropoff Finals. The relationship is genuinely many-to-many.

### 16.2 Where the truth lives

`SMT Purchase Order Allocation` was already the join table. Every row states
*"this many kg of this item, from this Dropoff Final, settled against this Price
Lock (or Spot) at this rate."* v2 changes nothing about that row — it stops
pretending the relationship is 1:1.

**Critical constraint discovered during design:** `Dropoff Final Good Item` rows
are **derived, not source data**. `DropoffFinal.before_save` calls
`aggregate_from_sortings()`, which clears and rebuilds `good_items` from the
submitted Production Sorting records on *every save* — and Dropoff Final is not
submittable, so this keeps happening for the life of the document. A stored
settlement ledger on those rows would be silently destroyed the next time
production submitted another sorting session for the same dropoff.

The Price Lock pattern (`update_settled_qty` — atomic SQL increment against a
frozen, submitted row) therefore **cannot be transplanted onto Dropoff Final**.

**Decision: derive, never store.** `settled_qty` / `remaining_qty` on the good
item row are recomputed in `before_save`, immediately after
`aggregate_from_sortings()` rebuilds the rows. The wipe stops being a hazard and
becomes the mechanism — rows and their ledger values are always regenerated
together from the same source of truth.

Consequences, all of them favourable:

| | Stored ledger (rejected) | Derived ledger (chosen) |
|---|---|---|
| Survives re-sorting | no — silently wiped | yes — recomputed |
| Can drift from allocations | possible | impossible |
| Needs a backfill patch for live data | yes | no — derives from existing allocations |
| PO Final submit/cancel | increments/decrements | triggers a recompute |
| Idempotent | no | yes |
| `revert_dropoff_finals` double-payment hole | present | cannot exist |

### 16.3 Data model changes

**`Dropoff Final Good Item`** — two new fields, read-only and system-managed,
with explicit grid `columns` widths so they are actually visible. Frappe caps
grid width at 10 units and silently drops trailing `in_list_view` columns; this
is why `SMT Price Lock Item.remaining_qty` was invisible for four months despite
being correctly maintained.

| Field | Type | Notes |
|---|---|---|
| `settled_qty` | Float(3) | Derived: sum of submitted allocations for this DFL + item |
| `remaining_qty` | Float(3) | `weight - settled_qty` |

**`Dropoff Final`**

| Field | Change |
|---|---|
| `status` | New value `Partially Settled`, between `Unsettled` and `Settled` |
| `settlement_documents` | New Small Text — comma-joined PO Final names, mirroring the existing `sorting_sessions` pattern |
| `po_final` | Retained, but now means **the most recent** settling PO Final. Not authoritative under many-to-many; read `settlement_documents` or query allocations |

**`SMT Purchase Order Dropoff`** — the `drop_off_finals` child table stays
hand-editable as the accountant's *selector* (it is what the pull button reads).
It is no longer a statement of what got closed:

| Field | Change |
|---|---|
| `total_weight` | Unchanged — the DFL's whole good weight (fetched) |
| `drawn_weight` | New Float(3), computed — what **this document** draws from that DFL |

The section label changes from *"Dropoff Finals Being Settled"* to *"Dropoff
Finals Drawn From"*, which is now literally true.

### 16.4 Validation changes (`SMT Purchase Order`)

- `validate_dropoff_coverage` — the v1 rule *"allocations must **equal** the DFL
  weight"* becomes *"this document's draw, plus everything already settled by
  **other** submitted PO Finals, must not **exceed** the DFL weight."* This is
  the single gate that made partial settlement impossible.
- Every listed Dropoff Final must have at least one allocation. Under `<=`, zero
  is an arithmetically valid draw, which would leave a row in the selector table
  asserting a relationship the document does not have.
- `validate_supplier_consistency` needs no change: it blocks `status == "Settled"`,
  and `Partially Settled` is correctly not that.
- Allocations still may not reference an item the Dropoff Final does not have.

**Side effect worth naming:** because coverage is no longer an equality, a
partially allocated PO Final is now a *valid draft*. In v1 it could not be saved
at all — `validate()` runs on every save, so an accountant halfway through
allocating was thrown. Work in progress now survives.

### 16.5 Controller flow

`DropoffFinal.before_save` gains a final step, which must run last because it
overrides status:

```
aggregate_from_sortings()    # wipes and rebuilds good_items
calculate_totals()
calculate_variance()
set_verification_status()
auto_complete_if_done()      # now also skips Partially Settled
apply_settlement_ledger()    # NEW - stamps settled/remaining, derives status
```

Status derivation: every good item fully drawn gives `Settled`; any draw at all
gives `Partially Settled`; otherwise whatever `auto_complete_if_done` chose is
left alone.

`SMTPurchaseOrder.on_submit` / `on_cancel` stop doing arithmetic on the Dropoff
Final. Both call `sync_dropoff_finals()`, which saves each affected DFL (with
`ignore_permissions=True` — accountants hold read-only on Dropoff Final per
§9.2) and lets the recompute do the work. Using the same call in both directions
is what makes it idempotent.

Note that the **Price Lock** side is unchanged: `SMT Price Lock Item` rows *are*
frozen source data, so the atomic-increment ledger there remains correct and
stays as it is.

### 16.6 The "Pull Items from Dropoff Finals" button

Implements §6 Step 2 to Step 4, specced in v1 and never built. Until now every
allocation row was hand-typed.

Flow: list the Dropoff Finals in the selector table, click **Pull Items from
Dropoff Finals**, and a dialog lists each DFL's *wanted* items (good items only
— unwanted material is never paid) with **remaining** qty already net of other
PO Finals. Tick rows, optionally reduce the qty, and allocation rows are
appended.

Deliberate omissions:

- **It does not guess `source_type`, `po`, or `rate`.** Design decision #7
  forbids automatic FIFO allocation — choosing which Price Lock to draw down is
  the accountant's business judgment. The button removes the transcription, not
  the decision.
- **It is additive**, keyed on `(drop_off_final, item_code)`. Re-clicking after
  adding a fourth Dropoff Final does not disturb allocation work already done on
  the first three, and it does not disturb a row that has been split across two
  Price Locks.
- Items already fully drawn, by this document or another, do not appear.

### 16.7 Knock-on fixes required

| Item | Why |
|---|---|
| `ใบสั่งซื้อ` print format | Iterated `drop_off_finals` printing `total_weight` — the DFL's *whole* weight. A supplier paid for 300 of 1000 kg would receive a document reading 1000 kg. Now prints `drawn_weight` |
| `test_320_dropoff_coverage` | Asserted that skipping an item throws. Under `<=` that is legal, so the test's intent is void; it now asserts over-draw is blocked instead |
| `smt_purchase_order.js` `set_query` | Hardcoded `status: "Unsettled"`; now `["in", ["Unsettled", "Partially Settled"]]` |

### 16.8 Operational consequence, accepted knowingly

Splitting one delivery across several PO Finals produces **several Purchase
Invoices and several Payment Entries for one truckload**. That is more paperwork
on both sides, and the supplier reconciles one delivery against multiple
payments. This was raised explicitly during design and accepted — the timing
flexibility is worth it.

---

## 17. The ERPNext boundary, and the accounting posture (2026-08-26)

### 17.1 What this app does and does not touch

**It never touches ERPNext's Purchase Order.** There are zero references to that
doctype anywhere in the codebase. `SMT Price Lock` and `SMT Purchase Order`
exist precisely to *replace* it — §1 records why: standard PO → Purchase Receipt
→ Purchase Invoice assumes a near-1:1 order-to-receipt relationship that this
business does not have.

The complete list of standard Frappe/ERPNext doctypes this app writes to:

| DocType | Where | Transactional? |
|---|---|---|
| `Supplier` | registration, master data | no |
| `Contact`, `Address` | registration | no |
| **`Purchase Invoice`** | `SMTPurchaseOrder.create_draft_purchase_invoice` | **yes — the only one** |

One document, one hop. The app owns everything up to *"here is what we owe this
supplier, and why"*; paying them is ERPNext's job. The draft Purchase Invoice is
the seam between the two, and it is the app's single point of contact with
accounting.

### 17.2 The app posts nothing to the ledger

Verified 2026-08-26 by grep and by querying the live `metal` site:

- No `make_gl_entries`, no GL Entry, no Stock Ledger Entry, no Purchase Receipt,
  no Stock Entry anywhere in the app.
- `create_draft_purchase_invoice` calls `pi.insert()`. **Nothing anywhere calls
  `.submit()` on a Purchase Invoice.** The only other touchpoint,
  `handle_purchase_invoice`, *blocks* cancellation if a human submitted one — it
  protects the accounting, it does not drive it.
- Site state at the time of writing: 10 PIs created by settlements, **0
  submitted**, Stock Received But Not Billed balance **0.00**, 0 Purchase
  Receipts.

A draft Purchase Invoice is `docstatus = 0` and posts no GL entries. So
submitting an `SMT Purchase Order` moves zero baht in the accounts. That is
design decision #5 working as intended: the accountant gets a review step before
anything is booked.

### 17.3 The "Stock Received But Not Billed" warning

Opening one of those drafts raises an ERPNext message:

> Row 1: Expense Head changed to 2210 - Stock Received But Not Billed as no
> Purchase Receipt is created against Item X. This is done to handle accounting
> for cases when Purchase Receipt is created after Purchase Invoice.

**What it means.** "Expense Head" is the account debited on that invoice line.
Stock Received But Not Billed (SRBNB) is not an expense account at all — it is a
*liability*, and it functions as a waiting room between the two documents
ERPNext expects when buying stock items:

```
Purchase Receipt   goods arrive, no bill yet
                   Dr Stock in Hand / Cr SRBNB          <- value parked

Purchase Invoice   the bill arrives
                   Dr SRBNB / Cr Creditors              <- value leaves
```

In healthy books SRBNB hovers at zero; things pass through it. ERPNext found no
Purchase Receipt for the item, concluded the invoice had arrived first, and
parked the value in the waiting room to be cleared when the receipt turns up.

**Why the assumption does not hold here.** There is no Purchase Receipt in this
flow at all, so the receipt it is waiting for never arrives. If one of these
invoices were submitted it would post `Dr SRBNB / Cr Creditors` — two liabilities,
with nothing ever clearing SRBNB. The purchase would reach neither inventory nor
the P&L.

**It has not happened.** The message fires on a draft. No invoice from this app
has ever been submitted, and SRBNB stands at 0.00. Read it as a weather
forecast, not a fire alarm.

### 17.4 Standing decision: hands off the accounting

**Decided 2026-08-26.** The app must continue to post **zero** GL entries, and
the SRBNB warning is to be left exactly as it is.

Four fixes were considered and all four **declined**:

| Option | Effect | Why declined |
|---|---|---|
| `update_stock = 1` on the PI | Dr Stock in Hand / Cr Creditors; no SRBNB | changes what lands in the client's books |
| Generate a Purchase Receipt too | textbook 3-document flow, SRBNB nets to zero | same, plus 2 docs per settlement |
| `is_stock_item = 0` on scrap items | cost to P&L directly, warning disappears | destroys any future inventory tracking |
| Override `expense_account` on PI rows | cost to P&L, warning disappears | stopgap; still no inventory |

The reason for declining is not that any of them is wrong — it is that the
accounting model is **not settled yet**, and each one changes what appears in a
real company's books. Choosing wrong is far more expensive than a cosmetic
warning on an unsubmitted draft.

Whichever is eventually chosen belongs to the parked warehouse work
(`project_warehouse_plan`), not to settlement. **Do not "fix" this warning in
passing.**
