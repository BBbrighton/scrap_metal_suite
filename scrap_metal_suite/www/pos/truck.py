"""POS Truck Scale Terminal - Dedicated page for truck weighing"""

import frappe
from frappe import _

no_cache = 1


def get_context(context):
    context.title = "Truck Scale Terminal"

    # Check if user is logged in
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/pos"
        raise frappe.Redirect

    # Check if user has POS access
    if not has_pos_access():
        context.error = "You don't have permission to access the POS system."
        return context

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
        if scale_usage_type and scale_usage_type != "Truck":
            # Session has a Scrap scale - redirect to scrap terminal
            frappe.local.flags.redirect_location = f"/pos/terminal?session={session_name}"
            raise frappe.Redirect

    context.session = session

    # Get operator full name
    operator_name = frappe.db.get_value("User", session.operator, "full_name") or session.operator
    context.operator_name = operator_name

    # Get POS profile
    profile = frappe.get_doc("POS Profile Scrap", session.pos_profile)
    context.profile = profile

    # Container model feature flag.
    # Until the POS Profile Scrap DocType has a real `use_container_model`
    # field, we default to True. Set the attribute on the profile (or wire
    # a real field) to flip back to the legacy scrap weight UI.
    context.use_container_model = bool(getattr(profile, "use_container_model", True))

    # Print toggles forwarded so the JS can decide whether to skip auto-print.
    context.enable_thermal_print = bool(getattr(profile, "enable_thermal_print", 0))
    context.enable_sticker_print = bool(getattr(profile, "enable_sticker_print", 0))

    # Items available for the container "Grade" dropdown — modelled after
    # terminal.py. We expose item_code / item_name / uom (canonical names;
    # never translated) plus the item_group so the modal can group by
    # category if needed.
    context.pos_items = []
    categories = set()
    for item in profile.items:
        item_doc = frappe.db.get_value(
            "Item",
            item.item_code,
            ["item_code", "item_name", "stock_uom", "item_group"],
            as_dict=True,
        )
        if item_doc:
            category = getattr(item, "category", None) or (item_doc.item_group or "")
            if category:
                categories.add(category)
            context.pos_items.append({
                "item_code": item.item_code,
                "item_name": item_doc.item_name,
                "uom": item_doc.stock_uom or "Kg",
                "item_group": item_doc.item_group or "",
                "display_order": item.display_order or 9999,
                "category": category,
            })
    context.pos_items.sort(key=lambda x: (x["category"] or "zzz", x["display_order"]))
    context.categories = sorted(list(categories))

    return context


def has_pos_access():
    """Check if current user has POS access."""
    roles = frappe.get_roles()
    return "POS Operator" in roles or "POS Manager" in roles or "System Manager" in roles
