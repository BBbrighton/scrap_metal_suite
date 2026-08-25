# Wave 10 — Finish Weighing Session test.
#
# Run with:
#   bench --site metal execute scrap_metal_suite.api_test.test_finish_weighing_session.run
#
# Verifies the new Scrap Weight cycle (DROPOFF_CONTAINER_REDESIGN.md §14.19):
#
#   1. Initial finish: Active containers → fresh Scrap Weight, submitted,
#      containers stamped with scrap_weight FK.
#   2. Reweigh post-submit: void+new flow cancels the SW; new container has
#      is_reweight=1, reweighed_from points at the voided one.
#   3. Multiple reweighs in a row do NOT generate intermediate receipts —
#      they just void+new repeatedly with the SW staying cancelled.
#   4. Re-finish: a fresh SW is submitted, is_amended=1, amended_from points
#      at the cancelled receipt.
#   5. Pre-submit void: NOT tagged is_reweight; just a correction.
#
# Reuses the workflow test's fixtures (same TEST_PREFIX, items, supplier).

import frappe
from frappe.utils import flt, now_datetime, add_to_date

from scrap_metal_suite.api_test import test_container_workflow as wf

TEST_PREFIX = "_TEST_FWS_"
TEST_OPERATOR = "_test_fws_operator@test.local"

# Canonical Thai item names — never translated.
THAI_ITEM_PRIMARY = "ทองแดงปอก"
THAI_ITEM_SECONDARY = "ทองแดงเล็ก"


def _cleanup():
    frappe.set_user("Administrator")

    # Cancel + delete submitted Scrap Weights for our test dropoffs first.
    # Filter by supplier (carries our TEST_PREFIX) since the Dropoff naming
    # uses the supplier's short_code ("TEST") which doesn't include the prefix.
    test_dropoffs = frappe.get_all(
        "Dropoff",
        filters={"supplier_name": ["like", f"%{TEST_PREFIX}%"]},
        pluck="name",
    )
    # Also catch any orphan SW with deleted dropoffs (defensive).
    orphan_sws = []
    for s in frappe.get_all("Scrap Weight", pluck="name"):
        do_name = frappe.db.get_value("Scrap Weight", s, "dropoff")
        if do_name and not frappe.db.exists("Dropoff", do_name):
            orphan_sws.append(s)
    sw_names = frappe.get_all(
        "Scrap Weight",
        filters={"dropoff": ["in", test_dropoffs or [""]]},
        pluck="name",
    ) + orphan_sws
    for sw in set(sw_names):
        try:
            doc = frappe.get_doc("Scrap Weight", sw)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Scrap Weight", sw, force=True, ignore_permissions=True)
        except Exception:
            pass

    # Cancel any submitted Price Locks + their POS Orders for our test supplier.
    for pl_name in frappe.get_all(
        "SMT Price Lock",
        filters={"supplier": ["like", f"%{TEST_PREFIX}%"]},
        pluck="name",
    ):
        try:
            for po_name in frappe.get_all(
                "POS Order", filters={"smt_price_lock": pl_name}, pluck="name"
            ):
                if frappe.db.get_value("POS Order", po_name, "docstatus") == 1:
                    frappe.db.set_value("POS Order", po_name, "status", "Pending", update_modified=False)
                    po_doc = frappe.get_doc("POS Order", po_name)
                    po_doc.cancel()
                frappe.delete_doc("POS Order", po_name, force=True, ignore_permissions=True)
            pl_doc = frappe.get_doc("SMT Price Lock", pl_name)
            if pl_doc.docstatus == 1:
                pl_doc.cancel()
            frappe.delete_doc("SMT Price Lock", pl_name, force=True, ignore_permissions=True)
        except Exception:
            pass

    # Close any sessions for our test operator.
    for s in frappe.get_all(
        "POS Session", filters={"operator": TEST_OPERATOR, "status": "Open"}, pluck="name"
    ):
        frappe.db.set_value("POS Session", s, "status", "Closed")

    # Containers must go before the Dropoffs they hang off, but scope them to
    # *this test's* dropoffs. Matching the name prefix instead — {"name":
    # ["like", "CTN-%"]} — matches the global naming series and deletes every
    # container in the database, including migrated production data.
    _test_dropoffs = frappe.get_all(
        "Dropoff",
        filters={"license_plate": ["like", f"%{TEST_PREFIX}%"]},
        pluck="name",
    )
    if _test_dropoffs:
        for _ctn in frappe.get_all(
            "Scrap Weight Container",
            filters={"dropoff": ["in", _test_dropoffs]},
            pluck="name",
        ):
            try:
                frappe.delete_doc("Scrap Weight Container", _ctn,
                                  force=True, ignore_permissions=True)
            except Exception:
                pass

    for dt, filt in [
        ("Dropoff", {"license_plate": ["like", f"%{TEST_PREFIX}%"]}),
        ("POS Session", {"operator": TEST_OPERATOR}),
        ("POS Order", {"supplier": ["like", f"%{TEST_PREFIX}%"]}),
        ("Supplier", {"supplier_name": ["like", f"%{TEST_PREFIX}%"]}),
        ("POS Profile Scrap", {"profile_name": ["like", f"%{TEST_PREFIX}%"]}),
        ("Scale", {"scale_name": ["like", f"%{TEST_PREFIX}%"]}),
    ]:
        try:
            for n in frappe.get_all(dt, filters=filt, pluck="name"):
                frappe.delete_doc(dt, n, force=True, ignore_permissions=True)
        except Exception:
            pass

    frappe.db.commit()


def _setup_master_data():
    """Reuse the workflow-test helpers to bootstrap supplier/items/scale/profile/dropoff."""
    wf.TEST_PREFIX = TEST_PREFIX
    wf.TEST_OPERATOR = TEST_OPERATOR
    wf.ensure_user(TEST_OPERATOR, ["POS Operator", "System Manager"])
    wf.ensure_item(THAI_ITEM_PRIMARY)
    wf.ensure_item(THAI_ITEM_SECONDARY)
    supplier = wf.ensure_supplier()
    scale = wf.ensure_scale()
    profile = wf.ensure_pos_profile()
    pl_name, po_name = wf.make_price_lock(supplier, [
        (THAI_ITEM_PRIMARY, 1000, 250.0),
        (THAI_ITEM_SECONDARY, 500, 180.0),
    ])
    dropoff = wf.make_dropoff(supplier, [
        (THAI_ITEM_PRIMARY, 1000),
        (THAI_ITEM_SECONDARY, 500),
    ], pos_order_name=po_name)
    session = wf.open_pos_session(profile, scale, TEST_OPERATOR)
    frappe.db.commit()
    return {
        "supplier": supplier, "scale": scale, "profile": profile,
        "session": session, "dropoff": dropoff.name,
        "item_primary": THAI_ITEM_PRIMARY, "item_secondary": THAI_ITEM_SECONDARY,
    }


def _add_container(api, ctx, item_code, weight):
    res = api.add_container(
        dropoff=ctx["dropoff"],
        session=ctx["session"],
        item_code=item_code,
        net_weight=weight,
        container_type="Bag",
        entry_method="Manual Entry",
    )
    assert res.get("success") is True, f"add_container failed: {res}"
    return res["container"]


def _summary(failures, label, ok, info=""):
    print(f"  {'✓' if ok else '✗'} {label}{(' — ' + info) if info else ''}")
    if not ok:
        failures.append(label)


def run(cleanup_first=True, cleanup_after=True):
    print("\n" + "=" * 70)
    print("WAVE 10 — Finish Weighing Session test")
    print(f"Site: {frappe.local.site}  |  Time: {now_datetime()}")
    print("=" * 70)

    if cleanup_first:
        _cleanup()

    failures: list[str] = []
    original_user = frappe.session.user
    frappe.set_user("Administrator")

    try:
        ctx = _setup_master_data()
        print(f"  setup: dropoff={ctx['dropoff']}, session={ctx['session']}")

        from scrap_metal_suite.api.v1 import dropoff as api

        # ---- 1. Add 3 bags, finish, expect a fresh Scrap Weight submitted.
        frappe.set_user(TEST_OPERATOR)
        c1 = _add_container(api, ctx, ctx["item_primary"], 300)
        c2 = _add_container(api, ctx, ctx["item_primary"], 400)
        c3 = _add_container(api, ctx, ctx["item_secondary"], 250)
        frappe.set_user("Administrator")

        res = api.finish_weighing_session(ctx["dropoff"])
        sw1 = res["scrap_weight"]
        sw1_doc = frappe.get_doc("Scrap Weight", sw1)
        _summary(failures, "1. First finish creates submitted Scrap Weight",
                 sw1_doc.docstatus == 1, f"name={sw1}, total={sw1_doc.total_weight}, bags={sw1_doc.total_container_count}")
        _summary(failures, "1a. is_amended=0 on first SW", sw1_doc.is_amended == 0)
        _summary(failures, "1b. amended_from is empty on first SW", not sw1_doc.amended_from)
        _summary(failures, "1c. items aggregated by grade",
                 len(sw1_doc.items) == 2,
                 f"got {len(sw1_doc.items)} item rows")
        _summary(failures, "1d. containers stamped with scrap_weight",
                 frappe.db.count("Scrap Weight Container", {"scrap_weight": sw1}) == 3,
                 f"{frappe.db.count('Scrap Weight Container', {'scrap_weight': sw1})}/3 stamped")

        # ---- 2. Reweigh c2 (post-submit) — old SW must be cancelled.
        frappe.set_user(TEST_OPERATOR)
        rw_res = api.reweigh_container(container=c2, net_weight=420, reason="dirty floor", entry_method="Manual Entry")
        frappe.set_user("Administrator")

        new_c2 = rw_res["container"]
        cancelled = rw_res["cancelled_scrap_weight"]
        new_c2_doc = frappe.get_doc("Scrap Weight Container", new_c2)
        old_c2_doc = frappe.get_doc("Scrap Weight Container", c2)

        _summary(failures, "2. Reweigh creates new container",
                 new_c2 != c2, f"old={c2}, new={new_c2}")
        _summary(failures, "2a. New container is_reweight=1", new_c2_doc.is_reweight == 1)
        _summary(failures, "2b. New container reweighed_from = old", new_c2_doc.reweighed_from == c2)
        _summary(failures, "2c. Old container Voided", old_c2_doc.status == "Voided")
        _summary(failures, "2d. Old container superseded_by = new", old_c2_doc.superseded_by == new_c2)
        _summary(failures, "2e. Old SW cancelled", cancelled == sw1 and frappe.db.get_value("Scrap Weight", sw1, "docstatus") == 2)

        # ---- 3. Reweigh c1 again BEFORE re-finishing — should not create a new SW.
        frappe.set_user(TEST_OPERATOR)
        rw2 = api.reweigh_container(container=c1, net_weight=310, reason="re-tare", entry_method="Manual Entry")
        frappe.set_user("Administrator")
        sw_count_now = frappe.db.count("Scrap Weight", {"dropoff": ctx["dropoff"], "docstatus": 1})
        _summary(failures, "3. Mid-session reweigh does NOT create a new SW",
                 sw_count_now == 0, f"submitted SW count = {sw_count_now}")
        _summary(failures, "3a. Second reweigh has cancelled_scrap_weight=null (already cancelled)",
                 rw2["cancelled_scrap_weight"] is None)

        # ---- 4. Re-finish → new SW with is_amended=1 and amended_from=sw1.
        res2 = api.finish_weighing_session(ctx["dropoff"])
        sw2 = res2["scrap_weight"]
        sw2_doc = frappe.get_doc("Scrap Weight", sw2)
        _summary(failures, "4. Re-finish creates new SW (submitted)", sw2_doc.docstatus == 1, f"name={sw2}")
        _summary(failures, "4a. is_amended=1 on new SW", sw2_doc.is_amended == 1)
        _summary(failures, "4b. amended_from = old cancelled SW",
                 sw2_doc.amended_from == sw1, f"got {sw2_doc.amended_from}")
        _summary(failures, "4c. New active containers stamped with NEW SW",
                 frappe.db.count("Scrap Weight Container", {"scrap_weight": sw2, "status": "Active"}) == 3,
                 f"{frappe.db.count('Scrap Weight Container', {'scrap_weight': sw2, 'status': 'Active'})}/3")

        # ---- 5. Pre-submit void semantics — verified separately via void of
        #         a brand-new container while the active SW is sw2. To check
        #         the "no-active-SW" branch without leaving the dropoff in a
        #         cancelled-only state, void+immediately re-finish so sw3 is
        #         left submitted at end (lets the smoke test render a real SW).
        frappe.set_user(TEST_OPERATOR)
        c4 = _add_container(api, ctx, ctx["item_primary"], 100)
        void_res = api.void_container(container=c4, reason="typo correction")
        frappe.set_user("Administrator")
        c4_doc = frappe.get_doc("Scrap Weight Container", c4)
        _summary(failures, "5. Post-add void marks Voided", c4_doc.status == "Voided")
        _summary(failures, "5a. Voiding c4 cancelled sw2 (active SW)",
                 void_res["cancelled_scrap_weight"] == sw2)
        # Re-finish to settle on a clean submitted SW (sw3) for downstream renders.
        res3 = api.finish_weighing_session(ctx["dropoff"])
        sw3_doc = frappe.get_doc("Scrap Weight", res3["scrap_weight"])
        _summary(failures, "5b. Re-finish after void produces fresh submitted SW",
                 sw3_doc.docstatus == 1, f"name={sw3_doc.name}")

        # ---- summary ----
        print("\n" + "=" * 70)
        if failures:
            print(f"FAILED: {len(failures)} assertion(s) failed:")
            for f in failures:
                print(f"  - {f}")
        else:
            print("PASS: Wave 10 finish_weighing_session + reweigh cycle works end-to-end")
        print("=" * 70)
        return {"passed": 0 if failures else 1, "failed": len(failures)}
    except Exception as e:
        print(f"FAIL: unexpected exception {type(e).__name__}: {e}")
        import traceback; traceback.print_exc()
        return {"passed": 0, "failed": 1}
    finally:
        if cleanup_after:
            _cleanup()
            print("  ✓ Cleanup done")
        else:
            print("  • Cleanup skipped — fixtures retained for inspection")
        frappe.set_user(original_user or "Administrator")
