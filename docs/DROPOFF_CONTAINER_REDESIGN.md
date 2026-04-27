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

**Two distinct print formats targeting two distinct printers:**

| Format | Printer | Paper | Trigger |
|---|---|---|---|
| `Scrap Weight Container Thermal` | Thermal receipt printer (80mm) | 80mm × auto | Per-container; auto on save + manual reprint |
| `Scrap Weight Container Sticker` | Label / sticker printer | Sticker stock (size TBD per hardware) | Per-container; auto on save + manual reprint |

Both formats consume the same `Scrap Weight Container` document. Operators don't choose between them — both fire on save (or one, per `POS Profile Scrap` configuration). The thermal copy stays at the weighing station as a paper trail; the sticker is physically applied to the bag.

`POS Profile Scrap` gains:
- `enable_thermal_print` (Check, default 1)
- `enable_sticker_print` (Check, default 1)
- `thermal_printer_name` (Data, optional — for OS-level printer routing)
- `sticker_printer_name` (Data, optional)

### 8.1 NEW: `Scrap Weight Container Thermal`
- Size: 80mm × auto (matches existing thermal pattern).
- Bilingual labels (UI text Thai+English); item name shown ONCE in canonical Thai.
- QR encodes container `name` only (scan resolves to current doc — never stale).
- Layout (text mock):

```
┌─────────────────────────────┐
│ DO-260320-00002             │
│ ทรัพย์หิรัณย์ • Tharp Hirun  │
├─────────────────────────────┤
│  CTN-2026-00007             │
│  [QR · 28mm sq]             │
│                             │
│  ทองแดงปอก                   │  ← item_name, ONLY
│                             │
│  Net • สุทธิ                 │
│  746.4 kg                   │  ← 32px bold
│                             │
│  Bag 7/10 • Type: Bag       │
│  ⚠ Downgrade                │  ← only if is_deviation=1
│  Op: jaruwan • 10:14        │
└─────────────────────────────┘
```

Note: supplier name shows in canonical form too; if you need an English transliteration, use `supplier.supplier_name_en` or similar (same rule as item names — don't translate at runtime).

### 8.2 NEW: `Scrap Weight Container Sticker`
- Size: matches the chosen sticker printer (e.g. 50×80mm, 40×60mm — TBD when hardware is selected).
- Same bilingual labels + canonical Thai item name as the thermal version.
- More compact: container ID + QR + item_name + net_weight as the prominent elements; supplier and dropoff IDs in fine print.
- Adhesive — applied directly to the bag/bin/pallet.
- QR encoding: identical to thermal (container `name` only).
- Layout (text mock, e.g. 50×80mm portrait):

```
┌──────────────────┐
│  CTN-2026-00007  │
│  [QR · 25mm sq]  │
│                  │
│  ทองแดงปอก       │
│                  │
│  746.4 kg        │
│                  │
│  DO-260320-00002 │
│  Bag 7/10 ⚠      │
└──────────────────┘
```

### 8.3 MODIFIED: `ใบคิวสองภาษา` (Dropoff summary)
- Replace the duplicated `actual_items` rows with a per-grade summary table:

| เกรด · Grade | จำนวน · Bags | น้ำหนัก · Weight (kg) | สถานะ · Status |
|---|---|---|---|
| ทองแดงปอก | 2 | 1,098.6 | OK |
| ทองแดงเล็ก | 1 | 433.6 | OK |
| ทองแดงสะอาด | 1 | 23.8 | ⚠ Downgrade |

- Add a containers detail page (optional second page) listing each container row.

### 8.4 Auto-print trigger
- Frontend on `add_container` success: fire **both** print formats in parallel (one hidden iframe per format), each routed to its own printer via OS print dialog (or auto-routed if `*_printer_name` configured at the OS level).
- Per-`POS Profile Scrap` toggles disable either format independently (`enable_thermal_print`, `enable_sticker_print`).
- Manual print buttons always present, each split into Thermal / Sticker:
  - Container list row → "Print Thermal" + "Print Sticker"
  - Scanner: scan QR → both reprint buttons
  - Bulk: dropoff page → "Print all (thermal)" + "Print all (stickers)"

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

**Implementation status as of 2026-04-25:** Waves 1–5 complete. Code lives on branch `feature/container-redesign` (uncommitted as of session signoff). Resume by running `bench migrate` and tests, then committing.

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

### Phase 4 — Print ✅ DONE (Wave 4)
- [x] Print format `Scrap Weight Container Thermal` (80mm × auto, bilingual, QR via `qr_src`)
- [x] Print format `Scrap Weight Container Sticker` (50×80mm placeholder, bilingual, QR)
- [x] Update `ใบคิวสองภาษา` — replaced per-row actual_items with per-grade item_summary table + deviations callout + verification override callout
- [x] Frontend auto-print: hidden iframes firing BOTH formats on `add_container` / `reweigh_container` success
- [x] Per-row + bulk print buttons (both formats)
- [x] Per-Profile auto-print toggles wired through

### Phase 5 — UI (truck terminal) ✅ MOSTLY DONE (Wave 5)
- [x] New Containers panel in `/pos/truck.html` (+862 lines HTML/JS)
- [x] "Add Container" modal (grade picker, type dropdown, manual weight, deviation prompt)
- [x] Container row actions (Reweigh, Print Thermal, Print Sticker, Void)
- [x] Pause / Resume buttons + status display
- [x] Scanner: QR → load container → action menu
- [x] Feature flag `use_container_model` (default on) — legacy scrap-weight panel preserved when off
- [ ] **FOLLOW-UP** Switch Scale / Reassign Session / Void Dropoff Weighing / Verify Dropoff buttons in truck terminal (currently desk-only; deferred per UI scope)
- [ ] **FOLLOW-UP** Live scale binding in Add Container modal (currently manual entry only — wire `scale_reader.js` callbacks)
- [ ] **FOLLOW-UP** QR scan action chooser uses `window.prompt` — replace with proper popover
- [ ] **FOLLOW-UP** Add real `use_container_model` field to `POS Profile Scrap` doctype (currently read via `getattr`)

### Phase 6 — UI (desk) ✅ DONE (Wave 5)
- [x] Dropoff form: custom buttons in `Container Actions` group (Pause, Resume, Switch Scale, Reassign Session)
- [x] "Mark Verified (Override)" button on Dropoff (visible when `verification_status = Needs Review`)
- [x] Container form: Reweigh / Void / Print Thermal / Print Sticker / Approve Deviation buttons
- [x] Bulk print buttons on Dropoff (`Print all (thermal)` / `Print all (stickers)`)
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

### Phase 12 — Tests ✅ DONE (Wave 5)
- [x] `test_scrap_weight_container.py` — 14 unit tests covering all controller paths
- [x] `test_dropoff_container_settings.py` — 1 minimal defaults test
- [x] `api_test/test_container_workflow.py` — 11-step integration test (open session → add 5 containers → reweigh → pause → resume → 6th container → complete)
- [ ] **PENDING** Run tests: `bench --site metal execute scrap_metal_suite.api_test.test_container_workflow.run` (next session)
- [ ] **PENDING** Migration tests against real production data snapshot

---

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
