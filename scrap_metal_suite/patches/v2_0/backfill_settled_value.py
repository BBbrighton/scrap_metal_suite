"""Recompute `SMT Price Lock.total_settled_value` from the item ledger.

`update_settled_qty` mutates `settled_qty` with a raw SQL UPDATE for atomicity,
which never triggers `validate()`. `total_settled_value` was only ever computed
in `calculate_totals()` during validation, so it stayed at its last-validated
figure — 0.00 for every live record — while `status` advanced all the way to
"Fully Settled".

That field prints on ใบยืนยันราคา, the settlement document handed to the
supplier, so the printed value disagreed with the settled weight it was
supposed to represent.

The underlying data was never wrong: the item rows carry correct `settled_qty`
and `po_rate`. Only the parent rollup was stale, so this patch is a pure
recomputation with nothing to reconstruct.

`recompute_status()` now maintains the field going forward
(`smt_price_lock.py`); this patch fixes the records written before that.

Idempotent — re-running recomputes the same values and reports 0 changed.
"""

import frappe
from frappe.utils import flt


def execute():
    locks = frappe.get_all("SMT Price Lock", pluck="name")
    if not locks:
        print("  no SMT Price Lock records — nothing to do")
        return

    changed, unchanged = 0, 0
    report = []

    for name in locks:
        rows = frappe.get_all(
            "SMT Price Lock Item",
            filters={"parent": name},
            fields=["settled_qty", "po_rate"],
        )
        correct = flt(sum(flt(r.settled_qty) * flt(r.po_rate) for r in rows), 2)
        stored = flt(frappe.db.get_value("SMT Price Lock", name, "total_settled_value"))

        if abs(correct - stored) < 0.005:
            unchanged += 1
            continue

        frappe.db.set_value(
            "SMT Price Lock", name, "total_settled_value", correct,
            update_modified=False,
        )
        changed += 1
        report.append(f"{name}: {stored} -> {correct}")

    frappe.db.commit()

    print(f"  recomputed total_settled_value: {changed} corrected, {unchanged} already correct")
    for line in report[:25]:
        print(f"    {line}")
    if len(report) > 25:
        print(f"    … and {len(report) - 25} more")

    if changed:
        frappe.log_error(
            title="backfill_settled_value",
            message="Corrected total_settled_value on {0} Price Lock(s):\n{1}".format(
                changed, "\n".join(report)
            ),
        )
