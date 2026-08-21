"""Manager Portal - Dashboard"""

import frappe
from frappe.utils import nowdate, getdate, get_first_day, flt

no_cache = 1


from scrap_metal_suite.www.manager.utils import require_login


def get_context(context):
    require_login(context, "/manager")
    context.active_page = "dashboard"

    # Get supplier statistics
    context.total_suppliers = frappe.db.count("Supplier", {"disabled": 0})

    # New suppliers this month
    first_day = get_first_day(nowdate())
    context.new_suppliers_month = frappe.db.count(
        "Supplier",
        {"creation": [">=", first_day]}
    )

    # Pending registrations
    if frappe.db.exists("DocType", "Supplier Registration"):
        context.pending_registrations = frappe.db.count(
            "Supplier Registration",
            {"status": "Pending"}
        )

        # Recent registrations
        context.recent_registrations = frappe.get_all(
            "Supplier Registration",
            fields=["name", "company_name", "registration_date", "status"],
            order_by="creation desc",
            limit=5
        )
    else:
        context.pending_registrations = 0
        context.recent_registrations = []

    # Purchase statistics (placeholder - will need actual purchase data)
    context.total_purchases_formatted = "฿0"
    context.total_weight_formatted = "0 T"

    return context
