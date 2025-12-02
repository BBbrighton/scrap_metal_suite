"""POS Terminal - Main weight recording interface"""

import frappe
from frappe import _

no_cache = 1


def get_context(context):
    context.title = "POS Terminal"

    # Check if user is logged in
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/pos"
        raise frappe.Redirect

    # Get session from URL
    session_name = frappe.form_dict.get("session")

    if not session_name:
        frappe.local.flags.redirect_location = "/pos"
        raise frappe.Redirect

    # Validate session
    session = frappe.db.get_value(
        "POS Session",
        session_name,
        ["name", "pos_profile", "operator", "status", "opening_time"],
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

    # Get POS profile with items
    profile = frappe.get_doc("POS Profile Scrap", session.pos_profile)
    context.profile = profile

    # Get items for display (weight only, no rate)
    context.pos_items = []
    for item in sorted(profile.items, key=lambda x: x.display_order or 0):
        item_doc = frappe.db.get_value(
            "Item",
            item.item_code,
            ["item_code", "item_name", "stock_uom"],
            as_dict=True
        )
        if item_doc:
            context.pos_items.append({
                "item_code": item.item_code,
                "item_name": item_doc.item_name,
                "uom": item_doc.stock_uom or "Kg",
                "display_order": item.display_order
            })

    return context
