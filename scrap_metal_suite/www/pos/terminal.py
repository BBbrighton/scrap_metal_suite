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
        ["name", "pos_profile", "operator", "status", "opening_time", "scale"],
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

    # Check if session has a scale set and validate its type
    if session.scale:
        scale_usage_type = frappe.db.get_value("Scale", session.scale, "usage_type")
        if scale_usage_type and scale_usage_type != "Scrap":
            # Session has a Truck scale - redirect to truck terminal
            frappe.local.flags.redirect_location = f"/pos/truck?session={session_name}"
            raise frappe.Redirect

    context.session = session

    # Get operator full name
    operator_name = frappe.db.get_value("User", session.operator, "full_name") or session.operator
    context.operator_name = operator_name

    # Get POS profile with items
    profile = frappe.get_doc("POS Profile Scrap", session.pos_profile)
    context.profile = profile

    # Container model feature flag (mirrors truck.py)
    context.use_container_model = bool(getattr(profile, "use_container_model", True))
    context.enable_sticker_print = bool(getattr(profile, "enable_sticker_print", 0))

    # Get items for display (weight only, no rate) with categories
    context.pos_items = []
    categories = set()

    for item in profile.items:
        item_doc = frappe.db.get_value(
            "Item",
            item.item_code,
            ["item_code", "item_name", "stock_uom"],
            as_dict=True
        )
        if item_doc:
            category = getattr(item, "category", None) or ""
            if category:
                categories.add(category)
            context.pos_items.append({
                "item_code": item.item_code,
                "item_name": item_doc.item_name,
                "uom": item_doc.stock_uom or "Kg",
                "display_order": item.display_order or 9999,
                "category": category
            })

    # Sort: by category (alphabetically), then by display_order within category
    # Items without display_order (9999) go to end of their category
    context.pos_items.sort(key=lambda x: (x["category"] or "zzz", x["display_order"]))

    # Sort categories alphabetically
    context.categories = sorted(list(categories))

    return context
