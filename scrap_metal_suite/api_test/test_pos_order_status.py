"""Regression test: POS Order.status must track fulfilment as weight is allocated.

Background — this bug was live in production and had no test.

`Dropoff.allocate_weights_if_completed` -> `_recalculate_order_fulfillment`
saves each POS Order with `flags.ignore_validate = True`. That skips
`POSOrder.validate()`, and with it `update_status()`. So `status` never left
"Pending" however much weight was allocated, while `fulfillment_status` sat
right beside it correctly reading "Partial" or "Fulfilled". Anyone reading
`status` to decide whether an order was done got the wrong answer.

The flag is deliberate and stays: this runs inside `Dropoff.before_save` during
bulk allocation, and a future validation that threw would abort the whole
Dropoff save. The fix calls `update_status()` explicitly instead.

This test drives the REAL path — Price Lock -> POS Order -> two Drop-offs, each
weighed and completed — rather than calling `update_status()` directly, because
calling it directly would pass even with the bug present.

Two drop-offs against one order, so both transitions are exercised:
    40 kg of 100  -> Processing / Partial
   100 kg of 100  -> Processed  / Fulfilled

    bench --site <site> execute scrap_metal_suite.api_test.test_pos_order_status.run
"""

import frappe
from frappe.utils import flt

from scrap_metal_suite.api_test import test_container_workflow as wf
from scrap_metal_suite.api.v1 import dropoff as dapi

RESULTS = []
PREFIX = wf.TEST_PREFIX


def _check(label, ok, detail=""):
    RESULTS.append((label, bool(ok), detail))
    marker = "OK " if ok else "X  "
    suffix = f"  ({detail})" if detail else ""
    print(f"  {marker}{label}{suffix}")


def _weigh_and_complete(dropoff, session, item_code, kg, gross, tare):
    """Add one bag, issue the receipt, and complete the drop-off."""
    frappe.set_user(wf.TEST_OPERATOR)
    res = dapi.add_container(
        dropoff=dropoff.name,
        session=session,
        item_code=item_code,
        net_weight=kg,
        container_type="Bag",
        entry_method="Manual Entry",
    )
    assert res.get("success") is True, f"add_container failed: {res}"

    dapi.finish_weighing_session(dropoff=dropoff.name)

    frappe.set_user("Administrator")
    do = frappe.get_doc("Dropoff", dropoff.name)
    do.gross_weight = gross
    do.tare_weight = tare
    do.save(ignore_permissions=True)

    frappe.set_user(wf.TEST_OPERATOR)
    dapi.complete_dropoff(dropoff=dropoff.name)
    frappe.set_user("Administrator")


def _order_state(po_name):
    frappe.db.commit()
    o = frappe.get_doc("POS Order", po_name)
    return o.status, o.fulfillment_status, flt(o.total_received), flt(o.contracted_weight)


def run(cleanup_first=True, cleanup_after=True):
    RESULTS.clear()
    print("=" * 70)
    print("POS ORDER STATUS REGRESSION TEST")
    print("=" * 70)

    if cleanup_first:
        wf.cleanup_test_data()

    try:
        frappe.set_user("Administrator")
        wf.ensure_user(wf.TEST_OPERATOR, ["POS Operator", "System Manager"])
        item = wf.ensure_item(wf.THAI_ITEM_PRIMARY)
        supplier = wf.ensure_supplier()
        scale = wf.ensure_scale()
        profile = wf.ensure_pos_profile()
        session = wf.open_pos_session(profile, scale, wf.TEST_OPERATOR)

        # Lock 100 kg, which auto-creates the POS Order.
        _, po_name = wf.make_price_lock(supplier, [(item, 100.0, 50.0)])

        status, fulfil, received, contracted = _order_state(po_name)
        _check("fresh order is Pending / Pending",
               status == "Pending" and fulfil == "Pending",
               f"status={status} fulfillment={fulfil} contracted={contracted}")

        # ---- Drop-off 1: 40 of 100 kg -> partial ----
        do1 = wf.make_dropoff(supplier, [(item, 100.0)], po_name)
        _weigh_and_complete(do1, session, item, 40.0, 3000, 2960)

        status, fulfil, received, contracted = _order_state(po_name)
        _check("after 40/100 kg: status == Processing", status == "Processing",
               f"status={status} received={received}")
        _check("after 40/100 kg: fulfillment == Partial", fulfil == "Partial",
               f"fulfillment={fulfil}")
        _check("status and fulfillment agree (partial)",
               status == "Processing" and fulfil == "Partial",
               f"{status} / {fulfil}")

        # ---- Drop-off 2: the remaining 60 kg -> fulfilled ----
        do2 = wf.make_dropoff(supplier, [(item, 100.0)], po_name)
        _weigh_and_complete(do2, session, item, 60.0, 3000, 2940)

        status, fulfil, received, contracted = _order_state(po_name)
        _check("after 100/100 kg: status == Processed", status == "Processed",
               f"status={status} received={received}")
        _check("after 100/100 kg: fulfillment == Fulfilled", fulfil == "Fulfilled",
               f"fulfillment={fulfil}")
        _check("status and fulfillment agree (fulfilled)",
               status == "Processed" and fulfil == "Fulfilled",
               f"{status} / {fulfil}")
        _check("total_received accumulated across both drop-offs",
               abs(received - 100.0) < 0.01, f"received={received}")

    except Exception as exc:  # noqa: BLE001
        _check("test ran to completion", False, f"{type(exc).__name__}: {exc}")
        frappe.log_error(title="test_pos_order_status", message=frappe.get_traceback())
    finally:
        frappe.set_user("Administrator")
        if cleanup_after:
            try:
                wf.cleanup_test_data()
            except Exception:  # noqa: BLE001
                pass

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = len(RESULTS) - passed
    print("-" * 70)
    print(f"  {passed}/{len(RESULTS)} checks passed{', ' + str(failed) + ' FAILED' if failed else ''}")
    print("=" * 70)
    return {"passed": passed, "failed": failed}
