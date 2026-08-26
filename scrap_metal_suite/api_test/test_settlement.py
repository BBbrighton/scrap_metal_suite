# Settlement Integration Tests — SMT Price Lock & SMT Purchase Order
# Run with: bench --site metal execute scrap_metal_suite.api_test.test_settlement.run
#
# Tests the Price Lock Settlement business logic:
#   PO create/validate/expiry → PO Final allocation → settlement → cancel cascade
#   → partial settlement → multi-PO → spot rates → edge cases → permissions
#
# This is a standalone test — creates its own test data, cleans up after itself.

import frappe
from frappe.utils import now_datetime, add_days, flt, today


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
        print("SETTLEMENT TEST SUMMARY")
        print("=" * 70)
        total = self.passed + self.failed + self.skipped
        print(f"\nTotal: {total}  |  Passed: {self.passed}  |  Failed: {self.failed}  |  Skipped: {self.skipped}")

        if self.failed > 0:
            print("\nFAILED:")
            for status, name, error in self.results:
                if status == "FAIL":
                    print(f"  ✗ {name}: {str(error)[:200]}")

        if self.skipped > 0:
            print("\nSKIPPED:")
            for status, name, reason in self.results:
                if status == "SKIP":
                    print(f"  - {name}: {reason}")

        print("=" * 70)
        return {"passed": self.passed, "failed": self.failed, "skipped": self.skipped}


# ============================================================
# Test Data Constants
# ============================================================

TEST_PREFIX = "_TEST_SETTLE_"
TEST_ACCOUNTANT = "_test_settle_accountant@test.local"
TEST_ACCT_MANAGER = "_test_settle_acctmgr@test.local"


# ============================================================
# Helpers
# ============================================================

def cleanup_test_data():
    """Remove all settlement test data."""
    frappe.set_user("Administrator")

    # Cancel and delete SMT Purchase Orders first (they link to POs and Dropoff Finals)
    for name in frappe.get_all("SMT Purchase Order", filters={"supplier_name": ["like", f"%{TEST_PREFIX}%"]}, pluck="name"):
        try:
            doc = frappe.get_doc("SMT Purchase Order", name)
            if doc.docstatus == 1:
                # Delete draft PI first
                if doc.purchase_invoice and frappe.db.exists("Purchase Invoice", doc.purchase_invoice):
                    pi = frappe.get_doc("Purchase Invoice", doc.purchase_invoice)
                    if pi.docstatus == 0:
                        frappe.delete_doc("Purchase Invoice", doc.purchase_invoice, force=True, ignore_permissions=True)
                doc.cancel()
            frappe.delete_doc("SMT Purchase Order", name, force=True, ignore_permissions=True)
        except Exception:
            pass

    # Cancel and delete SMT Price Locks
    for name in frappe.get_all("SMT Price Lock", filters={"supplier_name": ["like", f"%{TEST_PREFIX}%"]}, pluck="name"):
        try:
            doc = frappe.get_doc("SMT Price Lock", name)
            if doc.docstatus == 1:
                # Reset settled qty so cancel doesn't block
                for row in doc.items:
                    frappe.db.set_value("SMT Price Lock Item", row.name, {"settled_qty": 0, "remaining_qty": row.po_qty})
                doc.reload()
                doc.cancel()
            frappe.delete_doc("SMT Price Lock", name, force=True, ignore_permissions=True)
        except Exception:
            pass

    # Delete Dropoff Finals (revert status first)
    for name in frappe.get_all("Dropoff Final", filters={"supplier_name": ["like", f"%{TEST_PREFIX}%"]}, pluck="name"):
        try:
            frappe.db.set_value("Dropoff Final", name, {
                "status": "Unsettled", "po_final": None, "settled_by": None, "settled_at": None
            })
            frappe.delete_doc("Dropoff Final", name, force=True, ignore_permissions=True)
        except Exception:
            pass

    # Delete draft Purchase Invoices linked to test supplier
    for supplier in frappe.get_all("Supplier", filters={"supplier_name": ["like", f"%{TEST_PREFIX}%"]}, pluck="name"):
        for pi_name in frappe.get_all("Purchase Invoice", filters={"supplier": supplier, "docstatus": 0}, pluck="name"):
            try:
                frappe.delete_doc("Purchase Invoice", pi_name, force=True, ignore_permissions=True)
            except Exception:
                pass

    # Delete test Dropoffs
    for name in frappe.get_all("Dropoff", filters={"license_plate": ["like", f"%{TEST_PREFIX}%"]}, pluck="name"):
        try:
            frappe.delete_doc("Dropoff", name, force=True, ignore_permissions=True)
        except Exception:
            pass

    # Delete test supplier
    for s in frappe.get_all("Supplier", filters={"supplier_name": ["like", f"%{TEST_PREFIX}%"]}, pluck="name"):
        frappe.delete_doc("Supplier", s, force=True, ignore_permissions=True)

    # Delete test users
    for email in [TEST_ACCOUNTANT, TEST_ACCT_MANAGER]:
        if frappe.db.exists("User", email):
            frappe.delete_doc("User", email, force=True, ignore_permissions=True)

    # Delete test items
    for item in frappe.get_all("Item", filters={"item_name": ["like", f"%{TEST_PREFIX}%"]}, pluck="name"):
        frappe.delete_doc("Item", item, force=True, ignore_permissions=True)

    frappe.db.commit()


def create_test_user(email, first_name, roles):
    """Create a test user with given roles."""
    if frappe.db.exists("User", email):
        user = frappe.get_doc("User", email)
    else:
        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": first_name,
            "send_welcome_email": 0,
            "new_password": "Test@12345",
        })
        user.insert(ignore_permissions=True)

    user.roles = []
    for role in roles:
        user.append("roles", {"role": role})
    user.save(ignore_permissions=True)
    return user


def assert_blocked_by(results, name, exc, must_contain):
    """Record a 'correctly blocked' pass ONLY if the error is the expected one.

    A bare `except ValidationError: results.add(name, True)` will happily accept
    an error from anywhere — including a broken fixture — and report the test as
    passing. That is exactly what happened here: when Wave 9 made the Dropoff
    fixture throw "POS Order Required", four negative tests caught that instead
    of the condition they were written to check, and reported green. The suite
    looked 28/37 healthy while its most important guards were inert.

    `must_contain` is a substring (or list of substrings, any one matching) that
    only the intended failure would produce.
    """
    text = str(exc)
    needles = [must_contain] if isinstance(must_contain, str) else list(must_contain)
    if any(n.lower() in text.lower() for n in needles):
        print(f"  ✓ {name} correctly blocked: {text[:80]}")
        results.add(name, True)
    else:
        results.add(
            name, False,
            f"blocked, but by the WRONG error — expected one of {needles}, got: {text[:160]}",
        )


def _price_lock_with_order(supplier, items):
    """Submit a Price Lock and return the POS Order its on_submit creates.

    Wave 9 (`Dropoff.validate_at_least_one_order`) forbids walk-in drop-offs, so
    every Dropoff fixture must link to a POS Order. Mirrors
    `ui_test/fixtures.py::_ensure_price_lock_with_order`.

    `items` is a list of `(item_code, weight)` tuples; the lock is raised for at
    least the weight being delivered so allocation tests are not blocked by an
    unrelated over-allocation guard.
    """
    pl = frappe.get_doc({
        "doctype": "SMT Price Lock",
        "supplier": supplier,
        "po_date": today(),
        "items": [
            {"item_code": code, "po_qty": max(weight, 1), "po_rate": 1}
            for code, weight in items
        ],
    })
    pl.insert(ignore_permissions=True)
    pl.submit()
    po_name = frappe.db.get_value("POS Order", {"smt_price_lock": pl.name}, "name")
    if not po_name:
        frappe.throw(f"Auto POS Order not created for SMT Price Lock {pl.name}")
    return pl.name, po_name


def create_test_dropoff_final(supplier, items, status="Unsettled"):
    """Create a Dropoff Final with good items for testing.
    items: list of (item_code, weight) tuples

    Builds the full Wave 9 chain: Price Lock → POS Order → Dropoff → Dropoff
    Final. The Dropoff is then forced to Completed via db_set.

    This helper used to create a bare Dropoff with no linked orders, on the
    stated assumption that it "bypasses most validation". Wave 9 added
    `validate_at_least_one_order`, which made that throw "POS Order Required" —
    and because the helper is used by most of this suite, that single failure
    cascaded into 5 failures, 4 skips, and 4 tests that PASSED FOR THE WRONG
    REASON (they caught the fixture's ValidationError and reported it as the
    condition they were meant to be testing).
    """
    _, po_name = _price_lock_with_order(supplier, items)

    # Wave 9: link the order, and mirror its items into expected_items —
    # `validate_expected_items_match_orders` checks both directions.
    dropoff = frappe.get_doc({
        "doctype": "Dropoff",
        "supplier": supplier,
        "status": "Draft",
        "license_plate": f"{TEST_PREFIX}TRUCK",
        "dropoff_scheduled_start": now_datetime(),
        "orders": [{"pos_order": po_name}],
        "expected_items": [
            {"item": code, "indicated_weight": weight} for code, weight in items
        ],
    })
    dropoff.insert(ignore_permissions=True)
    # Force status to Completed via db_set (bypasses validate)
    frappe.db.set_value("Dropoff", dropoff.name, "status", "Completed")

    # Create Dropoff Final with status=Unsettled
    # before_save calls aggregate_from_sortings() which returns early
    # because no Production Sorting records exist for this Dropoff.
    # auto_complete_if_done() returns early because status is already Unsettled.
    dof = frappe.get_doc({
        "doctype": "Dropoff Final",
        "dropoff": dropoff.name,
        "supplier": supplier,
        "status": status,
    })
    for item_code, weight in items:
        dof.append("good_items", {
            "item_code": item_code,
            "weight": weight,
            "uom": "Kg",
        })
    dof.total_good_weight = sum(w for _, w in items)
    dof.total_verified_weight = dof.total_good_weight
    dof.insert(ignore_permissions=True)
    frappe.db.commit()
    return dof.name


# ============================================================
# Test Groups
# ============================================================

def test_200_setup(results, ctx):
    """Create test users, items, supplier."""
    print("\n--- 200. Settlement Test Setup ---")

    # Create accountant user
    try:
        user = create_test_user(TEST_ACCOUNTANT, f"{TEST_PREFIX}Accountant",
                                ["SMT Accountant"])
        print(f"  ✓ Created SMT Accountant: {user.name}")
        results.add("create_accountant", True)
    except Exception as e:
        results.add("create_accountant", False, e)

    # Create accounting manager
    try:
        user = create_test_user(TEST_ACCT_MANAGER, f"{TEST_PREFIX}AcctMgr",
                                ["SMT Accounting Manager"])
        print(f"  ✓ Created SMT Accounting Manager: {user.name}")
        results.add("create_acct_manager", True)
    except Exception as e:
        results.add("create_acct_manager", False, e)

    # Create test items
    try:
        items = []
        for item_name in [f"{TEST_PREFIX}Copper Wire", f"{TEST_PREFIX}Aluminum Sheet", f"{TEST_PREFIX}Copper Grade B"]:
            if not frappe.db.exists("Item", {"item_name": item_name}):
                item = frappe.get_doc({
                    "doctype": "Item",
                    "item_code": item_name,
                    "item_name": item_name,
                    "item_group": "Raw Material",
                    "stock_uom": "Kg",
                    "is_stock_item": 1,
                })
                item.insert(ignore_permissions=True)
            items.append(item_name)
        ctx["items"] = items
        ctx["copper"] = items[0]
        ctx["aluminum"] = items[1]
        ctx["copper_b"] = items[2]
        print(f"  ✓ Created {len(items)} test items")
        results.add("create_items", True)
    except Exception as e:
        results.add("create_items", False, e)

    # Create test supplier
    try:
        supplier_name = f"{TEST_PREFIX}ACME Metals"
        if not frappe.db.exists("Supplier", {"supplier_name": supplier_name}):
            supplier = frappe.get_doc({
                "doctype": "Supplier",
                "supplier_name": supplier_name,
                "supplier_group": "Raw Material",
            })
            supplier.insert(ignore_permissions=True)
        ctx["supplier"] = frappe.db.get_value("Supplier", {"supplier_name": supplier_name}, "name")
        print(f"  ✓ Created supplier: {supplier_name}")
        results.add("create_supplier", True)
    except Exception as e:
        results.add("create_supplier", False, e)

    # Create a second supplier for cross-supplier tests
    try:
        supplier_name2 = f"{TEST_PREFIX}Beta Scrap"
        if not frappe.db.exists("Supplier", {"supplier_name": supplier_name2}):
            supplier2 = frappe.get_doc({
                "doctype": "Supplier",
                "supplier_name": supplier_name2,
                "supplier_group": "Raw Material",
            })
            supplier2.insert(ignore_permissions=True)
        ctx["supplier2"] = frappe.db.get_value("Supplier", {"supplier_name": supplier_name2}, "name")
        print(f"  ✓ Created supplier 2: {supplier_name2}")
        results.add("create_supplier2", True)
    except Exception as e:
        results.add("create_supplier2", False, e)

    frappe.db.commit()


def test_201_po_create_and_submit(results, ctx):
    """Create and submit an SMT Price Lock — happy path."""
    print("\n--- 201. SMT Price Lock Create & Submit ---")

    try:
        po = frappe.get_doc({
            "doctype": "SMT Price Lock",
            "supplier": ctx["supplier"],
            "po_date": today(),
            "items": [
                {"item_code": ctx["copper"], "po_qty": 10, "po_rate": 300},
                {"item_code": ctx["aluminum"], "po_qty": 5, "po_rate": 75},
            ]
        })
        po.insert(ignore_permissions=True)
        po.submit()

        assert po.docstatus == 1, f"Expected docstatus 1, got {po.docstatus}"
        assert po.status == "Open", f"Expected Open, got {po.status}"
        assert flt(po.total_po_value) == 3375.0, f"Expected 3375, got {po.total_po_value}"

        # Check item rows
        for row in po.items:
            assert flt(row.settled_qty) == 0, f"settled_qty should be 0, got {row.settled_qty}"
            assert flt(row.remaining_qty) == flt(row.po_qty), f"remaining_qty mismatch"

        ctx["po1"] = po.name
        ctx["po1_copper_row"] = po.items[0].name
        ctx["po1_aluminum_row"] = po.items[1].name
        print(f"  ✓ PO created and submitted: {po.name} (total: {po.total_po_value})")
        results.add("po_create_submit", True)
    except Exception as e:
        results.add("po_create_submit", False, e)

    frappe.db.commit()


def test_202_po_validation(results, ctx):
    """PO validation guards — zero qty, negative rate, no items."""
    print("\n--- 202. SMT Price Lock Validation Guards ---")

    # Zero qty
    try:
        po = frappe.get_doc({
            "doctype": "SMT Price Lock",
            "supplier": ctx["supplier"],
            "po_date": today(),
            "items": [{"item_code": ctx["copper"], "po_qty": 0, "po_rate": 300}]
        })
        po.insert(ignore_permissions=True)
        results.add("po_zero_qty_blocked", False, "Should have thrown")
    except frappe.exceptions.ValidationError:
        print(f"  ✓ Zero qty correctly blocked")
        results.add("po_zero_qty_blocked", True)
    except Exception as e:
        results.add("po_zero_qty_blocked", False, e)

    # Negative rate
    try:
        po = frappe.get_doc({
            "doctype": "SMT Price Lock",
            "supplier": ctx["supplier"],
            "po_date": today(),
            "items": [{"item_code": ctx["copper"], "po_qty": 5, "po_rate": -10}]
        })
        po.insert(ignore_permissions=True)
        results.add("po_negative_rate_blocked", False, "Should have thrown")
    except frappe.exceptions.ValidationError:
        print(f"  ✓ Negative rate correctly blocked")
        results.add("po_negative_rate_blocked", True)
    except Exception as e:
        results.add("po_negative_rate_blocked", False, e)

    # No items
    try:
        po = frappe.get_doc({
            "doctype": "SMT Price Lock",
            "supplier": ctx["supplier"],
            "po_date": today(),
            "items": []
        })
        po.insert(ignore_permissions=True)
        results.add("po_no_items_blocked", False, "Should have thrown")
    except (frappe.exceptions.ValidationError, frappe.exceptions.MandatoryError):
        print(f"  ✓ No items correctly blocked")
        results.add("po_no_items_blocked", True)
    except Exception as e:
        results.add("po_no_items_blocked", False, e)

    frappe.db.rollback()


def test_203_po_expiry(results, ctx):
    """Auto-expire only Open POs, not Partially Settled."""
    print("\n--- 203. SMT Price Lock Expiry ---")

    from scrap_metal_suite.scheduler import expire_open_pos

    # Create PO with past expiry date
    try:
        po = frappe.get_doc({
            "doctype": "SMT Price Lock",
            "supplier": ctx["supplier"],
            "po_date": today(),
            "expiry_date": add_days(today(), -1),
            "items": [{"item_code": ctx["copper"], "po_qty": 5, "po_rate": 100}]
        })
        po.insert(ignore_permissions=True)
        po.submit()
        ctx["po_expiry"] = po.name

        count = expire_open_pos()
        po.reload()
        assert po.status == "Expired", f"Expected Expired, got {po.status}"
        print(f"  ✓ Open PO correctly expired: {po.name}")
        results.add("po_expiry_open", True)
    except Exception as e:
        results.add("po_expiry_open", False, e)

    # PO with no expiry should NOT be expired
    try:
        po_main = frappe.get_doc("SMT Price Lock", ctx["po1"])
        assert po_main.status == "Open", f"Main PO should still be Open, got {po_main.status}"
        print(f"  ✓ PO without expiry NOT expired")
        results.add("po_no_expiry_safe", True)
    except Exception as e:
        results.add("po_no_expiry_safe", False, e)

    frappe.db.commit()


def test_210_create_dropoff_final(results, ctx):
    """Create an Unsettled Dropoff Final for settlement tests."""
    print("\n--- 210. Create Dropoff Final ---")

    try:
        dof_name = create_test_dropoff_final(
            ctx["supplier"],
            [
                (ctx["copper"], 9.0),
                (ctx["copper_b"], 1.0),
                (ctx["aluminum"], 5.0),
            ]
        )
        ctx["dof1"] = dof_name

        dof = frappe.get_doc("Dropoff Final", dof_name)
        assert dof.status == "Unsettled", f"Expected Unsettled, got {dof.status}"
        assert flt(dof.total_good_weight) == 15.0, f"Expected 15kg, got {dof.total_good_weight}"
        print(f"  ✓ Dropoff Final created: {dof_name} (15kg, Unsettled)")
        results.add("create_dropoff_final", True)
    except Exception as e:
        results.add("create_dropoff_final", False, e)


def test_220_po_final_simple(results, ctx):
    """Simple settlement — allocate all items from Dropoff Final."""
    print("\n--- 220. SMT Purchase Order — Simple Settlement ---")

    if not ctx.get("dof1") or not ctx.get("po1"):
        results.skip("po_final_simple", "Missing prerequisites")
        return

    try:
        pof = frappe.get_doc({
            "doctype": "SMT Purchase Order",
            "supplier": ctx["supplier"],
            "final_date": today(),
            "drop_off_finals": [
                {"drop_off_final": ctx["dof1"]}
            ],
            "allocations": [
                {
                    "drop_off_final": ctx["dof1"],
                    "item_code": ctx["copper"],
                    "qty": 9.0,
                    "source_type": "PO",
                    "po": ctx["po1"],
                    "rate": 300,
                },
                {
                    "drop_off_final": ctx["dof1"],
                    "item_code": ctx["copper_b"],
                    "qty": 1.0,
                    "source_type": "Spot",
                    "rate": 285,
                },
                {
                    "drop_off_final": ctx["dof1"],
                    "item_code": ctx["aluminum"],
                    "qty": 5.0,
                    "source_type": "PO",
                    "po": ctx["po1"],
                    "rate": 75,
                },
            ]
        })
        pof.insert(ignore_permissions=True)
        pof.submit()

        ctx["pof1"] = pof.name

        # Check totals
        assert flt(pof.total_po_value) == flt(9 * 300 + 5 * 75), \
            f"PO value: expected {9*300 + 5*75}, got {pof.total_po_value}"
        assert flt(pof.total_spot_value) == 285.0, \
            f"Spot value: expected 285, got {pof.total_spot_value}"
        assert flt(pof.total_amount) == flt(9*300 + 5*75 + 285), \
            f"Grand total: expected {9*300+5*75+285}, got {pof.total_amount}"
        print(f"  ✓ PO Final totals correct: PO={pof.total_po_value}, Spot={pof.total_spot_value}, Total={pof.total_amount}")

        # Check PO settlement
        po = frappe.get_doc("SMT Price Lock", ctx["po1"])
        copper_row = next(r for r in po.items if r.item_code == ctx["copper"])
        aluminum_row = next(r for r in po.items if r.item_code == ctx["aluminum"])

        assert flt(copper_row.settled_qty) == 9.0, f"Copper settled: expected 9, got {copper_row.settled_qty}"
        assert flt(copper_row.remaining_qty) == 1.0, f"Copper remaining: expected 1, got {copper_row.remaining_qty}"
        assert flt(aluminum_row.settled_qty) == 5.0, f"Aluminum settled: expected 5, got {aluminum_row.settled_qty}"
        assert flt(aluminum_row.remaining_qty) == 0.0, f"Aluminum remaining: expected 0, got {aluminum_row.remaining_qty}"
        assert po.status == "Partially Settled", f"PO status: expected Partially Settled, got {po.status}"
        print(f"  ✓ PO settled_qty updated: Copper 9/10, Aluminum 5/5")
        print(f"  ✓ PO status: {po.status}")

        # Check Dropoff Final marked settled
        dof = frappe.get_doc("Dropoff Final", ctx["dof1"])
        assert dof.status == "Settled", f"DOF status: expected Settled, got {dof.status}"
        assert dof.po_final == pof.name, f"DOF po_final: expected {pof.name}, got {dof.po_final}"
        print(f"  ✓ Dropoff Final status: Settled, linked to {pof.name}")

        # Check Draft PI created
        assert pof.purchase_invoice, "No Purchase Invoice created"
        pi = frappe.get_doc("Purchase Invoice", pof.purchase_invoice)
        assert pi.docstatus == 0, f"PI should be Draft, got docstatus {pi.docstatus}"
        assert len(pi.items) == 3, f"PI should have 3 items, got {len(pi.items)}"
        ctx["pi1"] = pi.name
        print(f"  ✓ Draft Purchase Invoice created: {pi.name}")

        results.add("po_final_simple", True)
    except Exception as e:
        import traceback
        traceback.print_exc()
        results.add("po_final_simple", False, e)

    frappe.db.commit()


def test_230_po_final_cancel(results, ctx):
    """Cancel PO Final — verify everything reverts."""
    print("\n--- 230. SMT Purchase Order Cancel Cascade ---")

    if not ctx.get("pof1"):
        results.skip("po_final_cancel", "No PO Final to cancel")
        return

    try:
        pof = frappe.get_doc("SMT Purchase Order", ctx["pof1"])
        pof.cancel()

        # Check PO reverted
        po = frappe.get_doc("SMT Price Lock", ctx["po1"])
        copper_row = next(r for r in po.items if r.item_code == ctx["copper"])
        assert flt(copper_row.settled_qty) == 0, f"Copper settled should be 0, got {copper_row.settled_qty}"
        assert po.status == "Open", f"PO status should be Open, got {po.status}"
        print(f"  ✓ PO reverted to Open, settled_qty = 0")

        # Check Dropoff Final reverted
        dof = frappe.get_doc("Dropoff Final", ctx["dof1"])
        assert dof.status == "Unsettled", f"DOF should be Unsettled, got {dof.status}"
        assert not dof.po_final, f"DOF po_final should be cleared, got {dof.po_final}"
        print(f"  ✓ Dropoff Final reverted to Unsettled")

        # Check Draft PI deleted
        assert not frappe.db.exists("Purchase Invoice", ctx.get("pi1")), \
            "Draft PI should have been deleted"
        print(f"  ✓ Draft Purchase Invoice deleted")

        results.add("po_final_cancel", True)
    except Exception as e:
        import traceback
        traceback.print_exc()
        results.add("po_final_cancel", False, e)

    frappe.db.commit()


def test_240_partial_settlement(results, ctx):
    """Partial PO settlement — settle less than PO qty."""
    print("\n--- 240. Partial Settlement ---")

    if not ctx.get("dof1") or not ctx.get("po1"):
        results.skip("partial_settlement", "Missing prerequisites")
        return

    # Create a new DOF with only copper (less than PO qty)
    try:
        dof2_name = create_test_dropoff_final(
            ctx["supplier"],
            [(ctx["copper"], 4.0)]
        )
        ctx["dof2"] = dof2_name

        pof = frappe.get_doc({
            "doctype": "SMT Purchase Order",
            "supplier": ctx["supplier"],
            "final_date": today(),
            "drop_off_finals": [{"drop_off_final": dof2_name}],
            "allocations": [
                {
                    "drop_off_final": dof2_name,
                    "item_code": ctx["copper"],
                    "qty": 4.0,
                    "source_type": "PO",
                    "po": ctx["po1"],
                    "rate": 300,
                }
            ]
        })
        pof.insert(ignore_permissions=True)
        pof.submit()
        ctx["pof2"] = pof.name

        po = frappe.get_doc("SMT Price Lock", ctx["po1"])
        copper_row = next(r for r in po.items if r.item_code == ctx["copper"])
        assert flt(copper_row.settled_qty) == 4.0, f"Expected 4, got {copper_row.settled_qty}"
        assert flt(copper_row.remaining_qty) == 6.0, f"Expected 6, got {copper_row.remaining_qty}"
        assert po.status == "Partially Settled", f"Expected Partially Settled, got {po.status}"
        print(f"  ✓ Partial settlement: 4/10 copper settled, status={po.status}")
        results.add("partial_settlement", True)
    except Exception as e:
        import traceback
        traceback.print_exc()
        results.add("partial_settlement", False, e)

    frappe.db.commit()


def test_241_complete_settlement(results, ctx):
    """Complete the remaining PO qty across another PO Final."""
    print("\n--- 241. Complete Remaining Settlement ---")

    if not ctx.get("po1"):
        results.skip("complete_settlement", "Missing PO")
        return

    try:
        # Settle remaining 6kg copper + 5kg aluminum
        dof3_name = create_test_dropoff_final(
            ctx["supplier"],
            [(ctx["copper"], 6.0), (ctx["aluminum"], 5.0)]
        )
        ctx["dof3"] = dof3_name

        pof = frappe.get_doc({
            "doctype": "SMT Purchase Order",
            "supplier": ctx["supplier"],
            "final_date": today(),
            "drop_off_finals": [{"drop_off_final": dof3_name}],
            "allocations": [
                {
                    "drop_off_final": dof3_name,
                    "item_code": ctx["copper"],
                    "qty": 6.0,
                    "source_type": "PO",
                    "po": ctx["po1"],
                    "rate": 300,
                },
                {
                    "drop_off_final": dof3_name,
                    "item_code": ctx["aluminum"],
                    "qty": 5.0,
                    "source_type": "PO",
                    "po": ctx["po1"],
                    "rate": 75,
                },
            ]
        })
        pof.insert(ignore_permissions=True)
        pof.submit()
        ctx["pof3"] = pof.name

        po = frappe.get_doc("SMT Price Lock", ctx["po1"])
        copper_row = next(r for r in po.items if r.item_code == ctx["copper"])
        aluminum_row = next(r for r in po.items if r.item_code == ctx["aluminum"])
        assert flt(copper_row.settled_qty) == 10.0, f"Copper settled: expected 10, got {copper_row.settled_qty}"
        assert flt(copper_row.remaining_qty) == 0.0, f"Copper remaining: expected 0, got {copper_row.remaining_qty}"
        assert flt(aluminum_row.settled_qty) == 5.0
        assert po.status == "Fully Settled", f"Expected Fully Settled, got {po.status}"
        print(f"  ✓ PO fully settled: Copper 10/10, Aluminum 5/5, status={po.status}")
        results.add("complete_settlement", True)
    except Exception as e:
        import traceback
        traceback.print_exc()
        results.add("complete_settlement", False, e)

    frappe.db.commit()


def test_250_multi_po(results, ctx):
    """Two POs at different rates, single dropoff (UC-3)."""
    print("\n--- 250. Multi-PO Single Dropoff ---")

    try:
        # Create two POs
        po_a = frappe.get_doc({
            "doctype": "SMT Price Lock",
            "supplier": ctx["supplier"],
            "po_date": today(),
            "items": [{"item_code": ctx["copper"], "po_qty": 5, "po_rate": 300}]
        })
        po_a.insert(ignore_permissions=True)
        po_a.submit()

        po_b = frappe.get_doc({
            "doctype": "SMT Price Lock",
            "supplier": ctx["supplier"],
            "po_date": today(),
            "items": [{"item_code": ctx["copper"], "po_qty": 5, "po_rate": 310}]
        })
        po_b.insert(ignore_permissions=True)
        po_b.submit()

        # One dropoff with 10kg copper
        dof = create_test_dropoff_final(ctx["supplier"], [(ctx["copper"], 10.0)])

        # Split allocation across two POs
        pof = frappe.get_doc({
            "doctype": "SMT Purchase Order",
            "supplier": ctx["supplier"],
            "final_date": today(),
            "drop_off_finals": [{"drop_off_final": dof}],
            "allocations": [
                {
                    "drop_off_final": dof,
                    "item_code": ctx["copper"],
                    "qty": 5.0,
                    "source_type": "PO",
                    "po": po_a.name,
                    "rate": 300,
                },
                {
                    "drop_off_final": dof,
                    "item_code": ctx["copper"],
                    "qty": 5.0,
                    "source_type": "PO",
                    "po": po_b.name,
                    "rate": 310,
                },
            ]
        })
        pof.insert(ignore_permissions=True)
        pof.submit()

        # Both POs fully settled
        po_a.reload()
        po_b.reload()
        assert po_a.status == "Fully Settled", f"PO-A: expected Fully Settled, got {po_a.status}"
        assert po_b.status == "Fully Settled", f"PO-B: expected Fully Settled, got {po_b.status}"

        # PI should have 2 items at different rates
        pi = frappe.get_doc("Purchase Invoice", pof.purchase_invoice)
        rates = sorted([flt(r.rate) for r in pi.items])
        assert rates == [300.0, 310.0], f"PI rates: expected [300, 310], got {rates}"
        assert flt(pof.total_amount) == flt(5*300 + 5*310), f"Total: expected {5*300+5*310}, got {pof.total_amount}"

        print(f"  ✓ Multi-PO settlement: 5kg@300 + 5kg@310 = {pof.total_amount}")
        results.add("multi_po", True)
    except Exception as e:
        import traceback
        traceback.print_exc()
        results.add("multi_po", False, e)

    frappe.db.commit()


def test_260_over_delivery(results, ctx):
    """Over-delivery — more material than PO covers (UC-5)."""
    print("\n--- 260. Over-Delivery with Spot ---")

    try:
        po = frappe.get_doc({
            "doctype": "SMT Price Lock",
            "supplier": ctx["supplier"],
            "po_date": today(),
            "items": [{"item_code": ctx["copper"], "po_qty": 5, "po_rate": 300}]
        })
        po.insert(ignore_permissions=True)
        po.submit()

        dof = create_test_dropoff_final(ctx["supplier"], [(ctx["copper"], 8.0)])

        pof = frappe.get_doc({
            "doctype": "SMT Purchase Order",
            "supplier": ctx["supplier"],
            "final_date": today(),
            "drop_off_finals": [{"drop_off_final": dof}],
            "allocations": [
                {
                    "drop_off_final": dof,
                    "item_code": ctx["copper"],
                    "qty": 5.0,
                    "source_type": "PO",
                    "po": po.name,
                    "rate": 300,
                },
                {
                    "drop_off_final": dof,
                    "item_code": ctx["copper"],
                    "qty": 3.0,
                    "source_type": "Spot",
                    "rate": 290,
                },
            ]
        })
        pof.insert(ignore_permissions=True)
        pof.submit()

        po.reload()
        assert po.status == "Fully Settled"
        assert flt(pof.total_po_value) == 1500.0
        assert flt(pof.total_spot_value) == 870.0
        print(f"  ✓ Over-delivery: 5kg@PO + 3kg@Spot = {pof.total_amount}")
        results.add("over_delivery", True)
    except Exception as e:
        import traceback
        traceback.print_exc()
        results.add("over_delivery", False, e)

    frappe.db.commit()


def test_270_over_allocation_blocked(results, ctx):
    """Cannot allocate more than PO remaining qty."""
    print("\n--- 270. Over-Allocation Blocked ---")

    try:
        po = frappe.get_doc({
            "doctype": "SMT Price Lock",
            "supplier": ctx["supplier"],
            "po_date": today(),
            "items": [{"item_code": ctx["copper"], "po_qty": 5, "po_rate": 300}]
        })
        po.insert(ignore_permissions=True)
        po.submit()

        dof = create_test_dropoff_final(ctx["supplier"], [(ctx["copper"], 6.0)])

        pof = frappe.get_doc({
            "doctype": "SMT Purchase Order",
            "supplier": ctx["supplier"],
            "final_date": today(),
            "drop_off_finals": [{"drop_off_final": dof}],
            "allocations": [
                {
                    "drop_off_final": dof,
                    "item_code": ctx["copper"],
                    "qty": 6.0,
                    "source_type": "PO",
                    "po": po.name,
                    "rate": 300,
                }
            ]
        })
        pof.insert(ignore_permissions=True)
        results.add("over_allocation_blocked", False, "Should have thrown validation error")
    except frappe.exceptions.ValidationError as e:
        assert_blocked_by(results, "over_allocation_blocked", e, ["exceeds", "over-allocation", "remaining"])
    except Exception as e:
        results.add("over_allocation_blocked", False, e)

    frappe.db.rollback()


def test_280_cross_supplier_blocked(results, ctx):
    """Cannot mix suppliers in PO Final."""
    print("\n--- 280. Cross-Supplier Blocked ---")

    try:
        # PO for supplier 1
        po = frappe.get_doc({
            "doctype": "SMT Price Lock",
            "supplier": ctx["supplier"],
            "po_date": today(),
            "items": [{"item_code": ctx["copper"], "po_qty": 5, "po_rate": 300}]
        })
        po.insert(ignore_permissions=True)
        po.submit()

        # Dropoff Final for supplier 2
        dof = create_test_dropoff_final(ctx["supplier2"], [(ctx["copper"], 5.0)])

        # PO Final for supplier 2 but referencing supplier 1's PO
        pof = frappe.get_doc({
            "doctype": "SMT Purchase Order",
            "supplier": ctx["supplier2"],
            "final_date": today(),
            "drop_off_finals": [{"drop_off_final": dof}],
            "allocations": [
                {
                    "drop_off_final": dof,
                    "item_code": ctx["copper"],
                    "qty": 5.0,
                    "source_type": "PO",
                    "po": po.name,
                    "rate": 300,
                }
            ]
        })
        pof.insert(ignore_permissions=True)
        results.add("cross_supplier_blocked", False, "Should have thrown")
    except frappe.exceptions.ValidationError as e:
        assert_blocked_by(results, "cross_supplier_blocked", e, "belongs to supplier")
    except Exception as e:
        results.add("cross_supplier_blocked", False, e)

    frappe.db.rollback()


def test_290_po_cancel_with_settlement(results, ctx):
    """Cannot cancel PO that has settled qty."""
    print("\n--- 290. PO Cancel With Settlement Blocked ---")

    if not ctx.get("po1"):
        results.skip("po_cancel_blocked", "No PO")
        return

    try:
        po = frappe.get_doc("SMT Price Lock", ctx["po1"])
        if po.status in ("Partially Settled", "Fully Settled"):
            po.cancel()
            results.add("po_cancel_blocked", False, "Should have thrown")
        else:
            results.skip("po_cancel_blocked", f"PO status is {po.status}, not settled")
    except frappe.exceptions.ValidationError as e:
        assert_blocked_by(results, "po_cancel_blocked", e, ["settled quantity", "Cannot cancel"])
    except Exception as e:
        results.add("po_cancel_blocked", False, e)


def test_300_accountant_read_access(results, ctx):
    """SMT Accountant can read other SMT doctypes but not create."""
    print("\n--- 300. Accountant Read Access ---")

    read_doctypes = [
        "Dropoff", "Dropoff Final", "Production Sorting", "Production Session",
        "Truck Weight", "Scrap Weight", "Scrap Purchase", "POS Order",
        "POS Session", "Scale",
    ]

    for dt in read_doctypes:
        try:
            frappe.set_user(TEST_ACCOUNTANT)
            has_read = frappe.has_permission(dt, "read")
            has_create = frappe.has_permission(dt, "create")
            frappe.set_user("Administrator")

            if has_read and not has_create:
                results.add(f"accountant_read_{dt.lower().replace(' ', '_')}", True)
            elif not has_read:
                print(f"  ✗ Accountant cannot read {dt}")
                results.add(f"accountant_read_{dt.lower().replace(' ', '_')}", False, "No read access")
            else:
                print(f"  ✗ Accountant has create access on {dt}")
                results.add(f"accountant_read_{dt.lower().replace(' ', '_')}", False, "Has create access")
        except Exception as e:
            frappe.set_user("Administrator")
            results.add(f"accountant_read_{dt.lower().replace(' ', '_')}", False, e)

    # Accountant should have full access on SMT Price Lock and SMT Purchase Order
    for dt in ["SMT Price Lock", "SMT Purchase Order"]:
        try:
            frappe.set_user(TEST_ACCOUNTANT)
            has_create = frappe.has_permission(dt, "create")
            frappe.set_user("Administrator")

            if has_create:
                print(f"  ✓ Accountant has create access on {dt}")
                results.add(f"accountant_create_{dt.lower().replace(' ', '_')}", True)
            else:
                results.add(f"accountant_create_{dt.lower().replace(' ', '_')}", False, "No create access")
        except Exception as e:
            frappe.set_user("Administrator")
            results.add(f"accountant_create_{dt.lower().replace(' ', '_')}", False, e)

    print(f"  ✓ Permission matrix verified for {len(read_doctypes)} read-only + 2 full-access doctypes")


def test_310_rate_locked(results, ctx):
    """PO rate cannot be overridden in allocation — forced to PO rate."""
    print("\n--- 310. PO Rate Locked ---")

    try:
        po = frappe.get_doc({
            "doctype": "SMT Price Lock",
            "supplier": ctx["supplier"],
            "po_date": today(),
            "items": [{"item_code": ctx["copper"], "po_qty": 5, "po_rate": 300}]
        })
        po.insert(ignore_permissions=True)
        po.submit()

        dof = create_test_dropoff_final(ctx["supplier"], [(ctx["copper"], 5.0)])

        # Try to set rate=350, should be forced to 300
        pof = frappe.get_doc({
            "doctype": "SMT Purchase Order",
            "supplier": ctx["supplier"],
            "final_date": today(),
            "drop_off_finals": [{"drop_off_final": dof}],
            "allocations": [
                {
                    "drop_off_final": dof,
                    "item_code": ctx["copper"],
                    "qty": 5.0,
                    "source_type": "PO",
                    "po": po.name,
                    "rate": 350,  # Wrong rate — should be forced to 300
                }
            ]
        })
        pof.insert(ignore_permissions=True)

        # Check rate was forced
        alloc = pof.allocations[0]
        assert flt(alloc.rate) == 300.0, f"Rate should be forced to 300, got {alloc.rate}"
        print(f"  ✓ PO rate locked: tried 350, forced to 300")
        results.add("rate_locked", True)

        # Clean up
        frappe.delete_doc("SMT Purchase Order", pof.name, force=True, ignore_permissions=True)
    except Exception as e:
        results.add("rate_locked", False, e)

    frappe.db.rollback()


def test_320_partial_dropoff_settlement(results, ctx):
    """v2: one Dropoff Final may be settled across several PO Finals.

    Replaces the v1 test that asserted the opposite. Under the old equality rule
    ("every item in a Dropoff Final must be fully allocated") skipping an item
    threw; v2 relaxed coverage to an upper bound so a delivery can be paid for in
    instalments, which makes that assertion void rather than merely failing.

    What still has to hold is the ceiling, so this walks the whole cycle:
    partial draw accepted -> DFL Partially Settled with the right remainder ->
    over-draw on an exhausted item blocked -> second PO Final closes it out.

    See docs/PRICE_LOCK_SETTLEMENT_DESIGN.md §16.4.
    """
    print("\n--- 320. Partial Dropoff Final Settlement (v2) ---")

    try:
        po = frappe.get_doc({
            "doctype": "SMT Price Lock",
            "supplier": ctx["supplier"],
            "po_date": today(),
            "items": [
                {"item_code": ctx["copper"], "po_qty": 10, "po_rate": 300},
                {"item_code": ctx["aluminum"], "po_qty": 10, "po_rate": 75},
            ]
        })
        po.insert(ignore_permissions=True)
        po.submit()

        # Delivery holds two items
        dof = create_test_dropoff_final(
            ctx["supplier"],
            [(ctx["copper"], 5.0), (ctx["aluminum"], 3.0)]
        )

        # --- 1. Draw only the copper. Legal in v2, threw in v1. ---------------
        pof1 = frappe.get_doc({
            "doctype": "SMT Purchase Order",
            "supplier": ctx["supplier"],
            "final_date": today(),
            "drop_off_finals": [{"drop_off_final": dof}],
            "allocations": [
                {
                    "drop_off_final": dof,
                    "item_code": ctx["copper"],
                    "qty": 5.0,
                    "source_type": "PO",
                    "po": po.name,
                    "rate": 300,
                }
            ]
        })
        pof1.insert(ignore_permissions=True)
        pof1.submit()
        results.add("partial_draw_accepted", True)

        # --- 2. The delivery is now partly, not wholly, settled --------------
        dof_doc = frappe.get_doc("Dropoff Final", dof)
        results.add(
            "dof_partially_settled",
            dof_doc.status == "Partially Settled",
            f"expected Partially Settled, got {dof_doc.status}",
        )

        ledger = {r.item_code: r for r in dof_doc.good_items}
        results.add(
            "copper_fully_drawn",
            flt(ledger[ctx["copper"]].remaining_qty, 3) == 0,
            f"copper remaining {ledger[ctx['copper']].remaining_qty}, expected 0",
        )
        results.add(
            "aluminum_untouched",
            flt(ledger[ctx["aluminum"]].remaining_qty, 3) == 3.0,
            f"aluminum remaining {ledger[ctx['aluminum']].remaining_qty}, expected 3",
        )
        results.add(
            "settlement_documents_recorded",
            pof1.name in (dof_doc.settlement_documents or ""),
            f"settlement_documents = {dof_doc.settlement_documents!r}",
        )

        # --- 3. The ceiling still holds: copper is exhausted -----------------
        try:
            over = frappe.get_doc({
                "doctype": "SMT Purchase Order",
                "supplier": ctx["supplier"],
                "final_date": today(),
                "drop_off_finals": [{"drop_off_final": dof}],
                "allocations": [
                    {
                        "drop_off_final": dof,
                        "item_code": ctx["copper"],
                        "qty": 1.0,
                        "source_type": "PO",
                        "po": po.name,
                        "rate": 300,
                    }
                ]
            })
            over.insert(ignore_permissions=True)
            results.add(
                "over_draw_blocked", False,
                "Should have thrown — copper already fully drawn by another PO Final",
            )
        except frappe.exceptions.ValidationError as e:
            assert_blocked_by(
                results, "over_draw_blocked", e,
                ["already", "remains", "exceed"],
            )

        # --- 4. A second PO Final closes out the remainder --------------------
        pof2 = frappe.get_doc({
            "doctype": "SMT Purchase Order",
            "supplier": ctx["supplier"],
            "final_date": today(),
            "drop_off_finals": [{"drop_off_final": dof}],
            "allocations": [
                {
                    "drop_off_final": dof,
                    "item_code": ctx["aluminum"],
                    "qty": 3.0,
                    "source_type": "PO",
                    "po": po.name,
                    "rate": 75,
                }
            ]
        })
        pof2.insert(ignore_permissions=True)
        pof2.submit()

        dof_doc.reload()
        results.add(
            "dof_settled_after_second_pof",
            dof_doc.status == "Settled",
            f"expected Settled, got {dof_doc.status}",
        )

        # drawn_weight reflects THIS document, not the delivery total —
        # this is what ใบสั่งซื้อ prints.
        results.add(
            "drawn_weight_is_per_document",
            flt(pof2.drop_off_finals[0].drawn_weight, 3) == 3.0,
            f"drawn_weight {pof2.drop_off_finals[0].drawn_weight}, expected 3",
        )

    except Exception as e:
        results.add("partial_dropoff_settlement", False, e)


def test_321_empty_draw_blocked(results, ctx):
    """A Dropoff Final listed in the selector table must actually be drawn from.

    Under an upper bound, drawing zero is arithmetically valid — but the row
    would assert a relationship the document does not have, and would print on
    ใบสั่งซื้อ as though the delivery were part of this settlement.
    """
    print("\n--- 321. Empty Draw Blocked ---")

    try:
        dof = create_test_dropoff_final(ctx["supplier"], [(ctx["copper"], 4.0)])

        po = frappe.get_doc({
            "doctype": "SMT Price Lock",
            "supplier": ctx["supplier"],
            "po_date": today(),
            "items": [{"item_code": ctx["copper"], "po_qty": 10, "po_rate": 300}],
        })
        po.insert(ignore_permissions=True)
        po.submit()

        dof2 = create_test_dropoff_final(ctx["supplier"], [(ctx["copper"], 2.0)])

        # dof2 is listed but every allocation points at dof
        pof = frappe.get_doc({
            "doctype": "SMT Purchase Order",
            "supplier": ctx["supplier"],
            "final_date": today(),
            "drop_off_finals": [
                {"drop_off_final": dof},
                {"drop_off_final": dof2},
            ],
            "allocations": [
                {
                    "drop_off_final": dof,
                    "item_code": ctx["copper"],
                    "qty": 4.0,
                    "source_type": "PO",
                    "po": po.name,
                    "rate": 300,
                }
            ]
        })
        pof.insert(ignore_permissions=True)
        results.add(
            "empty_draw_blocked", False,
            "Should have thrown — dof2 listed but nothing allocated from it",
        )
    except frappe.exceptions.ValidationError as e:
        assert_blocked_by(
            results, "empty_draw_blocked", e,
            ["nothing is allocated", "remove the row"],
        )
    except Exception as e:
        results.add("empty_draw_blocked", False, e)

    frappe.db.rollback()


def test_330_spot_zero_rate_blocked(results, ctx):
    """Spot allocation must have rate > 0."""
    print("\n--- 330. Spot Zero Rate Blocked ---")

    try:
        dof = create_test_dropoff_final(ctx["supplier"], [(ctx["copper"], 5.0)])

        pof = frappe.get_doc({
            "doctype": "SMT Purchase Order",
            "supplier": ctx["supplier"],
            "final_date": today(),
            "drop_off_finals": [{"drop_off_final": dof}],
            "allocations": [
                {
                    "drop_off_final": dof,
                    "item_code": ctx["copper"],
                    "qty": 5.0,
                    "source_type": "Spot",
                    "rate": 0,
                }
            ]
        })
        pof.insert(ignore_permissions=True)
        results.add("spot_zero_rate_blocked", False, "Should have thrown")
    except frappe.exceptions.ValidationError as e:
        print(f"  ✓ Spot zero rate correctly blocked")
        results.add("spot_zero_rate_blocked", True)
    except Exception as e:
        results.add("spot_zero_rate_blocked", False, e)

    frappe.db.rollback()


def test_340_expired_po_blocked(results, ctx):
    """Cannot allocate against an Expired PO."""
    print("\n--- 340. Expired PO Blocked ---")

    if not ctx.get("po_expiry"):
        results.skip("expired_po_blocked", "No expired PO")
        return

    try:
        dof = create_test_dropoff_final(ctx["supplier"], [(ctx["copper"], 3.0)])

        pof = frappe.get_doc({
            "doctype": "SMT Purchase Order",
            "supplier": ctx["supplier"],
            "final_date": today(),
            "drop_off_finals": [{"drop_off_final": dof}],
            "allocations": [
                {
                    "drop_off_final": dof,
                    "item_code": ctx["copper"],
                    "qty": 3.0,
                    "source_type": "PO",
                    "po": ctx["po_expiry"],
                    "rate": 100,
                }
            ]
        })
        pof.insert(ignore_permissions=True)
        results.add("expired_po_blocked", False, "Should have thrown")
    except frappe.exceptions.ValidationError as e:
        assert_blocked_by(results, "expired_po_blocked", e, "Expired")
    except Exception as e:
        results.add("expired_po_blocked", False, e)

    frappe.db.rollback()


# ============================================================
# Runner
# ============================================================

def run(cleanup_first=True):
    """Run the settlement integration test suite."""
    print("\n" + "=" * 70)
    print("SCRAP METAL SUITE — SETTLEMENT INTEGRATION TESTS")
    print(f"Site: {frappe.local.site}  |  Time: {now_datetime()}")
    print("=" * 70)

    results = TestResult()
    ctx = {}

    original_user = frappe.session.user
    frappe.set_user("Administrator")

    try:
        if cleanup_first:
            print("\nCleaning up previous test data...")
            cleanup_test_data()

        test_200_setup(results, ctx)
        test_201_po_create_and_submit(results, ctx)
        test_202_po_validation(results, ctx)
        test_203_po_expiry(results, ctx)
        test_210_create_dropoff_final(results, ctx)
        test_220_po_final_simple(results, ctx)
        test_230_po_final_cancel(results, ctx)
        test_240_partial_settlement(results, ctx)
        test_241_complete_settlement(results, ctx)
        test_250_multi_po(results, ctx)
        test_260_over_delivery(results, ctx)
        test_270_over_allocation_blocked(results, ctx)
        test_280_cross_supplier_blocked(results, ctx)
        test_290_po_cancel_with_settlement(results, ctx)
        test_300_accountant_read_access(results, ctx)
        test_310_rate_locked(results, ctx)
        test_320_partial_dropoff_settlement(results, ctx)
        test_321_empty_draw_blocked(results, ctx)
        test_330_spot_zero_rate_blocked(results, ctx)
        test_340_expired_po_blocked(results, ctx)

    except Exception as e:
        print(f"\n!!! FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        frappe.set_user(original_user or "Administrator")

    return results.summary()
