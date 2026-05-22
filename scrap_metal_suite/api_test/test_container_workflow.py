# Container Workflow Integration Test — Scrap Metal Suite
#
# Run with:
#   bench --site metal execute scrap_metal_suite.api_test.test_container_workflow.run
#
# Tests the full container weighing loop documented in
# docs/DROPOFF_CONTAINER_REDESIGN.md §11.2:
#   submit Price Lock → auto POS Order is created → schedule Dropoff linked
#   to that POS Order → open POS Session → add 5 containers across 3 grades →
#   reweigh one → pause → resume on a NEW session (same scale) → add another
#   container → complete → assert per-grade aggregation lives in
#   `item_summary` and the deprecated `actual_items` table is empty.
#
# The flow always begins with a Price Lock — there are no walk-in suppliers
# in this business (a PL is created on-the-spot if needed; see
# docs/DROPOFF_CONTAINER_REDESIGN.md §14.18). Tests that bypassed the upstream
# PL→PO chain by stuffing `expected_items` directly were rewritten to mirror
# the production path.
#
# Item names are CANONICAL THAI (BILINGUAL_GUIDE.md §2). This file never
# wraps `item_name` in `_()` and never compares to an English equivalent.

import frappe
from frappe.utils import flt, now_datetime, add_to_date


# Canonical Thai item names — never translated, never wrapped in _()
THAI_ITEM_PRIMARY = "ทองแดงปอก"
THAI_ITEM_SECONDARY = "ทองแดงเล็ก"
THAI_ITEM_TERTIARY = "ทองเหลือง"

TEST_PREFIX = "_TEST_CTNWF_"
TEST_OPERATOR = "_test_ctnwf_operator@test.local"


# ============================================================
# Result tracker — same shape as test_full_workflow.TestResult
# ============================================================

class TestResult:
    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0
        self.skipped = 0

    def add(self, name, success, error=None):
        self.results.append(("PASS" if success else "FAIL", name, error))
        if success:
            self.passed += 1
        else:
            self.failed += 1

    def skip(self, name, reason):
        self.results.append(("SKIP", name, reason))
        self.skipped += 1

    def summary(self):
        print("\n" + "=" * 70)
        print("CONTAINER WORKFLOW TEST SUMMARY")
        print("=" * 70)
        total = self.passed + self.failed + self.skipped
        print(f"\nTotal: {total}  |  Passed: {self.passed}  "
              f"|  Failed: {self.failed}  |  Skipped: {self.skipped}")

        if self.failed:
            print("\nFAILED:")
            for status, name, error in self.results:
                if status == "FAIL":
                    print(f"  ✗ {name}: {str(error)[:160]}")
        if self.skipped:
            print("\nSKIPPED:")
            for status, name, reason in self.results:
                if status == "SKIP":
                    print(f"  - {name}: {reason}")

        print("=" * 70)
        return {"passed": self.passed, "failed": self.failed, "skipped": self.skipped}


# ============================================================
# Fixture helpers
# ============================================================

def cleanup_test_data():
    """Remove anything we created on a previous run."""
    frappe.set_user("Administrator")

    # Close any open POS sessions for our operator (can't delete Open ones).
    for s in frappe.get_all(
        "POS Session",
        filters={"operator": TEST_OPERATOR, "status": "Open"},
        pluck="name",
    ):
        frappe.db.set_value("POS Session", s, "status", "Closed")

    # Release scales we own.
    for name in frappe.get_all(
        "Scale",
        filters={"scale_name": ["like", f"%{TEST_PREFIX}%"]},
        pluck="name",
    ):
        frappe.db.set_value(
            "Scale", name, {"in_use": 0, "in_use_by_session": None}
        )
    frappe.db.commit()

    # Cancel any submitted Price Locks for our test supplier first — submitted
    # docs can't be deleted directly. Each PL has a paired POS Order
    # (auto-created on PL submit) which must be cancelled before its parent.
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
                    frappe.db.set_value(
                        "POS Order", po_name, "status", "Pending",
                        update_modified=False,
                    )
                    po_doc = frappe.get_doc("POS Order", po_name)
                    po_doc.cancel()
                frappe.delete_doc("POS Order", po_name, force=True, ignore_permissions=True)

            pl_doc = frappe.get_doc("SMT Price Lock", pl_name)
            if pl_doc.docstatus == 1:
                pl_doc.cancel()
            frappe.delete_doc("SMT Price Lock", pl_name, force=True, ignore_permissions=True)
        except Exception:
            pass

    # Delete in dependency order.
    for dt, filt in [
        ("Scrap Weight Container", {"name": ["like", "CTN-%"]}),
        ("Dropoff", {"license_plate": ["like", f"%{TEST_PREFIX}%"]}),
        ("POS Session", {"operator": TEST_OPERATOR}),
        # Orphan POS Orders from suppliers we're about to delete.
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

    # Delete our test items (keyed by Thai item_name).
    for thai_name in (THAI_ITEM_PRIMARY, THAI_ITEM_SECONDARY, THAI_ITEM_TERTIARY):
        try:
            for n in frappe.get_all("Item", filters={"item_name": thai_name}, pluck="name"):
                # Only delete items we created — by-test items typically have
                # the canonical Thai as both code and name. Don't disturb
                # production master data.
                if frappe.db.get_value("Item", n, "owner") == "Administrator":
                    frappe.delete_doc("Item", n, force=True, ignore_permissions=True)
        except Exception:
            pass

    if frappe.db.exists("User", TEST_OPERATOR):
        try:
            frappe.delete_doc("User", TEST_OPERATOR, force=True, ignore_permissions=True)
        except Exception:
            pass

    frappe.db.commit()


def ensure_user(email, roles):
    if frappe.db.exists("User", email):
        user = frappe.get_doc("User", email)
    else:
        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": email.split("@")[0],
            "send_welcome_email": 0,
            "new_password": "Test@12345",
        })
        user.insert(ignore_permissions=True)
    user.roles = []
    for role in roles:
        user.append("roles", {"role": role})
    user.save(ignore_permissions=True)
    return user


def ensure_item(item_name):
    code = frappe.db.get_value("Item", {"item_name": item_name}, "name")
    if code:
        return code
    doc = frappe.get_doc({
        "doctype": "Item",
        "item_code": item_name,
        "item_name": item_name,            # canonical Thai, never translated
        "item_group": "Raw Material",
        "stock_uom": "Kg",
        "is_stock_item": 1,
    })
    doc.insert(ignore_permissions=True)
    return doc.name


def ensure_supplier():
    name = f"{TEST_PREFIX}Supplier"
    if frappe.db.exists("Supplier", {"supplier_name": name}):
        return frappe.db.get_value("Supplier", {"supplier_name": name}, "name")
    doc = frappe.get_doc({
        "doctype": "Supplier",
        "supplier_name": name,
        "supplier_group": "Raw Material",
    })
    doc.insert(ignore_permissions=True)
    return doc.name


def ensure_scale():
    scale_name = f"{TEST_PREFIX}Scale-01"
    existing = frappe.db.get_value("Scale", {"scale_name": scale_name}, "name")
    if existing:
        return existing
    doc = frappe.get_doc({
        "doctype": "Scale",
        "scale_name": scale_name,
        "scale_type": "Platform",
        "usage_type": "Scrap",
        "location": "Test Bay",
        "is_active": 1,
        "max_capacity_kg": 5000,
        "baud_rate": 9600,
        "data_bits": 8,
        "parity": "none",
        "stop_bits": 1,
    })
    doc.insert(ignore_permissions=True)
    return doc.name


def ensure_pos_profile():
    profile_name = f"{TEST_PREFIX}Profile"
    existing = frappe.db.get_value(
        "POS Profile Scrap", {"profile_name": profile_name}, "name"
    )
    if existing:
        return existing
    price_list = frappe.db.get_value("Price List", {"buying": 1}, "name") or "Standard Buying"
    doc = frappe.get_doc({
        "doctype": "POS Profile Scrap",
        "profile_name": profile_name,
        "is_active": 1,
        "price_list": price_list,
    })
    # `items` child table is mandatory; populate from the test items.
    for code in (THAI_ITEM_PRIMARY, THAI_ITEM_SECONDARY, THAI_ITEM_TERTIARY):
        if frappe.db.exists("Item", code):
            doc.append("items", {"item_code": code, "item_name": code})
    doc.insert(ignore_permissions=True)
    return doc.name


def open_pos_session(profile, scale, operator):
    # POS Session.before_insert overrides `operator` to `frappe.session.user`,
    # so set the session user to the desired operator for the duration of
    # the insert. Then close any other Open session for that operator first
    # (the doctype enforces one-open-per-operator).
    prior_user = frappe.session.user
    frappe.set_user(operator)
    try:
        for s in frappe.db.get_all(
            "POS Session", filters={"operator": operator, "status": "Open"}
        ):
            frappe.db.set_value("POS Session", s.name, "status", "Closed",
                                update_modified=False)
        frappe.db.commit()

        doc = frappe.get_doc({
            "doctype": "POS Session",
            "pos_profile": profile,
            "operator": operator,
            "scale": scale,
            "status": "Open",
            "opening_time": now_datetime(),
        })
        doc.insert(ignore_permissions=True)
    finally:
        frappe.set_user(prior_user)
    return doc.name


def make_price_lock(supplier, items):
    """Submit an SMT Price Lock and return (price_lock_name, pos_order_name).

    `items` is a list of (item_code, qty_kg, rate) tuples. The submit triggers
    automatic POS Order creation via the PL controller's on_submit hook;
    we read the auto-created PO back from the link.
    """
    pl = frappe.get_doc({
        "doctype": "SMT Price Lock",
        "supplier": supplier,
        "po_date": now_datetime(),
        "items": [
            {"item_code": c, "po_qty": q, "po_rate": r}
            for c, q, r in items
        ],
    })
    pl.insert(ignore_permissions=True)
    pl.submit()

    po_name = frappe.db.get_value("POS Order", {"smt_price_lock": pl.name}, "name")
    if not po_name:
        frappe.throw(f"Auto POS Order not created for SMT Price Lock {pl.name}")
    return pl.name, po_name


def make_dropoff(supplier, expected, pos_order_name):
    """Schedule a Dropoff bound to a POS Order.

    `expected` is the list of (item_code, indicated_kg) tuples that gets
    written into Dropoff.expected_items. In production this is populated by
    the office when scheduling; tests pass it explicitly to keep the test
    data deterministic. The Dropoff is also linked to the upstream POS Order
    via the `orders` child table — every Dropoff has at least one PO link
    (no walk-ins).
    """
    doc = frappe.get_doc({
        "doctype": "Dropoff",
        "dropoff_scheduled_start": now_datetime(),
        "dropoff_scheduled_end": add_to_date(now_datetime(), hours=2),
        "license_plate": f"{TEST_PREFIX}WF-001",
        "supplier": supplier,
        "status": "Scheduled",
        # Realistic thresholds (matching production defaults, post Wave 7 fix).
        # The reweigh in step 5 introduces a ~2.5% truck-vs-scrap variance which
        # exceeds 0.1%, so the dropoff naturally lands in Needs Review at
        # completion — exactly the production behavior. Manager would then
        # resolve via verify_dropoff override.
        "truck_variance_threshold_percent": 0.1,
        "indicated_variance_threshold_percent": 0.1,
        "orders": [{"pos_order": pos_order_name}],
    })
    for code, indicated in expected:
        doc.append("expected_items", {"item": code, "indicated_weight": flt(indicated)})
    doc.insert(ignore_permissions=True)
    return doc


# ============================================================
# Main runner
# ============================================================

def run(cleanup_first=True, cleanup_after=True):
    """Run the container workflow integration test."""
    print("\n" + "=" * 70)
    print("SCRAP METAL SUITE — CONTAINER WORKFLOW INTEGRATION TEST")
    print(f"Site: {frappe.local.site}  |  Time: {now_datetime()}")
    print("=" * 70)

    results = TestResult()
    original_user = frappe.session.user
    frappe.set_user("Administrator")

    try:
        if cleanup_first:
            print("\nCleaning previous test data…")
            cleanup_test_data()

        # ----- Master data -----
        try:
            ensure_user(TEST_OPERATOR, ["POS Operator", "System Manager"])
            item_a = ensure_item(THAI_ITEM_PRIMARY)
            item_b = ensure_item(THAI_ITEM_SECONDARY)
            item_c = ensure_item(THAI_ITEM_TERTIARY)
            supplier = ensure_supplier()
            scale = ensure_scale()
            profile = ensure_pos_profile()
            frappe.db.commit()
            print(f"  ✓ Master data ready (scale={scale}, supplier={supplier})")
            results.add("setup_master_data", True)
        except Exception as e:
            results.add("setup_master_data", False, e)
            return results.summary()

        # ----- Step 1a: Submit a Price Lock (the upstream commitment) -----
        try:
            pl_name, po_name = make_price_lock(supplier, [
                (item_a, 1500, 250.0),
                (item_b, 800, 180.0),
                (item_c, 400, 120.0),
            ])
            print(f"  ✓ Submitted Price Lock {pl_name} → auto POS Order {po_name}")
            results.add("step01a_submit_price_lock", True)
        except Exception as e:
            results.add("step01a_submit_price_lock", False, e)
            return results.summary()

        # ----- Step 1b: Schedule a Dropoff bound to that POS Order -----
        try:
            dropoff = make_dropoff(supplier, [
                (item_a, 1500),
                (item_b, 800),
                (item_c, 400),
            ], pos_order_name=po_name)
            print(f"  ✓ Created Dropoff {dropoff.name} linked to {po_name} with 3 expected items")
            results.add("step01b_create_dropoff", True)
        except Exception as e:
            results.add("step01b_create_dropoff", False, e)
            return results.summary()

        # ----- Step 2: Open POS Session as operator -----
        try:
            session1 = open_pos_session(profile, scale, TEST_OPERATOR)
            print(f"  ✓ Opened POS session 1: {session1}")
            results.add("step02_open_session", True)
        except Exception as e:
            results.add("step02_open_session", False, e)
            return results.summary()

        # ----- Step 3: add_container x 5 across 3 grades -----
        # Use the API as operator, mirroring real terminal flow.
        from scrap_metal_suite.api.v1 import dropoff as dropoff_api

        bag_specs = [
            (item_a, 250.0),
            (item_a, 300.0),
            (item_b, 200.0),
            (item_b, 150.0),
            (item_c, 100.0),
        ]
        container_names = []
        try:
            frappe.set_user(TEST_OPERATOR)
            for code, weight in bag_specs:
                res = dropoff_api.add_container(
                    dropoff=dropoff.name,
                    session=session1,
                    item_code=code,
                    net_weight=weight,
                    container_type="Bag",
                    entry_method="Manual Entry",
                )
                assert res.get("success") is True
                # item_name MUST be canonical Thai (verbatim) — never translated.
                # Compare to the value we inserted, which is the Thai name itself.
                assert res.get("item_name") == code, (
                    f"item_name should equal item_code (canonical Thai master); "
                    f"got {res.get('item_name')!r}, expected {code!r}"
                )
                container_names.append(res["container"])
            print(f"  ✓ Inserted {len(container_names)} containers via add_container")
            results.add("step03_add_containers", True)
        except Exception as e:
            import traceback; traceback.print_exc()
            results.add("step03_add_containers", False, e)
            return results.summary()
        finally:
            frappe.set_user("Administrator")

        # ----- Step 4: total_actual_weight == sum of weights -----
        expected_total = sum(w for _, w in bag_specs)  # 1000 kg
        try:
            do = frappe.get_doc("Dropoff", dropoff.name)
            actual_total = flt(do.total_actual_weight)
            assert flt(actual_total, 1) == flt(expected_total, 1), (
                f"total_actual_weight={actual_total}, expected {expected_total}"
            )
            assert do.container_count == 5
            assert do.weighing_session == session1
            assert do.weighing_scale == scale
            assert do.status == "In Progress"
            print(f"  ✓ Dropoff total = {actual_total} kg, status={do.status}, "
                  f"container_count={do.container_count}")
            results.add("step04_total_matches", True)
        except Exception as e:
            results.add("step04_total_matches", False, e)

        # ----- Step 5: reweigh_container on one bag, total updates -----
        try:
            frappe.set_user(TEST_OPERATOR)
            target = container_names[0]   # was 250 kg
            new_weight = 275.0
            old_total = flt(frappe.db.get_value("Dropoff", dropoff.name, "total_actual_weight"))
            res = dropoff_api.reweigh_container(
                container=target,
                net_weight=new_weight,
                reason="Recalibrated scale, re-weighed first bag",
            )
            assert res["success"] is True
            assert flt(res["net_weight"]) == new_weight
            new_total = flt(res["dropoff_total"])
            assert flt(new_total, 1) == flt(old_total - 250.0 + new_weight, 1), (
                f"new_total={new_total}, expected {old_total - 250.0 + new_weight}"
            )
            print(f"  ✓ Reweigh: bag 1 {250} → {new_weight} kg; new total = {new_total}")
            results.add("step05_reweigh", True)
        except Exception as e:
            import traceback; traceback.print_exc()
            results.add("step05_reweigh", False, e)
        finally:
            frappe.set_user("Administrator")

        # ----- Step 6: pause_dropoff -----
        try:
            frappe.set_user(TEST_OPERATOR)
            res = dropoff_api.pause_dropoff(dropoff=dropoff.name, reason="End of shift")
            assert res["status"] == "Paused"
            do = frappe.get_doc("Dropoff", dropoff.name)
            assert do.status == "Paused"
            assert not do.weighing_session  # cleared on pause
            assert do.weighing_scale == scale  # but scale lock survives
            print(f"  ✓ Pause: status={do.status}, scale lock retained ({do.weighing_scale})")
            results.add("step06_pause", True)
        except Exception as e:
            results.add("step06_pause", False, e)
        finally:
            frappe.set_user("Administrator")

        # ----- Step 7: open new POS Session on SAME scale, then resume -----
        try:
            # Close session 1 first; new session also belongs to TEST_OPERATOR.
            frappe.db.set_value("POS Session", session1, "status", "Closed")
            frappe.db.commit()

            session2 = open_pos_session(profile, scale, TEST_OPERATOR)
            print(f"  ✓ Opened POS session 2: {session2} (same scale)")

            frappe.set_user(TEST_OPERATOR)
            res = dropoff_api.resume_dropoff(dropoff=dropoff.name, session=session2)
            assert res["status"] == "In Progress"
            do = frappe.get_doc("Dropoff", dropoff.name)
            assert do.weighing_session == session2
            assert do.weighing_scale == scale
            print(f"  ✓ Resumed under session 2; scale lock preserved")
            results.add("step07_resume", True)
        except Exception as e:
            import traceback; traceback.print_exc()
            results.add("step07_resume", False, e)
            return results.summary()
        finally:
            frappe.set_user("Administrator")

        # ----- Step 8: add another container under session 2 -----
        try:
            frappe.set_user(TEST_OPERATOR)
            res = dropoff_api.add_container(
                dropoff=dropoff.name,
                session=session2,
                item_code=item_c,
                net_weight=80.0,
                container_type="Bag",
                entry_method="Manual Entry",
            )
            assert res["success"] is True
            container_names.append(res["container"])
            assert res.get("item_name") == item_c, (
                f"item_name canonical-Thai mismatch: {res.get('item_name')!r}"
            )
            print(f"  ✓ Added 6th container under session 2 ({res['container']})")
            results.add("step08_add_after_resume", True)
        except Exception as e:
            results.add("step08_add_after_resume", False, e)
        finally:
            frappe.set_user("Administrator")

        # ----- Step 9: finish_weighing_session (Wave 10 — generates Scrap Weight receipt) -----
        try:
            frappe.set_user(TEST_OPERATOR)
            res = dropoff_api.finish_weighing_session(dropoff=dropoff.name)
            sw_name = res["scrap_weight"]
            sw = frappe.get_doc("Scrap Weight", sw_name)
            assert sw.docstatus == 1, f"Scrap Weight not submitted: {sw.docstatus}"
            assert sw.dropoff == dropoff.name
            assert sw.total_container_count == 6, f"expected 6 bags, got {sw.total_container_count}"
            assert len(sw.items) == 3, f"expected 3 grade rows, got {len(sw.items)}"
            print(f"  ✓ finish_weighing_session: SW={sw_name}, total={sw.total_weight}kg, bags={sw.total_container_count}, items={len(sw.items)}")
            results.add("step09_finish_weighing_session", True)
        except Exception as e:
            import traceback; traceback.print_exc()
            results.add("step09_finish_weighing_session", False, e)
        finally:
            frappe.set_user("Administrator")

        # ----- Step 10: complete_dropoff -----
        try:
            # Truck weights for verification reconciliation (independent of bag side).
            do = frappe.get_doc("Dropoff", dropoff.name)
            do.gross_weight = 3500
            do.tare_weight = 2400
            do.save(ignore_permissions=True)
            do.reload()

            frappe.set_user(TEST_OPERATOR)
            res = dropoff_api.complete_dropoff(dropoff=dropoff.name)
            assert res["status"] == "Completed"
            do = frappe.get_doc("Dropoff", dropoff.name)
            assert do.status == "Completed"
            print(f"  ✓ complete_dropoff: status={do.status}, "
                  f"verification_status={do.verification_status}")
            results.add("step10_complete", True)
        except Exception as e:
            import traceback; traceback.print_exc()
            results.add("step10_complete", False, e)
        finally:
            frappe.set_user("Administrator")

        # ----- Step 11: actual_items DEPRECATED (empty), item_summary populated -----
        try:
            do = frappe.get_doc("Dropoff", dropoff.name)
            # Deprecated table: should be empty in the container model.
            assert len(do.actual_items or []) == 0, (
                f"actual_items must be empty (deprecated); got {len(do.actual_items)} rows"
            )
            # item_summary should have one row per grade (3 grades used).
            grades_in_summary = {row.item for row in do.item_summary}
            assert grades_in_summary == {item_a, item_b, item_c}, (
                f"item_summary grades={grades_in_summary}, expected 3"
            )
            # Verify per-grade weight matches sum of Active container weights.
            # item_a was reweighed: 275 + 300 = 575
            # item_b: 200 + 150 = 350
            # item_c: 100 + 80 (added under session 2) = 180
            EXPECTED_BY_GRADE = {item_a: 575.0, item_b: 350.0, item_c: 180.0}
            for row in do.item_summary:
                expected = EXPECTED_BY_GRADE[row.item]
                assert flt(row.total_weight, 1) == flt(expected, 1), (
                    f"{row.item}: total_weight={row.total_weight}, expected {expected}"
                )
                # item_name on summary rows must also be canonical Thai.
                assert row.item_name == row.item, (
                    f"item_summary.item_name should equal canonical Thai "
                    f"item code/name; got {row.item_name!r}"
                )
            print(f"  ✓ actual_items empty (deprecated); item_summary aggregates "
                  f"{len(do.item_summary)} grades correctly")
            results.add("step11_aggregation_shape", True)
        except Exception as e:
            results.add("step11_aggregation_shape", False, e)

    except Exception as e:
        print(f"\n!!! FATAL: {e}")
        import traceback; traceback.print_exc()
        results.add("fatal", False, e)
    finally:
        # ----- Step 11: cleanup (optional) -----
        if cleanup_after:
            try:
                frappe.set_user("Administrator")
                cleanup_test_data()
                print("  ✓ Cleanup done")
            except Exception as e:
                print(f"  ! Cleanup error (non-fatal): {e}")
        else:
            print("  • Cleanup skipped — fixtures retained in the DB for inspection")
        frappe.set_user(original_user or "Administrator")

    return results.summary()
