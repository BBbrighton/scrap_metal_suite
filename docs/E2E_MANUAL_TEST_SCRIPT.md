# End-to-End Manual Test Script — Receiving Workflow

**Scope:** Full business flow from **price booking → completed dropoff, ready to grade.**
Price Lock → (auto) POS Order → Dropoff → container weighing → Completed → Production Sorting handoff.

**Includes:** happy path **plus** erroneous-input / human-error / correction scenarios at every stage.

**Site:** `metal` (dev). **Branch:** `feature/container-redesign`.
Every error message below is quoted from the live controller/API source — if the UI shows different text, that's a finding.

> **Legend:** ✅ = expected happy-path result · ⛔ = deliberately-wrong input, expect the quoted error · 🔧 = how to correct and continue.

---

## Stage 0 — Environment prep

- [ ] Logged into desk as a user with **System Manager / Manager** (Stages 1–3 are desk forms) **and** who also holds **POS Operator** (Stage 4 terminal) and **Production Worker** (Stage 5 terminal) roles. Administrator has all.
- [ ] **Hard-refresh** the browser (`Ctrl+Shift+R`) — JS/CSS changed extensively this branch.
- [ ] (Optional) Reset prior test data: `bench --site metal execute scrap_metal_suite.api_test.setup_inprogress_dropoff.run` cleans `_TEST_CTNWF_` fixtures. For a true from-scratch run you'll create fresh docs below, so this is optional.
- [ ] Confirm at least one **Scale** exists with `usage_type = "Scrap"`, `is_active = 1`, and a sane `max_capacity_kg` (you'll test the capacity bound against it). Note its capacity: __________ kg.

---

## Stage 1 — Price Lock (book the price)

Route: **`/app/smt-price-lock/new`**. Submitting a Price Lock **auto-creates the POS Order** — this is the only supported way to originate an order (no walk-ins).

### 1a. Happy path
- [ ] New SMT Price Lock → pick **Supplier** (supplier_name auto-fills).
- [ ] `po_date` defaults to today; optionally set `expiry_date`.
- [ ] Add **Items** rows: `item_code` (grade), `po_qty` (contracted kg), `po_rate` (THB/kg). Add 2–3 grades.
- [ ] **Save**, then **Submit**.
  - ✅ Green alert: **"POS Order … created"** with a link. `status` → **Open**. Record PL name: __________ and POS Order name: __________ (naming mirrors PLO→PDR, e.g. `PLO-ACME-2604-001` → `PDR-ACME-2604-001`).

### 1b. Erroneous inputs (test validation, then correct)
- [ ] ⛔ Submit with the **Items grid empty** → `At least one item row is required`.
- [ ] ⛔ Row with **`po_qty` = 0** (or negative) → `Row {n}: Qty must be greater than 0`.
- [ ] ⛔ Row with **`po_rate` = 0** → `Row {n}: Rate must be greater than 0`.
- [ ] 🔧 Fix the row(s) with valid qty/rate → Submit succeeds (1a).

### 1c. Human-error later: tried to cancel after settlement
- [ ] ⛔ (If a PO Final has settled against this PL) Cancel the PL → `Cannot cancel: Row {n} (…) has settled quantity …. Cancel related PO Finals first.` — 🔧 cancel the downstream PO Final first. *(Skip if you haven't reached settlement.)*

---

## Stage 2 — POS Order (auto-created)

Route: **`/app/pos-order`**. Created automatically by Stage 1; not submittable (status drives it: Pending → Processing → Processed).

- [ ] Open the POS Order from the Stage 1 alert.
  - ✅ `smt_price_lock` links back to the PL; `order_items` mirrors the PL items (weights = `po_qty`); `status = Pending`.
- [ ] Note: there is **no "Create Dropoff" button here** — the Dropoff points back to the order, not vice-versa. Proceed to Stage 3.

---

## Stage 3 — Dropoff (create + link the order)

Route: **`/app/dropoff/new`** (desk-only creation — there is no portal/terminal create path).

### 3a. Happy path
- [ ] New Dropoff. Set `dropoff_scheduled_start` (defaults Now; `.js` auto-fills `_end` to +2h).
- [ ] Set **`license_plate`**.
- [ ] In **Linked Orders** (child = Dropoff Order) add a row → pick the **submitted POS Order** from Stage 1.
  - ✅ **Expected Items** auto-populates from the order (via `get_items_from_orders`). `supplier` auto-fills read-only from the order.
- [ ] Fill each Expected Item's `indicated_weight` (what the supplier claims per grade).
- [ ] **Save.**
  - ✅ Status auto-transitions **Draft → Scheduled** (license_plate + scheduled_start present). Record Dropoff name: __________.

### 3b. Erroneous inputs
- [ ] ⛔ Save with **Linked Orders empty** → `A Dropoff must be linked to at least one POS Order. Create a Price Lock first (it auto-creates the POS Order), then add it to this Dropoff's Linked Orders table.` (dialog title **"POS Order Required"**).
- [ ] ⛔ Add **two orders from different suppliers** → `All orders in a Drop-off must be from the same supplier. Found: …`.
- [ ] ⛔ Link the **same POS Order twice** → `Same order cannot be linked multiple times to the same Drop-off`.
- [ ] ⛔ Manually add an **Expected Item not in any linked order** → `Item '{x}' in Expected Items is not found in any linked POS Order`.
- [ ] ⛔ Set **Scheduled End before Start** → `Scheduled End must be after Scheduled Start`.
- [ ] ⛔ Set truck **gross**, then a **tare ≥ gross** → `Tare weight ({t} kg) must be less than gross weight ({g} kg)`.
- [ ] 🔧 Correct each and re-save to reach a clean **Scheduled** dropoff.

### 3c. Truck weighing (gross / tare)
- [ ] Record **gross** then **tare** (desk fields or the truck terminal `/pos/truck`). Net = gross − tare.
  - ⛔ Change tare/gross to make **tare ≥ gross** → same tare error as above. 🔧 fix.

---

## Stage 4 — Container weighing (the scrap floor)

Terminal: go to **`/pos`** → open a **POS Session** with **POS Profile Scrap** + a **Scrap** scale → you land on **`/pos/terminal?session=…`** (three-pane). *(A Truck-scale session would redirect to `/pos/truck`.)*

### 4a. Bind the dropoff & weigh (happy path)
- [ ] In the search bar, enter/scan the **Dropoff name** (Stage 3).
  - ✅ LEFT: grade buttons · MIDDLE: context + weigh card · RIGHT: empty journal.
- [ ] Pick a grade → enter a weight → **Save & Print Sticker**.
  - ✅ New bag `CTN-YYMM-#####` appears in RIGHT; sticker prints; status flips **Scheduled → In Progress** and the dropoff is now **locked to your session + scale**.
- [ ] Add several bags across the grades.
  - ✅ "Containers (N)" badge + running total update.

### 4b. Erroneous inputs (weight & scale)
- [ ] ⛔ Save a bag with **weight = 0** (or negative) → `Net weight must be greater than 0`.
- [ ] ⛔ Save a bag with **weight > scale capacity** (Stage 0) → `Weight {w} exceeds scale capacity {cap}`.
- [ ] 🔧 Enter a valid weight → save succeeds.

### 4c. Human error: wrong weight or wrong grade → **Reweigh corrects (never duplicates)**
- [ ] On a bag row, click **Reweigh** → enter the corrected weight + reason.
  - ✅ **Same bag identity preserved:** old row → **Voided** (strikethrough, `superseded_by` set); a **new** `CTN-…` appears with `reweighed_from` = old; a **Container Weight History** row is appended. Totals reflect only the new weight (no double count).
  - ✅ If a Scrap Weight receipt was already issued, reweigh **cancels** it — you must re-run **Finish** (4e).

### 4d. Human error: bag shouldn't count → **Void**
- [ ] Click **Void** on a bag → enter reason.
  - ⛔ Void with **blank reason** → `Void reason is required`. 🔧 add a reason.
  - ✅ Row folds to Voided; total drops by that weight.

### 4e. Finish weighing → receipt
- [ ] Click **Finish Container Weighing**.
  - ⛔ If **no active containers** (all voided) → `Cannot finish weighing: no active containers on this Dropoff.` 🔧 add/keep at least one active bag.
  - ✅ A **submitted Scrap Weight** receipt is produced; the bilingual queue (`ใบคิวสองภาษา`) prints. **Watch the date/time render** here — the queue previously referenced removed Dropoff fields; a blank/garbled timestamp is a finding (see `docs/DROPOFF_CONTAINER_REDESIGN.md` §14.22 posting_time note).

### 4f. Lock / session error scenarios
- [ ] ⛔ From a **second POS Session** (different login/scale), try to add a bag to the same dropoff → `Dropoff {d} is locked to session {s}. Pause and resume to switch.`
- [ ] ⛔ Resume/weigh with a session whose scale ≠ the pinned scale → `Dropoff {d} requires scale {a}; current session uses {b}.`
- [ ] 🔧 **Pause** (desk: *Pause Weighing*, or terminal) then **Resume** on the intended session/scale.
  - ⛔ Pause when status isn't In Progress → `Cannot pause: status is {x}`. Resume when not Paused → `Cannot resume: status is {x}`.

### 4g. Complete the dropoff
- [ ] Ensure gross + tare + at least one submitted Scrap Weight exist, then **Complete**.
  - ✅ Status → **Completed**.
  - ⛔ Complete while **Paused** → `Cannot complete: dropoff is paused`. 🔧 resume first.
- [ ] **Variance check (soft, not a block):** if truck-variance or indicated-variance or grade-mix exceeds the threshold (Dropoff fields `truck_variance_threshold_percent` / `indicated_variance_threshold_percent`, default **0.1%**), the dropoff still completes but `verification_status = **Needs Review**`.
  - 🔧 To clear it: **Mark Verified (Override)** (desk button, shown when Needs Review).
    - ⛔ Override with **no reason** → `Override reason required to verify a Needs-Review dropoff`. 🔧 supply a reason → status **Verified**.

### 4h. Human error: closed too early / need more bags → **Reopen**
- [ ] ⛔ On a **Completed** dropoff, try to add a bag → `Dropoff {d} is {status} — no new bags can be added. To correct a bag, open it and click Reweigh.` (title **"Dropoff Closed"**).
- [ ] Click **Reopen** → enter reason.
  - ⛔ Reopen with **blank reason** → `Reason required to reopen a Dropoff`.
  - ✅ Status → **In Progress**; add more bags; **Finish** again → new receipt with `is_amended=1`; **Reprint** fetches the *latest* active receipt (not the stale cancelled one).

---

## Stage 5 — Ready to grade (Production Sorting handoff)

Only a **Completed** dropoff is gradeable. Terminal: **`/production`** → open a **Production Session** with a scale → **`/production/terminal?session=…`**. (Desk alt: `/app/production-sorting/new`, pick the Dropoff.)

### 5a. The gate
- [ ] ⛔ Before the dropoff is Completed, try to pick it for sorting (or call create_sorting) → `Dropoff {d} is not in Completed status`. The terminal's dropoff lookup **only returns Completed** dropoffs — an in-progress one simply won't appear.
- [ ] 🔧 Complete the dropoff (Stage 4g) → it becomes selectable.

### 5b. Happy path
- [ ] In the production terminal, look up the **Completed** dropoff.
  - ✅ `source_items` populate from the dropoff's per-grade `item_summary` (read-only reference).
- [ ] Split each grade into **Good (Keep & Pay)** and **Unwanted (Return to Supplier)** with a `return_reason`.
  - ⛔ Any item weight **≤ 0** → `Weight must be greater than zero for item {x}`.
  - ⛔ Submit with **no items** → `At least one good or unwanted item is required` (or `Cannot submit sorting with no items`).
- [ ] **Submit** the sorting.
  - ✅ Production Sorting submitted; a **Dropoff Final** is auto-created/updated ("Dropoff Final … updated"). The dropoff is now graded.

### 5c. Session errors
- [ ] ⛔ Open a second production session while one is open → `You already have an open session: {s}. Please close it first.`
- [ ] ⛔ Pick a scale already in use → `Scale '{x}' is already in use by session {s}`.

---

## Consolidated human-error → correction matrix

| # | Human error simulated | Stage | Expected system response | Correction |
|---|---|---|---|---|
| 1 | Empty items when booking price | 1 | `At least one item row is required` | Add a valid item row |
| 2 | Zero/negative qty or rate | 1 | `Row {n}: Qty/Rate must be greater than 0` | Enter positive values |
| 3 | Forgot to link an order to the dropoff | 3 | `…linked to at least one POS Order` (title "POS Order Required") | Add the POS Order in Linked Orders |
| 4 | Mixed suppliers on one dropoff | 3 | `All orders … must be from the same supplier` | Remove the foreign order |
| 5 | Scheduled end before start | 3 | `Scheduled End must be after Scheduled Start` | Fix the times |
| 6 | Tare ≥ gross | 3 | `Tare weight … must be less than gross weight …` | Re-enter tare/gross |
| 7 | Overweight / zero bag | 4 | `Weight … exceeds scale capacity …` / `Net weight must be greater than 0` | Re-weigh with valid value |
| 8 | Weighed wrong weight/grade | 4 | (no error) | **Reweigh** — supersedes the bag, no duplicate |
| 9 | Bag counted by mistake | 4 | `Void reason is required` if blank | **Void** with reason |
| 10 | Two operators on one dropoff | 4 | `…locked to session {s}. Pause and resume to switch.` | Pause → resume on right session |
| 11 | Wrong scale on resume | 4 | `…requires scale {a}; current session uses {b}` | Switch to the pinned scale |
| 12 | Completed too early | 4 | `…no new bags can be added…` (title "Dropoff Closed") | **Reopen** (with reason) → add → re-finish |
| 13 | Over-threshold variance | 4 | Completes but **Needs Review** | **Mark Verified (Override)** with reason |
| 14 | Grading a not-yet-completed dropoff | 5 | `Dropoff {d} is not in Completed status` | Complete the dropoff first |

---

## Sign-off

- [ ] Stages 1–5 happy path pass end-to-end (Price Lock → graded Dropoff Final).
- [ ] All ⛔ scenarios produced the quoted error and 🔧 correction restored the flow.
- [ ] Bilingual queue timestamp renders correctly (4e).
- [ ] Item names render in **canonical Thai** under both TH and EN UI.
- [ ] Tester: __________  Date: __________  Build/commit: __________

> Wrong or missing error text, a variance breach that *blocks* completion, or any bag double-counting after reweigh are the highest-value findings — note them against the step number above.
