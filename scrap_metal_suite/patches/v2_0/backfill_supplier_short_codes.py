"""Fill in `Supplier.short_code` for suppliers that predate the field.

`short_code` is `reqd` on the Supplier Custom Field and feeds document naming as
`PLO-{short_code}-YYMM-###` (see `overrides/naming.py`). It is populated by the
`populate_short_code` hook on Supplier `validate`/`before_save` — which only
fires when a supplier is *saved*. Every supplier that existed before the field
was introduced therefore has none, and the first Price Lock against one fails:

    Supplier {0} has no Short Code. Open the supplier and set one
    (2-8 ASCII chars) before creating documents that reference it.

On a site with real history that is one failure per supplier, discovered one at
a time by whoever happens to trade with them next. This patch derives the codes
up front, using exactly the same helpers as the hook so the result is identical
to having saved each supplier by hand.

**Deliberately does not invent codes it cannot derive.** A supplier whose name
has fewer than two ASCII alphanumerics — Thai-only names, the common case for
this business — is left blank and listed in the log for a human to fill in. A
short code is a business identifier that gets printed on paper and embedded in
permanent document IDs; guessing a transliteration would be worse than leaving
it obviously absent.

Collisions are resolved by `_free_short_code`, which appends a numeric suffix
(`INFI`, `INFI2`, `INFI3`, ...). Where several suppliers share a prefix the
suffix order is arbitrary, so the log prints every derived code — review it if
the office already uses specific abbreviations.

Idempotent: suppliers that already have a code are skipped untouched.

**Creates the Custom Field itself when it is missing.** Frappe syncs fixtures
*after* post-model-sync patches, so on any site that has never carried this
field — which is every site before this release, production included — the
column does not exist when this patch runs, and the query dies with

    (1054, "Unknown column 'tabSupplier.short_code' in 'WHERE'")

That takes the whole migration down with it: the three patches queued after this
one never execute and `bench migrate` exits on a half-migrated site. Caught by
dry-running against a production backup; it did not show up on the dev bench
only because the field had been created there by an earlier install. A patch
cannot assume its own fixture has landed yet.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from scrap_metal_suite.overrides.supplier import _derive_default, _free_short_code

# Kept in step with fixtures/custom_field.json — see the module docstring for
# why this patch cannot wait for that fixture to be applied.
SHORT_CODE_FIELD = {
    "fieldname": "short_code",
    "fieldtype": "Data",
    "label": "Short Code",
    "insert_after": "supplier_name",
    "length": 8,
    "reqd": 1,
    "unique": 1,
    "description": (
        "2-8 ASCII chars (A-Z, 0-9). Used in document IDs (PLO-{short}-YYMM-###). "
        "Editable, but only affects new documents — existing ones keep their "
        "original names. Auto-defaulted from supplier_name when possible; for "
        "Thai-only names you must type it."
    ),
}


def _ensure_short_code_field():
    """Create `Supplier.short_code` when this site has never had it."""
    if frappe.db.has_column("Supplier", "short_code"):
        return

    print("  Supplier.short_code is missing — creating the Custom Field first")
    create_custom_fields({"Supplier": [SHORT_CODE_FIELD]}, ignore_validate=True)
    frappe.db.commit()
    frappe.clear_cache(doctype="Supplier")


def execute():
    _ensure_short_code_field()

    suppliers = frappe.get_all(
        "Supplier",
        filters=[["short_code", "in", [None, ""]]],
        fields=["name", "supplier_name"],
        order_by="creation asc",
    )

    if not suppliers:
        print("backfill_supplier_short_codes: nothing to do")
        return

    filled = []
    needs_human = []

    for sup in suppliers:
        candidate = _derive_default(sup.supplier_name or "")

        if not candidate:
            needs_human.append(sup)
            continue

        code = _free_short_code(candidate, exclude_supplier=sup.name)

        # db.set_value, not doc.save(): saving a Supplier runs the full ERPNext
        # validation stack, which can fail on unrelated pre-existing data (a
        # missing tax category, a stale address link) and would abort the whole
        # migration for a reason that has nothing to do with short codes.
        frappe.db.set_value("Supplier", sup.name, "short_code", code,
                            update_modified=False)
        filled.append((sup.name, code))

    frappe.db.commit()

    print("backfill_supplier_short_codes: filled %d, needs manual entry %d"
          % (len(filled), len(needs_human)))

    for name, code in filled:
        print("    %-40s -> %s" % (name, code))

    if needs_human:
        print("  The following have no ASCII characters to derive from and are")
        print("  still blank. Set a 2-8 character code on each before raising a")
        print("  Price Lock against them:")
        for sup in needs_human:
            print("    %-40s (%s)" % (sup.name, sup.supplier_name))
