"""Production Terminal - Production Sorting QA/QC Interface"""

import frappe
from frappe import _

no_cache = 1


def get_context(context):
    context.title = "Production Sorting"

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/pos/production"
        raise frappe.Redirect

    if not has_production_access():
        context.error = "You don't have permission to access the Production Sorting system."
        return context

    context.active_session = get_active_production_session()

    operator_name = frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user
    context.operator_name = operator_name

    # Get settings first (needed for item filtering)
    settings = get_production_settings()
    context.settings = settings

    # Get items filtered by allowed item groups
    context.production_items = get_production_items(settings.get("allowed_item_groups", []))

    # Get unique categories for filter tabs
    context.categories = sorted(set(
        item.get("category") for item in context.production_items if item.get("category")
    ))

    context.scales = get_production_scales()

    return context


def has_production_access():
    roles = frappe.get_roles()
    return "Production Worker" in roles or "Production Manager" in roles or "System Manager" in roles


def get_active_production_session():
    session = frappe.db.get_value(
        "Production Session",
        {"operator": frappe.session.user, "status": "Open"},
        ["name", "opening_time", "scale"],
        as_dict=True
    )
    return session


def get_production_items(allowed_item_groups=None):
    """Get items filtered by allowed item groups from Production Sorting Settings."""
    filters = {"disabled": 0}

    if allowed_item_groups:
        filters["item_group"] = ["in", allowed_item_groups]

    items = frappe.get_all(
        "Item",
        filters=filters,
        fields=["item_code", "item_name", "stock_uom", "item_group"],
        order_by="item_group, item_name"
    )

    for item in items:
        item["uom"] = item.get("stock_uom") or "Kg"
        item["category"] = item.get("item_group") or "Other"

    return items


def get_production_scales():
    """Get all active scales available for production."""
    scales = frappe.get_all(
        "Scale",
        filters={"usage_type": "Production", "is_active": 1},
        fields=["name", "scale_name", "location"],
        order_by="scale_name"
    )
    return scales


def get_production_settings():
    """Get Production Sorting Settings."""
    try:
        settings = frappe.get_single("Production Sorting Settings")
        return {
            "variance_threshold_percent": settings.variance_threshold_percent or 0.5,
            "allowed_item_groups": [d.item_group for d in settings.allowed_item_groups] if hasattr(settings, 'allowed_item_groups') and settings.allowed_item_groups else [],
            "session_timeout_minutes": getattr(settings, 'session_timeout_minutes', 10)
        }
    except Exception:
        return {
            "variance_threshold_percent": 0.5,
            "allowed_item_groups": [],
            "session_timeout_minutes": 10
        }
