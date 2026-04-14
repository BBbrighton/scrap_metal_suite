"""Production Sorting Terminal - Main sorting interface"""

import frappe
from frappe import _
from frappe.utils import flt

no_cache = 1


def get_context(context):
    context.title = "Sorting Terminal"

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/production"
        raise frappe.Redirect

    session_name = frappe.form_dict.get("session")
    if not session_name:
        frappe.local.flags.redirect_location = "/production"
        raise frappe.Redirect

    session = frappe.db.get_value(
        "Production Session", session_name,
        ["name", "operator", "status", "opening_time", "scale"],
        as_dict=True
    )

    if not session:
        context.error = "Session not found"
        return context

    if session.status != "Open":
        context.error = "This session has been closed"
        return context

    if session.operator != frappe.session.user:
        context.error = "This session belongs to another operator"
        return context

    context.session = session
    context.operator_name = (
        frappe.db.get_value("User", session.operator, "full_name")
        or session.operator
    )

    # Get allowed items from Production Sorting Settings
    settings = frappe.get_single("Production Sorting Settings")
    context.variance_threshold = flt(settings.variance_threshold_percent) or 0.1

    allowed_groups = []
    if settings.allowed_item_groups:
        allowed_groups = [row.item_group for row in settings.allowed_item_groups]

    context.item_groups = sorted(allowed_groups)

    # Get items from allowed groups
    context.allowed_items = []
    if allowed_groups:
        items = frappe.get_all(
            "Item",
            filters={"item_group": ["in", allowed_groups], "disabled": 0},
            fields=["item_code", "item_name", "item_group", "stock_uom"],
            order_by="item_group, item_name"
        )
        context.allowed_items = items

    return context
