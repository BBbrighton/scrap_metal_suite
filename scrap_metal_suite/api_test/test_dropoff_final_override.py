"""Regression test: an out-of-tolerance Dropoff Final must have a way out.

Background — five live records were stranded by this and could never be settled.

`DropoffFinal.auto_complete_if_done` parks a record at "In Progress" when it has
sorted items but `variance_ok` is false. Nothing could move it out: no API, no
desk button, every field read-only, and `dropoff_final.js` calls
`frm.disable_save()`. The only other exit is for the variance to become
acceptable — which for a genuine weight discrepancy it never will. One stranded
record sat at 30% variance.

`DropoffFinal.accept_variance()` is the deliberate human decision that releases
it, mirroring `Dropoff.mark_verified`.

The subtle half is step 5. `set_verification_status` runs on every save and
would drag an overridden record back to "Needs Review", silently undoing the
override and re-stranding the document. That is the check most likely to break
if someone refactors the controller.

    bench --site <site> execute scrap_metal_suite.api_test.test_dropoff_final_override.run
"""

import frappe
from frappe.utils import flt

from scrap_metal_suite.api_test import test_container_workflow as wf
from scrap_metal_suite.api.v1 import production as papi

RESULTS = []


def _check(label, ok, detail=""):
    RESULTS.append((label, bool(ok), detail))
    marker = "OK " if ok else "X  "
    suffix = f"  ({detail})" if detail else ""
    print(f"  {marker}{label}{suffix}")


def _make_out_of_tolerance_final(supplier, item, dropoff_name):
    """A Dropoff Final whose sorted weight misses the declared weight badly.

    100 kg received vs 90 kg sorted = 10% variance against a 0.1% threshold, so
    auto_complete_if_done parks it at "In Progress" — the stuck state.

    `dropoff_total_weight` carries `fetch_from: dropoff.total_actual_weight`, so
    setting it on the Dropoff Final directly is silently overwritten. Seed the
    source instead. Written with db.set_value rather than save() because saving
    the Dropoff would recompute total_actual_weight from its containers, of
    which this fixture deliberately has none — we are testing the Dropoff
    Final's override logic, not Dropoff aggregation.
    """
    frappe.db.set_value("Dropoff", dropoff_name, "total_actual_weight", 100.0)

    doc = frappe.get_doc({
        "doctype": "Dropoff Final",
        "dropoff": dropoff_name,
        "supplier": supplier,
        "status": "Draft",
        "variance_threshold_percent": 0.1,
    })
    doc.append("good_items", {"item_code": item, "weight": 90.0, "uom": "Kg"})
    doc.insert(ignore_permissions=True)
    doc.reload()
    return doc


def run(cleanup_first=True, cleanup_after=True):
    RESULTS.clear()
    print("=" * 70)
    print("DROPOFF FINAL VARIANCE OVERRIDE REGRESSION TEST")
    print("=" * 70)

    if cleanup_first:
        wf.cleanup_test_data()

    try:
        frappe.set_user("Administrator")
        wf.ensure_user(wf.TEST_OPERATOR, ["POS Operator", "Production Worker", "System Manager"])
        item = wf.ensure_item(wf.THAI_ITEM_PRIMARY)
        supplier = wf.ensure_supplier()
        _, po_name = wf.make_price_lock(supplier, [(item, 100.0, 50.0)])
        dropoff = wf.make_dropoff(supplier, [(item, 100.0)], po_name)

        # ---- 1. It really does get stuck ----
        dof = _make_out_of_tolerance_final(supplier, item, dropoff.name)
        _check("out-of-tolerance final parks at In Progress",
               dof.status == "In Progress",
               f"status={dof.status} variance={flt(dof.variance_percent, 2)}%")
        _check("and is flagged Needs Review",
               dof.verification_status == "Needs Review",
               f"verification_status={dof.verification_status}")

        # ---- 2. Re-saving does not free it ----
        dof.save(ignore_permissions=True)
        dof.reload()
        _check("re-saving leaves it stuck (this is the trap)",
               dof.status == "In Progress", f"status={dof.status}")

        # ---- 3. Override demands a reason ----
        try:
            dof.accept_variance(None)
            _check("override without a reason is rejected", False, "no exception raised")
        except frappe.ValidationError as exc:
            _check("override without a reason is rejected",
                   "reason" in str(exc).lower(), str(exc)[:70])

        # ---- 4. Override releases it, through the real API ----
        frappe.set_user(wf.TEST_OPERATOR)
        res = papi.accept_dropoff_final_variance(
            dropoff_final=dof.name,
            override_reason="Moisture loss confirmed by supervisor",
        )
        frappe.set_user("Administrator")
        _check("API reports success", res.get("success") is True, str(res)[:70])

        dof.reload()
        _check("status released to Unsettled", dof.status == "Unsettled", f"status={dof.status}")
        _check("verification_status is Verified",
               dof.verification_status == "Verified", f"={dof.verification_status}")
        _check("audit: variance_overridden set", bool(dof.variance_overridden))
        _check("audit: reason recorded",
               dof.variance_override_reason == "Moisture loss confirmed by supervisor",
               f"={dof.variance_override_reason}")
        _check("audit: who and when recorded",
               bool(dof.variance_override_by) and bool(dof.variance_override_at),
               f"by={dof.variance_override_by} at={dof.variance_override_at}")

        # ---- 5. THE IMPORTANT ONE: a later save must not undo the override ----
        # set_verification_status runs on every save and, without the override
        # guard, would reset this to "Needs Review" and re-strand the document.
        dof.save(ignore_permissions=True)
        dof.reload()
        _check("override survives a subsequent save — status",
               dof.status == "Unsettled", f"status={dof.status}")
        _check("override survives a subsequent save — verification_status",
               dof.verification_status == "Verified",
               f"verification_status={dof.verification_status}")
        _check("variance itself is untouched (we accept it, not hide it)",
               not dof.variance_ok and flt(dof.variance_percent) > 0.1,
               f"variance_ok={dof.variance_ok} pct={flt(dof.variance_percent, 2)}")

        # ---- 6. Idempotent ----
        dof.accept_variance("second attempt")
        dof.reload()
        _check("second override is a no-op, original reason kept",
               dof.variance_override_reason == "Moisture loss confirmed by supervisor",
               f"={dof.variance_override_reason}")

        # ---- 7. Refuses on a settled record ----
        frappe.db.set_value("Dropoff Final", dof.name, "status", "Settled")
        dof.reload()
        try:
            dof.accept_variance("too late")
            _check("override refused once Settled", False, "no exception raised")
        except frappe.ValidationError as exc:
            _check("override refused once Settled", "Settled" in str(exc), str(exc)[:70])

    except Exception as exc:  # noqa: BLE001
        _check("test ran to completion", False, f"{type(exc).__name__}: {exc}")
        frappe.log_error(title="test_dropoff_final_override", message=frappe.get_traceback())
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
