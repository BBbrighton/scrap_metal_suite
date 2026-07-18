"""LANE A — E2E observational walkthrough (throwaway diagnostic).

Drives the FULL receiving flow through the real controllers/APIs, headless:
    Price Lock -> auto POS Order -> Dropoff -> weigh containers -> reweigh/void
    -> finish (Scrap Weight receipt) -> complete -> verify override
    -> Production Sorting -> Dropoff Final

AND probes every documented error scenario from docs/E2E_MANUAL_TEST_SCRIPT.md,
capturing the ACTUAL frappe error text (it observes, it does not assert-fail —
so mismatches surface as FINDINGs instead of aborting the run).

Run:
    bench --site metal execute scrap_metal_suite.api_test._e2e_walkthrough.run

Lane B (test_e2e_full_flow.py) turns the verified behaviour below into hard
assertions integrated with the permanent suite.
"""

import frappe
from frappe.utils import flt, now_datetime, add_to_date

from scrap_metal_suite.api_test import test_container_workflow as wf
from scrap_metal_suite.api.v1 import dropoff as dapi
from scrap_metal_suite.api.v1 import production as papi


# ---- observation recorders -------------------------------------------------

HAPPY = []   # (stage, ok, detail)
ERRORS = []  # (label, verdict, expected, actual)


def _stage(name, ok, detail=""):
    HAPPY.append((name, ok, detail))
    mark = "✓" if ok else "✗ FAIL"
    print(f"  {mark} {name}: {detail}")


def expect_error(label, expected_substr, fn):
    """Run fn expecting a throw containing expected_substr. Observe, never abort."""
    try:
        fn()
    except Exception as e:
        msg = frappe.utils.strip_html(str(e)) if hasattr(frappe.utils, "strip_html") else str(e)
        msg = " ".join(msg.split())
        ok = expected_substr.lower() in msg.lower()
        verdict = "MATCH" if ok else "MISMATCH"
        ERRORS.append((label, verdict, expected_substr, msg[:200]))
        mark = "✓" if ok else "⚠ MISMATCH"
        print(f"  {mark} [{label}] caught: {msg[:150]}")
        frappe.db.rollback()
        return
    # No error raised at all -> finding.
    ERRORS.append((label, "NO_ERROR", expected_substr, "(no exception raised)"))
    print(f"  ⚠ FINDING [{label}]: expected error ~{expected_substr!r} but NONE raised")
    frappe.db.rollback()


def _as(user):
    frappe.set_user(user)


# ---- extra cleanup for downstream docs (Production Sorting / Dropoff Final) --

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
        # secondary operator/supplier used for mixed-supplier + lock probes
        for u in ("_test_ctnwf_op2@test.local",):
            if frappe.db.exists("User", u):
                try:
                    frappe.delete_doc("User", u, force=True, ignore_permissions=True)
                except Exception:
                    pass
        frappe.db.commit()
    except Exception:
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


# ===========================================================================

def run():
    print("\n" + "=" * 72)
    print("LANE A  —  E2E OBSERVATIONAL WALKTHROUGH")
    print(f"Site: {frappe.local.site}  |  {now_datetime()}")
    print("=" * 72)

    _as("Administrator")
    _extra_cleanup()
    wf.cleanup_test_data()

    # ---- master data --------------------------------------------------------
    wf.ensure_user(wf.TEST_OPERATOR, ["POS Operator", "Production Worker", "System Manager"])
    ia = wf.ensure_item(wf.THAI_ITEM_PRIMARY)
    ib = wf.ensure_item(wf.THAI_ITEM_SECONDARY)
    ic = wf.ensure_item(wf.THAI_ITEM_TERTIARY)
    supplier = wf.ensure_supplier()
    scale = wf.ensure_scale()
    scale2 = _ensure_second_scale()
    profile = wf.ensure_pos_profile()
    frappe.db.commit()
    print(f"\n[setup] operator={wf.TEST_OPERATOR}, scale={scale}, scale2={scale2}, supplier={supplier}")

    # =======================================================================
    print("\n--- STAGE 1: PRICE LOCK (errors + happy) ---")
    # 1b error probes
    def _pl(items):
        pl = frappe.get_doc({"doctype": "SMT Price Lock", "supplier": supplier,
                             "po_date": now_datetime(),
                             "items": [{"item_code": c, "po_qty": q, "po_rate": r}
                                       for c, q, r in items]})
        pl.insert(ignore_permissions=True)
        pl.submit()

    expect_error("PL empty items", "At least one item row is required",
                 lambda: _pl([]))
    expect_error("PL qty<=0", "Qty must be greater than 0",
                 lambda: _pl([(ia, 0, 250.0)]))
    expect_error("PL rate<=0", "Rate must be greater than 0",
                 lambda: _pl([(ia, 100, 0)]))

    # 1a happy
    try:
        pl_name, po_name = wf.make_price_lock(supplier, [(ia, 1500, 250.0), (ib, 800, 180.0), (ic, 400, 120.0)])
        _stage("PL submit -> auto POS Order", True, f"{pl_name} -> {po_name}")
    except Exception as e:
        _stage("PL submit -> auto POS Order", False, str(e)); return _summary()

    # =======================================================================
    print("\n--- STAGE 3: DROPOFF (errors + happy) ---")
    # no-orders
    def _do_no_orders():
        # supplier set explicitly so autonaming succeeds and the *validation*
        # (validate_at_least_one_order) is what fires — not the naming guard.
        d = frappe.get_doc({"doctype": "Dropoff", "dropoff_scheduled_start": now_datetime(),
                            "dropoff_scheduled_end": add_to_date(now_datetime(), hours=2),
                            "license_plate": f"{wf.TEST_PREFIX}NOORD", "supplier": supplier,
                            "expected_items": []})
        d.insert(ignore_permissions=True)
    expect_error("DO no linked orders", "at least one POS Order", _do_no_orders)

    # duplicate order
    def _do_dup():
        d = frappe.get_doc({"doctype": "Dropoff", "dropoff_scheduled_start": now_datetime(),
                            "dropoff_scheduled_end": add_to_date(now_datetime(), hours=2),
                            "license_plate": f"{wf.TEST_PREFIX}DUP", "supplier": supplier,
                            "orders": [{"pos_order": po_name}, {"pos_order": po_name}],
                            "expected_items": [{"item": ia, "indicated_weight": 100}]})
        d.insert(ignore_permissions=True)
    expect_error("DO duplicate order", "cannot be linked multiple times", _do_dup)

    # mixed suppliers
    try:
        sup2 = f"{wf.TEST_PREFIX}Supplier2"
        if not frappe.db.exists("Supplier", {"supplier_name": sup2}):
            frappe.get_doc({"doctype": "Supplier", "supplier_name": sup2,
                            "supplier_group": "Raw Material"}).insert(ignore_permissions=True)
        sup2_name = frappe.db.get_value("Supplier", {"supplier_name": sup2}, "name")
        _, po2 = wf.make_price_lock(sup2_name, [(ia, 100, 250.0)])
        frappe.db.commit()
        def _do_mixed():
            d = frappe.get_doc({"doctype": "Dropoff", "dropoff_scheduled_start": now_datetime(),
                                "dropoff_scheduled_end": add_to_date(now_datetime(), hours=2),
                                "license_plate": f"{wf.TEST_PREFIX}MIX", "supplier": supplier,
                                "orders": [{"pos_order": po_name}, {"pos_order": po2}],
                                "expected_items": [{"item": ia, "indicated_weight": 100}]})
            d.insert(ignore_permissions=True)
        expect_error("DO mixed suppliers", "same supplier", _do_mixed)
    except Exception as e:
        ERRORS.append(("DO mixed suppliers", "SETUP_FAIL", "same supplier", str(e)[:200]))
        print(f"  ⚠ [DO mixed suppliers] setup failed: {e}")

    # happy dropoff (main)
    try:
        do_main = wf.make_dropoff(supplier, [(ia, 1500), (ib, 800), (ic, 400)], pos_order_name=po_name)
        _stage("DO create (Scheduled, linked PO)", True, f"{do_main.name} status={do_main.status}")
    except Exception as e:
        _stage("DO create", False, str(e)); return _summary()

    # =======================================================================
    print("\n--- STAGE 4: WEIGH + runtime errors (dropoff_main) ---")
    sess1 = wf.open_pos_session(profile, scale, wf.TEST_OPERATOR)
    _stage("POS session open", True, sess1)

    _as(wf.TEST_OPERATOR)
    bags = []
    try:
        for code, w in [(ia, 250.0), (ib, 200.0), (ic, 100.0)]:
            r = dapi.add_container(dropoff=do_main.name, session=sess1, item_code=code,
                                   net_weight=w, container_type="Bag", entry_method="Manual Entry")
            bags.append(r["container"])
        _stage("add_container x3", True, f"{bags}")
    except Exception as e:
        _as("Administrator"); _stage("add_container x3", False, str(e)); return _summary()
    _as("Administrator"); frappe.db.commit()

    # weight errors
    _as(wf.TEST_OPERATOR)
    expect_error("add weight<=0", "greater than 0",
                 lambda: dapi.add_container(dropoff=do_main.name, session=sess1, item_code=ia,
                                            net_weight=0, container_type="Bag", entry_method="Manual Entry"))
    expect_error("add > scale capacity", "exceeds scale capacity",
                 lambda: dapi.add_container(dropoff=do_main.name, session=sess1, item_code=ia,
                                            net_weight=999999, container_type="Bag", entry_method="Manual Entry"))
    expect_error("void without reason", "reason is required",
                 lambda: dapi.void_container(container=bags[0], reason=""))
    _as("Administrator")

    # session lock: 2nd operator, own session -> add to main dropoff
    try:
        op2 = "_test_ctnwf_op2@test.local"
        wf.ensure_user(op2, ["POS Operator", "System Manager"])
        sess2 = wf.open_pos_session(profile, scale2, op2)
        frappe.db.commit()
        _as(op2)
        expect_error("session lock (2nd operator)", "locked to session",
                     lambda: dapi.add_container(dropoff=do_main.name, session=sess2, item_code=ia,
                                                net_weight=50, container_type="Bag", entry_method="Manual Entry"))
        _as("Administrator")
        frappe.db.set_value("POS Session", sess2, "status", "Closed")
        frappe.db.commit()
    except Exception as e:
        _as("Administrator")
        ERRORS.append(("session lock (2nd operator)", "SETUP_FAIL", "locked to session", str(e)[:200]))
        print(f"  ⚠ [session lock] setup failed: {e}")

    # reweigh (correction) + void (correction)
    _as(wf.TEST_OPERATOR)
    try:
        r = dapi.reweigh_container(container=bags[0], net_weight=275.0, reason="scale recalibrated")
        _stage("reweigh corrects in place", True, f"new total={r.get('dropoff_total')}")
    except Exception as e:
        _stage("reweigh corrects in place", False, str(e))
    try:
        dapi.void_container(container=bags[2], reason="wrong bag, removed")
        _stage("void with reason", True, f"{bags[2]} voided")
    except Exception as e:
        _stage("void with reason", False, str(e))
    _as("Administrator"); frappe.db.commit()

    # complete-while-paused
    _as(wf.TEST_OPERATOR)
    try:
        dapi.pause_dropoff(dropoff=do_main.name, reason="probe")
        _as("Administrator"); frappe.db.commit(); _as(wf.TEST_OPERATOR)
        expect_error("complete while paused", "paused",
                     lambda: dapi.complete_dropoff(dropoff=do_main.name))
        dapi.resume_dropoff(dropoff=do_main.name, session=sess1)
        _stage("pause -> (block complete) -> resume", True, "resumed under sess1")
    except Exception as e:
        _stage("pause/resume probe", False, str(e))
    _as("Administrator"); frappe.db.commit()

    # finish weighing (receipt)
    _as(wf.TEST_OPERATOR)
    try:
        r = dapi.finish_weighing_session(dropoff=do_main.name)
        sw = r["scrap_weight"]
        _stage("finish_weighing_session -> SW receipt", True, sw)
    except Exception as e:
        _stage("finish_weighing_session", False, str(e))
    _as("Administrator")

    # truck weights + complete
    try:
        d = frappe.get_doc("Dropoff", do_main.name)
        d.gross_weight = 3500; d.tare_weight = 2400
        d.save(ignore_permissions=True); frappe.db.commit()
    except Exception as e:
        print(f"  (truck weight set failed: {e})")
    _as(wf.TEST_OPERATOR)
    try:
        dapi.complete_dropoff(dropoff=do_main.name)
        d = frappe.get_doc("Dropoff", do_main.name)
        _stage("complete_dropoff", True, f"status={d.status} verification={d.verification_status}")
    except Exception as e:
        _stage("complete_dropoff", False, str(e))
    _as("Administrator"); frappe.db.commit()

    # verify override (if Needs Review)
    d = frappe.get_doc("Dropoff", do_main.name)
    if d.verification_status == "Needs Review":
        _as(wf.TEST_OPERATOR)
        expect_error("verify without reason", "reason required",
                     lambda: dapi.verify_dropoff(dropoff=do_main.name, override_reason=None))
        try:
            dapi.verify_dropoff(dropoff=do_main.name, override_reason="variance reviewed, accepted")
            d = frappe.get_doc("Dropoff", do_main.name)
            _stage("verify override", True, f"verification={d.verification_status}")
        except Exception as e:
            _stage("verify override", False, str(e))
        _as("Administrator"); frappe.db.commit()
    else:
        _stage("verify override", True, f"(skipped; verification={d.verification_status})")

    # =======================================================================
    print("\n--- STAGE 5: PRODUCTION SORTING (gate + happy) ---")
    # gate: create_sorting on a NOT-completed dropoff
    try:
        do_gate = wf.make_dropoff(supplier, [(ia, 100)], pos_order_name=po_name)
        frappe.db.commit()
        _as(wf.TEST_OPERATOR)
        psess = papi.open_session(scale=scale)
        psess_name = psess["session"] if isinstance(psess, dict) else psess
        frappe.db.commit()  # persist session so expect_error's rollback can't wipe it
        expect_error("sorting on non-Completed dropoff", "not in Completed status",
                     lambda: papi.create_sorting(session=psess_name, dropoff=do_gate.name,
                                                  good_items=[{"item_code": ia, "weight": 50}]))
        # sorting with no items
        expect_error("sorting no items", "At least one good or unwanted",
                     lambda: papi.create_sorting(session=psess_name, dropoff=do_main.name,
                                                  good_items=[], unwanted_items=[]))
        # sorting weight<=0
        expect_error("sorting weight<=0", "greater than zero",
                     lambda: papi.create_sorting(session=psess_name, dropoff=do_main.name,
                                                  good_items=[{"item_code": ia, "weight": 0}]))
        # happy sorting on the completed dropoff
        summ = frappe.get_doc("Dropoff", do_main.name)
        grades = [(row.item, flt(row.total_weight)) for row in summ.item_summary]
        good = [{"item_code": grades[0][0], "weight": grades[0][1]}] if grades else []
        unwanted = ([{"item_code": grades[1][0], "weight": grades[1][1], "return_reason": "Contamination"}]
                    if len(grades) > 1 else [])
        res = papi.create_sorting(session=psess_name, dropoff=do_main.name,
                                  good_items=good, unwanted_items=unwanted)
        sort_name = res.get("sorting") or res.get("name") if isinstance(res, dict) else res
        _stage("create_sorting (happy) -> submitted", True, f"{sort_name}")
        # Dropoff Final auto-created?
        finals = frappe.get_all("Dropoff Final", filters={"dropoff": do_main.name}, pluck="name")
        _stage("Dropoff Final auto-created", bool(finals), f"{finals}")
        _as("Administrator"); frappe.db.commit()
    except Exception as e:
        _as("Administrator")
        import traceback; traceback.print_exc()
        _stage("Production Sorting stage", False, str(e))

    return _summary()


def _summary():
    _as("Administrator")
    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    hp = sum(1 for _, ok, _ in HAPPY if ok)
    print(f"\nHappy-path stages: {hp}/{len(HAPPY)} ok")
    for name, ok, detail in HAPPY:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}  — {detail}")
    print(f"\nError scenarios: {len(ERRORS)} probed")
    for label, verdict, expected, actual in ERRORS:
        print(f"  [{verdict:9}] {label}")
        print(f"             expected ~ {expected!r}")
        print(f"             actual   = {actual}")
    findings = [e for e in ERRORS if e[1] not in ("MATCH",)]
    print(f"\nFINDINGS (error verdict != MATCH): {len(findings)}")
    for label, verdict, expected, actual in findings:
        print(f"  - [{verdict}] {label}: {actual}")
    print("=" * 72)
    return {"happy_ok": hp, "happy_total": len(HAPPY),
            "errors_probed": len(ERRORS),
            "findings": len(findings)}
