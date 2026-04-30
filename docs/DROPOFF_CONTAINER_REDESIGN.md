# Dropoff & Container Redesign

**Status:** Design — pending implementation
**Authors:** Brighton + Claude
**Last updated:** 2026-04-25

---

## 1. Context & problem

The current Dropoff + Scrap Weight model creates a new `Scrap Weight` document on every "submit" and treats each one as a *snapshot of the entire weighed state of the dropoff*. The aggregator (`Dropoff.sync_actual_items`) faithfully sums every Scrap Weight Item across every Scrap Weight tied to the dropoff.

Concrete failure: **DO-260320-00002** has 6 `Scrap Weight` docs (`WGT-2026-00102` through `00107`), each containing the same 10 items at identical weights. Aggregation reports `total_actual_weight = 18,202.8 kg` while the truck net is 3,030 kg — a 6× over-count. The truck variance check then flags a clean dropoff as -500% off.

The model is also missing two real-world concepts:

1. **Container** — physical unit (bag / bin / pallet) with its own identity, label, and QR. Operators need to weigh-and-tag each container as a discrete record. Today there is no container abstraction.
2. **Operator session lock** — a dropoff is a single physical operation with one operator on one scale. The schema lets multiple sessions/scales contribute records to the same dropoff with no constraint.

Workflow gaps: no per-container print, no reweigh model that *replaces* (vs duplicates), no pause/resume, no deviation/downgrade tracking, no audit trail on session/scale changes.

This redesign collapses `Scrap Weight` and `Scrap Weight Item` into a single `Scrap Weight Container` doctype and constrains the dropoff to one operator-session/scale at a time.

---

## 2. Design goals

1. **One Dropoff = one operator session = one scale** at any moment, enforced by controller validation, with audit-logged manager overrides for shift change / scale swap.
2. **Container as first-class document** — one container holds one grade and one weight, has a unique ID, gets a printed sticker with QR.
3. **Reweigh corrects, never duplicates** — updating a container preserves the document and appends to a weight history child table.
4. **Pause / Resume** the weighing of a dropoff across operator sessions without losing data integrity or breaking the lock.
5. **Deviation tracking** — capture when the actual grade weighed differs from the dropoff's expected items, with reason + optional approval.
6. **Bilingual UI** (Thai / English) for desk + custom truck terminal. Item names stay canonical (Thai) — never translated. See `BILINGUAL_GUIDE.md`.
7. **Backward-compatible migration** — existing dropoffs migrate cleanly; the most recent `Scrap Weight` per dropoff is treated as truth.

---

## 3. Hierarchy

```
POS Session (operator login session)
  └── Dropoff (1 truck, 1 supplier)
        ├── Expected Items (from POS Order)
        └── Scrap Weight Container (NEW)        ← printable sticker, QR = name
              ├── 1 grade (item_code)
              ├── 1 weight (net)
              └── weight history (reweigh log)
```

`Scrap Weight` and `Scrap Weight Item` doctypes are removed. The Dropoff itself plays the role of "weighing session" via its `weighing_session` and `weighing_scale` lock fields.

---

## 4. Data model

### 4.1 NEW DocType: `Scrap Weight Container`

**Naming series:** `CTN-.YYYY.-.#####` (e.g. `CTN-2026-00007`)

| Field | Type | Required | Description |
|---|---|---|---|
| `naming_series` | Data | yes | `CTN-.YYYY.-.#####` |
| `dropoff` | Link → Dropoff | yes | Parent dropoff |
| `session` | Link → POS Session | yes | Session that recorded THIS container (denormalised for filter) |
| `scale` | Link → Scale | yes | Scale used to weigh THIS container |
| `operator` | Link → User | yes | Operator who weighed it |
| `item_code` | Link → Item | yes | The grade |
| `item_name` | Data | yes | Denormalised, canonical Thai (never translated) |
| `container_no` | Int | yes | Sequence within the dropoff (1, 2, 3, ...) |
| `container_type` | Select | yes | `Bag` / `Bin` / `Pallet` / `Other` |
| `net_weight` | Float | yes | Weight of contents (kg) — read from scale (operator tares the empty bag, then weighs). Tare/gross precision deferred to Production Sorting module. |
| `entry_method` | Select | yes | `Scale (Auto)` / `Manual Entry` |
| `status` | Select | yes | `Active` / `Reweighed` / `Voided` |
| `is_reweighed` | Check | no | True after first reweigh |
| `last_reweigh_at` | Datetime | no | Most recent reweigh |
| `last_reweigh_by` | Link → User | no | |
| `last_reweigh_reason` | Small Text | no | |
| `expected_item` | Link → Item | no | What the dropoff expected at this slot (auto-populated if exact match exists) |
| `is_deviation` | Check | computed | `1` if `item_code` not in `dropoff.expected_items` |
| `deviation_type` | Select | no | `Downgrade` / `Upgrade` / `Substitution` / `Unplanned-Add` |
| `deviation_reason` | Small Text | no | Required when `is_deviation=1` |
| `deviation_approved_by` | Link → User | no | Set when threshold-based approval is needed |
| `deviation_approved_at` | Datetime | no | |
| `superseded_by` | Link → Scrap Weight Container | no | Set when status=`Voided` and replaced by another container |
| `voided_reason` | Small Text | no | |
| `voided_at` | Datetime | no | |
| `voided_by` | Link → User | no | |
| `legacy_scrap_weight` | Data | no | Migration trail — original Scrap Weight name(s) |
| `weight_history` | Child Table → Container Weight History | no | Append-only audit |
| `remarks` | Small Text | no | |

**Permissions (initial — no role guard yet):**
- `POS Operator`: read, create, write, submit (no delete)
- `Production Operator`: read
- `Manager`: full
- `System Manager`: full

**Indexes:**
- `(dropoff, status)` — fast aggregation
- `(session, status)` — operator's active containers
- `(item_code, status)` — per-grade queries

---

### 4.2 NEW Child DocType: `Container Weight History`

Stores every weight change for audit. Append-only (never edited or deleted).

| Field | Type | Description |
|---|---|---|
| `weight` | Float | Net weight at this point in time |
| `recorded_at` | Datetime | When the weight was set |
| `recorded_by` | Link → User | Who set it |
| `event` | Select | `Initial` / `Reweigh` / `Adjustment` |
| `reason` | Small Text | Required for non-Initial events |
| `scale` | Link → Scale | Scale used for this entry |
| `entry_method` | Select | `Scale (Auto)` / `Manual Entry` |

On container insert: append `Initial` row.
On reweigh: append `Reweigh` row, update parent `net_weight`, set `is_reweighed=1`.

---

### 4.3 MODIFIED DocType: `Dropoff`

**New fields:**

| Field | Type | Description |
|---|---|---|
| `weighing_session` | Link → POS Session | Lock: which session is currently weighing containers. Cleared on Pause. |
| `weighing_scale` | Link → Scale | Lock: which container scale this dropoff is bound to. Survives Pause. |
| `paused_at` | Datetime | Most recent pause |
| `paused_by` | Link → User | |
| `pause_reason` | Small Text | |
| `resumed_at` | Datetime | Most recent resume |
| `resumed_by` | Link → User | |
| `weighing_reassigned_at` | Datetime | Audit: last session reassignment |
| `weighing_reassigned_by` | Link → User | |
| `weighing_reassign_reason` | Small Text | |
| `weighing_scale_changed_at` | Datetime | Audit: last scale switch |
| `weighing_scale_changed_by` | Link → User | |
| `weighing_scale_change_reason` | Small Text | |
| `container_count` | Int | Computed — Active containers |
| `deviation_container_count` | Int | Computed |
| `has_unapproved_deviation` | Check | Computed |
| `verification_overridden` | Check | Set when manager manually marks a Needs-Review dropoff as Verified |
| `verification_override_at` | Datetime | Audit |
| `verification_override_by` | Link → User | Audit |
| `verification_override_reason` | Small Text | Audit — required when overriding |

**Status enum (extended):**

```
Draft → Scheduled → In Progress ⇄ Paused → Completed → Verified
                                                    ↘ Needs Review
                              ↘ Voided (manager only)
```

**Deprecated fields (kept for one release for migration / rollback):**
- `actual_items` (child table) — replaced by virtual aggregation from containers
- `item_summary.weigh_count` — renamed to `container_count`
- `is_reweighed` — moved to container level

**Aggregation rewrite:** see §6.

---

### 4.4 MODIFIED Child DocType: `Dropoff Item Summary`

| Field | Type | Description |
|---|---|---|
| `item` | Link → Item | Grade |
| `item_name` | Data | Canonical Thai |
| `total_weight` | Float | SUM of Active container `net_weight` for this grade |
| `container_count` | Int | COUNT of Active containers (renamed from `weigh_count`) |
| `deviation_count` | Int | NEW: how many of these are deviations |
| `is_expected` | Check | NEW: whether this grade was in `expected_items` |

---

### 4.5 DEPRECATED: `Scrap Weight`, `Scrap Weight Item`

Migration plan: see §10. Both doctypes are removed after the cutover. Their data is consolidated into `Scrap Weight Container` records; original Scrap Weight name preserved in `Scrap Weight Container.legacy_scrap_weight`.

---

### 4.6 NEW DocType (Single): `Dropoff Container Settings`

Centralises the deviation thresholds and gate flags so they don't live in code.

| Field | Type | Default | Description |
|---|---|---|---|
| `deviation_approval_threshold_kg` | Float | 100 | Single-container deviation > this kg triggers approval gate |
| `deviation_approval_threshold_pct` | Percent | 5 | Or > this % of dropoff expected total |
| `allow_unplanned_grades` | Check | 1 | If 0, block grades not in expected_items |
| `require_reason_on_deviation` | Check | 1 | Block save if reason missing |
| `auto_print_sticker_default` | Check | 1 | Default behaviour; per-Profile override below |
| `weight_variance_threshold_pct` | Percent | 0.1 | Used by truck/scrap variance check |

`POS Profile Scrap` gets an `auto_print_sticker` field (Check, default = settings value) for per-profile override.

---

## 5. API contract

All endpoints under `scrap_metal_suite.api.v1.dropoff` unless noted. All return JSON with `success`, `message`, and endpoint-specific fields.

### 5.1 Container CRUD

```python
# Add a container (the main weighing action)
add_container(
    dropoff: str,
    session: str,
    item_code: str,
    net_weight: float,
    container_type: str,           # Bag/Bin/Pallet/Other
    entry_method: str = "Manual Entry",
    deviation_reason: str = None,  # required if grade not in expected
    deviation_type: str = None,
    remarks: str = None
) -> dict
# Returns: {container, container_no, item_code, net_weight, is_deviation,
#          dropoff_total, dropoff_status, print_url}
```

```python
# Reweigh — updates in place
reweigh_container(
    container: str,
    net_weight: float,
    reason: str,                   # required
    entry_method: str = "Manual Entry"
) -> dict
# Returns: {container, net_weight, is_reweighed, dropoff_total, print_url}
```

```python
# Void a single container
void_container(
    container: str,
    reason: str
) -> dict
```

```python
# Lookup by ID (QR scan)
get_container(name: str) -> dict
```

```python
# List containers for a dropoff
list_containers(
    dropoff: str,
    include_voided: bool = False
) -> list[dict]
```

### 5.2 Dropoff lifecycle

```python
pause_dropoff(dropoff: str, reason: str = None) -> dict
# Sets status=Paused, weighing_session=NULL, paused_at/by/reason
# Containers untouched. weighing_scale survives.
```

```python
resume_dropoff(dropoff: str, session: str) -> dict
# Validates: session.scale == dropoff.weighing_scale
# Sets status=In Progress, weighing_session=session, resumed_at/by
# If scale differs, returns error suggesting switch_scale first
```

```python
reassign_dropoff(dropoff: str, new_session: str, reason: str) -> dict
# Manager override (no role guard yet — audit-only)
# Validates: new_session.scale == dropoff.weighing_scale (otherwise switch_scale first)
# Sets weighing_session=new_session, audit fields
```

```python
switch_scale(dropoff: str, new_scale: str, reason: str) -> dict
# Manager override (no role guard yet — audit-only)
# Validates: dropoff has 0 active containers OR audit-confirmed
# Sets weighing_scale=new_scale, audit fields
# Existing containers KEEP their original scale stamp
```

```python
void_dropoff_weighing(dropoff: str, reason: str) -> dict
# Marks all Active containers Voided
# Resets weighing_session=NULL, weighing_scale=NULL
# Sets dropoff status back to Scheduled (allows fresh re-weighing)
```

```python
complete_dropoff(dropoff: str) -> dict
# Validates: gross+tare+net_weight set, all containers Active or Voided,
#            no unapproved deviations, truck/scrap variance within threshold
# Sets status=Completed
# Triggers verification status calc
```

```python
# Approve a single container's deviation (clears the unapproved flag)
approve_container_deviation(
    container: str,
    reason: str = None
) -> dict
# Sets deviation_approved_by = current user, deviation_approved_at = now
# Recomputes parent dropoff.has_unapproved_deviation
# No role guard yet — anyone with write on Scrap Weight Container can approve
```

```python
# Manual override: mark a Needs-Review dropoff as Verified
verify_dropoff(
    dropoff: str,
    override_reason: str = None  # required if verification_status was Needs Review
) -> dict
# If verification_status=Verified already → idempotent
# If verification_status=Needs Review and override_reason provided →
#   sets verification_status=Verified, verification_overridden=1,
#   verification_override_by/at/reason fields populated, audit comment added
# If verification_status=Needs Review and no override_reason → throws
# No role guard yet — anyone with write on Dropoff can verify/override
```

### 5.3 Validation rules (enforced in `add_container` and on save)

```python
# Lock check
if dropoff.weighing_session and dropoff.weighing_session != session:
    throw("Dropoff locked to session {0}. Pause and resume to switch.")
if dropoff.weighing_scale and dropoff.weighing_scale != current_session.scale:
    throw("Dropoff requires scale {0}; current session uses {1}.")

# Status check
if dropoff.status not in ("In Progress", "Scheduled"):
    throw("Cannot add container; dropoff is {status}")

# Item validation
if not allow_unplanned_grades and item_code not in expected_codes:
    throw("Grade {0} not expected. Manager must update expected items first.")

# Weight bounds
if net_weight <= 0:
    throw("Weight must be > 0")
if scale.max_capacity_kg and net_weight > scale.max_capacity_kg:
    throw("Weight {0} exceeds scale capacity {1}")

# Deviation guard
if is_deviation and require_reason_on_deviation and not deviation_reason:
    throw("Reason required for grade deviation")
if is_deviation and exceeds_threshold and not approval:
    container.is_pending_approval = 1   # block dropoff Complete until resolved

# First-container binds the lock
if not dropoff.weighing_session:
    dropoff.weighing_session = session
    dropoff.weighing_scale = current_session.scale
    dropoff.status = "In Progress"
```

---

## 6. Aggregation rewrite

`Dropoff.sync_actual_items` becomes:

```python
def sync_actual_items(self):
    """Aggregate from active Scrap Weight Container records."""
    if not self.name:
        return

    self.item_summary = []

    containers = frappe.db.get_all(
        "Scrap Weight Container",
        filters={"dropoff": self.name, "status": "Active"},
        fields=["name", "item_code", "item_name", "net_weight",
                "is_deviation", "container_no"]
    )

    expected_codes = {row.item for row in self.expected_items}

    summary = {}
    total = 0
    deviation_total = 0
    deviation_count = 0
    has_unapproved = False

    for ct in containers:
        total += flt(ct.net_weight)
        if ct.item_code not in summary:
            summary[ct.item_code] = {
                "item_name": ct.item_name,
                "weight": 0,
                "count": 0,
                "deviation_count": 0,
                "is_expected": ct.item_code in expected_codes,
            }
        summary[ct.item_code]["weight"] += flt(ct.net_weight)
        summary[ct.item_code]["count"] += 1
        if ct.is_deviation:
            summary[ct.item_code]["deviation_count"] += 1
            deviation_total += flt(ct.net_weight)
            deviation_count += 1

    # Pending-approval check (separate query)
    has_unapproved = frappe.db.exists(
        "Scrap Weight Container",
        {"dropoff": self.name, "status": "Active",
         "is_deviation": 1, "deviation_approved_by": ["is", "not set"]}
    )

    for code, data in summary.items():
        self.append("item_summary", {
            "item": code,
            "item_name": data["item_name"],
            "total_weight": data["weight"],
            "container_count": data["count"],
            "deviation_count": data["deviation_count"],
            "is_expected": data["is_expected"],
        })

    self.total_actual_weight = total
    self.container_count = len(containers)
    self.deviation_container_count = deviation_count
    self.has_unapproved_deviation = bool(has_unapproved)
```

The `actual_items` flat child table is removed entirely — `item_summary` (per-grade) is sufficient for variance reporting; per-container detail is queried directly from `Scrap Weight Container`.

---

## 7. Workflows (concrete)

### 7.1 Normal weighing
1. Operator opens POS Session on truck terminal (existing flow).
2. Picks dropoff `DO-...` from queue → status `Scheduled`.
3. Picks grade from dropdown (filtered to allowed Item Group).
4. Places bag on scale; system reads stable weight (or operator types).
5. Confirms → `add_container` API called.
6. First call: dropoff lock-fields populated, status → `In Progress`.
7. Container saved; sticker auto-prints.
8. Repeat for each bag.
9. After last bag → operator clicks "Complete" → variance checks → status `Completed`.

### 7.2 Reweigh single container
1. Operator scans QR (or picks from list).
2. UI shows existing container details + "Reweigh" button.
3. Operator weighs again → enters reason → confirms.
4. `reweigh_container` API → `net_weight` updated, weight_history row appended, sticker reprinted (operator replaces old sticker on the bag).

### 7.3 Reweigh entire dropoff (rare)
1. Manager clicks "Void weighing" on dropoff.
2. Confirms with reason.
3. `void_dropoff_weighing` → all Active containers → `Voided`. Locks reset.
4. Status → `Scheduled`. Operator re-weighs from scratch.

### 7.4 Pause / Resume (shift change)
1. Operator A clicks "Pause" mid-dropoff. Status → `Paused`. Lock cleared.
2. Operator A closes POS Session.
3. Operator B opens new POS Session on **same scale**.
4. B picks paused dropoff → "Resume" → lock re-binds to B's session. Status → `In Progress`.
5. B continues adding containers.

If B is on a different scale: resume blocked. Manager runs `switch_scale` first (audit-logged).

### 7.5 Switch scale (scale broke)
1. Manager (or anyone — no guard yet) on dropoff: clicks "Switch scale" → picks new scale → reason.
2. `switch_scale` API → `weighing_scale` updated, audit fields written.
3. Existing containers keep their original `scale` stamp; new ones use the new scale.

### 7.6 Deviation flow
1. Operator picks grade B (not in expected_items).
2. Frontend detects (compares to dropoff.expected_items list returned in dropoff fetch).
3. Modal: "This grade isn't expected — Reason? Type? (Downgrade/Substitution/Unplanned)"
4. Operator fills, confirms.
5. `add_container` with `deviation_reason`, `deviation_type` → container saved with `is_deviation=1`.
6. If exceeds approval threshold → `is_pending_approval=1`; manager must approve before dropoff can `Complete`.
7. Sticker prints with ⚠ icon.

---

## 8. Print formats

**One per-container print format** + the existing per-Dropoff thermal receipt:

| Format | Printer | Paper | Trigger |
|---|---|---|---|
| `Scrap Weight Container Sticker` | Label / sticker printer | Sticker stock (size TBD per hardware) | Per-container; auto on save + manual reprint |
| `ใบคิวสองภาษา` (existing — Dropoff) | Thermal receipt printer (80mm) | 80mm × auto | Per-Dropoff; manual on completion |

The sticker is physically applied to each bag/bin/pallet. The customer-facing thermal receipt is rendered from the parent Dropoff (one per dropoff, not per container) — same as before the redesign.

> **Decision (2026-05-01)**: removed the per-container `Scrap Weight Container Thermal` format originally specified in §8.1. It was redundant with the per-Dropoff `ใบคิวสองภาษา` summary, and no operator workflow needed a paper receipt per bag. Schema (`POS Profile Scrap.enable_thermal_print` / `thermal_printer_name`), API (`_build_container_print_urls` thermal branch), terminal UI (Print Thermal buttons, action chooser entry, hidden auto-print iframe), translations (`action_print_thermal*`), tests, and the live `Scrap Weight Container Thermal` Print Format have all been ripped out. See §14.15.

`POS Profile Scrap` has:
- `enable_sticker_print` (Check, default 1)
- `sticker_printer_name` (Data, optional — for OS-level printer routing)

### 8.1 NEW: `Scrap Weight Container Sticker`
- Size: matches the chosen sticker printer (50×80mm portrait by default).
- Bilingual labels (UI text Thai+English); item name shown ONCE in canonical Thai (never translated — see [BILINGUAL_GUIDE.md §2](BILINGUAL_GUIDE.md)).
- QR encodes container `name` only (scan resolves to current doc — never stale).
- Adhesive — applied directly to the bag/bin/pallet.
- Required minimum content (per Wave 7 spec): Drop-off ID, Supplier, Plate, Operator, Date (= `last_reweigh_at` if reweighed, else `creation`), Bag #. Plus QR, container ID, item name, net weight.
- Layout (text mock, 50×80mm portrait):

```
┌──────────────────┐
│  CTN-2026-00007  │
│  [QR · 22mm sq]  │
│                  │
│  ทองแดงปอก       │
│                  │
│  746.4 kg        │
├──────────────────┤
│ Drop-off  DO-... │
│ ผู้ขาย    ...    │
│ ทะเบียน   ...    │
│ ผู้ชั่ง    ...    │
│ วันที่    yyyy-... ↻ │  ← ↻ if reweighed
│ Bag       7 ⚠    │
└──────────────────┘
```

### 8.2 MODIFIED: `ใบคิวสองภาษา` (Dropoff summary)
- Replace the duplicated `actual_items` rows with a per-grade summary table:

| เกรด · Grade | จำนวน · Bags | น้ำหนัก · Weight (kg) | สถานะ · Status |
|---|---|---|---|
| ทองแดงปอก | 2 | 1,098.6 | OK |
| ทองแดงเล็ก | 1 | 433.6 | OK |
| ทองแดงสะอาด | 1 | 23.8 | ⚠ Downgrade |

- Add a containers detail page (optional second page) listing each container row.

### 8.3 Auto-print trigger
- Frontend on `add_container` / `reweigh_container` success: fire the sticker print via a hidden iframe (routed to the OS-level sticker printer if `sticker_printer_name` is set on the POS Profile).
- Per-`POS Profile Scrap` toggle: `enable_sticker_print`.
- Manual reprint affordances (sticker only):
  - Container list row → "Print Sticker"
  - Scanner: scan QR → reprint sticker
  - Bulk: dropoff page → "Print all (stickers)"

---

## 9. UI changes

### 9.1 Truck terminal (`/pos/truck.html`)

**New "Containers" panel** replaces / augments the current scrap-weight panel:

```
┌───────────────────── Dropoff Detail ─────────────────────┐
│ DO-260320-00002 • In Progress • Scale: ตราชั่งใหญ่         │
│ ทรัพย์หิรัณย์ • Total: 1,556.0 kg • 7 containers           │
│                                                          │
│ [+ Add Container]  [Pause]  [Complete]                   │
├──────────────────────────────────────────────────────────┤
│  CTN-007  ทองแดงปอก   746.4 kg   [Reweigh] [Print] [⋯]  │
│  CTN-006  ทองแดงปอก   352.2 kg   [Reweigh] [Print] [⋯]  │
│  CTN-005  ทองแดงเล็ก   433.6 kg   [Reweigh] [Print] [⋯]  │
│  ...                                                     │
└──────────────────────────────────────────────────────────┘
```

**Add Container modal:**
1. Grade dropdown (filtered to dropoff's allowed Item Group; flagged ⚠ if not in expected).
2. Container type dropdown (Bag/Bin/Pallet/Other).
3. Weight input — live read from scale (or manual).
4. Optional tare/gross fields.
5. If deviation → reason + type fields appear.
6. "Save & Print" / "Save".

**Scanner integration:**
- Existing `html5-qrcode` scans container QR.
- On scan → load container detail panel → action buttons.

### 9.2 Dropoff doctype form (desk)
- New "Containers" section: list view child link to Scrap Weight Container.
- Read-only `item_summary` (computed from containers).
- "Print all stickers" button.
- Status badge with paused/resume info.
- Audit timeline showing reassignments / scale switches / pause-resume cycles.

### 9.3 Production Sorting downstream
- Production Sorting consumes containers naturally: scan QR → load container → use as source for sorted output.
- Update `Production Sorting Source Item` to link `scrap_weight_container` instead of `scrap_weight`.

---

## 10. Migration plan

### 10.1 Strategy
**Big-bang cutover** with fallback. Production data is bounded (low thousands of dropoffs at most). Run the migration in a staging copy first.

### 10.2 Algorithm

```python
def migrate_dropoff_to_containers(dropoff_name):
    """
    For each Dropoff:
      1. Find all Scrap Weight docs linked to it
      2. Identify the LATEST (by creation) — its items are the truth
         (because the bug pattern was: each new SW = full snapshot)
      3. For each Scrap Weight Item row in the latest SW:
           - Create a Scrap Weight Container
           - Stamp legacy_scrap_weight = latest_sw.name
           - Stamp session = latest_sw.session, scale = latest_sw.scale
           - container_no = row index
           - Append Initial weight history row
      4. Mark older Scrap Weights as 'migration-obsolete'
         (or move to backup table for rollback)
      5. Recompute Dropoff aggregations
      6. Verify: total_actual_weight ≈ truck net_weight (within
         truck_variance_threshold_percent)
    """
```

### 10.3 Verification
- For each migrated dropoff: assert `|total_actual − truck_net| / truck_net < threshold`.
- Spot-check 20 dropoffs manually: compare migrated containers to source data.
- Compare aggregate kg before/after for each supplier (no surprise drops).

### 10.4 Rollback
- Keep deprecated `Scrap Weight` / `Scrap Weight Item` tables for one full release.
- Feature flag: `use_container_model` (default off until cutover, then on).
- Rollback = flag off; aggregator falls back to legacy logic.

### 10.5 Migration script location
- `scrap_metal_suite/patches/v2_0/migrate_to_containers.py`
- Hooked via `patches.txt`.

### 10.6 Pre-migration cleanup (manual)
For known-bad dropoffs like DO-260320-00002:
- Run a dedup pass: if all SW docs for a dropoff have identical items at identical weights → keep only the latest.
- Log a report of all dropoffs with N>1 SW docs for review.

---

## 11. Test plan

### 11.1 Unit tests (Python)
- `add_container` happy path
- `add_container` first-call binds lock
- `add_container` blocked when locked to different session
- `add_container` blocked when locked to different scale
- `add_container` blocked when status not In Progress / Scheduled
- `reweigh_container` updates weight + appends history
- `void_container` updates status + dropoff aggregation
- `pause_dropoff` clears session, keeps scale
- `resume_dropoff` re-binds session, validates same scale
- `resume_dropoff` blocks if scale differs
- `switch_scale` updates lock + audit
- `reassign_dropoff` updates session + audit
- `complete_dropoff` blocks when has_unapproved_deviation
- Deviation detection: grade in expected → no flag
- Deviation detection: grade not in expected → flag + require reason
- Deviation threshold: above kg → require approval
- Aggregation: containers Active only, voided excluded
- Aggregation: per-grade sum + count
- Migration: 6× duplicated SW → 1 set of 10 containers
- Migration: dropoffs with single SW → 1:1 container mapping

### 11.2 Integration tests
- Full operator session: open → 3 dropoffs → 30 containers → close
- Pause/Resume across sessions, same scale
- Switch scale mid-dropoff, audit visible
- Reweigh chain: weigh → reweigh → reweigh → history shows 3 entries

### 11.3 UI / manual tests
- Truck terminal: add container → sticker prints
- Scan QR → container detail loads → reweigh
- Bulk print stickers
- Bilingual: switch user lang Thai/English, all labels render correctly
- Item names always show in Thai (canonical) regardless of user language

### 11.4 Migration test (staging)
- Restore production snapshot to staging
- Run migration
- Verify aggregates match
- Run integration tests on migrated data
- Run UI smoke tests

---

## 12. Rollout

| Phase | Scope | Gate |
|---|---|---|
| 1 — Schema | Doctypes, settings, child tables | Migrate on local `metal` site clean |
| 2 — Controller + API | Add/reweigh/void/pause/resume/switch/reassign/complete | Unit tests pass |
| 3 — Aggregation | Rewrite `sync_actual_items`, deprecate `actual_items` table | Aggregations match expected on test data |
| 4 — Print | Container thermal format + auto-print + dropoff summary update | Manual print test |
| 5 — UI | Truck terminal containers panel + scan-to-reweigh + bulk print | Manual end-to-end |
| 6 — Translations | Desk th.csv + pos-translations.js extend | Bilingual QA pass |
| 7 — Migration script | Patch + dry-run on staging | Verification report passes |
| 8 — Production cutover | Deploy + flag on + monitor | Variance reports clean for 7 days |
| 9 — Cleanup | Drop deprecated `Scrap Weight` / `Scrap Weight Item` | After 1 release window |

---

## 13. Risks & open questions

| Risk | Mitigation |
|---|---|
| Migration drops legitimate data on a real-world dropoff that had multiple legitimate SW reweighs (not duplication bug) | Pre-migration report flags such dropoffs for human review |
| Auto-print fires before sticker printer is set up at a site | Per-Profile toggle disables auto-print |
| Deviation thresholds set too low → noisy approvals | Settings tuned per site; defaults conservative (100 kg / 5 %) |
| Scanner misreads QR | Manual ID entry fallback in scanner UI |
| Operator confusion over "Pause vs Complete" | Truck terminal disables Complete until variance passes; clear button states |
| Production Sorting consumes the legacy SW model | Update Production Sorting in same release; migrate `Production Sorting Source Item.scrap_weight` → `scrap_weight_container` |

**Open questions — all resolved 2026-04-25:**

1. ~~**Container `tare_weight` workflow**~~ — RESOLVED: net weight only at receiving (operator tares empty bag on scale, weighs filled bag, records net). Tare/gross precision deferred to Production Sorting module's reweigh phase.
2. ~~**Sticker printer hardware**~~ — RESOLVED: TWO print formats, TWO printers. Thermal receipt printer (80mm) AND a separate sticker/label printer. Both fire on container save, configurable per POS Profile Scrap. See §8.
3. ~~**Approval workflow for unapproved deviations**~~ — RESOLVED: manual override added (§5.2 `approve_container_deviation` and `verify_dropoff` endpoints). No role guard yet — anyone with write privilege can approve / mark Verified. Audit fields capture who/when/why. Role guard added later (Phase 11 follow-ups).
4. ~~**Production Sorting compatibility**~~ — DEFERRED: belongs to the Production Sorting maintainer. Once this redesign stabilises, write a comprehensive integration doc covering: how Production Sorting consumes containers, how `Production Sorting Source Item.scrap_weight` becomes `scrap_weight_container`, how QR scanning bridges Dropoff → Sorting, where tare/gross precision (re)appears on the sorting side. See Phase 11 follow-ups.
5. ~~**Backfill `weighing_scale` for legacy dropoffs**~~ — RESOLVED: not needed. Lock activates only on first NEW container after migration; legacy completed dropoffs leave the lock fields NULL and stay read-only.
6. ~~**Multi-language for supplier names**~~ — RESOLVED: same rule as item names. `Supplier.supplier_name` is canonical and never translated. Render verbatim in UI, print, and error messages.

---

## 14. To-do (implementation checklist)

**Implementation status as of 2026-04-27:** Waves 1–5 + Phase 12 (tests) committed at `8cca2f3`. Wave 6 (UI relocation, redesign, translations, multi-doc tests) work-in-progress on `feature/container-redesign`, uncommitted. See §14.13 for the running summary.

### Phase 1 — Schema ✅ DONE (Wave 1)
- [x] Create DocType `Scrap Weight Container` (JSON + controller + tests) — 35 fields, naming `CTN-.YYYY.-.#####`
- [x] Create child DocType `Container Weight History` — 7 fields, `istable: 1`
- [x] Create Single DocType `Dropoff Container Settings` — 6 settings + 4 layout fields
- [x] Add new fields to `Dropoff` (lock fields + audit fields + computed) — 20 new fields + 5 section breaks
- [x] Add `enable_thermal_print`, `enable_sticker_print`, `thermal_printer_name`, `sticker_printer_name` to `POS Profile Scrap`
- [x] Update `Dropoff Item Summary` (rename `weigh_count` → `container_count`, add `deviation_count`, `is_expected`)
- [x] Add `Paused` status to Dropoff status enum
- [ ] **PENDING** Run `bench migrate` on local `metal` site (not run yet — for next session)

### Phase 2 — Controllers ✅ DONE (Wave 2)
- [x] `Scrap Weight Container` controller — 11 methods (before_insert, before_save, after_insert, record_reweigh, record_void, approve_deviation, plus 5 private helpers)
- [x] `Dropoff` controller — 9 new methods (lock helpers, pause/resume, reassign, switch_scale, void_weighing, mark_verified)
- [x] `Dropoff.sync_actual_items` rewritten to aggregate from `Scrap Weight Container` (Active only)
- [x] `Dropoff.calculate_totals` updated minimally (sources from new aggregation)

### Phase 3 — API ✅ DONE (Wave 3)
- [x] API: `add_container` (lock acquisition + first-container status transition)
- [x] API: `reweigh_container`
- [x] API: `void_container`
- [x] API: `get_container`
- [x] API: `list_containers`
- [x] API: `pause_dropoff`
- [x] API: `resume_dropoff`
- [x] API: `reassign_dropoff` (audit-only, no role guard)
- [x] API: `switch_scale` (audit-only, no role guard)
- [x] API: `void_dropoff_weighing`
- [x] API: `complete_dropoff` (replaces legacy; with deviation/variance gates)
- [x] API: `approve_container_deviation` (manual override, audit-only)
- [x] API: `verify_dropoff` (manual override for Needs Review, audit-only)
- [x] Legacy `record_scrap_weight` and `load_scrap_weight` preserved for backward compat

### Phase 4 — Print ✅ DONE (Wave 4 + Wave 7 simplification)
- [x] ~~Print format `Scrap Weight Container Thermal`~~ — **REMOVED Wave 7 (2026-05-01)**: redundant with the per-Dropoff `ใบคิวสองภาษา`. See §14.15.
- [x] Print format `Scrap Weight Container Sticker` (50×80mm, bilingual, QR via `qr_data_uri`, all 6 required fields per Wave 7)
- [x] Update `ใบคิวสองภาษา` — replaced per-row actual_items with per-grade item_summary table + deviations callout + verification override callout
- [x] Frontend auto-print: hidden iframe firing the sticker on `add_container` / `reweigh_container` success
- [x] Per-row + bulk sticker reprint buttons
- [x] Per-Profile sticker auto-print toggle wired through

### Phase 5 — UI (POS terminal) ✅ DONE (Wave 5 + Wave 6 corrections)
- [x] ~~New Containers panel in `/pos/truck.html`~~ — **CORRECTED**: panel moved to `/pos/terminal.html` (Scrap-usage scale terminal). Truck terminal is for whole-truck gross/tare/net only.
- [x] Container UI relocated `truck.html` → `terminal.html` (2026-04-27): truck.html lost ~858 lines, terminal.html gained ~861 lines. Terminal.py provides `use_container_model` and `enable_sticker_print` context (the `enable_thermal_print` flag was removed in Wave 7). Truck.py reverted to pre-redesign.
- [x] **Inline weighing card** replaces the modal (2026-04-27): redesigned right panel as single unified flow. Operator clicks grade in left panel `รายการสินค้า` → grade becomes Active Grade → live weight display + manual override + Container Type → Save & Print. Cart UI gated off when `use_container_model=on`.
- [x] CONTAINER_UI module gained `setActiveGrade()`, `clearActiveGrade()`, `saveActiveContainer()`, `tare()`, `onLiveWeight()`, `onWeightInput()`, `isEnabled()`. Legacy modal functions kept as no-op shims for back-compat.
- [x] CSS for container UI (~280 lines appended to `pos.css`): `.container-weigh-card`, `.weigh-grade-row/-empty/-pill`, `.weigh-scale-row/-live-display`, `.weigh-input-row`, `.weigh-action-row`, `.container-row` with full sub-class layout, voided rows folded with strikethrough, light-theme overrides.
- [x] Translation fixes (2026-04-27): `select_grade_from_items`, `manualEntry`, `scaleAuto`, `tare`, `save_and_print`, `live_weight` added to `container-translations.js` (en + th). Was rendering raw key names due to missing entries.
- [x] Container row actions (Reweigh, Print Sticker, Void) — wired (Print Thermal removed Wave 7)
- [x] Pause / Resume / Complete buttons + status display
- [x] Scanner: QR → load container → action menu (existing flow preserved)
- [x] Feature flag `use_container_model` (default on) — legacy cart-based scrap-weight panel preserved when off (rollback path, unexercised by tests)
- [ ] **FOLLOW-UP** Live scale binding tested only in static manual-entry mode — wire `scale_reader.js` continuous read into `CONTAINER_UI.onLiveWeight()` and verify (the hook exists, just needs hardware)
- [ ] **FOLLOW-UP** Switch Scale / Reassign Session / Void Dropoff Weighing / Verify Dropoff buttons in terminal UI (currently desk-only)
- [ ] **FOLLOW-UP** QR scan action chooser uses `window.prompt` — replace with proper popover
- [ ] **FOLLOW-UP** Add real `use_container_model` field to `POS Profile Scrap` doctype (currently read via `getattr`)
- [x] ~~**FOLLOW-UP** Replace `qr_src` Jinja filter with `qr_foundry` module~~ — DONE (2026-05-01): both Container Thermal and Sticker now use `<img src="{{ qr_data_uri(doc.doctype, doc.name) }}">` (qr_foundry's documented inline-data-URI pattern from `test_print_format.html`). The previous `{{ qr_src(...) }}` was bare inside a `<div>` so the URL rendered as plain text — no QR ever printed. Verified by rendering both formats against `CTN-2026-00023`: both return `<img>` + base64 PNG data URI.

### Phase 6 — UI (desk) ✅ DONE (Wave 5)
- [x] Dropoff form: custom buttons in `Container Actions` group (Pause, Resume, Switch Scale, Reassign Session)
- [x] "Mark Verified (Override)" button on Dropoff (visible when `verification_status = Needs Review`)
- [x] Container form: Reweigh / Void / Print Sticker / Approve Deviation buttons (Print Thermal removed Wave 7)
- [x] Bulk print button on Dropoff (`Print all (stickers)`) — Print all (thermal) removed Wave 7
- [ ] **FOLLOW-UP** Audit timeline visualization (pauses, resumes, reassigns, scale switches, verification overrides) — fields exist, but no dedicated timeline widget yet
- [ ] **FOLLOW-UP** Dropoff form: read-only containers list section (separate from buttons)

### Phase 7 — Translations ✅ DONE (Wave 4)
- [x] Added 47 new rows to `translations/th.csv` (controller errors, API messages, print labels, deviation types — 1 duplicate "Total" skipped)
- [x] Created `scrap_metal_suite/public/js/container-translations.js` — 76 keys per language × 2 (152 entries) using `POS_I18N.extend()` pattern
- [x] Wired `container-translations.js` in `hooks.py` `web_include_js` (after `pos-translations.js`)
- [x] Bilingual labels added to both container sticker templates and dropoff summary print
- [ ] **PENDING** Add `__()` strings from desk form scripts (Wave 5 desk-button labels) to th.csv — ~30 strings collected by agent, awaiting append
- [ ] **PENDING** QA pass: switch user lang Thai/English, verify all UI labels render correctly (manual test, next session)
- [ ] **PENDING** QA pass: confirm item names always render in canonical Thai under both languages

### Phase 8 — Migration ✅ PATCH WRITTEN (Wave 5)
- [x] Patch `patches/v2_0/migrate_to_containers.py` written — idempotent, picks LATEST Scrap Weight per dropoff, dedups duplicates, preserves `legacy_scrap_weight` audit trail
- [x] Pre-flight report: counts dropoffs with N>1 Scrap Weight (logged via `frappe.log_error`)
- [x] Variance check post-migration (>1% logged as warning, doesn't crash patch)
- [x] Patch registered in `patches.txt` under `[post_model_sync]`
- [ ] **PENDING** Dry-run on staging (production snapshot) — needs production data
- [ ] **PENDING** Verification: post-migration aggregate kg matches pre-migration truck net per supplier
- [ ] **PENDING** Spot-check 20+ dropoffs manually

### Phase 9 — Production cutover (NOT STARTED — gated by Phase 8 verification)
- [ ] Backup production DB
- [ ] Deploy code (feature flag off initially)
- [ ] Run migration patch
- [ ] Run verification report
- [ ] Enable feature flag (cutover)
- [ ] Monitor: variance reports clean for 7 days
- [ ] Operator training (10 min walkthrough)

### Phase 10 — Cleanup (NOT STARTED — post-cutover)
- [ ] Remove deprecated `Scrap Weight` and `Scrap Weight Item` (or rename `_legacy`)
- [ ] Remove `Dropoff.actual_items` field
- [ ] Update `Production Sorting Source Item` references (`scrap_weight` → `scrap_weight_container`)
- [ ] Tag release `v2.0.0`

### Phase 11 — Follow-ups (post-v2)
- [ ] Add role guard to `reassign_dropoff`, `switch_scale`, `approve_container_deviation`, `verify_dropoff` (Manager only)
- [ ] Grade hierarchy (Item.grade_rank) for auto-detection of Downgrade vs Substitution
- [ ] Per-supplier deviation analytics dashboard
- [ ] Cumulative deviation alerts (e.g. supplier exceeds N% deviation rate over 30 days)
- [ ] Live scale binding in Add Container modal
- [ ] QR scan popover (replace `window.prompt`)
- [ ] Real `use_container_model` field on POS Profile Scrap (currently `getattr` default)
- [ ] Truck terminal admin actions (Switch Scale / Reassign / Void Weighing / Verify) — currently desk-only
- [ ] Audit timeline widget on Dropoff form
- [ ] **Production Sorting integration doc** — once this redesign is finalised and merged, write a comprehensive integration spec for the Production Sorting maintainer covering:
    - How Production Sorting consumes containers (scan QR → load → start sorting)
    - Mapping `Production Sorting Source Item.scrap_weight` → `scrap_weight_container`
    - Where tare/gross precision is captured during sorting (the reweigh phase that's deferred from receiving)
    - Status transitions across modules (Container → Sorting → Final Settlement)
    - Test fixtures for cross-module workflows

### Phase 12 — Tests ✅ DONE (Wave 5 + Wave 6 expansion)
- [x] `test_scrap_weight_container.py` — 14 unit tests covering all controller paths (all passing on `metal` after fixture fixes — POS Profile Scrap items child uses `item_code` not `item`; POS Session validate_open_session enforces one-per-operator; calculate_verification_status now respects `verification_overridden` flag)
- [x] `test_dropoff_container_settings.py` — 1 minimal defaults test
- [x] `api_test/test_container_workflow.py` — 11-step integration test (open session → add 5 containers → reweigh → pause → resume → 6th container → complete) — passing
- [x] `api_test/test_container_multi_doc_workflow.py` — **NEW (2026-04-27)**: Two scenarios, 14/14 assertions passing:
    - Scenario A: 1 Price Lock → 3 Dropoffs across days, multiple grades, multiple containers per grade. Assert each `add_container` returns thermal+sticker print URLs; FIFO allocation cumulatively reaches Fulfilled (100%).
    - Scenario B: 2 Price Locks → 1 Dropoff (mixed shipments). 10 containers (5×100kg grade A + 5×100kg grade D). Assert PL1 = 50% Partial, PL2 = 100% Fulfilled. Dropoff-level print URL constructable.
- [x] `ui_test/` — **NEW (2026-04-27)**: Playwright + pytest scaffold. 2 tests passing (~22s headed):
    - `test_pos_terminal.py::test_add_container_happy_path` — drives the new inline weighing flow at `/pos/terminal`
    - `test_desk_dropoff.py::test_mark_verified_override` — clicks the desk Dropoff form's Mark Verified button, asserts override audit fields
    - Fixtures use document API only (no direct `db.set_value`); each seed bound to a unique `_TEST_UI_` prefix.
    - Run: `cd ~/frappe-bench && SMT_UI_ADMIN_PWD="$SMT_UI_ADMIN_PWD" env/bin/pytest apps/scrap_metal_suite/scrap_metal_suite/ui_test/ -v`
    - Env vars: `SMT_UI_HEADLESS=1` (hide browser), `SMT_UI_SLOW_MO=0` (no throttle), `SMT_UI_BASE_URL`, `SMT_UI_SITE`, `SMT_UI_ADMIN_PWD`.
- [ ] **PENDING** Migration tests against real production data snapshot
- [ ] **PENDING** UI test for legacy cart fallback path (when `use_container_model=false`)
- [ ] **PENDING** UI test for Pause/Resume cycle
- [ ] **PENDING** UI test for Reweigh flow

---

### 14.13 — Wave 6 running summary (2026-04-27, uncommitted)

In one continuous push following the `8cca2f3` checkpoint, the following landed on `feature/container-redesign` (uncommitted as of writing):

1. **Bench migrate** — schema applied cleanly to `metal` site
2. **Unit tests** — fixed 3 fixture bugs, all 14 pass; one controller bug fixed (`calculate_verification_status` now respects `verification_overridden=1`)
3. **Multi-doc integration test** — wrote `test_container_multi_doc_workflow.py` from scratch covering both Scenario A and Scenario B (1↔N relationships between Price Lock / POS Order / Dropoff). 14/14 assertions pass.
4. **Container UI relocation** — moved CONTAINER_UI from `truck.html` (wrong) to `terminal.html` (correct — Scrap-usage scale terminal). truck.html reverted to truck weighing only. Both controllers updated.
5. **Inline weighing card redesign** — replaced the modal-based "+ Add Container" flow with an always-visible inline card. Operator picks a grade from the existing left-panel `รายการสินค้า`, the right panel shows Active Grade + Live Scale + Type + Save & Print. Cart UI gated off when `use_container_model` is on.
6. **CSS** — ~280 lines of styles for the new card and container row layout (was previously rendering as unstyled inline text).
7. **Translations** — 6 new keys added to `container-translations.js` (en + th) for inline card labels that were rendering raw key names.
8. **Playwright UI tests** — set up scaffolding (`ui_test/` directory: conftest.py, fixtures.py, 2 tests). Both pass in ~22s headed mode. Login via `/api/method/login` with `SMT_UI_ADMIN_PWD` env var (the admin password for this site is held outside the repo).
9. **Operational notes** — `redis_cache` had been killed in a prior session; restarted on port 13001. `bench start` requires both redis services running. Use `bench build --app scrap_metal_suite` after CSS/JS edits to bundle assets, then `bench --site metal clear-cache` and a hard browser refresh.

**Pending for next session:**
- Browser smoke test of the actual scale-driven flow (live serial reads)
- Commit Wave 6 as a follow-up commit (or two — one for the relocation, one for the redesign)
- More UI tests (Pause/Resume, Reweigh, legacy cart fallback)

### 14.14 — Wave 7 print format completion (2026-05-01)

Fixed the broken QR rendering and expanded the sticker to carry the minimum 6 fields a yard-floor sticker needs to be self-sufficient.

**Schema additions** to `Scrap Weight Container` (snapshot fields, all `read_only`, populated by `fetch_from`):
| field | source | rationale |
|-------|--------|-----------|
| `supplier` | `dropoff.supplier` | reportable / filterable without joining Dropoff |
| `supplier_name` | `dropoff.supplier_name` | sticker text + survives Dropoff field edits |
| `license_plate` | `dropoff.license_plate` | required on the sticker; cached at weighing time |
| `operator_name` | `operator.full_name` | friendlier display than `operator` (User email) |

**Backfill patch** `scrap_metal_suite.patches.v2_0.backfill_container_snapshot_fields` — populates the four new columns on existing rows from their related Dropoff/User. Idempotent: only touches rows where the target field is empty.

**Print format fixes** (in `fixtures/print_format.json`):
- **QR rendering** — both Container Thermal and Sticker were calling `{{ qr_src(...) }}` *bare* inside a `<div>`, so the URL string rendered as text and no QR ever printed. Switched to `<img src="{{ qr_data_uri(doc.doctype, doc.name) }}">` per qr_foundry's documented inline-data-URI pattern. Self-contained PNG, offline-safe for thermal printers.
- **Container Thermal**: replaced runtime `frappe.db.get_value` lookup with cached `doc.supplier_name`; added License Plate row; switched Operator row to display `operator_name` (with `operator` fallback).
- **Container Sticker**: replaced the one-line footer (`{{ doc.dropoff }} • Bag {{ doc.container_no }}`) with a 6-row meta block: Drop-off, Supplier, Plate, Operator, Date, Bag.

**Verification** ([api_test/test_container_print.py](../scrap_metal_suite/api_test/test_container_print.py)):
- Renders both formats for a real container (`CTN-2026-00023`)
- Asserts `<img>` + base64 data URI + no unrendered Jinja
- Asserts each of the 6 required fields appears in the rendered HTML
- Both formats: PASS

Existing tests still green: container workflow integration test (11/11) and multi-doc workflow test (14/14).

**Helper:** `api_test/update_container_pf.py` re-pushes the Container Sticker `html` from the fixture into the live site, bypassing `sync_fixtures` (blocked on this site by unrelated legacy formats with stale `standard=Yes`). Useful while iterating on the print format. Worth a separate small patch later to flip those legacy formats to `standard=No` so `sync_fixtures` works site-wide.

### 14.15 — Wave 7 thermal-removal + variance-threshold fix (2026-05-01)

**Decision: drop the per-container thermal print format.**
The `Scrap Weight Container Thermal` (80mm receipt) was redundant with the per-Dropoff `ใบคิวสองภาษา` summary. No operator workflow needed a paper receipt per bag — only the sticker (the physical adhesive label that stays on the bag/bin/pallet). Removing it simplifies the print UX (one format, one printer toggle, one auto-print iframe).

**What changed:**
- `fixtures/print_format.json` — `Scrap Weight Container Thermal` entry deleted.
- Live `metal` site — `Print Format` record deleted via `api_test/drop_container_thermal_pf.py` one-shot.
- `POS Profile Scrap` doctype — `enable_thermal_print` and `thermal_printer_name` fields removed; `column_break_printing` removed (only one column needed now).
- `api/v1/dropoff.py:_build_container_print_urls` — thermal branch dropped; returns only `{"sticker": ...}` when the profile flag is on.
- `www/pos/terminal.py` — `context.enable_thermal_print` removed.
- `www/pos/terminal.html` — Save & Print button text → "Save & Print Sticker"; row "Print Thermal" button removed; scanner action chooser drops the Print Thermal entry; `printOneImpl` simplified (sticker-only, no `kind` argument); `fireBothPrints` keeps the name but only fires the sticker (kept the function name to avoid a wider rename).
- `public/js/container-translations.js` — `action_print_thermal` and `action_print_all_thermal` keys dropped (en + th).
- `ui_test/fixtures.py` — `enable_thermal_print: 1` dropped from POS Profile fixture.
- `api_test/test_container_multi_doc_workflow.py` — header comment + `add_containers` helper updated to assert sticker-only; sample print log no longer prints the thermal URL.
- `api_test/test_container_print.py` — loop reduced to the single sticker format.
- `api_test/update_container_pf.py` — `TARGETS` reduced to `{"Scrap Weight Container Sticker"}`.

**Variance-threshold fix (incidental, same wave):**
The truck terminal was showing "✓ ค่าต่างอยู่ในเกณฑ์" (within threshold) for a 23% variance — the `Percent` field was being multiplied by 100 in JS, turning a saved 1% threshold into 100%. Server-side flags (`truck_variance_ok`, `indicated_variance_ok`) were already correct; only the UI was wrong. Fixed [truck.html:1338, 1380, 3237, 3259](../scrap_metal_suite/www/pos/truck.html#L1338) (drop `* 100`), corrected the JSON defaults from `0.001` → `0.1` ([dropoff.json:347, 383](../scrap_metal_suite/scrap_metal_suite/doctype/dropoff/dropoff.json#L347)), and the controller fallbacks ([dropoff.py:417, 440](../scrap_metal_suite/scrap_metal_suite/doctype/dropoff/dropoff.py#L417)). Backfill patch `patches.v2_0.fix_variance_threshold_defaults` updated 53 of 59 stale-default Dropoffs to 0.1%.

**Pending after Wave 7:**
- Print UI / UX (auto-print timing, dual-printer routing — now actually single-printer, much simpler)
- Naming series review (`CTN-.YYYY.-.#####` vs `CTN-{dropoff}-####` etc.)

### 14.16 — Wave 8 naming-series redesign (2026-05-01)

**Decision: embed `Supplier.short_code` in document IDs across the four operator-facing doctypes**, so paper, screen, and spoken IDs identify *who* and *when* at a glance instead of being opaque global counters.

**New patterns:**

| DocType | Pattern | Sample | Counter scope |
|---|---|---|---|
| `SMT Price Lock` | `PLO-{short}-YYMM-###` | `PLO-ACME-2604-001` | per-supplier × per-month |
| `POS Order` | mirrors PLO (no own counter) | `PDR-ACME-2604-001` (from PLO-ACME-2604-001) | derived 1:1 from `smt_price_lock` |
| `SMT Purchase Order` | `SPO-{short}-YYMM-###` | `SPO-ACME-2604-001` | per-supplier × per-month |
| `Dropoff` | `DO-{short}-YYMMDD-#` | `DO-ACME-260427-1` | per-supplier × per-day |

PDR mirroring (1:1) is the structural contract: a PLO names its derived POS Order by swapping the `PLO-` prefix for `PDR-`. If a PLO ever spawned two POS Orders, the second insert would collide on the unique `name` constraint — that's the safety net, not a workaround.

**`Supplier.short_code` Custom Field:**
- Data, 2-8 ASCII chars (`[A-Z0-9]`), `reqd: 1`, `unique: 1`
- In list view + standard filter for easy supplier scoping
- Auto-defaulted by `overrides/supplier.populate_short_code`: takes the first 4 ASCII alphanumerics of `supplier_name`, uppercased; appends `2`, `3`, ... on collision (e.g. `ACME` then `ACME2` then `ACME3`).
- For Thai-only supplier names (no usable ASCII chars) the auto-default refuses and the operator must type a code — they already have spoken nicknames for these suppliers (e.g. `TRP`, `LUNG`), and forcing them to type the office's own abbreviation produces docnames the office actually uses.
- Edit policy: editable forever, but only affects *new* documents. Existing submitted docs keep their original names. Description on the field surfaces this rule. Cascade-rename of historical docs is not implemented (would risk audit-trail integrity).

**Implementation:**
- Custom Field in `fixtures/custom_field.json`
- Auto-default + ASCII validation in `overrides/supplier.py` (wired via `doc_events.Supplier.before_insert` and `before_save` in `hooks.py`)
- Shared naming helpers in [overrides/naming.py](../scrap_metal_suite/overrides/naming.py): `supplier_short()`, `supplier_monthly_name()`, `supplier_daily_name()`, `derive_pdr_from_plo()`
- `autoname()` overrides on the four target controllers; the legacy `naming_series` field + `"autoname": "naming_series:"` directive removed from each JSON; `naming_rule` set to `"Expression (old style)"` (a Frappe-recognised value indicating controller-driven naming)

**Existing data**: per the design discussion, the user opted not to backfill old docnames. Old PLs (`PL-2026-*`), POs (`SMTPL-2026-*`), Dropoffs (`DO-YYMMDD-#####`, `DROP-*`) keep their original names. New docs created after this wave use the new patterns. No collision risk because the new prefixes (`PLO`, `PDR`, `SPO`) don't overlap with the old (`PL`, `SMTPL`, `DO`) — the old `DO-YYMMDD-#####` and new `DO-{short}-YYMMDD-#` share the `DO-` root but the second segment width differentiates them.

**Verification (against `metal`):**
- Container workflow integration test: `Created Dropoff DO-TEST-260501-1 ...` → 11/11 pass
- Multi-doc workflow test: `PL1 PLO-TEST-2605-002 -> POS Order PDR-TEST-2605-002` → 14/14 pass (PDR mirror confirmed)
- Sticker render smoke test: 6/6 required fields + valid QR

**Pending after Wave 8:**
- Print UI / UX (the ground is much smoother now — single sticker format, supplier-coded names)
- Optional: `Supplier.short_code` editor convenience (preview button "this would name your next PLO `PLO-XYZ-2605-001`") — only if operators ask

## 15. Appendix

### 15.1 Status state machine (Dropoff)

```
                  ┌──────────────────┐
                  │      Draft       │
                  └────────┬─────────┘
                           ▼
                  ┌──────────────────┐
            ┌────►│    Scheduled     │◄─── void_dropoff_weighing
            │     └────────┬─────────┘
            │              │ first add_container
            │              ▼
            │     ┌──────────────────┐
            │     │   In Progress    │◄────────┐
            │     └────────┬─────────┘         │ resume
            │              │                   │
            │       pause  │                   │
            │              ▼                   │
            │     ┌──────────────────┐         │
            │     │     Paused       │─────────┘
            │     └────────┬─────────┘
            │              │ complete_dropoff
            │              ▼
            │     ┌──────────────────┐
            │     │    Completed     │
            │     └────────┬─────────┘
            │              │ verification
            │              ▼
            │     ┌──────────────────┐    ┌──────────────────┐
            │     │     Verified     │    │   Needs Review   │
            │     └──────────────────┘    └────────┬─────────┘
            │                                      │
            └──────────────────────────────────────┘ (manager re-opens)
```

### 15.2 Status state machine (Container)

```
       ┌───────────┐ reweigh
       │  Active   │────────► (same doc, weight_history++, is_reweighed=1)
       └────┬──────┘
            │ void / void_dropoff_weighing
            ▼
       ┌───────────┐
       │  Voided   │
       └───────────┘
```

### 15.3 Sticker QR encoding
- QR content = container `name` only (e.g. `CTN-2026-00007`)
- Decoded in scanner → call `get_container(name)` API → load detail panel
- Never encode weight/grade — those mutate; container ID is stable.
