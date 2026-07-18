# E2E Test Results — Lane A (observational walkthrough)

**Date:** 2026-07-18 · **Site:** `metal` · **Branch:** `feature/container-redesign` (HEAD `ab64ef6`)
**Driver:** `scrap_metal_suite.api_test._e2e_walkthrough.run` (executed headless via `bench execute`).
**Method:** drives the real controllers/APIs through the full receiving flow and every documented error scenario from [E2E_MANUAL_TEST_SCRIPT.md](E2E_MANUAL_TEST_SCRIPT.md); *observes* actual behaviour (captures real error text) rather than asserting, so mismatches surface as findings.

> Scope note: this exercises the **server-side logic path** (same controllers the UI calls). The physical browser click-through + hardware (scanner/scale/printer) integration remains a manual step — run [E2E_MANUAL_TEST_SCRIPT.md](E2E_MANUAL_TEST_SCRIPT.md) in the browser for that. Lane B (`test_e2e_full_flow.py`) turns the verified behaviour below into permanent assertions.

## Result: ✅ 12/12 happy-path stages · 15/15 error scenarios matched · **0 findings**

```
{"happy_ok": 12, "happy_total": 12, "errors_probed": 15, "findings": 0}
```

---

## Happy path — full chain (12/12)

| # | Stage | Actual outcome |
|---|---|---|
| 1 | Price Lock submit → auto POS Order | `PLO-TEST-2607-###` → `PDR-TEST-2607-###` (auto-created on submit) |
| 2 | Dropoff create (linked PO) | `DO-…` status **Scheduled**, supplier auto-set, expected items populated |
| 3 | POS Session open | `SES-…` on the Scrap scale |
| 4 | add_container × 3 | `CTN-2607-00001/2/3` (naming series `CTN-YYMM`) |
| 5 | reweigh (correction) | bag 1 250 → 275 kg; total updates to **575** with **no duplication** (old bag Voided + superseded) |
| 6 | void (correction) | bag 3 voided with reason |
| 7 | pause → (complete blocked) → resume | pause clears session, keeps scale lock; resume re-binds |
| 8 | finish_weighing_session | submitted **Scrap Weight** receipt `SW-…` |
| 9 | complete_dropoff | status **Completed**, `verification_status = Needs Review` (variance from reweigh, as designed) |
| 10 | verify override | `verification_status = Verified` (with reason) |
| 11 | create_sorting (Production) | `SORT-…` inserted **and submitted** |
| 12 | Dropoff Final auto-created | `DFL-260718-00001` created on sorting submit |

**Confirmed invariants:** reweigh corrects in place (no 6× duplication regression), pause preserves the scale lock, completion is decoupled from variance (soft Needs Review), and the Completed → Production Sorting → Dropoff Final handoff works end-to-end.

---

## Error / human-error scenarios — all 15 fired with expected text

| # | Scenario | Actual error message (verbatim) |
|---|---|---|
| 1 | Price Lock, empty items | `At least one item row is required` |
| 2 | Price Lock, qty ≤ 0 | `Row 1: Qty must be greater than 0` |
| 3 | Price Lock, rate ≤ 0 | `Row 1: Rate must be greater than 0` |
| 4 | Dropoff, no linked orders | `A Dropoff must be linked to at least one POS Order. Create a Price Lock first (it auto-creates the POS Order), then add it to this Dropoff's Linked Orders table.` |
| 5 | Dropoff, duplicate order | `Same order cannot be linked multiple times to the same Drop-off` |
| 6 | Dropoff, mixed suppliers | `All orders in a Drop-off must be from the same supplier. Found: …` |
| 7 | add_container, weight ≤ 0 | `Net weight must be greater than 0` |
| 8 | add_container, > scale capacity | `Weight 999999.0 exceeds scale capacity 5000.0` |
| 9 | void without reason | `Void reason is required` |
| 10 | 2nd operator adds to locked dropoff | `Dropoff … is locked to session …. Pause and resume to switch.` |
| 11 | complete while paused | `Cannot complete: dropoff is paused` |
| 12 | verify Needs-Review w/o reason | `Override reason required to verify a Needs-Review dropoff` |
| 13 | sort a non-Completed dropoff | `Dropoff … is not in Completed status` |
| 14 | sort with no items | `At least one good or unwanted item is required` |
| 15 | sort item weight ≤ 0 | `Weight must be greater than zero for item ทองแดงปอก` |

---

## Notes & nuances discovered (not defects)

1. **Dropoff naming needs a supplier.** A Dropoff with **no supplier** fails autonaming (`Supplier is required to generate a document ID`) *before* the friendly `POS Order Required` / single-supplier validations run. In the desk UI `supplier` auto-fills from the first linked order, so the friendly guards are what a real user sees — but a supplier-less save (e.g. via API) hits the cryptic naming error first. Minor UX consideration only.
2. **Valid `return_reason` values** (Production Sorting unwanted items): `Contamination`, `Wrong Material`, `Packaging`, `Dirt/Debris`, `Other`. (Not free text.)
3. **Variance is soft, by design.** Over-threshold variance completes the dropoff into `Needs Review` — it never blocks completion. Cleared only via **Mark Verified (Override)** with a reason.

## Cross-references — still owed (from design review, not covered here)

- **`posting_time` on Scrap Weight** — bilingual queue print still uses `creation` as a fallback (see `DROPOFF_CONTAINER_REDESIGN.md` §14.22). Verify the queue timestamp renders in the browser walkthrough.
- **Stale Dropoff print field** — the queue print references removed `doc.is_reweighed` / `doc.reweight_reason`; confirm it renders cleanly (potential blank/garbled field).
- **Hardware integration** — scanner + scale continuous-read + physical print not exercised here; browser walkthrough only.
