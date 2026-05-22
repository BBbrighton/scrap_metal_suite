"""Confirm the Wave 9 no-walk-in validation actually blocks orderless Dropoffs."""

import frappe


def run():
    test_supplier = "_TEST_NOWALKIN_Supplier"

    # Ensure clean state.
    if frappe.db.exists("Supplier", test_supplier):
        frappe.delete_doc("Supplier", test_supplier, force=True, ignore_permissions=True)
        frappe.db.commit()

    s = frappe.get_doc({
        "doctype": "Supplier",
        "supplier_name": test_supplier,
        "supplier_group": frappe.db.get_value("Supplier Group", {}, "name") or "All Supplier Groups",
    })
    s.insert(ignore_permissions=True)
    print(f"Created supplier {s.name} (short_code={s.short_code})")

    # Try to insert a Dropoff with NO orders — should throw.
    try:
        d = frappe.get_doc({
            "doctype": "Dropoff",
            "supplier": s.name,
            "license_plate": "_TEST_NOWALKIN_PLATE",
            "dropoff_scheduled_start": frappe.utils.now_datetime(),
            "status": "Scheduled",
            # No orders → should be blocked.
        })
        d.insert(ignore_permissions=True)
        print(f"FAIL: Dropoff {d.name} was inserted without orders — validation didn't fire")
    except frappe.ValidationError as e:
        msg = str(e)
        if "POS Order" in msg or "Linked Orders" in msg:
            print(f"PASS: Dropoff insert blocked as expected — {msg.splitlines()[0][:120]}")
        else:
            print(f"PARTIAL: Got ValidationError but message doesn't reference POS Order: {msg[:200]}")
    except Exception as e:
        print(f"FAIL: Unexpected exception {type(e).__name__}: {e}")
    finally:
        # Cleanup
        for d in frappe.get_all("Dropoff", filters={"supplier": test_supplier}, pluck="name"):
            frappe.delete_doc("Dropoff", d, force=True, ignore_permissions=True)
        if frappe.db.exists("Supplier", test_supplier):
            frappe.delete_doc("Supplier", test_supplier, force=True, ignore_permissions=True)
        frappe.db.commit()
