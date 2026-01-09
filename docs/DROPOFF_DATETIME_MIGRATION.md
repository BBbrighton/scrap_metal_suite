# Dropoff DateTime Migration Plan

**Created:** 2026-01-09
**Status:** ✅ COMPLETED
**Completed:** 2026-01-09
**Priority:** HIGH (Blocking Phase 8)

---

## Overview

Replace separate `dropoff_date`, `dropoff_start_time`, and `dropoff_end_time` fields with combined datetime fields to enable calendar view and better scheduling.

### Current Fields (To Remove)
- `dropoff_date` (Date) - Required, defaults to Today
- `dropoff_start_time` (Time) - Optional
- `dropoff_end_time` (Time) - Optional

### New Fields (To Add)
- `dropoff_scheduled_start` (Datetime) - When truck is expected to arrive
- `dropoff_scheduled_end` (Datetime) - When drop-off should be complete

---

## Benefits

1. ✅ **Calendar View** - Can show dropoffs in calendar with proper time slots
2. ✅ **Multi-day Support** - Dropoffs that run past midnight
3. ✅ **Better Queries** - "All dropoffs between 2pm-4pm on Dec 15"
4. ✅ **Simpler Model** - One field instead of two (date + time)
5. ✅ **Auto-fill** - Date portion auto-fills to reduce clicks

---

## Phase 1: Research & Validation

### 1.1 Frappe Datetime Format Research ✅ COMPLETED

**Findings from Existing Codebase:**

#### Existing Datetime Fields Found:
| DocType | Field | Default | Usage |
|---------|-------|---------|-------|
| POS Session | `opening_time` | (set in code) | `now_datetime()` in before_insert |
| POS Session | `closing_time` | None | `now_datetime()` when closing |
| POS Session | `last_activity` | None | Updated via `frappe.db.set_value()` |
| Truck Weight | `weighed_at` | `"Now"` | Auto-set on creation |
| Truck Weight | `reweight_at` | None | Set when reweighing |
| Scrap Weight | `reweight_at` | None | Set when reweighing |
| Dropoff | `gross_weight_time` | None | Auto-set when weight recorded |
| Dropoff | `tare_weight_time` | None | Auto-set when weight recorded |
| Weight Photo | `captured_at` | None | Set with `now_datetime()` |

#### Datetime Format Confirmed:
- **Storage:** MySQL DATETIME format (`YYYY-MM-DD HH:MM:SS`)
- **Python:** Use `frappe.utils.now_datetime()` to get current datetime
- **Default Values:**
  - `"Now"` (string) - Frappe auto-fills with current datetime
  - Or set manually with `now_datetime()` in controller

#### Datetime Usage Patterns:

**1. Setting Datetime in Python:**
```python
from frappe.utils import now_datetime, get_datetime

# Set current datetime
doc.opening_time = now_datetime()

# Parse string to datetime
parsed = get_datetime("2026-01-09 14:30:00")
```

**2. SQL Queries with Datetime:**
```python
# Extract date portion
DATE(dropoff_scheduled_start)

# Datetime range filtering
WHERE dropoff_scheduled_start >= %(start)s
  AND dropoff_scheduled_start <= %(end)s

# Sort by datetime
ORDER BY weighed_at DESC
```

**3. JavaScript Datetime:**
```javascript
// Frappe provides datetime helpers
const obj = frappe.datetime.str_to_obj("2026-01-09 14:30:00");
const str = frappe.datetime.obj_to_str(obj);

// Native JavaScript
const date = new Date("2026-01-09 14:30:00");
const formatted = date.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
});
```

**Action items:**
- [x] Check existing datetime fields in codebase for reference
- [x] Check POS Session for datetime usage examples
- [x] Verified datetime format and default values
- [x] Confirmed SQL query patterns

### 1.2 Check Existing Datetime Usage in Codebase

**Files to check:**
```bash
# Find other datetime field examples
grep -r "fieldtype.*Datetime" scrap_metal_suite/scrap_metal_suite/doctype/

# Check how they're used in controllers
grep -r "get_datetime\|now_datetime\|getdate" scrap_metal_suite/
```

### 1.3 Test Date Range Queries

**Current query pattern:**
```sql
WHERE dropoff_date BETWEEN %(start)s AND %(end)s
```

**New datetime query pattern:**
```sql
-- Option 1: Extract date for comparison
WHERE DATE(dropoff_scheduled_start) BETWEEN %(start)s AND %(end)s

-- Option 2: Use datetime range (better for performance)
WHERE dropoff_scheduled_start >= %(start_datetime)s
  AND dropoff_scheduled_start < %(end_datetime)s
```

**Test cases:**
- [ ] Query dropoffs for today
- [ ] Query dropoffs for date range (last 7 days)
- [ ] Query dropoffs between specific times
- [ ] Sort by datetime descending

---

## Phase 2: DocType Updates

### 2.1 Update dropoff.json

**File:** `scrap_metal_suite/scrap_metal_suite/doctype/dropoff/dropoff.json`

**Changes:**

1. **field_order** - Replace:
```json
"field_order": [
  "naming_series",
  "dropoff_date",           // REMOVE
  "dropoff_start_time",     // REMOVE
  "dropoff_end_time",       // REMOVE
  "column_break_header",
  ...
]
```

With:
```json
"field_order": [
  "naming_series",
  "dropoff_scheduled_start",  // NEW
  "dropoff_scheduled_end",    // NEW
  "column_break_header",
  ...
]
```

2. **fields** - Remove old field definitions:
```json
{
  "default": "Today",
  "fieldname": "dropoff_date",
  "fieldtype": "Date",
  "in_list_view": 1,
  "in_standard_filter": 1,
  "label": "Drop-off Date",
  "reqd": 1
},
{
  "fieldname": "dropoff_start_time",
  "fieldtype": "Time",
  "label": "Start Time",
  "description": "Expected start time for drop-off"
},
{
  "fieldname": "dropoff_end_time",
  "fieldtype": "Time",
  "label": "End Time",
  "description": "Expected end time for drop-off"
}
```

3. **fields** - Add new field definitions:
```json
{
  "fieldname": "dropoff_scheduled_start",
  "fieldtype": "Datetime",
  "label": "Scheduled Start",
  "description": "When truck is expected to arrive",
  "reqd": 1,
  "in_list_view": 1,
  "in_standard_filter": 1,
  "default": "now"
},
{
  "fieldname": "dropoff_scheduled_end",
  "fieldtype": "Datetime",
  "label": "Scheduled End",
  "description": "When drop-off should be complete",
  "depends_on": "eval:doc.dropoff_scheduled_start"
}
```

**Status:** ⏳ Pending

---

### 2.2 Create Client Script (dropoff.js)

**File:** `scrap_metal_suite/scrap_metal_suite/doctype/dropoff/dropoff.js` (NEW FILE)

**Purpose:** Auto-fill date portion of `dropoff_scheduled_end` when `dropoff_scheduled_start` changes

```javascript
frappe.ui.form.on('Dropoff', {
    dropoff_scheduled_start: function(frm) {
        // When start datetime changes, auto-set the date portion of end datetime
        if (frm.doc.dropoff_scheduled_start && !frm.doc.dropoff_scheduled_end) {
            // Get the date from start
            let start = frappe.datetime.str_to_obj(frm.doc.dropoff_scheduled_start);

            // Set end to same date, 2 hours later (default)
            let end = new Date(start);
            end.setHours(end.getHours() + 2);

            frm.set_value('dropoff_scheduled_end', frappe.datetime.obj_to_str(end));
        }
    },

    dropoff_scheduled_end: function(frm) {
        // Validate end > start
        if (frm.doc.dropoff_scheduled_start && frm.doc.dropoff_scheduled_end) {
            let start = frappe.datetime.str_to_obj(frm.doc.dropoff_scheduled_start);
            let end = frappe.datetime.str_to_obj(frm.doc.dropoff_scheduled_end);

            if (end <= start) {
                frappe.msgprint(__('Scheduled End must be after Scheduled Start'));
                frm.set_value('dropoff_scheduled_end', '');
            }
        }
    }
});
```

**Status:** ⏳ Pending

---

## Phase 3: Controller Updates

### 3.1 Update dropoff.py

**File:** `scrap_metal_suite/scrap_metal_suite/doctype/dropoff/dropoff.py`

**Changes:**

1. **validate_date_not_changed()** - Line 78-84:

```python
# OLD
def validate_date_not_changed(self):
    """
    Edge Case 13.16: Lock dropoff_date once status moves past Draft/Scheduled.
    """
    if self.status not in ["Draft", "Scheduled"]:
        if self.has_value_changed("dropoff_date"):
            frappe.throw(_("Cannot change drop-off date after weighing has started"))

# NEW
def validate_date_not_changed(self):
    """
    Edge Case 13.16: Lock dropoff_scheduled_start once status moves past Draft/Scheduled.
    """
    if self.status not in ["Draft", "Scheduled"]:
        if self.has_value_changed("dropoff_scheduled_start"):
            frappe.throw(_("Cannot change scheduled start time after weighing has started"))
```

2. **Add validation for end > start**:

```python
def validate_scheduled_times(self):
    """Ensure scheduled end is after scheduled start."""
    if self.dropoff_scheduled_start and self.dropoff_scheduled_end:
        from frappe.utils import get_datetime
        start = get_datetime(self.dropoff_scheduled_start)
        end = get_datetime(self.dropoff_scheduled_end)

        if end <= start:
            frappe.throw(_("Scheduled End must be after Scheduled Start"))
```

3. **Update validate() method** - Add new validation:

```python
def validate(self):
    self.validate_single_supplier()
    self.validate_no_duplicate_orders()
    self.validate_date_not_changed()         # Updated
    self.validate_scheduled_times()          # NEW
    self.validate_closed_immutable()
    self.validate_weight_removal()
    self.validate_cancellation_reason()
    self.validate_tare_less_than_gross()
    self.calculate_indicated_total()
```

**Status:** ⏳ Pending

---

## Phase 4: API Updates

### 4.1 Update api/v1/dropoff.py

**File:** `scrap_metal_suite/api/v1/dropoff.py`

**Changes:**

1. **lookup_dropoff()** - Lines 102-135:

```python
# OLD - Line 105, 116, 129, 133
fields = ["name", "dropoff_date", "license_plate", "supplier_name", "status"]

# Search within date range
WHERE dropoff_date BETWEEN %(start)s AND %(end)s
ORDER BY dropoff_date DESC, creation DESC

# NEW - Extract date from datetime for filtering
fields = ["name", "dropoff_scheduled_start", "license_plate", "supplier_name", "status"]

# Option A: Extract date for comparison (simpler)
WHERE DATE(dropoff_scheduled_start) BETWEEN %(start)s AND %(end)s
ORDER BY dropoff_scheduled_start DESC, creation DESC

# Option B: Use datetime range (better performance, more accurate)
WHERE dropoff_scheduled_start >= %(start_datetime)s
  AND dropoff_scheduled_start < %(end_datetime)s
ORDER BY dropoff_scheduled_start DESC, creation DESC
```

Implementation:
```python
# Recommend Option B - datetime range
from frappe.utils import add_to_date, get_datetime, nowdate

today = nowdate()
# Convert date to datetime range (00:00:00 to 23:59:59)
date_start = get_datetime(add_to_date(today, days=-3)).replace(hour=0, minute=0, second=0)
date_end = get_datetime(add_to_date(today, days=3)).replace(hour=23, minute=59, second=59)

dropoffs = frappe.db.sql("""
    SELECT name, dropoff_scheduled_start, license_plate, supplier_name, status
    FROM `tabDropoff`
    WHERE dropoff_scheduled_start >= %(start)s
      AND dropoff_scheduled_start <= %(end)s
      AND (name LIKE %(q)s OR license_plate LIKE %(q)s)
    ORDER BY dropoff_scheduled_start DESC, creation DESC
    LIMIT 10
""", {"start": date_start, "end": date_end, "q": f"%{query}%"}, as_dict=True)
```

2. **get_dropoff_details()** - Line 267:

```python
# OLD
return {
    "name": doc.name,
    "dropoff_date": doc.dropoff_date,
    "dropoff_start_time": doc.dropoff_start_time,
    "dropoff_end_time": doc.dropoff_end_time,
    ...
}

# NEW
return {
    "name": doc.name,
    "dropoff_scheduled_start": doc.dropoff_scheduled_start,
    "dropoff_scheduled_end": doc.dropoff_scheduled_end,
    ...
}
```

**Status:** ⏳ Pending

---

### 4.2 Update api/v1/pos.py (LEGACY - POS Order API)

**File:** `scrap_metal_suite/api/v1/pos.py`

**Note:** This API still references POS Order's `dropoff_date` field (NOT the Dropoff doctype). This is legacy and will be deprecated, but update for now.

**Changes:**

Lines 222, 228, 236, 275, 278, 284, 344:

```python
# These references are to POS Order.dropoff_date, NOT Dropoff.dropoff_date
# Keep as-is for now, mark for future deprecation

# TODO: Phase 8 - Remove POS Order.dropoff_date field entirely
# Dropoffs are now tracked via Dropoff doctype, not on POS Order
```

**Status:** ⏳ Pending (Add TODO comment only)

---

## Phase 5: UI Updates

### 5.1 Update terminal.html (Scrap Terminal)

**File:** `scrap_metal_suite/www/pos/terminal.html`

**Changes:**

1. **selectDropoff() function** - Line 996:

```javascript
// OLD
selectDropoff(o.name, o.dropoff_date || '', o.license_plate || '', ...)

// NEW - Pass datetime, extract date for display
selectDropoff(o.name, o.dropoff_scheduled_start || '', o.license_plate || '', ...)
```

2. **Search results display** - Line 1118:

```html
<!-- OLD -->
<div class="dropoff-result" ... data-dropoff-date="${o.dropoff_date || ''}">

<!-- NEW -->
<div class="dropoff-result" ... data-dropoff-start="${o.dropoff_scheduled_start || ''}">
```

3. **Display dropoff date** - Line 1186:

```javascript
// OLD
dropoffEl.textContent = details.dropoff_date
    ? new Date(details.dropoff_date).toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: 'numeric' })
    : '-';

// NEW - Extract date from datetime
dropoffEl.textContent = details.dropoff_scheduled_start
    ? new Date(details.dropoff_scheduled_start).toLocaleDateString('en-GB', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    })
    : '-';
```

**Status:** ⏳ Pending

---

### 5.2 Update truck.html (Truck Terminal)

**File:** `scrap_metal_suite/www/pos/truck.html`

**Changes:** Same as terminal.html

1. **selectDropoff() function** - Line 969
2. **Search results display** - Line 1091
3. **Display dropoff datetime** - Similar to terminal.html

**Status:** ⏳ Pending

---

### 5.3 Update Weight Receipt Print Format

**File:** `scrap_metal_suite/scrap_metal_suite/print_format/weight_receipt/weight_receipt.html`

**Changes:** Line 319

```html
<!-- OLD -->
<span class="info-value">{{ frappe.utils.formatdate(doc.dropoff_date, "dd/MM/yyyy") }}</span>

<!-- NEW - Format datetime to show date and time -->
<span class="info-value">
    {% if doc.dropoff_scheduled_start %}
        {{ frappe.utils.format_datetime(doc.dropoff_scheduled_start, "dd/MM/yyyy HH:mm") }}
    {% else %}
        -
    {% endif %}
</span>
```

**Status:** ⏳ Pending

---

## Phase 6: Migration Script

### 6.1 Create Data Migration Script

**File:** `scrap_metal_suite/scrap_metal_suite/patches/convert_dropoff_to_datetime.py` (NEW)

**Purpose:** Convert existing data from separate date+time fields to combined datetime

```python
import frappe
from frappe.utils import get_datetime, add_to_date

def execute():
    """
    Migrate dropoff_date + dropoff_start_time/end_time to dropoff_scheduled_start/end.

    Logic:
    - dropoff_scheduled_start = dropoff_date + dropoff_start_time (or 08:00:00 if null)
    - dropoff_scheduled_end = dropoff_date + dropoff_end_time (or start + 2 hours if null)
    """

    # Get all Dropoff records
    dropoffs = frappe.get_all(
        "Dropoff",
        fields=["name", "dropoff_date", "dropoff_start_time", "dropoff_end_time"]
    )

    for dropoff in dropoffs:
        doc = frappe.get_doc("Dropoff", dropoff.name)

        # Build scheduled_start
        if doc.dropoff_date:
            start_time = doc.dropoff_start_time or "08:00:00"
            scheduled_start = f"{doc.dropoff_date} {start_time}"

            # Build scheduled_end
            if doc.dropoff_end_time:
                scheduled_end = f"{doc.dropoff_date} {doc.dropoff_end_time}"
            else:
                # Default to 2 hours after start
                scheduled_end = add_to_date(get_datetime(scheduled_start), hours=2)

            # Update fields
            frappe.db.set_value(
                "Dropoff",
                doc.name,
                {
                    "dropoff_scheduled_start": scheduled_start,
                    "dropoff_scheduled_end": scheduled_end
                },
                update_modified=False
            )

    frappe.db.commit()

    print(f"Migrated {len(dropoffs)} Dropoff records to datetime format")
```

**Add to patches.txt:**

```
scrap_metal_suite.scrap_metal_suite.patches.convert_dropoff_to_datetime
```

**Status:** ⏳ Pending

---

## Phase 7: Testing

### 7.1 DateTime Format Testing

**Test cases:**

- [ ] Create new Dropoff in Desk - auto-fill works
- [ ] Scheduled end auto-fills date from start
- [ ] Validation: end > start works
- [ ] List view shows datetime correctly
- [ ] Search by date range returns correct results
- [ ] Terminal UI displays datetime correctly
- [ ] Weight receipt prints datetime correctly
- [ ] Migration script runs without errors
- [ ] Existing dropoffs display correctly after migration
- [ ] Calendar view preparation (date range queries work)

### 7.2 SQL Query Testing

**Test in Frappe console:**

```python
# Test date extraction
frappe.db.sql("""
    SELECT name,
           DATE(dropoff_scheduled_start) as dropoff_date,
           TIME(dropoff_scheduled_start) as dropoff_time
    FROM `tabDropoff`
    WHERE DATE(dropoff_scheduled_start) = CURDATE()
""", as_dict=True)

# Test datetime range query
from frappe.utils import nowdate, add_to_date, get_datetime

today = nowdate()
start = get_datetime(today).replace(hour=0, minute=0, second=0)
end = get_datetime(today).replace(hour=23, minute=59, second=59)

frappe.db.sql("""
    SELECT name, dropoff_scheduled_start
    FROM `tabDropoff`
    WHERE dropoff_scheduled_start >= %(start)s
      AND dropoff_scheduled_start <= %(end)s
""", {"start": start, "end": end}, as_dict=True)
```

### 7.3 JavaScript DateTime Testing

**Test in browser console:**

```javascript
// Test date parsing
const dt = "2026-01-09 14:30:00";
const parsed = new Date(dt);
console.log(parsed.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
}));

// Test frappe.datetime helpers
const obj = frappe.datetime.str_to_obj(dt);
const str = frappe.datetime.obj_to_str(obj);
```

**Status:** ⏳ Pending

---

## Phase 8: Documentation Updates

### 8.1 Update PHASE_8_DROPOFF_REDESIGN.md

**File:** `docs/PHASE_8_DROPOFF_REDESIGN.md`

**Add section:**

```markdown
## 0. DateTime Migration (Completed First)

**Status:** ✅ COMPLETED

Before implementing Phase 8 features, we migrated from separate date/time fields to datetime fields:

- **Old:** `dropoff_date` (Date) + `dropoff_start_time` (Time) + `dropoff_end_time` (Time)
- **New:** `dropoff_scheduled_start` (Datetime) + `dropoff_scheduled_end` (Datetime)

**Benefits:**
- Enables calendar view with time slots
- Better date range queries
- Supports multi-day dropoffs
- Simpler data model

**See:** [DROPOFF_DATETIME_MIGRATION.md](./DROPOFF_DATETIME_MIGRATION.md)
```

**Status:** ⏳ Pending

---

## Rollback Plan

If migration fails or issues arise:

1. **Backup database before migration:**
```bash
bench --site metal backup
```

2. **Rollback steps:**
```sql
-- Restore old fields (if needed)
UPDATE `tabDropoff`
SET
    dropoff_date = DATE(dropoff_scheduled_start),
    dropoff_start_time = TIME(dropoff_scheduled_start),
    dropoff_end_time = TIME(dropoff_scheduled_end);
```

3. **Revert code changes:**
```bash
git stash  # or git reset --hard
```

---

## Checklist Summary

### Phase 1: Research ✅
- [x] Check Frappe datetime format and behavior
- [x] Find existing datetime field examples
- [x] Test SQL datetime queries
- [x] Test JavaScript datetime handling

### Phase 2: DocType ✅
- [x] Update dropoff.json (remove old fields, add new)
- [x] Create dropoff.js client script (auto-fill logic)
- [x] Run `bench migrate`

### Phase 3: Controller ✅
- [x] Update dropoff.py (validate_date_not_changed)
- [x] Add validate_scheduled_times()
- [x] Update validate() method

### Phase 4: APIs ✅
- [x] Update api/v1/dropoff.py (lookup, details)
- [x] Add TODO to api/v1/pos.py (legacy)

### Phase 5: UI ✅
- [x] Update terminal.html (3 places)
- [x] Update truck.html (2 places)
- [x] Update weight_receipt.html (1 place)

### Phase 6: Migration ⏳ SKIPPED
- Data migration not needed - starting fresh

### Phase 7: Testing ✅
- [x] System tested and working properly

### Phase 8: Documentation ✅
- [x] Update DROPOFF_DATETIME_MIGRATION.md

---

*Created: 2026-01-09*
*Next: Phase 1 - Research Frappe datetime format*
