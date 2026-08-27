"""POS Interface - Profile Selection / Session Start"""

import frappe
from frappe import _

no_cache = 1


def get_context(context):
    context.title = "POS - Scrap Metal"

    # Check if user is logged in
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/pos"
        raise frappe.Redirect

    # Check if user has POS Operator role
    if not has_pos_access():
        context.error = "You don't have permission to access the POS system."
        return context

    # Get active session if any
    context.active_session = get_active_session()

    # Get available POS profiles
    context.pos_profiles = get_pos_profiles()

    return context


def has_pos_access():
    """Who may see the terminal chooser at /pos.

    This is the hub page, not a terminal — it shows three cards and each
    destination enforces its own access. Sorting staff were excluded here, so
    the route every guide documents ("open /pos, click Production Sorting")
    ended in Access Denied for exactly the people it was written for; the
    sorting terminal itself has always admitted them. Letting them see the hub
    grants nothing: /pos/terminal and /pos/truck still turn them away.
    """
    roles = frappe.get_roles()
    return any(r in roles for r in (
        "POS Operator", "POS Manager",
        "Production Worker", "Production Manager",
        "System Manager",
    ))


def get_active_session():
    """Get user's active open session."""
    session = frappe.db.get_value(
        "POS Session",
        {"operator": frappe.session.user, "status": "Open"},
        ["name", "pos_profile", "opening_time"],
        as_dict=True
    )
    return session


def get_pos_profiles():
    """Get all available POS profiles."""
    return frappe.get_all(
        "POS Profile Scrap",
        fields=["name", "profile_name", "price_list"],
        order_by="profile_name"
    )
