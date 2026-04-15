# Production Sorting Module — Code Audit Report

**Date:** 2026-04-14
**Version:** v1.0.0
**Branch:** develop (post-merge of develop3)
**Audited by:** Claude Code (4 parallel audit agents + 5 verification agents)
**Verification status:** ALL FINDINGS VERIFIED — zero false positives
**Fix status:** C1-C7, W1-W2, W6-W7, W8-W14 — ALL FIXED (2026-04-14)

---

## Audit Scope

Four parallel audits were conducted, followed by 5 parallel verification agents that reproduced each finding and proposed minimal fixes:

1. **SQL & Data Access** — Direct SQL manipulation, injection risks, ORM usage
2. **API Patterns & Auth** — Whitelisting, auth guards, input validation, error handling
3. **DocType Definitions & Cleanup** — JSON validity, hooks consistency, dead code, backup files
4. **Frontend & Templates** — JS quality, XSS risks, CSS conflicts, backup files

---

## Summary

| Severity | Count | Verified |
|----------|-------|----------|
| CRITICAL | 7 | 7/7 confirmed |
| WARNING  | 19 | 19/19 confirmed (W8 downgraded to INFO) |
| INFO     | 8 | 8/8 confirmed |
| CLEAN    | SQL layer (no issues), DocType JSONs, `__init__.py` files, hooks references |

---

## CRITICAL Findings (7) — All Verified, All Fixed

### C1. Field Name Mismatch — Production Session Close Returns 0 Weight

- **File:** `scrap_metal_suite/scrap_metal_suite/doctype/production_session/production_session.py` (lines 48, 52)
- **Status:** CONFIRMED
- **FIXED:** Changed `total_sorted_weight` → `total_weight` on lines 48 and 52

---

### C2. `ignore_permissions=True` on Session Insert

- **File:** `scrap_metal_suite/api/v1/production.py` (line 31)
- **Status:** CONFIRMED
- **FIXED:** Removed `ignore_permissions=True` from `session.insert()`

---

### C3. No XSS Sanitization on String Inputs

- **File:** `scrap_metal_suite/api/v1/production.py` — `create_sorting()` and `update_sorting()`
- **Status:** CONFIRMED
- **FIXED:** Added `sanitize_html` import, applied to `remarks` and `return_reason` in 4 locations (both functions, both item loops). Pattern: `sanitize_html(str(...).strip())[:1000]`. Also removed unused `nowdate` import (W7).

---

### C4. XSS via innerHTML in production-terminal.js

- **File:** `scrap_metal_suite/public/js/production-terminal.js`
- **Status:** CONFIRMED
- **FIXED:** Added `escapeHtml()` helper function at top of file. Applied to all dynamic values in `displayDropoffResults`, `selectDropoff` inner loop, and `updateItemsList` (good + unwanted sections).

---

### C5. XSS via innerHTML in terminal.html Inline JS

- **File:** `scrap_metal_suite/www/production/terminal.html`
- **Status:** CONFIRMED
- **FIXED:** Added `escapeHtml()` helper at top of inline `<script>`. Applied to all dynamic values in: search results, dropoff card, cart rendering, and scale list.

---

### C6. Jinja2 XSS in onclick Handlers

- **File:** `scrap_metal_suite/www/pos/production.html` + `www/production/terminal.html`
- **Status:** CONFIRMED
- **FIXED:** Converted all Jinja2 `{{ }}` in onclick handlers to `data-*` attributes with `| e` filter:
  - `pos/production.html`: scale buttons (line 100) and item cards (line 216)
  - `production/terminal.html`: category tabs (line 68) and item buttons (line 74)

---

### C7. production.css Loaded Globally

- **File:** `scrap_metal_suite/hooks.py`
- **Status:** CONFIRMED
- **FIXED:** Removed `production.css` from `web_include_css`. Both production templates (`terminal.html`, `index.html`) already load it via `<link>` in `{% block head_include %}`.

---

## WARNING Findings (19) — All Verified

### API Warnings

| # | File | Issue | Status |
|---|------|-------|--------|
| W1 | `production.py` | `json.loads()` without try/except — raw tracebacks | **FIXED** — Added try/except with `frappe.throw()` in both `create_sorting` and `update_sorting` |
| W2 | `production.py` | No validation that `dropoff` exists before creating sorting | **FIXED** — Added `frappe.db.get_value` check for existence and "Completed" status |
| W3 | `production.py` | No validation that `item_code` values are real Items | NOT FIXED — deferred (low risk, items come from `get_allowed_items` UI) |
| W4 | `production.py` | No max weight validation against scale capacity | NOT FIXED — deferred (low risk, POS pattern available for reference) |
| W5 | `production.py` | `get_dropoff_for_sorting` loads full doc via `frappe.get_doc()` | NOT FIXED — deferred (performance, not correctness) |

### DocType / Code Warnings

| # | File | Issue | Status |
|---|------|-------|--------|
| W6 | `dropoff_final.py` | `variance_threshold_percent` — no settings fallback | **FIXED** — Added fallback to Production Sorting Settings, then 5.0% default |
| W7 | `production.py` | Unused import `nowdate` | **FIXED** — Removed, replaced with `sanitize_html` import (part of C3 fix) |

### Cleanup Warnings

| # | File | Issue | Status |
|---|------|-------|--------|
| W8 | `api/v1/production.py.backup` | Backup file tracked in git | **FIXED** — `git rm --cached` |
| W9 | `api/v1/production.py.phase4_backup` | Backup file tracked in git | **FIXED** — `git rm --cached` |
| W10 | `doctype/production_sorting/production_sorting.json.backup` | Backup file tracked in git | **FIXED** — `git rm --cached` |
| W11 | `doctype/dropoff/dropoff.json.backup` | Backup file tracked in git | **FIXED** — `git rm --cached` |
| W12 | `www/pos/index.html.backup` | Backup file tracked in git | **FIXED** — `git rm --cached` |
| W13 | `www/pos/production.html.backup` | Backup file tracked in git | **FIXED** — `git rm --cached` |
| W14 | `example_tobedeleted/` | Directory still tracked | **FIXED** — `git rm -r --cached` |

All cleanup items also added to `.gitignore` (`*.backup`, `*.phase4_backup`, `example_tobedeleted/`).

### Frontend Warnings

| # | File | Issue | Fix | Verified |
|---|------|-------|-----|----------|
| W15 | `production-terminal.js` | 18 global variables polluting window scope | Wrap in IIFE | CONFIRMED |
| W16 | `www/production/terminal.html` | ~415 lines of inline JS | Extract to external JS file | CONFIRMED |
| W17 | `public/css/production-theme-fix.css` | Orphaned — not referenced anywhere | Delete or merge into `production-theme.css` | CONFIRMED |
| W18 | Multiple CSS files | Duplicate/conflicting class names | Consolidate into one canonical CSS | CONFIRMED |
| W19 | `www/production/terminal.html:576` | Uses native `confirm()` instead of `frappe.confirm()` | Replace with Frappe dialog | CONFIRMED |

### Architectural Warning

**Two parallel terminal implementations exist:**
- `/pos/production` — orange theme, 3-panel layout, uses `production-terminal.js`
- `/production/terminal` — blue theme, 2-panel layout, inline JS with `POS_CORE` integration

These share the same API endpoints but have different UIs, state management, and CSS. **One should be chosen as canonical and the other removed.**

---

## INFO Findings (8) — All Verified

| # | File | Issue | Verified |
|---|------|-------|----------|
| I1 | `production.py:232` | `search_dropoff` is a one-line alias for `lookup_dropoff` | CONFIRMED |
| I2 | `production.py:185` | LIKE wildcards not escaped in lookup query | CONFIRMED |
| I3 | `production.py` (multiple) | Inconsistent empty returns: `None` vs `[]` vs `{}` | CONFIRMED |
| I4 | `production.py:232` | `search_dropoff` relies on `lookup_dropoff` for auth | CONFIRMED |
| I5 | `smt/` directory | Empty module directory with only `__init__.py` | CONFIRMED |
| I6 | repo root | `migrate_dropoff_datetime.py` one-time migration script committed | CONFIRMED |
| I7 | Multiple JS files | `console.error()` statements left in production code | CONFIRMED |
| I8 | `www/production/index.html` | `open_session` called without `scale` arg — not a crash (optional param) | CONFIRMED — downgraded from W8 |

---

## Clean Areas (No Issues)

- **SQL layer:** All `frappe.db.sql()` calls use parameterized queries. No SQL injection risks. No direct SQL writes — all mutations go through the Frappe document API.
- **DocType JSON files:** All 33 files valid, proper `module` fields.
- **`__init__.py` files:** All present in all required directories.
- **hooks.py references:** All scheduler functions, doc_events, and CSS file paths point to existing files.
- **Auth guards:** All whitelisted API functions call `check_production_operator()`.
- **`@frappe.whitelist()`:** Present on all public API functions. Internal helper `update_dropoff_final` correctly lacks it.

---

## Recommended Fix Priority

### DONE — Fixed on 2026-04-14
- **C1-C7** — All 7 critical findings fixed
- **W1-W2** — JSON error handling + dropoff validation
- **W6-W7** — Variance threshold fallback + unused import
- **W8-W14** — All backup files removed from tracking, `.gitignore` updated

### Remaining — Not Yet Fixed (deferred, lower risk)
- **W3** — item_code validation (low risk — UI already constrains to allowed items)
- **W4** — Max weight validation against scale capacity
- **W5** — `get_dropoff_for_sorting` loads full doc (performance, not correctness)
- **W15-W19** — Frontend consolidation (IIFE wrapper, extract inline JS, CSS cleanup)
- **Architectural** — Choose one terminal implementation (`/pos/production` vs `/production/terminal`), remove the other
