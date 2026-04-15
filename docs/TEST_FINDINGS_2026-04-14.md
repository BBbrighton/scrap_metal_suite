# Test Findings & Fixes — 2026-04-14/15

**Test suite:** `scrap_metal_suite/api_test/test_full_workflow.py`
**Run command:** `bench --site metal execute scrap_metal_suite.api_test.test_full_workflow.run`
**Final result:** 77 passed, 0 failed, 2 skipped

---

## 1. Issues Discovered & Fixed During Testing

### 1.1 POS Operator Has No DocType Permissions (CRITICAL — FIXED)

**Found:** POS Operator role had zero permissions on 7 of 8 POS DocTypes. Only Scale had read-only.

**Impact:** A pure POS Operator (without System Manager role) could not use the POS system at all.

**Fix:** Added proper DocType permissions for POS Operator:

| DocType | Permissions Added |
|---------|------------------|
| POS Session | create, read, write |
| POS Order | read, write |
| Scrap Weight | create, read, write |
| Scrap Purchase | create, read, write |
| Truck Weight | create, read, write |
| Scale | read, write (was read-only) |
| POS Profile Scrap | read |
| Dropoff | read, write |

Same fix for Production Worker:

| DocType | Permissions Added/Updated |
|---------|--------------------------|
| Production Sorting | Added create (had read/write/submit) |
| Dropoff Final | Added create, write (was read-only) |
| Scale | Added read, write |
| Production Session | Already correct |

### 1.2 `ignore_permissions=True` Was Correct, Not a Bug

**Original audit finding C2:** Flagged `ignore_permissions=True` on session insert as wrong.

**Reality:** With DocType permissions now properly set, all `ignore_permissions=True` calls have been **removed**. Frappe handles permissions natively. The auth guards (`check_pos_operator`, `check_production_operator`) provide API-level authorization, and DocType permissions handle document-level access.

### 1.3 Frappe Lowercases Email Addresses

**Found:** Test constants used mixed case but Frappe stores emails lowercase. Session operator checks failed on case mismatch.

**Fix:** All test email constants use lowercase.

### 1.4 Scrap Weight API Missing Required `dropoff` Field

**Found:** `create_scrap_weight` in pos.py doesn't populate the `dropoff` field on Scrap Weight, but the DocType has `reqd: 1`.

**Status:** Not fixed in API — worked around in test. Needs follow-up ticket.

### 1.5 Scale `in_use_by_session` Only Links to POS Session

**Found:** The Scale DocType's `in_use_by_session` field is a Link to "POS Session" only. Production sessions can't use this field, causing "Could not find" errors when production sessions try to set it.

**Status:** Known bug — documented. Needs the field changed to Dynamic Link or a separate field for production sessions.

---

## 2. Business Logic Verified

### 2.1 Reweight Flow (test_110)
- Truck weight reweight **correctly requires a reason** — empty/missing reason is rejected
- Reweight **updates in-place** (not creating new record)
- Flags set correctly: `is_reweight=1`, `reweight_reason`, `reweight_by`, `reweight_at`
- Old weight value overwritten with new value

### 2.2 Variance Calculations (tests 120-121)

**Truck Variance** (net truck weight vs total scrap weight):
- Formula: `net_truck_weight - total_scrap_weight`
- Percentage: `|variance / net_truck_weight| × 100`
- Tested: 15kg net, 14.5kg scrap → 0.5kg variance (3.33%) — within 5% threshold → `truck_variance_ok=True`
- Tested: 100kg net, 90kg scrap → 10kg variance (10%) — exceeds 1% threshold → `truck_variance_ok=False`

**Indicated Variance** (supplier-claimed vs actual weighed):
- Formula: `total_indicated_weight - total_actual_weight`
- Same percentage calculation
- Both pass/fail scenarios verified

**Verification Status**:
- Both variances OK → `"Verified"`
- Either variance exceeds threshold → `"Needs Review"`

### 2.3 Sorting Variance (test_130)

**Dropoff Final Variance** (dropoff actual weight vs sorted weight):
- Dropoff actual: 20kg, sorted: 19kg → variance 1kg (5%)
- Production Sorting Settings threshold: 0.1%
- 5% > 0.1% → `variance_ok=False`, status `"Needs Review"`
- Correctly uses settings fallback (from our W6 fix)

### 2.4 Status Auto-Transitions (test_140)
- `Draft` → `Scheduled`: when license plate + scheduled start set
- `Scheduled` → `In Progress`: when first weight (gross/tare/scrap) recorded
- `In Progress` → `Completed`: when all weights (gross + tare + scrap) recorded
- Transition logic enforced by Dropoff controller on every save

### 2.5 XSS Sanitization (test_60)
- `<script>alert("xss")</script>` in remarks → stripped by `sanitize_html()`
- Verified: `<script>` tag not present in stored value

### 2.6 Input Validation (test_99)
- Zero weight → rejected with error
- Negative weight → rejected with error
- Empty items list → rejected with error
- Very small weight (0.001 kg) → accepted

### 2.7 Session Security (tests 80, 101)
- Supplier user blocked from POS and Production endpoints
- POS Operator blocked from Production endpoints
- Production Worker blocked from POS endpoints
- Manager CAN close another operator's session
- Operator CANNOT heartbeat another operator's session

---

## 3. Test Results Progression

| Run | Passed | Failed | Skipped | Key Change |
|-----|--------|--------|---------|------------|
| 1 | 28 | 11 | 5 | Initial — field value mismatches |
| 2 | 32 | 7 | 5 | Fixed parity, field names, return_reason |
| 3 | 33 | 6 | 5 | Fixed scheduler duplicate session |
| 4 | 38 | 7 | 3 | Restored ignore_permissions, lowercase emails |
| 5 | 41 | 4 | 3 | Fixed POS user, sorting insert perms |
| 6 | 43 | 2 | 3 | Fixed Dropoff Final perms |
| 7 | 47 | 0 | 2 | All core tests passing |
| 8 | 59 | 0 | 2 | Added edge cases + permission matrix + operator flows |
| 9 | 72 | 2 | 2 | Added reweight + variance + status transition tests |
| **10** | **77** | **0** | **2** | **Fixed test data for reweight + sorting variance** |

---

## 4. Full Test Coverage (77 tests)

| Group | # | Tests | Status |
|-------|---|-------|--------|
| **01. Users & Roles** | 4 | Create operator, manager, worker, supplier | All pass |
| **02. Master Data** | 5 | Items, Scale, Supplier, POS Profile, Prod Settings | All pass |
| **03. Role Permissions** | 5 | Auth guards: POS, Production, cross-role blocking | All pass |
| **10. POS Session** | 5 | Open, duplicate blocked, heartbeat, active, scale | All pass |
| **20. Dropoff** | 3 | Create, add items, complete | All pass |
| **30. Truck Weight** | 2 | Gross + tare recording | All pass |
| **40. Scrap Weight** | 3 | POS Order, weight creation, totals | All pass |
| **50. POS Close** | 3 | Close, status check, scale released | All pass |
| **60. Production Sorting** | 7 | Session, lookup, sorting, XSS, bad JSON, bad dropoff | All pass |
| **65. Dropoff Final** | 1 | Auto-creation, weights, variance | Pass |
| **70. Production Close** | 2 | Close + C1 fix verification (weight != 0) | All pass |
| **80. Cross-User** | 1 | Supplier blocked from production | Pass |
| **90. Scheduler** | 2 | POS idle close (90min) + Production idle close (10min) | All pass |
| **95. Print Formats** | 4 | Existence check (2 found, 2 expected skips) | 2 pass, 2 skip |
| **96. Permission Matrix** | 1 | 17 role × DocType checks | Pass |
| **97. POS Operator Flow** | 1 | Pure operator: open→heartbeat→active→close | Pass |
| **98. Production Worker Flow** | 1 | Pure worker: open→lookup→sort→close | Pass |
| **99. Data Edge Cases** | 4 | Zero weight, negative, empty items, 0.001 kg | All pass |
| **100. Session Lifecycle** | 3 | Closed heartbeat, double close, orphan recovery | All pass |
| **101. Cross-User Security** | 2 | Manager override, cross-role block | All pass |
| **110. Reweight Flow** | 3 | No-reason blocked, with-reason succeeds, flags verified | All pass |
| **120. Variance (pass)** | 7 | Truck 3.33%, indicated 3.33%, status=Verified | All pass |
| **121. Variance (fail)** | 3 | Truck 10%, indicated 10%, status=Needs Review | All pass |
| **130. Sorting Variance** | 2 | 5% vs 0.1% threshold, Dropoff Final created | Pass |
| **140. Status Transitions** | 3 | Scheduled→In Progress→Completed auto-transitions | All pass |

---

## 5. Known Issues (Not Fixed)

| Issue | Severity | Notes |
|-------|----------|-------|
| `create_scrap_weight` API missing `dropoff` field | Medium | API doesn't populate required field from POS Order |
| Scale `in_use_by_session` only links to POS Session | Low | Production sessions can't use this field |
| No print formats for Scrap Purchase, Production Sorting | Low | Expected — not yet created |
| Sorting variance threshold from settings is 0.1% | Info | Very tight — may need business review for production use |
