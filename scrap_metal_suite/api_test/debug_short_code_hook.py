"""One-shot debug: see if populate_short_code fires on a fresh Supplier insert."""

import frappe


def run():
    test_name = "_TEST_DEBUG_Supplier"
    if frappe.db.exists("Supplier", test_name):
        frappe.delete_doc("Supplier", test_name, force=True, ignore_permissions=True)
        frappe.db.commit()

    print("Hook config in app:")
    hook_cfg = frappe.get_hooks("doc_events", app_name="scrap_metal_suite")
    print(f"  doc_events from scrap_metal_suite: {hook_cfg}")

    print("\n1. Direct hook invocation:")
    from scrap_metal_suite.overrides.supplier import populate_short_code
    test_doc = frappe.get_doc({
        "doctype": "Supplier",
        "supplier_name": test_name,
        "supplier_group": frappe.db.get_value("Supplier Group", {}, "name") or "All Supplier Groups",
    })
    print(f"  short_code BEFORE hook: {test_doc.short_code!r}")
    populate_short_code(test_doc)
    print(f"  short_code AFTER hook:  {test_doc.short_code!r}")

    print("\n2. Attempting Supplier insert (uses hooks via doc_events):")
    try:
        doc = frappe.get_doc({
            "doctype": "Supplier",
            "supplier_name": test_name,
            "supplier_group": frappe.db.get_value("Supplier Group", {}, "name") or "All Supplier Groups",
        })
        print(f"  short_code in get_doc: {doc.short_code!r}")
        doc.insert(ignore_permissions=True)
        print(f"  inserted: {doc.name}")
        print(f"  short_code: {doc.short_code!r}")
    except Exception as e:
        print(f"  failed: {type(e).__name__}: {e}")
    finally:
        if frappe.db.exists("Supplier", test_name):
            frappe.delete_doc("Supplier", test_name, force=True, ignore_permissions=True)
            frappe.db.commit()
