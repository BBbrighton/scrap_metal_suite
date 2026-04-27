# Bilingual Implementation Guide (Thai / English)

**Status:** Production guideline
**Audience:** Engineers adding features to Scrap Metal Suite
**Last updated:** 2026-04-25

---

## 1. Goal

Production-ready Thai / English support across:

- **Frappe desk** — DocType labels, list views, server-side validation messages
- **Custom UI** — POS terminal, truck terminal, supplier portal, manager portal
- **Print formats** — A4 documents and thermal receipts/stickers

Switching the user's language toggles all *UI text*. Master data (Item names, Supplier names) is **never** translated.

---

## 2. The cardinal rule: never translate item names

**Item names are canonical Thai and must never be translated.** This applies to:

- Item dropdown labels (UI) → render `item.item_name` as stored
- Print formats → render the raw Thai once, do NOT add an English equivalent
- Validation messages → quote `item.item_name` verbatim, do not pass through `_()`
- Translation files (`th.csv`, `pos-translations.js`) → must NOT contain Item names as keys

**Why:** the Thai term *is* the identifier. There is no English Item record by any other name. Generating a fake English equivalent ("Old Stripped Copper Wire" for ทองแดงปอก) creates an alias that doesn't exist anywhere else in the system, breaks search, confuses operators, and risks misidentification across portals/print formats.

The same rule applies to other master-data names:

| Field | Translate? |
|---|---|
| `Item.item_name` | ❌ Never |
| `Item.item_code` | ❌ Never |
| `Supplier.supplier_name` | ❌ Never |
| `Scale.scale_name` | ❌ Never |
| `Item Group.item_group_name` | ❌ Never (it's master data) |
| Item Group descriptions / static catalog text | ✅ OK if maintained as a separate field |

What CAN be translated:

| Item | Translate? |
|---|---|
| DocType / field labels | ✅ Yes (via th.csv) |
| Button captions | ✅ Yes (via pos-translations.js) |
| Status terms ("Active", "Paused") | ✅ Yes |
| Section headers, navigation, tooltips | ✅ Yes |
| Validation / error messages | ✅ Yes (the message text — but interpolated item names stay Thai) |
| Domain terms ("Container", "Bag", "Dropoff", "Reweigh") | ✅ Yes |

---

## 3. Two layers

### 3.1 Layer A — Frappe desk (server + form rendering)

**File:** [`scrap_metal_suite/translations/th.csv`](../scrap_metal_suite/translations/th.csv)

**Format:** CSV. Each row is `"source","translation"` or `"source","translation","context"`.

**What it covers:**
- Every DocType label and field label declared in `*.json`
- Every string wrapped with `_()` in Python
- Every string wrapped with `__()` in JavaScript that runs inside the desk
- Frappe-rendered notifications, comments, list view filters

**What it does NOT cover:**
- Strings inside `www/` HTML files served as guest pages
- Strings inside the truck terminal / POS terminal custom JS (Layer B)

**How to add a new translation:**

1. Write source strings in English in code/JSON.
2. Wrap user-facing strings in `_()`:
   ```python
   frappe.throw(_("Dropoff {0} is locked to session {1}").format(name, session))
   ```
3. Run extractor (collects all `_(...)` and DocType labels into a CSV scaffold):
   ```bash
   bench update-translations scrap_metal_suite th
   ```
4. Open `translations/th.csv`, fill the second column with Thai.
5. Reload site:
   ```bash
   bench --site metal clear-cache
   bench --site metal reload-doctype "Scrap Weight Container"
   ```
6. Switch a user's language to Thai (Settings → Language) and verify.

**Conventions:**
- Source = full sentence (don't concatenate fragments — concatenation breaks translation)
- Use `{0}`, `{1}` for interpolation (Python `.format()`)
- One context per row when the same English maps to different Thai meanings
- Keep source identical to the code — even a trailing space differs

**Example rows:**

```csv
"Container","ภาชนะ"
"Container Number","เลขที่ภาชนะ"
"Net Weight","น้ำหนักสุทธิ"
"Reweigh","ชั่งใหม่"
"Dropoff {0} is locked to session {1}","ใบส่งมอบ {0} ถูกล็อกกับเซสชัน {1}"
"Reason required for grade deviation","ต้องระบุเหตุผลเมื่อเกรดต่างจากที่คาด"
"Save","บันทึก"
"Save","ประหยัด","Cost context"
```

### 3.2 Layer B — Custom UI (truck terminal, POS, portals)

**Files:**
- Base singleton: [`scrap_metal_suite/public/js/pos-translations.js`](../scrap_metal_suite/public/js/pos-translations.js)
- Per-module extensions: e.g. `production-translations.js` uses `POS_I18N.extend({...})`

**What it covers:**
- Strings inside `scrap_metal_suite/www/pos/*.html` (truck terminal, POS)
- Strings inside `scrap_metal_suite/www/production/*.html`
- Anywhere the `t('key')` helper is used

**Existing pattern (from memory):** `POS_I18N` singleton holds a `~300-key` shared dictionary, `production-translations.js` uses `POS_I18N.extend()` to layer in module-specific keys without duplicating the shared ones.

**How to add a new translation:**

1. Decide module:
   - Shared / used by truck terminal AND production → add to `pos-translations.js`
   - Module-specific (only one terminal) → create or extend `<module>-translations.js`
2. Add an entry under both `en` and `th`:
   ```javascript
   const containerKeys = {
     en: {
       container: 'Container',
       new_container: 'New Container',
       reweigh: 'Reweigh',
       weight_history: 'Weight history',
     },
     th: {
       container: 'ภาชนะ',
       new_container: 'เพิ่มภาชนะ',
       reweigh: 'ชั่งใหม่',
       weight_history: 'ประวัติการชั่ง',
     },
   };
   POS_I18N.extend(containerKeys);
   ```
3. Use `t('key')` in HTML/JS:
   ```html
   <button class="btn-primary">${t('reweigh')}</button>
   <h3>${t('weight_history')}</h3>
   ```
4. For interpolation, use `t('key', {variable: value})` (verify the helper supports this; otherwise concatenate the literal):
   ```javascript
   alert(t('container_added', {no: container.container_no}));
   // en: 'Container {no} added'
   // th: 'เพิ่มภาชนะ {no} แล้ว'
   ```
5. Make sure the script is loaded by the page's `hooks.py` `web_include_js`.

**Key naming conventions:**

| Pattern | Example |
|---|---|
| `<module>_<thing>` | `container_type`, `dropoff_status` |
| `action_<verb>` for buttons | `action_save`, `action_pause`, `action_resume` |
| `status_<state>` for states | `status_active`, `status_paused`, `status_completed` |
| `error_<short>` for error messages | `error_locked_session`, `error_scale_mismatch` |
| `prompt_<context>` for modals/prompts | `prompt_deviation_reason` |

Use `snake_case` consistently. Keep keys flat (no nesting); namespacing via prefix is sufficient.

---

## 4. Print formats

Print formats are **bilingual side-by-side** — both Thai and English appear in the rendered output (no language switching). This means:

- UI labels are written into the Jinja template directly with both languages.
- Item names appear ONCE, in canonical Thai (the rule).
- Numbers, dates, and IDs render as-is.

### 4.1 Existing patterns to follow

- [`Scrap Weight Thermal`](../scrap_metal_suite/fixtures/print_format.json) — 80mm × auto thermal, side-by-side TH/EN
- `ใบคิวสองภาษา` (Dropoff Receipt) — A4 bilingual

### 4.2 Pattern in Jinja

```jinja
<div class="row">
  <div class="col">
    <small>น้ำหนักสุทธิ • Net Weight</small>
    <h2>{{ "{:,.1f}".format(doc.net_weight) }} kg</h2>
  </div>
</div>

<div class="row">
  <div class="col">
    <small>เกรด</small>
    <p>{{ doc.item_name }}</p>     {# canonical, no English here #}
  </div>
</div>
```

### 4.3 Template guidance

- Use `<small>` for the bilingual UI label (Thai • English) above the data
- Use the data field directly for canonical names (item, supplier)
- Format numbers with `{:,.1f}` for kg (1 decimal) or `{:,.2f}` for prices
- For dates, use `frappe.utils.format_datetime(...)` with site-default format (Thai users typically see Buddhist Era OR Western — site setting controls)

### 4.4 Sticker example for `Scrap Weight Container Thermal`

```jinja
<div class="container">
  <div class="header">
    <strong>{{ doc.dropoff }}</strong><br>
    <small>{{ doc.supplier_name }}</small>     {# canonical #}
  </div>

  <div class="qr">
    <strong>{{ doc.name }}</strong>
    {{ qr_src('Scrap Weight Container', doc.name) }}
  </div>

  <div class="grade">
    <h2>{{ doc.item_name }}</h2>                {# canonical Thai, only #}
  </div>

  <div class="weight">
    <small>น้ำหนักสุทธิ • Net Weight</small>
    <h1>{{ "{:,.1f}".format(doc.net_weight) }} kg</h1>
  </div>

  <div class="meta">
    <small>ภาชนะที่ • Bag</small> {{ doc.container_no }}
    {% if doc.is_deviation %}
      <span class="warn">⚠ {{ _("Deviation") }}</span>
    {% endif %}
  </div>
</div>
```

Note: the only translated thing on the sticker is the small-print bilingual UI labels. Item name = canonical, never translated.

---

## 5. Choosing the right layer

| Where the string appears | Layer |
|---|---|
| DocType / field label (any `*.json` doctype file) | A — `th.csv` (auto-extracted) |
| `frappe.throw(_("..."))` in Python | A — `th.csv` |
| `frappe.msgprint(_("..."))` in Python | A — `th.csv` |
| `__("...")` in JS that runs in the desk | A — `th.csv` |
| HTML in `scrap_metal_suite/www/` (Jinja templates) | A — `{{ _("...") }}` resolves via `th.csv` |
| Custom JS `t('key')` in truck/POS terminal | B — `pos-translations.js` |
| Hard-coded text in static `<h1>` / `<button>` etc. | Wrap in `t('key')` (preferred) or `{{ _("...") }}` if Jinja |
| Print format Jinja | Inline bilingual (no translation file) |

If unsure: prefer Layer A (`th.csv`) for anything served through Frappe's request lifecycle. Use Layer B only when you're inside a custom singleton-style page (truck/POS terminal) and `pos-translations.js` is loaded.

---

## 6. Workflow when adding a new feature

For every user-visible string in a new feature:

1. **Identify** the string and where it lives.
2. **Pick the layer** (table above).
3. **Write source in English** (always — Thai source confuses extractors).
4. **Wrap appropriately:**
   - Python: `_("...")`
   - JS in desk: `__("...")`
   - JS in custom UI: `t('key_name')`
   - Jinja in www: `{{ _("...") }}`
   - Jinja in print: bilingual side-by-side, no wrapping
5. **For Layer A:** run `bench update-translations scrap_metal_suite th`, fill in Thai.
6. **For Layer B:** add `en` + `th` entry to the appropriate translations JS file.
7. **For print:** edit Jinja directly with both languages.
8. **Test** by switching user language to Thai → confirm all UI strings render correctly.
9. **Confirm** item names render in canonical Thai (the rule).

---

## 7. Terminology dictionary (curated)

This is the canonical EN→TH for domain terms used by the Container redesign and adjacent modules. Use these exact translations to keep terminology consistent across desk + UI + print.

### 7.1 Core domain

| English | Thai | Notes |
|---|---|---|
| Dropoff | ใบส่งมอบ | The truck-arrival document |
| Scrap Weight | น้ำหนักเศษ | (legacy term — fading out) |
| Container | ภาชนะ | The new core unit |
| Bag | ถุง | container type |
| Bin | ถัง | container type |
| Pallet | พาเลท | container type (transliteration) |
| Other | อื่น ๆ | container type |
| Grade | เกรด | Item / scrap classification |
| Supplier | ผู้จัดส่ง | |
| Operator | ผู้ปฏิบัติงาน | |
| Manager | ผู้จัดการ | |
| Session | เซสชัน | POS Session |
| Scale | ตราชั่ง | |
| Truck | รถ | |

### 7.2 Weight terms

| English | Thai |
|---|---|
| Gross Weight | น้ำหนักรวม |
| Tare Weight | น้ำหนักภาชนะ |
| Net Weight | น้ำหนักสุทธิ |
| Indicated Weight | น้ำหนักตามแจ้ง |
| Actual Weight | น้ำหนักจริง |
| Total Weight | น้ำหนักรวมทั้งหมด |
| Variance | ค่าส่วนต่าง |
| Threshold | เกณฑ์ |

### 7.3 Status terms

| English | Thai |
|---|---|
| Draft | ร่าง |
| Scheduled | นัดหมาย |
| In Progress | กำลังดำเนินการ |
| Paused | หยุดชั่วคราว |
| Completed | เสร็จสิ้น |
| Verified | ตรวจสอบแล้ว |
| Needs Review | ต้องตรวจสอบ |
| Voided | ยกเลิก |
| Active | ใช้งาน |
| Reweighed | ชั่งใหม่แล้ว |

### 7.4 Actions

| English | Thai |
|---|---|
| Save | บันทึก |
| Cancel | ยกเลิก |
| Print | พิมพ์ |
| Reprint | พิมพ์ซ้ำ |
| Print Sticker | พิมพ์สติ๊กเกอร์ |
| Print all stickers | พิมพ์สติ๊กเกอร์ทั้งหมด |
| Add Container | เพิ่มภาชนะ |
| Reweigh | ชั่งใหม่ |
| Void | ยกเลิก |
| Pause | หยุดชั่วคราว |
| Resume | ทำงานต่อ |
| Complete | เสร็จสิ้น |
| Switch Scale | เปลี่ยนตราชั่ง |
| Reassign Session | เปลี่ยนเซสชัน |
| Approve | อนุมัติ |
| Reject | ปฏิเสธ |
| Confirm | ยืนยัน |
| Scan | สแกน |

### 7.5 Deviations

| English | Thai |
|---|---|
| Deviation | ความเบี่ยงเบน |
| Grade differs from expected | เกรดต่างจากที่คาดไว้ |
| Downgrade | ลดเกรด |
| Upgrade | เพิ่มเกรด |
| Substitution | ทดแทน |
| Unplanned-Add | เพิ่มนอกแผน |
| Reason | เหตุผล |
| Approval Required | ต้องขออนุมัติ |
| Approved by | อนุมัติโดย |
| Approve Deviation | อนุมัติความเบี่ยงเบน |
| Mark Verified | ยืนยันการตรวจสอบ |
| Verification Overridden | ยืนยันโดยข้ามการตรวจสอบ |
| Override Reason | เหตุผลในการข้ามการตรวจสอบ |

### 7.6 Common errors

| English | Thai |
|---|---|
| Required | จำเป็น |
| Not allowed | ไม่อนุญาต |
| Not found | ไม่พบ |
| Already exists | มีอยู่แล้ว |
| Out of range | นอกช่วงที่กำหนด |
| Permission denied | ไม่มีสิทธิ์ |
| Session expired | เซสชันหมดอายุ |
| Locked | ถูกล็อก |
| Scale mismatch | ตราชั่งไม่ตรงกัน |
| Weight must be greater than 0 | น้ำหนักต้องมากกว่า 0 |

### 7.7 Print labels (small-print bilingual on stickers/receipts)

Format: `Thai • English` together, `<small>` styled.

| Sticker label |
|---|
| `น้ำหนักสุทธิ • Net Weight` |
| `เกรด • Grade` |
| `ภาชนะที่ • Bag #` |
| `ผู้ปฏิบัติงาน • Operator` |
| `เวลา • Time` |
| `ใบส่งมอบ • Dropoff` |
| `ผู้จัดส่ง • Supplier` |

---

## 8. Common pitfalls

1. **Hard-coded strings in HTML.** A `<button>Save</button>` in a Jinja template renders English to a Thai user. Always use `{{ _("Save") }}` or `${t('action_save')}`.

2. **Concatenated strings.**
   ❌ `_("Container ") + str(no) + _(" added")` — three fragments, untranslatable.
   ✅ `_("Container {0} added").format(no)` — one source, interpolation.

3. **Translating item names.** Cardinal rule. If you find yourself adding an Item name to `th.csv` or `pos-translations.js`, stop.

4. **Trailing-space drift.** `_("Save ")` and `_("Save")` are different keys to the extractor. Strip trailing spaces.

5. **DocType label changes after CSV exists.** If you rename a field label from "Weight" to "Weight (kg)", the old `th.csv` row still says "Weight". Re-run `bench update-translations` and add the new row.

6. **Mixed casing.** `_("Save")` and `_("save")` are two different rows. Be consistent.

7. **Missed `_()` wraps in messages.**
   ❌ `frappe.throw("Container is required")` — never translates.
   ✅ `frappe.throw(_("Container is required"))`

8. **Translating an interpolated value inside a message.**
   ❌ `_("Container is for grade {0}").format(_(item_name))` — runs item_name through translations. Wrong.
   ✅ `_("Container is for grade {0}").format(item_name)` — message translated, item name verbatim.

9. **Forgetting to reload after editing th.csv.** Edits don't take effect without `bench --site <site> clear-cache`. Worse: a stale browser cache shows old translations even after server reload.

10. **Loading order in custom UI.** `pos-translations.js` must load BEFORE any module that calls `t('...')`. Check `hooks.py web_include_js` order.

---

## 9. Testing checklist (per feature)

Before shipping a new feature with user-visible text:

- [ ] Switch a test user's language to Thai (User → Settings → Language → Thai).
- [ ] Visit every screen the feature touches; confirm every label/button/message renders Thai.
- [ ] Switch back to English; confirm all render English.
- [ ] Trigger every error path; confirm Thai messages.
- [ ] Confirm item names render canonical Thai under BOTH user languages (the rule).
- [ ] Print a representative sticker / receipt; confirm bilingual side-by-side renders correctly.
- [ ] Print a representative A4 (dropoff summary, PO, etc.); confirm bilingual layout.
- [ ] Verify date / number formatting renders sanely in Thai (e.g. "1,234.5 kg" not "1.234,5 kg" — site setting).
- [ ] Spot-check that no English fallback leaks (search for source strings in rendered HTML).

---

## 10. Container redesign — translation to-do

Specific tasks to ship the redesign with bilingual support.

### Layer A — `translations/th.csv`

Add (or verify existing) rows for:

- All field labels of `Scrap Weight Container` doctype (Container Number, Net Weight, Container Type, Operator, Scale, Session, Item Code, Status, Is Deviation, Deviation Type, Deviation Reason, Approved By, Approved At, Voided Reason, Reweigh Reason, etc.)
- All field labels of `Container Weight History` (Recorded At, Recorded By, Event, Reason, Entry Method)
- All field labels of `Dropoff Container Settings` (the threshold + flag fields)
- All NEW field labels added to `Dropoff` (Weighing Session, Weighing Scale, Paused At, Pause Reason, Resumed At, Reassigned At, Reassign Reason, Container Count, Deviation Container Count, Has Unapproved Deviation, etc.)
- New status enum values: `Paused`
- New container status enum: `Active`, `Reweighed`, `Voided`
- All `_(...)` messages in:
  - `Scrap Weight Container` controller
  - `Dropoff` updated controller (lock validation, pause/resume errors, verification override messages)
  - `api/v1/dropoff.py` new endpoints (`add_container`, `reweigh_container`, `void_container`, `pause_dropoff`, `resume_dropoff`, `switch_scale`, `reassign_dropoff`, `void_dropoff_weighing`, `complete_dropoff`, `approve_container_deviation`, `verify_dropoff`)

Estimate: ~35–45 new rows.

### Layer B — `pos-translations.js` (or new `container-translations.js`)

Suggest creating `scrap_metal_suite/public/js/container-translations.js` that uses `POS_I18N.extend({...})`, mirroring the `production-translations.js` pattern.

Keys to add (en + th):

```text
container, new_container, edit_container, void_container, reweigh
container_no, container_type, container_count, weight_history
bag, bin, pallet, other
net_weight, tare_weight, gross_weight, total_weight, indicated_weight
grade, scale, session, operator
status_active, status_reweighed, status_voided, status_paused, status_in_progress, status_completed, status_needs_review
action_save, action_cancel, action_pause, action_resume, action_complete, action_switch_scale, action_reassign, action_approve, action_void, action_scan
action_print, action_reprint, action_print_thermal, action_print_sticker, action_print_all_thermal, action_print_all_stickers
action_approve_deviation, action_mark_verified, action_override_verification
prompt_deviation_reason, prompt_deviation_type, prompt_reweigh_reason, prompt_pause_reason, prompt_void_reason, prompt_switch_scale_reason
deviation, downgrade, upgrade, substitution, unplanned_add, deviation_warning, deviation_approval_required
error_locked_session, error_scale_mismatch, error_weight_invalid, error_weight_exceeds_capacity, error_grade_not_expected, error_reason_required
sticker_printed, container_added, container_reweighed, container_voided, dropoff_paused, dropoff_resumed, scale_switched, session_reassigned
```

Estimate: ~50–60 keys × 2 languages = ~110 entries.

Wire it up in `hooks.py`:

```python
web_include_js = [
    # ... existing ...
    "/assets/scrap_metal_suite/js/pos-translations.js",
    "/assets/scrap_metal_suite/js/container-translations.js",  # NEW, after pos-translations
]
```

### Print formats

- **NEW** `Scrap Weight Container Thermal` — bilingual labels per §4.4 above. Item name canonical Thai only.
- **MODIFIED** `ใบคิวสองภาษา` — replace the actual_items section's column headers with bilingual versions; replace per-row scrap-weight rows with per-grade summary rows; add a deviation callout section.

### QA pass

- [ ] Run through §9 testing checklist with the new container flows
- [ ] Confirm all NEW DocType fields show Thai labels in desk
- [ ] Confirm all NEW truck terminal buttons show Thai when user language is Thai
- [ ] Confirm container sticker renders correctly with bilingual labels + canonical Thai item name
- [ ] Confirm dropoff summary renders correctly with new aggregations
- [ ] Confirm `bench update-translations` finds all the new `_(...)` calls

---

## 11. Reference

- Frappe translations docs: <https://frappeframework.com/docs/v15/user/en/translations>
- Frappe `_()` helper: `from frappe import _` (Python), `frappe._` or `__` (JS)
- Frappe `qr_src` Jinja filter: built-in, generates inline SVG QR
- Existing files to mirror:
  - [`scrap_metal_suite/translations/th.csv`](../scrap_metal_suite/translations/th.csv)
  - [`scrap_metal_suite/public/js/pos-translations.js`](../scrap_metal_suite/public/js/pos-translations.js)
  - [`scrap_metal_suite/public/js/production-translations.js`](../scrap_metal_suite/public/js/production-translations.js) — extend pattern
  - [`scrap_metal_suite/fixtures/print_format.json`](../scrap_metal_suite/fixtures/print_format.json) — bilingual print template examples
