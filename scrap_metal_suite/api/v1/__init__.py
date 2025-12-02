# API v1 Endpoints
# All whitelisted methods should be organized by domain:
# - inventory.py: Inventory management endpoints
# - pricing.py: Pricing and quotation endpoints
# - transactions.py: Purchase/sale transaction endpoints
# - reports.py: Reporting endpoints

import frappe


@frappe.whitelist(allow_guest=True)
def get_countries():
    """Get list of all countries for dropdowns"""
    return frappe.get_all(
        "Country",
        fields=["name"],
        order_by="name",
        ignore_permissions=True
    )


@frappe.whitelist()
def debug_supplier_link():
    """Debug endpoint to check User → Contact → Supplier linking"""
    user = frappe.session.user
    result = {
        "user": user,
        "user_roles": frappe.get_roles(user),
        "has_supplier_role": "Supplier" in frappe.get_roles(user),
        "contact": None,
        "dynamic_links": [],
        "supplier": None
    }

    # Find Contact linked to this user
    contact = frappe.db.get_value("Contact", {"user": user}, ["name", "email_id"], as_dict=True)
    result["contact"] = contact

    if contact:
        # Find all Dynamic Links for this Contact
        dynamic_links = frappe.get_all(
            "Dynamic Link",
            filters={"parent": contact.name, "parenttype": "Contact"},
            fields=["link_doctype", "link_name"]
        )
        result["dynamic_links"] = dynamic_links

        # Find Supplier link specifically
        supplier_link = frappe.db.get_value(
            "Dynamic Link",
            {
                "parent": contact.name,
                "parenttype": "Contact",
                "link_doctype": "Supplier"
            },
            "link_name"
        )

        if supplier_link:
            supplier = frappe.get_doc("Supplier", supplier_link)
            result["supplier"] = {
                "name": supplier.name,
                "supplier_name": supplier.supplier_name
            }

    return result
