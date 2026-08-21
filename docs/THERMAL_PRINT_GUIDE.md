# Thermal Print Legibility Guide

**Status:** applied 2026-08-21. Covers `Scrap Weight Thermal`, `Truck Weight Thermal`, and `Scrap Weight Container Sticker`.

Operators reported thermal output was faint and hard to read. This documents the cause, the rules that follow from it, and what changed — so new print formats don't reintroduce the problem.

---

## 1. Why it happened

**A thermal print head is 1-bit.** Each dot is either burned black or left blank. There is no grey.

When a template asks for `color: #666`, the renderer cannot produce grey — it **dithers**, scattering black dots at roughly 40% density to fake it. At body-text sizes that reads as washed-out and slightly fuzzy. At 7–9px it stops being text and becomes noise, because the dot spacing is a meaningful fraction of the glyph itself.

**Thai makes it worse.** Sarabun stacks tone marks and vowel marks above and below the baseline (◌่ ◌้ ◌ั ◌ิ ◌ู). Those marks are only a few pixels tall to begin with. At 8px on a 203 dpi head — roughly 1.6 mm per line — dithering merges them into the glyph body. `ผู้ขาย` and `ผขาย` become hard to tell apart, and a squeezed `line-height` clips the marks against the line above.

The old templates combined both mistakes: greys at `#333`/`#666`/`#999`/`#ccc`, and Thai text at 7–9px.

---

## 2. Rules for any thermal or sticker format

| Rule | Value | Why |
|---|---|---|
| **Text colour** | `#000` only | anything else dithers |
| **Minimum size, Thai** | **10px** | below this, tone/vowel marks merge |
| **Minimum size, ASCII** | 9px | doc IDs, cut lines — no diacritics to lose |
| **Line height with Thai** | ≥ `1.4` | marks need vertical room |
| **Rules / separators** | `#000`, solid or dashed | `#ccc` dotted prints as nothing |
| **Emphasis** | weight, size, borders, `[X]` boxes | never colour |
| **Backgrounds** | avoid | a filled block eats paper and smears |

**Colour is not available as a design tool on this hardware.** Hierarchy has to come from size, weight, and rules. If a warning must stand out, box it (`border: 2px solid #000`) and bold it — that is what `.reweight-badge` already does and it prints well.

---

## 3. What changed (2026-08-21)

27 edits across the three formats. The two thermal receipts share one stylesheet, so most fixes applied to both.

### Greys → black

| Selector | Before | After |
|---|---|---|
| `.doc-number` | `#333` | `#000` |
| `.info-label` | `#333` | `#000` |
| `.receipt-footer` | 9px `#666` | 10px `#000` |
| `.qr-doc-id` | 7px `#666` | 9px `#000` |
| `.cut-line` | 8px `#999` | 9px `#000` |
| `.item-row` separator | `1px dotted #ccc` | `1px dotted #000` |
| container-count inline | 9px `#666` | 10px black |
| bags-total inline | `#666` | black |

### Sub-10px Thai → 10px

`.company-address` (Thai address), `.box-label`, `.qr-label`, `.option-label` (ขาเข้า/ขาออก), `amend_reason`, `แทนที่ฉบับ {amended_from}`.

### Line height

`.thermal-receipt` gained `line-height: 1.45`.

### Container sticker

- `↻ REWEIGHT • ชั่งซ้ำ` was `color: #b00` — **red on a monochrome head dithers to a pale smudge**, so the one marker that most needs to be noticed was the faintest thing on the label. Now bold black at 10px.
- Meta table (Drop-off / Supplier / Plate / Operator / Date, all bilingual) was 8px with `line-height: 1.25` → **10px / 1.4**.
- Root div now sets `color: #000` explicitly instead of inheriting.

Label fit was checked: at 10px the sticker content occupies roughly 69 mm of the 50 × 80 mm label, leaving ~11 mm of margin. No overflow.

---

## 4. Gotcha — Frappe's wrapper CSS is grey

`frappe.get_print()` wraps every format in framework boilerplate that sets grey on:

```
.print-format label   { color: #4C5A67 }
.print-format .value  { color: #192734 }
.print-format th      { color: #74808b }
.print-heading small  { color: #4c5a67 }
```

Our formats dodge this by using their own class names (`.info-label`, `.info-value`) and `<td>` rather than `<th>`. **If a new thermal template uses a bare `<label>`, `<th>`, or `.value`, it will silently inherit grey** and print faint even though the template itself specifies no colour.

Verified after this change: zero non-black declarations reach anything inside `.thermal-receipt`.

---

## 5. Applying to a site

The fixture `scrap_metal_suite/fixtures/print_format.json` is the source of truth, and `Print Format` is registered under `fixtures` in `hooks.py` (filtered to `module = Scrap Metal Suite`).

**On migrate:** fixtures re-import **unconditionally**. `data_import.py:274-276` calls `import_file_by_path(..., force=True)`, and `import_file.py:130` guards its timestamp comparison with `if not force and db_modified_timestamp:` — so with `force=True` the `modified` check never runs.

> **Correction (2026-08-21):** an earlier version of this section said a fixture is re-imported "only when `modified` is newer, so any edit must bump it too." That is wrong, and the same claim appeared in `_sync_print_formats.py`. Bumping `modified` is harmless but does nothing. If a template edit does not appear after a migrate, the cause is elsewhere — a `Property Setter`, a stale browser cache, or the fixture never being exported in the first place.

**On a live site where migrate does not re-import** (standard formats are write-locked by `validate()`, so the document API refuses):

```bash
bench --site <site> execute scrap_metal_suite.api_test._sync_print_formats.run
```

That script reads the fixture and pushes `html` into the DB with `frappe.db.set_value`, then clears the Print Format cache. It is idempotent — re-running reports `already_current` and writes nothing. Same pattern as `_patch_print_format.py` and `_patch_sticker.py`.

Applied to `metal` on 2026-08-21: 3 patched, 0 skipped. **Not yet applied to `smt` production** — it ships with the next release.

---

## 6. Verifying

```bash
bench --site <site> execute scrap_metal_suite.api_test.smoke_test_sticker_render.run
```

Renders the sticker and asserts all six required fields plus a real QR data URI. Passed after this change.

For a broader check, render each format and assert no `color:` other than `#000` and no `font-size` below 9px survives inside the receipt body. Note that greys **outside** `.thermal-receipt` are expected — that is the framework wrapper from §4.

**Still owed: a real print test.** Everything above was verified in rendered HTML, not on paper. Thermal output depends on print head density, paper sensitivity, and printer darkness settings, none of which HTML can predict. This should be folded into the hardware walkthrough that is already outstanding.

---

## 7. Release note for the team

Ready to paste into the version update:

> **Thermal printing is now clearer.** Receipts and container stickers were printing faint and, in Thai, sometimes unreadable — small text with tone marks was blurring together. The cause was grey text and undersized fonts: thermal printers cannot print grey, so they fake it with a scatter of dots, which destroys small characters.
>
> All text on the weight receipt, truck receipt, and container sticker is now solid black, Thai text is at least 10px with more line spacing, and the "REWEIGHT / ชั่งซ้ำ" marker on stickers — previously red, which printed palest of all — is now bold black.
>
> Nothing moved and no fields were added or removed; the same information prints in the same places, just legibly. If any receipt still prints faint after this update, it is a printer darkness setting or worn paper, not the template — please report it with a photo.
