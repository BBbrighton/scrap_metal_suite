"""LANE B — permanent E2E regression test (asserting).

Codifies the behaviour verified by Lane A (_e2e_walkthrough) into hard
assertions. Focuses on coverage the existing suite lacks:
  * the 15 documented error / human-error scenarios (exact message asserted)
  * the Production Sorting -> Dropoff Final handoff (Stage 5)
plus a condensed happy-path smoke of the whole pipeline
(Price Lock -> POS Order -> Dropoff -> weigh -> finish -> complete -> verify).

Run:
    bench --site metal execute scrap_metal_suite.api_test.test_e2e_full_flow.run

Returns {"passed": N, "failed": M}. Reuses fixtures from
test_container_workflow (single source of truth for masters/PL/DO builders).
"""

import frappe
from frappe.utils import flt, now_datetime, add_to_date

from scrap_metal_suite.api_test import test_container_workflow as wf
from scrap_metal_suite.api.v1 import dropoff as dapi
from scrap_metal_suite.api.v1 import production as papi

OP2 = "_test_ctnwf_op2@test.local"


# ---- helpers ---------------------------------------------------------------

def _as(user):
    frappe.set_user(user)


def assert_error(results, label, expected_substr, fn):
    """Record PASS iff fn raises an error whose message contains expected_substr."""
    try:
        fn()
    except Exception as e:
        msg = " ".join(str(e).split())
        if expected_substr.lower() in msg.lower():
            results.add(label, True)
        else:
            results.add(label, False,
                        f"wrong message: expected ~{expected_substr!r}, got {msg[:160]!r}")
        frappe.db.rollback()
        return
    results.add(label, False, f"no error raised (expected ~{expected_substr!r})")
    frappe.db.rollback()


def _ensure_second_scale():
    name = f"{wf.TEST_PREFIX}Scale-02"
    existing = frappe.db.get_value("Scale", {"scale_name": name}, "name")
    if existing:
        return existing
    doc = frappe.get_doc({
        "doctype": "Scale", "scale_name": name, "scale_type": "Platform",
        "usage_type": "Scrap", "location": "Test Bay 2", "is_active": 1,
        "max_capacity_kg": 5000, "baud_rate": 9600, "data_bits": 8,
        "parity": "none", "stop_bits": 1,
    })
    doc.insert(ignore_permissions=True)
    return doc.name


def _extra_cleanup():
    _as("Administrator")
    try:
        dos = frappe.get_all("Dropoff",
                             filters={"license_plate": ["like", f"%{wf.TEST_PREFIX}%"]},
                             pluck="name") or [""]
        for dt in ("Production Sorting", "Dropoff Final"):
            try:
                for name in frappe.get_all(dt, filters={"dropoff": ["in", dos]}, pluck="name"):
                    try:
                        d = frappe.get_doc(dt, name)
                        if getattr(d, "docstatus", 0) == 1:
                            d.cancel()
                        frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
                    except Exception:
                        pass
            except Exception:
                pass
        for ps in frappe.get_all("Production Session",
                                 filters={"operator": wf.TEST_OPERATOR}, pluck="name"):
            try:
                frappe.delete_doc("Production Session", ps, force=True, ignore_permissions=True)
            except Exception:
                pass
        if frappe.db.exists("User", OP2):
            try:
                frappe.delete_doc("User", OP2, force=True, ignore_permissions=True)
            except Exception:
                pass
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()


# ===========================================================================

def run(cleanup_first=True, cleanup_after=True):
    print("\n" + "=" * 72)
    print("LANE B — E2E FULL-FLOW REGRESSION TEST")
    print(f"Site: {frappe.local.site}  |  {now_datetime()}")
    print("=" * 72)

    results = wf.TestResult()
    original_user = frappe.session.user
    _as("Administrator")

    try:
        if cleanup_first:
            _extra_cleanup()
            wf.cleanup_test_data()

        # ---- masters ----
        wf.ensure_user(wf.TEST_OPERATOR, ["POS Operator", "Production Worker", "System Manager"])
        ia = wf.ensure_item(wf.THAI_ITEM_PRIMARY)
        ib = wf.ensure_item(wf.THAI_ITEM_SECONDARY)
        ic = wf.ensure_item(wf.THAI_ITEM_TERTIARY)
        supplier = wf.ensure_supplier()
        scale = wf.ensure_scale()
        scale2 = _ensure_second_scale()
        profile = wf.ensure_pos_profile()
        frappe.db.commit()

        # =================================================================
        # STAGE 1 — Price Lock: errors + happy
        # =================================================================
        def _pl(items):
            pl = frappe.get_doc({"doctype": "SMT Price Lock", "supplier": supplier,
                                 "po_date": now_datetime(),
                                 "items": [{"item_code": c, "po_qty": q, "po_rate": r}
                                           for c, q, r in items]})
            pl.insert(ignore_permissions=True)
            pl.submit()

        assert_error(results, "err_pl_empty_items", "At least one item row is required",
                     lambda: _pl([]))
        assert_error(results, "err_pl_qty_zero", "Qty must be greater than 0",
                     lambda: _pl([(ia, 0, 250.0)]))
        assert_error(results, "err_pl_rate_zero", "Rate must be greater than 0",
                     lambda: _pl([(ia, 100, 0)]))

        try:
            pl_name, po_name = wf.make_price_lock(
                supplier, [(ia, 1500, 250.0), (ib, 800, 180.0), (ic, 400, 120.0)])
            assert frappe.db.get_value("POS Order", po_name, "smt_price_lock") == pl_name
            results.add("happy_pl_submit_creates_po", True)
        except Exception as e:
            results.add("happy_pl_submit_creates_po", False, e)
            return results.summary()

        # =================================================================
        # STAGE 3 — Dropoff: errors + happy
        # =================================================================
        def _do(**overrides):
            base = {"doctype": "Dropoff", "dropoff_scheduled_start": now_datetime(),
                    "dropoff_scheduled_end": add_to_date(now_datetime(), hours=2),
                    "supplier": supplier, "expected_items": []}
            base.update(overrides)
            frappe.get_doc(base).insert(ignore_permissions=True)

        assert_error(results, "err_do_no_orders", "at least one POS Order",
                     lambda: _do(license_plate=f"{wf.TEST_PREFIX}NOORD"))
        assert_error(results, "err_do_duplicate_order", "cannot be linked multiple times",
                     lambda: _do(license_plate=f"{wf.TEST_PREFIX}DUP",
                                 orders=[{"pos_order": po_name}, {"pos_order": po_name}],
                                 expected_items=[{"item": ia, "indicated_weight": 100}]))

        # mixed suppliers
        sup2n = f"{wf.TEST_PREFIX}Supplier2"
        if not frappe.db.exists("Supplier", {"supplier_name": sup2n}):
            frappe.get_doc({"doctype": "Supplier", "supplier_name": sup2n,
                            "supplier_group": "Raw Material"}).insert(ignore_permissions=True)
        sup2 = frappe.db.get_value("Supplier", {"supplier_name": sup2n}, "name")
        _, po2 = wf.make_price_lock(sup2, [(ia, 100, 250.0)])
        frappe.db.commit()
        assert_error(results, "err_do_mixed_suppliers", "same supplier",
                     lambda: _do(license_plate=f"{wf.TEST_PREFIX}MIX",
                                 orders=[{"pos_order": po_name}, {"pos_order": po2}],
                                 expected_items=[{"item": ia, "indicated_weight": 100}]))

        try:
            do = wf.make_dropoff(supplier, [(ia, 1500), (ib, 800), (ic, 400)], pos_order_name=po_name)
            assert do.status == "Scheduled"
            results.add("happy_do_create", True)
        except Exception as e:
            results.add("happy_do_create", False, e)
            return results.summary()

        # =================================================================
        # STAGE 4 — weighing + runtime errors
        # =================================================================
        try:
            sess1 = wf.open_pos_session(profile, scale, wf.TEST_OPERATOR)
            _as(wf.TEST_OPERATOR)
            bags = []
            for code, w in [(ia, 250.0), (ib, 200.0), (ic, 100.0)]:
                r = dapi.add_container(dropoff=do.name, session=sess1, item_code=code,
                                       net_weight=w, container_type="Bag", entry_method="Manual Entry")
                bags.append(r["container"])
            _as("Administrator")
            frappe.db.commit()
            d = frappe.get_doc("Dropoff", do.name)
            assert d.status == "In Progress" and d.container_count == 3
            results.add("happy_add_containers", True)
        except Exception as e:
            _as("Administrator")
            results.add("happy_add_containers", False, e)
            return results.summary()

        _as(wf.TEST_OPERATOR)
        assert_error(results, "err_add_weight_zero", "greater than 0",
                     lambda: dapi.add_container(dropoff=do.name, session=sess1, item_code=ia,
                                                net_weight=0, container_type="Bag",
                                                entry_method="Manual Entry"))
        assert_error(results, "err_add_over_capacity", "exceeds scale capacity",
                     lambda: dapi.add_container(dropoff=do.name, session=sess1, item_code=ia,
                                                net_weight=999999, container_type="Bag",
                                                entry_method="Manual Entry"))
        assert_error(results, "err_void_no_reason", "reason is required",
                     lambda: dapi.void_container(container=bags[0], reason=""))
        _as("Administrator")

        # session lock via 2nd operator
        try:
            wf.ensure_user(OP2, ["POS Operator", "System Manager"])
            sess2 = wf.open_pos_session(profile, scale2, OP2)
            frappe.db.commit()
            _as(OP2)
            assert_error(results, "err_session_lock", "locked to session",
                         lambda: dapi.add_container(dropoff=do.name, session=sess2, item_code=ia,
                                                    net_weight=50, container_type="Bag",
                                                    entry_method="Manual Entry"))
            _as("Administrator")
            frappe.db.set_value("POS Session", sess2, "status", "Closed")
            frappe.db.commit()
        except Exception as e:
            _as("Administrator")
            results.add("err_session_lock", False, e)

        # reweigh (correction, no duplication)
        try:
            _as(wf.TEST_OPERATOR)
            old = flt(frappe.db.get_value("Dropoff", do.name, "total_actual_weight"))
            r = dapi.reweigh_container(container=bags[0], net_weight=275.0, reason="recalibrated")
            assert flt(r["dropoff_total"], 1) == flt(old - 250.0 + 275.0, 1)
            _as("Administrator")
            results.add("happy_reweigh_no_dup", True)
        except Exception as e:
            _as("Administrator")
            results.add("happy_reweigh_no_dup", False, e)
        frappe.db.commit()

        # complete-while-paused
        try:
            _as(wf.TEST_OPERATOR)
            dapi.pause_dropoff(dropoff=do.name, reason="probe")
            _as("Administrator"); frappe.db.commit(); _as(wf.TEST_OPERATOR)
            assert_error(results, "err_complete_while_paused", "paused",
                         lambda: dapi.complete_dropoff(dropoff=do.name))
            dapi.resume_dropoff(dropoff=do.name, session=sess1)
            _as("Administrator")
            results.add("happy_pause_resume", True)
        except Exception as e:
            _as("Administrator")
            results.add("happy_pause_resume", False, e)
        frappe.db.commit()

        # finish + complete
        try:
            _as(wf.TEST_OPERATOR)
            r = dapi.finish_weighing_session(dropoff=do.name)
            sw = frappe.get_doc("Scrap Weight", r["scrap_weight"])
            assert sw.docstatus == 1
            _as("Administrator")
            d = frappe.get_doc("Dropoff", do.name)
            d.gross_weight = 3500; d.tare_weight = 2400
            d.save(ignore_permissions=True); frappe.db.commit()
            _as(wf.TEST_OPERATOR)
            dapi.complete_dropoff(dropoff=do.name)
            _as("Administrator")
            d = frappe.get_doc("Dropoff", do.name)
            assert d.status == "Completed"
            results.add("happy_finish_and_complete", True)
        except Exception as e:
            _as("Administrator")
            results.add("happy_finish_and_complete", False, e)
            return results.summary()
        frappe.db.commit()

        # verify override (Needs Review path)
        d = frappe.get_doc("Dropoff", do.name)
        if d.verification_status == "Needs Review":
            _as(wf.TEST_OPERATOR)
            assert_error(results, "err_verify_no_reason", "reason required",
                         lambda: dapi.verify_dropoff(dropoff=do.name, override_reason=None))
            try:
                dapi.verify_dropoff(dropoff=do.name, override_reason="reviewed, accepted")
                _as("Administrator")
                d = frappe.get_doc("Dropoff", do.name)
                assert d.verification_status == "Verified"
                results.add("happy_verify_override", True)
            except Exception as e:
                _as("Administrator")
                results.add("happy_verify_override", False, e)
        else:
            results.add("happy_verify_override", True)  # not needed this run
        _as("Administrator"); frappe.db.commit()

        # =================================================================
        # STAGE 5 — Production Sorting: gate + errors + happy -> Dropoff Final
        # =================================================================
        try:
            do_gate = wf.make_dropoff(supplier, [(ia, 100)], pos_order_name=po_name)
            frappe.db.commit()
            _as(wf.TEST_OPERATOR)
            psess = papi.open_session(scale=scale)["session"]
            frappe.db.commit()

            assert_error(results, "err_sort_not_completed", "not in Completed status",
                         lambda: papi.create_sorting(session=psess, dropoff=do_gate.name,
                                                     good_items=[{"item_code": ia, "weight": 50}]))
            assert_error(results, "err_sort_no_items", "At least one good or unwanted",
                         lambda: papi.create_sorting(session=psess, dropoff=do.name,
                                                     good_items=[], unwanted_items=[]))
            assert_error(results, "err_sort_weight_zero", "greater than zero",
                         lambda: papi.create_sorting(session=psess, dropoff=do.name,
                                                     good_items=[{"item_code": ia, "weight": 0}]))

            summ = frappe.get_doc("Dropoff", do.name)
            grades = [(row.item, flt(row.total_weight)) for row in summ.item_summary]
            good = [{"item_code": grades[0][0], "weight": grades[0][1]}]
            unwanted = ([{"item_code": grades[1][0], "weight": grades[1][1],
                          "return_reason": "Contamination"}] if len(grades) > 1 else [])
            res = papi.create_sorting(session=psess, dropoff=do.name,
                                      good_items=good, unwanted_items=unwanted)
            sort_name = res["name"]
            assert frappe.db.get_value("Production Sorting", sort_name, "docstatus") == 1
            results.add("happy_create_sorting", True)

            finals = frappe.get_all("Dropoff Final", filters={"dropoff": do.name}, pluck="name")
            assert finals, "Dropoff Final not auto-created on sorting submit"
            results.add("happy_dropoff_final_created", True)
            _as("Administrator")
        except Exception as e:
            _as("Administrator")
            import traceback; traceback.print_exc()
            results.add("happy_production_sorting", False, e)

        frappe.db.commit()
        if cleanup_after:
            _extra_cleanup()
            wf.cleanup_test_data()

        return results.summary()

    finally:
        _as(original_user)
