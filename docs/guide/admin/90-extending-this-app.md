# Extending This App — Developer Reference

> **Status:** Production
> **Source:** repo conventions observed across `api/v1/`, `scrap_metal_suite/doctype/`, `www/`, `fixtures/`, `patches/`
> **Last verified:** 2026-08-21

How to add a module without breaking the patterns the rest of the app relies on — and how to keep this documentation current as you go.

---

## 1. Before writing code

Answer these first. Each one has bitten this codebase at least once.

| Question | Why it matters |
|---|---|
| Does an existing DocType already model this? | 40 exist. `Dropoff`, `POS Order` and `SMT Purchase Order` all overlap conceptually; adding a fourth "order" would compound that. |
| Does it need submit/cancel/amend? | Submittable is the audit spine here. If the document is a record of something that happened and must not be silently edited, make it submittable and accept the amend workflow. |
| Which role does the work? | Determines the auth guard, the DocType permissions, and whether a terminal or the desk is the right surface. |
| Does it touch hardware? | Scales, scanners and printers force a terminal page and WebSerial constraints — see [00 §7](00-architecture.md). |
| Does it need a data migration? | Anything that changes existing rows needs a patch, and a dry-run against a production snapshot before deploy. |

---

## 2. The checklist

### 2.1 DocType

```
scrap_metal_suite/doctype/<snake_name>/
├── __init__.py
├── <snake_name>.json          schema
├── <snake_name>.py            controller
├── <snake_name>.js            desk form behaviour (optional)
└── test_<snake_name>.py       unit tests
```

- **Naming series** — follow the existing convention. Dated series use `YYMM`, not `YYYY` (`CTN-.YY.MM.-.#####`). If a series does not take effect, look for a `Property Setter` overriding it (see §5).
- **Child tables** get `"istable": 1` and are never linked directly.
- **Settings** go in a `Single` doctype named `<Module> Settings`, matching `Dropoff Container Settings` and `Production Sorting Settings`.
- Put validation in the controller's `validate()`, not in the API layer. The API is one caller among several — the desk is another.

### 2.2 API

Add to an existing `api/v1/*.py` if it fits the subsystem, or create a new module.

```python
@frappe.whitelist()
def do_the_thing(dropoff, weight):
    """One line on what it does.

    Args / Returns, and any side effect that is not obvious from the name.
    """
    check_pos_operator()          # Layer 1 — always first
    ...
    doc.insert(ignore_permissions=True)   # correct AFTER a guard; see 00 §6
```

Rules the rest of the app follows:

- **Guard first, always.** `check_pos_operator()` / `check_production_operator()` from `api/v1/auth.py`.
- `ignore_permissions=True` after a guard is deliberate, not a shortcut — terminal roles intentionally lack blanket create rights.
- Return plain dicts, not Documents. Terminals consume JSON.
- Never trust a client-supplied weight without validating it against the scale's `max_capacity_kg`.
- Coerce booleans from the client explicitly — everything arrives as a string.

### 2.3 Terminal page (only if it needs one)

```
www/<area>/<page>.html      template, extends templates/web.html
www/<area>/<page>.py        get_context, no_cache = 1
```

Copy the structural conventions from `www/pos/terminal.py`:

- `no_cache = 1` so the HTML is never cached
- Set `context.error` and **return** on a bad precondition — do not raise
- Guard the whole inline `<script>` block with `{% if not error %}`. The markup is inside `{% if error %}`, but a script block outside it will still render and dereference undefined context, producing an HTTP 417 instead of your error page. This has happened twice.
- Version your asset URLs: `?v={{ asset_v }}`, backed by a `get_asset_version()` that reads file mtimes — see [60 §Asset caching](60-deployment-operations.md)

### 2.4 CSS

- **Prefix every custom property `--pos-`.** Frappe defines `--card-bg`, `--text-muted`, `--success`, `--warning` and more at `:root` on every www page. An unprefixed `var(--card-bg, #1e293b)` silently resolves to Frappe's Bootstrap value and your fallback never runs.
- **Use the slate palette**, not gray. `#0f172a` page, `#1e293b` surface, `#334155` border, `#e2e8f0` text, `#94a3b8` muted. Mixing Tailwind gray into slate reads as muddy.
- Verify with `getComputedStyle(document.documentElement).getPropertyValue('--yourtoken')` — a non-empty result means the name is already taken.

Full reasoning in [UI_TERMINAL_UNIFORMITY_PLAN.md §1a](../../UI_TERMINAL_UNIFORMITY_PLAN.md).

### 2.5 Translations

```js
POS_I18N.extend('en', { my_key: 'My Label' });
POS_I18N.extend('th', { my_key: 'ป้ายของฉัน' });
```

Load after `pos-translations.js`. Mark up with `data-i18n="my_key"`.

**Never add an item name as a translation key.** Item names are canonical Thai and are rendered verbatim from `item.item_name`.

### 2.6 Print formats

Source of truth is `fixtures/print_format.json`, not the database.

1. Edit the fixture's `html`
2. Run `bench --site <site> migrate` — fixtures re-import **unconditionally**, so no `modified` bump is needed (`data_import.py:274-276` passes `force=True`; `import_file.py:130` skips the timestamp check when forced)
3. Or, to update templates without a full migrate: `bench --site <site> execute scrap_metal_suite.api_test._sync_print_formats.run`

**Watch the fixture filters.** `hooks.py` declares `{"dt": "Scale"}` with **no filter**, so `bench export-fixtures` sweeps up every Scale row on whatever site you run it on — including `_TEST_*` scales — and installing the app then creates them elsewhere. Add a filter before running export, or hand-prune the result. `Custom Field` and `Print Format` are correctly filtered to the module.

For thermal output follow [40 — Printing](40-printing.md): solid `#000` only, 10px floor for Thai, no greys.

### 2.7 Migrations

```
scrap_metal_suite/patches/v2_0/<patch_name>.py    with def execute()
```

Register in `patches.txt` under `[post_model_sync]`. Requirements:

- **Idempotent.** It will be re-run.
- **Logs a pre-flight count** before mutating anything.
- **Verifies after** — compare aggregates before and after and log a warning on drift rather than crashing mid-migration.
- **Dry-run against a restored production snapshot** before deploy. Local fixtures have never seen the shapes a year of real data produces. This is the actual deploy gate.

### 2.8 Tests

| Kind | Where | Run |
|---|---|---|
| Controller unit | `doctype/<name>/test_<name>.py` | `bench --site metal run-tests --doctype "<Name>"` |
| API / integration | `api_test/test_<thing>.py` with a `run()` | `bench --site metal execute scrap_metal_suite.api_test.test_<thing>.run` |
| Browser | `ui_test/test_<thing>.py` | `SMT_UI_HEADLESS=1 SMT_UI_ADMIN_PWD=… env/bin/pytest apps/scrap_metal_suite/scrap_metal_suite/ui_test/ -q` |

Add to `api_test/test_e2e_full_flow.py` if your module is part of the main receiving path — that suite is the permanent regression lane.

Browser-test gotchas that will cost you an hour otherwise: `POS_SCANNER` is a top-level `const`, not on `window`; `CONTAINER_UI` **is** on `window`; `containerState` is closure-private and unreachable from `page.evaluate` — assert against the DOM or the API instead. Dropoff fixtures must include `orders=[{"pos_order": …}]` or they throw "POS Order Required". Details in [70 — Testing](70-testing.md).

---

## 3. Documenting it

**Same commit as the code.** A guide that lies is worse than no guide, because the reader acts on it.

1. `cp docs/guide/TEMPLATE-user.md docs/guide/user/NN-<module>.md`
2. `cp docs/guide/TEMPLATE-admin.md docs/guide/admin/NN-<module>.md`
3. Pick `NN` from the range table in [README](../README.md) — leave gaps
4. Add one row to each table in the README
5. Fill both files, obeying their header comments:
   - **user/** is bilingual, Thai first, task-shaped, with numbered walkthroughs carrying real values
   - **admin/** is English, reference-shaped, every behavioural claim cited `path:line`
6. Mark anything you did not verify `⚠️ UNVERIFIED — reason`
7. If it is not production-ready, say so in the status banner of **both** files

Nothing else needs restructuring. That is the point of the numbering.

---

## 4. Definition of done

- [ ] DocType JSON, controller, and unit tests
- [ ] API endpoints guarded, documented, returning plain dicts
- [ ] Permissions set on the DocType for every role that touches it
- [ ] Terminal page (if any) handles the error path without a 500
- [ ] CSS tokens `--pos-` prefixed, slate palette
- [ ] Strings translated both ways; item names left alone
- [ ] Print formats in the fixture with `modified` bumped
- [ ] Migration patch idempotent, and dry-run on a production snapshot
- [ ] Tests added, and the E2E lane still green
- [ ] `user/NN-*.md` and `admin/NN-*.md` written and linked from the README
- [ ] Status banners honest about maturity

---

## 5. Traps this codebase has already hit

Each cost real time. They are listed here so the next person recognises the symptom.

| Trap | Symptom | Cause |
|---|---|---|
| Frappe CSS variable collision | A dark-theme panel renders white | `--card-bg` is defined by Frappe as white; your fallback never runs |
| Property Setter override | A naming-series change in JSON has no effect | A `Property Setter` row overrides the JSON. Check `frappe.get_all("Property Setter", filters={"doc_type": …, "field_name": "naming_series"})` |
| Orphaned DB column | A query "works" but matches nothing | A field removed from the doctype leaves its column behind in MariaDB, silently full of NULLs |
| Unversioned assets | A deploy appears not to take effect | Browsers cache `/assets/…` for 12 hours; no server-side command evicts them |
| Script outside the error guard | HTTP 417 instead of an error page | The `<script>` block sits outside `{% if error %}` and dereferences undefined context |
| Write-locked print formats | Edits to a standard format silently refused | `validate()` blocks it; use `frappe.db.set_value` or the sync script |
| Removed fields still written | An insert fails with a misleading naming error | Code writes fields deleted in a redesign; the failure surfaces somewhere unrelated |
| **A JSON field default kills a fallback** | A Settings knob saves fine and changes nothing | Frappe applies field defaults at document creation, **before `validate()`**. So `if not self.x: self.x = <setting>` is unreachable whenever `x` has a `"default"` in the doctype JSON. Cost months on `variance_threshold_percent`. |

### The fallback trap, in both its forms

Two bugs this codebase has hit are the same bug wearing different clothes: **a fallback that never fires because the value is always set.**

```python
# Python — dead if the field has a JSON "default"
threshold = flt(self.variance_threshold_percent)
if not threshold:
    threshold = get_single_value("Production Sorting Settings", ...)
```

```css
/* CSS — dead because Frappe defines --card-bg at :root */
background: var(--card-bg, #1e293b);
```

Both read as correct in review. Neither errors. Both silently use the wrong value.

**Before relying on any fallback, prove the "unset" case actually occurs:**

- Python/Frappe — `frappe.get_meta(dt).get_field(f).default` must be empty
- CSS — `getComputedStyle(document.documentElement).getPropertyValue('--token')` must be empty

And when you fix one, **add a test that fails if the default comes back** — `api_test/test_variance_threshold.py` is the worked example. It was verified by reintroducing the bug and confirming 4 of its 5 checks fail.

---

## ⚠️ Never name a doctype so its table contains a SQL keyword

> **Found the hard way:** 2026-08-27, on production, an hour after a deploy.

Every desk page carrying a `Dropoff` shortcut showed:

> *Use of sub-query or function is restricted*

Nothing in this app caused it. Frappe's injection guard
(`frappe/model/db_query.py`, `sanitize_fields`) takes the text after `count(`,
splits on the first space, and asks whether that token **contains** a
blacklisted SQL keyword:

```python
field  = "count(`tabDropoff`.name) as total_count"
token  = "`tabdropoff"
"drop" in "`tabdropoff"   # True  ->  frappe.throw(...)
```

The doctype is called **Dropoff**. `tabDropoff` contains `drop`. A row count
reads as a `DROP TABLE`.

**The blacklist:** `select`, `create`, `insert`, `delete`, `drop`, `update`,
`case`, `show`. A doctype named *Showroom*, *Case Study*, *Update Log* or
*Insertion Point* hits the same wall.

**Check before you name one:**

```python
token = ("`tab" + doctype.lower()).split(" ", 1)[0]
[k for k in ["select","create","insert","delete","drop","update","case","show"]
 if k in token]        # must be empty
```

Only the *first word* matters — the token is split on the first space. So
`Dropoff Final` trips (`tabdropoff`) while `Scrap Weight Container` is fine
(`tabscrap`).

### Where it surfaces, and where it does not

The count is requested client-side, in `shortcut_widget.js`:

```js
let filters = frappe.utils.process_filter_expression(this.stats_filter);
if (this.type == "DocType" && this.doc_view != "New" && filters) { …count… }
```

`stats_filter` is stored as `'[]'` — an empty array, which is **truthy in
JavaScript** — so the count fires for every DocType shortcut. Clearing
`stats_filter` makes the condition false and the request is never made.

Two traps when diagnosing this:

- **`frappe.client.get_count` succeeds** where the desk fails. The browser calls
  `frappe.desk.reportview.get_count`, which is the one that builds the
  `count(...)` field. Testing the wrong one says everything is fine.
- **`List View Settings.disable_count` does not help.** The workspace shortcut
  never consults it.

`patches/v2_0/fix_dropoff_shortcut_counts.py` clears `stats_filter` on exactly
the shortcuts whose target trips the guard, and leaves every other count alone.

**Renaming the doctype is not the fix** — 617 live records, every reference and
every URL. Losing a number badge is the cheaper trade.
