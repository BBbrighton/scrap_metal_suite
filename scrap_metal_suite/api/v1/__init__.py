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
