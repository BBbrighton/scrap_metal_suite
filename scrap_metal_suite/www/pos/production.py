"""Production Terminal - Production Sorting QA/QC Interface"""

import frappe
from frappe import _

no_cache = 1


def get_context(context):
    context.title = "Production Sorting"

    # Check if user is logged in
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/pos/production"
        raise frappe.Redirect

    # Check if user has Production access
    if not has_production_access():
        context.error = "You don't have permission to access the Production Sorting system."
        return context

    # Get active session if any
    context.active_session = get_active_production_session()

    # Get operator full name
    operator_name = frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user
    context.operator_name = operator_name

    # Get available items from Item master
    context.production_items = get_production_items()

    # Get available scales for production
    context.scales = get_production_scales()

    # Get settings
    context.settings = get_production_settings()

    return context


def has_production_access():
    """Check if current user has Production access."""
    roles = frappe.get_roles()
    return "Production Worker" in roles or "Production Manager" in roles or "System Manager" in roles


def get_active_production_session():
    """Get user's active open production session."""
    session = frappe.db.get_value(
        "Production Session",
        {"operator": frappe.session.user, "status": "Open"},
        ["name", "opening_time", "scale"],
        as_dict=True
    )
    return session


def get_production_items():
    """Get all items available for production sorting."""
    items = frappe.get_all(
        "Item",
        filters={"disabled": 0},
        fields=["item_code", "item_name", "stock_uom", "item_group"],
        order_by="item_name"
    )

    for item in items:
        item["uom"] = item.get("stock_uom") or "Kg"
        item["category"] = item.get("item_group") or "Other"

    return items


def get_production_scales():
    """Get all scales available for production (Scrap usage type)."""
    scales = frappe.get_all(
        "Scale",
        filters={"usage_type": "Scrap"},
        fields=["name", "scale_name", "location"],
        order_by="scale_name"
    )
    return scales


def get_production_settings():
    """Get Production Sorting Settings."""
    settings = frappe.get_single("Production Sorting Settings")
    return {
        "variance_threshold_percent": settings.variance_threshold_percent or 0.5,
        "allowed_item_groups": [d.item_group for d in settings.allowed_item_groups] if hasattr(settings, 'allowed_item_groups') else []
    }
