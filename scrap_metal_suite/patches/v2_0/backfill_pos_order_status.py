"""Recompute `POS Order.status` for orders whose status never advanced.

`Dropoff.allocate_weights_if_completed` -> `_recalculate_order_fulfillment`
saved each POS Order with `flags.ignore_validate = True`, which skips
`POSOrder.validate()` — and therefore `update_status()`. Orders stayed at
"Pending" no matter how much weight was allocated, while `fulfillment_status`
correctly read "Partial" or "Fulfilled" right beside it.

Anyone reading `status` to decide whether an order was done got the wrong
answer; the right answer was in the next column.

`_recalculate_order_fulfillment` now calls `update_status()` explicitly, so new
allocations stay correct. This patch fixes the records written before that.

The underlying figures were never wrong — `total_received` and
`contracted_weight` are both accurate — so this is a pure recomputation using
the same `update_status()` logic the controller uses.

Cancelled orders are left alone: `update_status()` returns early for them by
design, and that is the correct behaviour.

Idempotent — re-running reports 0 changed.
"""

import frappe


def execute():
    names = frappe.get_all("POS Order", pluck="name")
    if not names:
        print("  no POS Orders — nothing to do")
        return

    changed, unchanged, skipped = 0, 0, 0
    report = []

    for name in names:
        doc = frappe.get_doc("POS Order", name)

        if doc.status == "Cancelled":
            skipped += 1
            continue

        before = doc.status
        doc.update_status()
        after = doc.status

        if before == after:
            unchanged += 1
            continue

        frappe.db.set_value("POS Order", name, "status", after, update_modified=False)
        changed += 1
        report.append(
            f"{name}: {before} -> {after} "
            f"(received={doc.total_received}, contracted={doc.contracted_weight})"
        )

    frappe.db.commit()

    print(f"  POS Order status: {changed} corrected, {unchanged} already correct, "
          f"{skipped} cancelled (skipped)")
    for line in report[:25]:
        print(f"    {line}")
    if len(report) > 25:
        print(f"    … and {len(report) - 25} more")

    if changed:
        frappe.log_error(
            title="backfill_pos_order_status",
            message="Corrected status on {0} POS Order(s):\n{1}".format(
                changed, "\n".join(report)
            ),
        )
