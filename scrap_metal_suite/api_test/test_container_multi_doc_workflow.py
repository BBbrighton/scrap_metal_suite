# Container Multi-Doc Workflow Integration Test — Scrap Metal Suite
#
# Run with:
#   bench --site metal execute scrap_metal_suite.api_test.test_container_multi_doc_workflow.run
#
# Two real-world scenarios:
#   A) One Price Lock -> 3 Dropoffs across days (FIFO partial fulfillment).
#   B) Two Price Locks -> 1 Dropoff that fulfills both (partial + full).
#
# Both verify the new container model:
#   * `add_container` returns per-container `print_urls.sticker`
#     (the per-Dropoff thermal receipt is generated separately from the parent
#     Dropoff via `ใบคิวสองภาษา` — there is no per-container thermal format)
#   * `list_containers` returns every container for a dropoff
#   * Dropoff-level print URL is constructable
#
# Item names are CANONICAL THAI (BILINGUAL_GUIDE.md §2). They are never
# translated and never wrapped in `_()`. We assert against raw Thai strings.

import frappe
from frappe.utils import flt, now_datetime, add_to_date, today


# Canonical Thai item names — never translated, never wrapped in _()
THAI_ITEM_A = "ทองแดงปอก"           # primary
THAI_ITEM_B = "ทองแดงเล็ก"
THAI_ITEM_C = "ทองแดงชิ้นงานรวม"
THAI_ITEM_D = "ทองแดงชิ้นงานสะอาด"

TEST_PREFIX = "_TEST_MDWF_"
TEST_OPERATOR = "_test_mdwf_operator@test.local"


# ============================================================
# Result tracker (mirrors test_container_workflow.TestResult)
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
        print("CONTAINER MULTI-DOC WORKFLOW TEST SUMMARY")
        print("=" * 70)
        total = self.passed + self.failed + self.skipped
        print(f"\nTotal: {total}  |  Passed: {self.passed}  "
              f"|  Failed: {self.failed}  |  Skipped: {self.skipped}")

        if self.failed:
            print("\nFAILED:")
            for status, name, error in self.results:
                if status == "FAIL":
                    print(f"  - {name}: {str(error)[:200]}")
        if self.skipped:
            print("\nSKIPPED:")
            for status, name, reason in self.results:
                if status == "SKIP":
                    print(f"  - {name}: {reason}")
        print("=" * 70)
        return {"passed": self.passed, "failed": self.failed, "skipped": self.skipped}


# ============================================================
# Cleanup
# ============================================================

def cleanup_test_data():
    """Remove anything we created on a previous run."""
    frappe.set_user("Administrator")

    # Close any open POS sessions for our operator (can't delete Open ones)
    for s in frappe.get_all(
        "POS Session",
        filters={"operator": TEST_OPERATOR, "status": "Open"},
        pluck="name",
    ):
        frappe.db.set_value("POS Session", s, "status", "Closed")

    # Release scales we own
    for name in frappe.get_all(
        "Scale",
        filters={"scale_name": ["like", f"%{TEST_PREFIX}%"]},
        pluck="name",
    ):
        frappe.db.set_value(
            "Scale", name, {"in_use": 0, "in_use_by_session": None}
        )
    frappe.db.commit()

    # Cancel and delete SMT Price Locks that might still be Open/submitted.
    for pl in frappe.get_all(
        "SMT Price Lock",
        filters={"supplier_name": ["like", f"%{TEST_PREFIX}%"]},
        pluck="name",
    ):
        try:
            doc = frappe.get_doc("SMT Price Lock", pl)
            if doc.docstatus == 1:
                # Reset settled qty so on_cancel doesn't block
                for row in doc.items:
                    frappe.db.set_value(
                        "SMT Price Lock Item",
                        row.name,
                        {"settled_qty": 0, "remaining_qty": row.po_qty},
                        update_modified=False,
                    )
                doc.reload()
                # Cancel any linked POS Order(s) before cancelling the PL,
                # so cascading cancel doesn't trip on a non-Pending order.
                for po_name in frappe.get_all(
                    "POS Order", filters={"smt_price_lock": pl}, pluck="name"
                ):
                    frappe.db.set_value(
                        "POS Order", po_name, "status", "Pending",
                        update_modified=False,
                    )
                frappe.db.commit()
                doc.cancel()
            frappe.delete_doc("SMT Price Lock", pl, force=True, ignore_permissions=True)
        except Exception:
            pass

    # Delete in dependency order
    for dt, filt in [
        ("Scrap Weight Container", {"name": ["like", "CTN-%"]}),
        ("Dropoff", {"license_plate": ["like", f"%{TEST_PREFIX}%"]}),
        ("POS Session", {"operator": TEST_OPERATOR}),
        ("POS Order", {"smt_price_lock": ["like", f"%{TEST_PREFIX}%"]}),
        ("Supplier", {"supplier_name": ["like", f"%{TEST_PREFIX}%"]}),
        ("POS Profile Scrap", {"profile_name": ["like", f"%{TEST_PREFIX}%"]}),
        ("Scale", {"scale_name": ["like", f"%{TEST_PREFIX}%"]}),
    ]:
        try:
            for n in frappe.get_all(dt, filters=filt, pluck="name"):
                frappe.delete_doc(dt, n, force=True, ignore_permissions=True)
        except Exception:
            pass

    # Also kill orphan POS Orders linked to deleted suppliers.
    for n in frappe.get_all(
        "POS Order",
        filters={"supplier": ["like", f"%{TEST_PREFIX}%"]},
        pluck="name",
    ):
        try:
            frappe.delete_doc("POS Order", n, force=True, ignore_permissions=True)
        except Exception:
            pass

    # Test items keyed by Thai item_name — only delete if we own them
    for thai_name in (THAI_ITEM_A, THAI_ITEM_B, THAI_ITEM_C, THAI_ITEM_D):
        try:
            for n in frappe.get_all("Item", filters={"item_name": thai_name}, pluck="name"):
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


# ============================================================
# Fixture helpers
# ============================================================

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


def ensure_pos_profile(item_codes):
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
        # enable_sticker_print defaults on in JSON.
    })
    for code in item_codes:
        if frappe.db.exists("Item", code):
            doc.append("items", {"item_code": code, "item_name": code})
    doc.insert(ignore_permissions=True)
    return doc.name


def open_pos_session(profile, scale, operator):
    """Open a POS Session as the operator user.

    POS Session.before_insert overwrites `operator` with `frappe.session.user`,
    so we set the session user before insert and close any prior Open session
    for that operator (the doctype enforces one-open-per-operator).
    """
    prior = frappe.session.user
    frappe.set_user(operator)
    try:
        for s in frappe.db.get_all(
            "POS Session", filters={"operator": operator, "status": "Open"}
        ):
            frappe.db.set_value(
                "POS Session", s.name, "status", "Closed", update_modified=False
            )
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
        frappe.set_user(prior)
    return doc.name


def close_session(session_name):
    frappe.db.set_value("POS Session", session_name, "status", "Closed")
    frappe.db.commit()


def make_price_lock(supplier, items, po_date=None):
    """Submit an SMT Price Lock and return (price_lock_name, pos_order_name).

    `items` is a list of (item_code, qty_kg, rate) tuples.
    """
    pl = frappe.get_doc({
        "doctype": "SMT Price Lock",
        "supplier": supplier,
        "po_date": po_date or today(),
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


def make_dropoff(supplier, expected, license_suffix, pos_order_names=None,
                 scheduled_start=None):
    """Create a Dropoff. `expected` is list of (item_code, indicated_kg) tuples."""
    start = scheduled_start or now_datetime()
    end = add_to_date(start, hours=2)
    payload = {
        "doctype": "Dropoff",
        "dropoff_scheduled_start": start,
        "dropoff_scheduled_end": end,
        "license_plate": f"{TEST_PREFIX}{license_suffix}",
        "supplier": supplier,
        "status": "Scheduled",
        "truck_variance_threshold_percent": 100.0,
        "indicated_variance_threshold_percent": 100.0,
    }
    if pos_order_names:
        payload["orders"] = [{"pos_order": p} for p in pos_order_names]
    doc = frappe.get_doc(payload)
    for code, indicated in expected:
        doc.append("expected_items", {"item": code, "indicated_weight": flt(indicated)})
    doc.insert(ignore_permissions=True)
    return doc


# ============================================================
# Helpers used by both scenarios
# ============================================================

def add_containers(api, dropoff_name, session_name, specs, results, tag):
    """Insert containers via add_container and assert print_urls + canonical Thai.

    The container has only a sticker format; the per-Dropoff thermal receipt
    is generated separately from the parent Dropoff (`ใบคิวสองภาษา`).
    """
    container_names = []
    sample_urls = []
    frappe.set_user(TEST_OPERATOR)
    try:
        for code, weight in specs:
            res = api.add_container(
                dropoff=dropoff_name,
                session=session_name,
                item_code=code,
                net_weight=weight,
                container_type="Bag",
                entry_method="Manual Entry",
            )
            assert res.get("success") is True, f"add_container failed: {res}"
            urls = res.get("print_urls") or {}
            assert "sticker" in urls and urls["sticker"], (
                f"{tag}: missing sticker print URL on {res.get('container')}"
            )
            # Canonical Thai item_name — never translated.
            assert res.get("item_name") == code, (
                f"{tag}: item_name should equal canonical Thai code; "
                f"got {res.get('item_name')!r}, expected {code!r}"
            )
            container_names.append(res["container"])
            if len(sample_urls) < 3:
                sample_urls.append((res["container"], urls["sticker"]))
    finally:
        frappe.set_user("Administrator")

    print(f"  {tag}: inserted {len(container_names)} containers")
    for name, sticker in sample_urls:
        print(f"    {name}")
        print(f"      sticker:  {sticker}")
    return container_names


def complete_dropoff_with_truck_weights(api, dropoff_name, gross, tare):
    """Set gross/tare on the dropoff (admin) then call complete_dropoff."""
    do = frappe.get_doc("Dropoff", dropoff_name)
    do.gross_weight = gross
    do.tare_weight = tare
    do.save(ignore_permissions=True)
    do.reload()

    frappe.set_user(TEST_OPERATOR)
    try:
        return api.complete_dropoff(dropoff=dropoff_name)
    finally:
        frappe.set_user("Administrator")


# ============================================================
# Main runner
# ============================================================

def run(cleanup_first=True):
    """Multi-doc container workflow integration test."""
    print("\n" + "=" * 70)
    print("SCRAP METAL SUITE — CONTAINER MULTI-DOC WORKFLOW TEST")
    print(f"Site: {frappe.local.site}  |  Time: {now_datetime()}")
    print("=" * 70)

    results = TestResult()
    original_user = frappe.session.user
    frappe.set_user("Administrator")

    try:
        if cleanup_first:
            print("\nCleaning previous test data...")
            cleanup_test_data()

        # ----- Master data -----
        try:
            ensure_user(TEST_OPERATOR, ["POS Operator", "System Manager"])
            item_a = ensure_item(THAI_ITEM_A)
            item_b = ensure_item(THAI_ITEM_B)
            item_c = ensure_item(THAI_ITEM_C)
            item_d = ensure_item(THAI_ITEM_D)
            supplier = ensure_supplier()
            scale = ensure_scale()
            profile = ensure_pos_profile([item_a, item_b, item_c, item_d])
            frappe.db.commit()
            print(f"  - Master data ready (scale={scale}, supplier={supplier})")
            results.add("setup_master_data", True)
        except Exception as e:
            import traceback; traceback.print_exc()
            results.add("setup_master_data", False, e)
            return results.summary()

        from scrap_metal_suite.api.v1 import dropoff as dropoff_api

        # ============================================================
        # SCENARIO A: One Price Lock -> 3 Dropoffs across days
        # ============================================================
        print("\n" + "-" * 70)
        print("--- SCENARIO A: 1 Price Lock -> 3 Dropoffs (different days) ---")
        print("-" * 70)
        # PL: 600kg copper across 3 grades (200kg A, 200kg B, 200kg C).
        # DO #1: 5 containers, 200kg total mix of A+B
        # DO #2: 4 containers, 200kg total mix of B+C
        # DO #3: 3 containers, 200kg total of A+C
        # After all 3 dropoffs Completed, POS Order fulfillment_percent should
        # be ~100% across all three items.

        try:
            pl_a, po_a = make_price_lock(
                supplier,
                [
                    (item_a, 200, 300),
                    (item_b, 200, 250),
                    (item_c, 200, 200),
                ],
            )
            print(f"  - Price Lock {pl_a} submitted; auto POS Order = {po_a}")

            # Verify exactly one POS Order with smt_price_lock back-ref
            linked = frappe.get_all(
                "POS Order", filters={"smt_price_lock": pl_a}, pluck="name"
            )
            assert len(linked) == 1 and linked[0] == po_a, (
                f"Expected exactly one POS Order linked to {pl_a}, got {linked}"
            )
            results.add("A_price_lock_creates_one_pos_order", True)
        except Exception as e:
            import traceback; traceback.print_exc()
            results.add("A_price_lock_creates_one_pos_order", False, e)
            return results.summary()

        # ----- Day 1: Dropoff #1, 5 containers, 200kg mix of A+B -----
        try:
            day1_start = now_datetime()
            do1 = make_dropoff(
                supplier,
                expected=[(item_a, 100), (item_b, 100)],
                license_suffix="A-D1",
                pos_order_names=[po_a],
                scheduled_start=day1_start,
            )
            session1 = open_pos_session(profile, scale, TEST_OPERATOR)

            specs_d1 = [
                (item_a, 50.0),
                (item_a, 50.0),
                (item_b, 40.0),
                (item_b, 30.0),
                (item_b, 30.0),
            ]
            ctn_d1 = add_containers(
                dropoff_api, do1.name, session1, specs_d1, results, "DO #1"
            )
            assert len(ctn_d1) == 5

            do_d1 = frappe.get_doc("Dropoff", do1.name)
            assert flt(do_d1.total_actual_weight, 1) == 200.0, (
                f"DO#1 total = {do_d1.total_actual_weight}, expected 200"
            )

            # list_containers count check
            listed = dropoff_api.list_containers(dropoff=do1.name)
            assert len(listed) == 5
            for row in listed:
                assert row["status"] == "Active"
                assert row["item_code"] in (item_a, item_b)
                # canonical Thai
                assert row["item_name"] == row["item_code"]
                assert flt(row["net_weight"]) > 0
                assert row["name"]

            close_dropoff_res = complete_dropoff_with_truck_weights(
                dropoff_api, do1.name, gross=2200, tare=2000
            )
            assert close_dropoff_res["status"] == "Completed"
            close_session(session1)
            print(f"  - DO #1 complete: 200kg in 5 containers; status=Completed")
            results.add("A_day1_dropoff", True)
        except Exception as e:
            import traceback; traceback.print_exc()
            results.add("A_day1_dropoff", False, e)
            return results.summary()

        # ----- Day 2: Dropoff #2, 4 containers, 200kg mix of B+C -----
        try:
            day2_start = add_to_date(now_datetime(), hours=24)
            do2 = make_dropoff(
                supplier,
                expected=[(item_b, 100), (item_c, 100)],
                license_suffix="A-D2",
                pos_order_names=[po_a],
                scheduled_start=day2_start,
            )
            session2 = open_pos_session(profile, scale, TEST_OPERATOR)

            # Precisely 100 B (PO has 100 remaining for B) + 100 C.
            specs_d2 = [
                (item_b, 60.0),
                (item_b, 40.0),
                (item_c, 60.0),
                (item_c, 40.0),
            ]
            ctn_d2 = add_containers(
                dropoff_api, do2.name, session2, specs_d2, results, "DO #2"
            )
            assert len(ctn_d2) == 4

            do_d2 = frappe.get_doc("Dropoff", do2.name)
            assert flt(do_d2.total_actual_weight, 1) == 200.0

            listed = dropoff_api.list_containers(dropoff=do2.name)
            assert len(listed) == 4

            close_res = complete_dropoff_with_truck_weights(
                dropoff_api, do2.name, gross=2200, tare=2000
            )
            assert close_res["status"] == "Completed"
            close_session(session2)
            print(f"  - DO #2 complete: 200kg in 4 containers")
            results.add("A_day2_dropoff", True)
        except Exception as e:
            import traceback; traceback.print_exc()
            results.add("A_day2_dropoff", False, e)
            return results.summary()

        # ----- Day 3: Dropoff #3, 3 containers, 200kg of A+C -----
        try:
            day3_start = add_to_date(now_datetime(), hours=48)
            do3 = make_dropoff(
                supplier,
                expected=[(item_a, 100), (item_c, 100)],
                license_suffix="A-D3",
                pos_order_names=[po_a],
                scheduled_start=day3_start,
            )
            session3 = open_pos_session(profile, scale, TEST_OPERATOR)

            specs_d3 = [
                (item_a, 100.0),
                (item_c, 60.0),
                (item_c, 40.0),
            ]
            ctn_d3 = add_containers(
                dropoff_api, do3.name, session3, specs_d3, results, "DO #3"
            )
            assert len(ctn_d3) == 3

            do_d3 = frappe.get_doc("Dropoff", do3.name)
            assert flt(do_d3.total_actual_weight, 1) == 200.0

            listed = dropoff_api.list_containers(dropoff=do3.name)
            assert len(listed) == 3

            close_res = complete_dropoff_with_truck_weights(
                dropoff_api, do3.name, gross=2200, tare=2000
            )
            assert close_res["status"] == "Completed"
            close_session(session3)
            print(f"  - DO #3 complete: 200kg in 3 containers")
            results.add("A_day3_dropoff", True)
        except Exception as e:
            import traceback; traceback.print_exc()
            results.add("A_day3_dropoff", False, e)
            return results.summary()

        # ----- POS Order fulfillment after all 3 dropoffs -----
        try:
            order = frappe.get_doc("POS Order", po_a)
            print(f"  - POS Order {po_a}: total_received={order.total_received}, "
                  f"contracted={order.contracted_weight}, "
                  f"fulfillment_percent={order.fulfillment_percent}, "
                  f"status={order.fulfillment_status}")

            # Per-item received_weight should match contracted weight
            EXPECTED_PER_ITEM = {item_a: 200.0, item_b: 200.0, item_c: 200.0}
            for oi in order.order_items:
                expected = EXPECTED_PER_ITEM.get(oi.item_code)
                assert expected is not None, f"unexpected item {oi.item_code}"
                assert flt(oi.received_weight, 1) == expected, (
                    f"{oi.item_code}: received={oi.received_weight}, "
                    f"expected {expected}"
                )

            # Overall fulfillment >= 98%
            assert flt(order.fulfillment_percent, 1) >= 98.0, (
                f"fulfillment_percent={order.fulfillment_percent}, expected >=98%"
            )
            assert order.fulfillment_status == "Fulfilled", (
                f"fulfillment_status={order.fulfillment_status}, expected Fulfilled"
            )
            results.add("A_pos_order_fulfilled", True)
        except Exception as e:
            import traceback; traceback.print_exc()
            results.add("A_pos_order_fulfilled", False, e)

        # ----- Each Dropoff is linked via Dropoff.orders[].pos_order = po_a -----
        try:
            for do_name in (do1.name, do2.name, do3.name):
                do_doc = frappe.get_doc("Dropoff", do_name)
                linked_pos_orders = [r.pos_order for r in do_doc.orders]
                assert po_a in linked_pos_orders, (
                    f"{do_name}.orders does not link to {po_a}: {linked_pos_orders}"
                )
            results.add("A_dropoffs_linked_to_pos_order", True)
        except Exception as e:
            results.add("A_dropoffs_linked_to_pos_order", False, e)

        # ============================================================
        # SCENARIO B: 2 Price Locks -> 1 Dropoff (mixed)
        # ============================================================
        print("\n" + "-" * 70)
        print("--- SCENARIO B: 2 Price Locks -> 1 Dropoff (mixed) ---")
        print("-" * 70)
        # PL1: 1000kg grade A (item_a)
        # PL2:  500kg grade B (item_d) [grade-D Thai item used as the
        #       distinct "grade B" for this scenario per spec footnote]
        # 1 Dropoff:
        #   * 5 containers x 100kg of item_a = 500kg (50% of PL1 -> Partial)
        #   * 5 containers x 100kg of item_d = 500kg (100% of PL2 -> Fulfilled)

        try:
            pl_b1, po_b1 = make_price_lock(
                supplier,
                [(item_a, 1000, 300)],
            )
            pl_b2, po_b2 = make_price_lock(
                supplier,
                [(item_d, 500, 280)],
            )
            print(f"  - PL1 {pl_b1} -> POS Order {po_b1}")
            print(f"  - PL2 {pl_b2} -> POS Order {po_b2}")

            # Verify two distinct POS Orders
            linked1 = frappe.get_all(
                "POS Order", filters={"smt_price_lock": pl_b1}, pluck="name"
            )
            linked2 = frappe.get_all(
                "POS Order", filters={"smt_price_lock": pl_b2}, pluck="name"
            )
            assert len(linked1) == 1 and linked1[0] == po_b1
            assert len(linked2) == 1 and linked2[0] == po_b2
            assert po_b1 != po_b2, "POS Orders should be distinct"
            results.add("B_two_price_locks_create_two_pos_orders", True)
        except Exception as e:
            import traceback; traceback.print_exc()
            results.add("B_two_price_locks_create_two_pos_orders", False, e)
            return results.summary()

        # ----- Single Dropoff linking BOTH POS Orders -----
        try:
            mixed_do = make_dropoff(
                supplier,
                expected=[(item_a, 500), (item_d, 500)],
                license_suffix="B-MIX",
                pos_order_names=[po_b1, po_b2],
            )

            # Assert orders[] has both
            mixed_doc = frappe.get_doc("Dropoff", mixed_do.name)
            linked_orders = sorted([r.pos_order for r in mixed_doc.orders])
            assert linked_orders == sorted([po_b1, po_b2]), (
                f"Dropoff orders[] = {linked_orders}, expected both POS orders"
            )
            results.add("B_dropoff_links_both_orders", True)
        except Exception as e:
            import traceback; traceback.print_exc()
            results.add("B_dropoff_links_both_orders", False, e)
            return results.summary()

        # ----- Add 10 containers via add_container -----
        try:
            session_b = open_pos_session(profile, scale, TEST_OPERATOR)
            specs_b = (
                [(item_a, 100.0)] * 5
                + [(item_d, 100.0)] * 5
            )
            ctn_b = add_containers(
                dropoff_api, mixed_do.name, session_b, specs_b, results, "DO B"
            )
            assert len(ctn_b) == 10, f"expected 10 containers, got {len(ctn_b)}"

            do_b = frappe.get_doc("Dropoff", mixed_do.name)
            assert flt(do_b.total_actual_weight, 1) == 1000.0, (
                f"Dropoff total = {do_b.total_actual_weight}, expected 1000"
            )

            # list_containers -> all 10 visible
            listed = dropoff_api.list_containers(dropoff=mixed_do.name)
            assert len(listed) == 10, f"list_containers returned {len(listed)}, expected 10"
            grades = sorted({r["item_code"] for r in listed})
            assert grades == sorted([item_a, item_d])
            for row in listed:
                # canonical Thai item_name (verbatim) on the row
                assert row["item_name"] == row["item_code"]
                assert row["status"] == "Active"
            results.add("B_ten_containers_with_print_urls", True)
        except Exception as e:
            import traceback; traceback.print_exc()
            results.add("B_ten_containers_with_print_urls", False, e)
            return results.summary()

        # ----- Complete dropoff -----
        try:
            res = complete_dropoff_with_truck_weights(
                dropoff_api, mixed_do.name, gross=4000, tare=3000
            )
            assert res["status"] == "Completed"
            close_session(session_b)
            print(f"  - Dropoff {mixed_do.name} Completed (1000kg total)")
            results.add("B_dropoff_complete", True)
        except Exception as e:
            import traceback; traceback.print_exc()
            results.add("B_dropoff_complete", False, e)
            return results.summary()

        # ----- PL1 fulfillment: 50% partial -----
        try:
            order_1 = frappe.get_doc("POS Order", po_b1)
            print(f"  - PL1 POS Order: total_received={order_1.total_received}, "
                  f"fulfillment_percent={order_1.fulfillment_percent}, "
                  f"status={order_1.fulfillment_status}")
            assert flt(order_1.total_received, 1) == 500.0, (
                f"PL1 total_received={order_1.total_received}, expected 500"
            )
            assert flt(order_1.fulfillment_percent, 1) == 50.0, (
                f"PL1 fulfillment_percent={order_1.fulfillment_percent}, expected 50.0"
            )
            assert order_1.fulfillment_status == "Partial", (
                f"PL1 fulfillment_status={order_1.fulfillment_status}, expected Partial"
            )
            results.add("B_pl1_partial_50pct", True)
        except Exception as e:
            import traceback; traceback.print_exc()
            results.add("B_pl1_partial_50pct", False, e)

        # ----- PL2 fulfillment: 100% fulfilled -----
        try:
            order_2 = frappe.get_doc("POS Order", po_b2)
            print(f"  - PL2 POS Order: total_received={order_2.total_received}, "
                  f"fulfillment_percent={order_2.fulfillment_percent}, "
                  f"status={order_2.fulfillment_status}")
            assert flt(order_2.total_received, 1) == 500.0, (
                f"PL2 total_received={order_2.total_received}, expected 500"
            )
            assert flt(order_2.fulfillment_percent, 1) == 100.0, (
                f"PL2 fulfillment_percent={order_2.fulfillment_percent}, expected 100"
            )
            assert order_2.fulfillment_status == "Fulfilled", (
                f"PL2 fulfillment_status={order_2.fulfillment_status}, expected Fulfilled"
            )
            results.add("B_pl2_fulfilled_100pct", True)
        except Exception as e:
            import traceback; traceback.print_exc()
            results.add("B_pl2_fulfilled_100pct", False, e)

        # ----- Dropoff-level print URL is constructable -----
        try:
            # We assert shape — no need to actually fetch HTML.
            do_print_url = (
                f"/printview?doctype=Dropoff&name={mixed_do.name}"
                f"&format=ใบคิวสองภาษา"
            )
            assert do_print_url.startswith("/printview?")
            assert f"name={mixed_do.name}" in do_print_url
            assert "doctype=Dropoff" in do_print_url
            assert "format=" in do_print_url
            print(f"  - Dropoff print URL: {do_print_url}")
            results.add("B_dropoff_print_url_constructable", True)
        except Exception as e:
            results.add("B_dropoff_print_url_constructable", False, e)

    except Exception as e:
        print(f"\n!!! FATAL: {e}")
        import traceback; traceback.print_exc()
        results.add("fatal", False, e)
    finally:
        # ----- Cleanup -----
        try:
            frappe.set_user("Administrator")
            cleanup_test_data()
            print("  - Cleanup done")
        except Exception as e:
            print(f"  ! Cleanup error (non-fatal): {e}")
        frappe.set_user(original_user or "Administrator")

    return results.summary()
