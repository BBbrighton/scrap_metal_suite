"""Production Terminal - Production Sorting QA/QC Interface"""

import frappe
from frappe import _

from scrap_metal_suite.utils.assets import asset_version

no_cache = 1

# Assets this page hand-links via plain <link>/<script> tags, relative to
# the app's public/ dir. Kept in sync with the tags in the template.
_LINKED_ASSETS = (
    "css/pos.css",
    "css/production-theme.css",
    "js/pos-translations.js",
    "js/scale_reader.js",
    "js/production-terminal.js",
)


def get_context(context):
    context.asset_v = asset_version(_LINKED_ASSETS)
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

    # Get settings
    settings = get_production_settings()
    context.settings = settings

    # Get items with categories from POS Profile
    context.production_items, context.categories = get_production_items()

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


def get_production_items():
    """Get items with categories from the first available POS Profile Scrap.
    Uses the same item list and categories as the scrap weighing terminal."""
    items = []
    categories = []

    profiles = frappe.get_all("POS Profile Scrap", limit=1)
    if not profiles:
        return items, categories

    profile = frappe.get_doc("POS Profile Scrap", profiles[0].name)
    cat_set = set()

    for profile_item in profile.items:
        item_doc = frappe.db.get_value(
            "Item", profile_item.item_code,
            ["item_code", "item_name", "stock_uom"], as_dict=True
        )
        if not item_doc:
            continue

        category = getattr(profile_item, "category", "") or ""
        if category:
            cat_set.add(category)

        items.append({
            "item_code": item_doc.item_code,
            "item_name": item_doc.item_name,
            "uom": item_doc.stock_uom or "Kg",
            "category": category,
            "display_order": getattr(profile_item, "display_order", 9999) or 9999
        })

    items.sort(key=lambda x: (x["category"] or "zzz", x["display_order"]))
    categories = sorted(list(cat_set))

    return items, categories


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
