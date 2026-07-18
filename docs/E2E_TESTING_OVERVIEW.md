# E2E Testing Overview — Receiving Workflow

Consolidated index for end-to-end testing of the receiving flow
(**Price Lock → POS Order → Dropoff → weigh → Completed → graded**). Ties
together the manual checklist, the observational walkthrough, and the permanent
regression test. **Last verified: 2026-07-18 on site `metal`, branch
`feature/container-redesign`.**

## Three-layer strategy

| Layer | Artifact | Purpose | How to run |
|---|---|---|---|
| **Manual** (human + hardware) | [E2E_MANUAL_TEST_SCRIPT.md](E2E_MANUAL_TEST_SCRIPT.md) | Browser click-through + scanner/scale/printer. The only layer that covers real hardware. | Follow in browser from `/app/smt-price-lock/new` |
| **Observational** (Lane A) | `api_test/_e2e_walkthrough.py` | Drives the real controllers/APIs headless, *captures* actual behaviour + error text (doesn't assert — surfaces findings). Discovery tool. | `bench --site metal execute scrap_metal_suite.api_test._e2e_walkthrough.run` |
| **Regression** (Lane B) | `api_test/test_e2e_full_flow.py` | Permanent, asserting. 15 error scenarios + Production Sorting handoff + happy smoke. Run on every change. | `bench --site metal execute scrap_metal_suite.api_test.test_e2e_full_flow.run` |

Lane A results are recorded in [E2E_TEST_RESULTS.md](E2E_TEST_RESULTS.md).

## Current status — all green (2026-07-18)

| Suite | Result |
|---|---|
| `test_finish_weighing_session` (reweigh/void/re-finish) | 20/20 ✅ |
| `smoke_test_sticker_render` | 6/6 ✅ |
| `smoke_test_container_photos` | 7/7 ✅ |
| Playwright UI (`ui_test/`) | 3/3 ✅ |
| **`test_e2e_full_flow` (Lane B)** | **24/24 ✅** (idempotent) |
| Lane A walkthrough | 12/12 happy · 15/15 errors · 0 findings |

## Lane B coverage (`test_e2e_full_flow.run` → 24 checks)

**Happy checkpoints (9):** PL submit auto-creates POS Order · Dropoff create (Scheduled) · add_container×3 (In Progress) · reweigh corrects with no duplication · pause→resume · finish→complete · verify override · create_sorting submitted · Dropoff Final auto-created.

**Error / human-error assertions (15):** PL empty items · PL qty≤0 · PL rate≤0 · Dropoff no orders · duplicate order · mixed suppliers · add weight≤0 · add > scale capacity · void without reason · session lock (2nd operator) · complete while paused · verify without reason · sort non-Completed dropoff · sort no items · sort item weight≤0. *(Each asserts the exact error text — see E2E_TEST_RESULTS.md for the verbatim messages.)*

Reuses the fixtures in `test_container_workflow.py` (single source of truth for masters / Price Lock / Dropoff builders). `cleanup_first`/`cleanup_after` default True, so it's self-contained and re-runnable.

## What is NOT covered here (still owed)

- **Browser + hardware** — physical scanner scan, live scale continuous-read, and actual sticker/queue printing. Manual layer only ([E2E_MANUAL_TEST_SCRIPT.md](E2E_MANUAL_TEST_SCRIPT.md)); consider a **Claude in Chrome / Cowork** exploratory pass against `http://localhost:8000`.
- **Playwright UI E2E of the full chain** — the current `ui_test/` covers the terminal surface, not the whole PL→grade pipeline through the desk forms. Future Layer-2 work.
- **`posting_time` on Scrap Weight** — bilingual queue still falls back to `creation`; verify the timestamp in the browser (see `DROPOFF_CONTAINER_REDESIGN.md` §14.22).
- **Stale Dropoff print field** — queue print references removed `doc.is_reweighed`/`doc.reweight_reason`; confirm it renders cleanly.
- **Role guards** — `reassign_dropoff`/`switch_scale`/`verify_dropoff` have no Manager-only guard (audit-only). Pre-production decision, not a test gap.

## Run everything (copy/paste)

```bash
cd ~/frappe-bench
# server suites
bench --site metal execute scrap_metal_suite.api_test.test_finish_weighing_session.run
bench --site metal execute scrap_metal_suite.api_test.smoke_test_sticker_render.run
bench --site metal execute scrap_metal_suite.api_test.smoke_test_container_photos.run
bench --site metal execute scrap_metal_suite.api_test.test_e2e_full_flow.run
# Playwright UI
SMT_UI_HEADLESS=1 SMT_UI_ADMIN_PWD="$SMT_UI_ADMIN_PWD" env/bin/pytest apps/scrap_metal_suite/scrap_metal_suite/ui_test/ -v
```
