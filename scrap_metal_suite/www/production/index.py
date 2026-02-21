"""Production Sorting - Landing Page"""

import frappe
from frappe import _

no_cache = 1


def get_context(context):
    context.title = "Production Sorting"

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/production"
        raise frappe.Redirect

    if not has_production_access():
        context.error = "You don't have permission to access Production Sorting."
        return context

    context.active_session = get_active_session()
    context.operator_name = (
        frappe.db.get_value("User", frappe.session.user, "full_name")
        or frappe.session.user
    )

    return context


def has_production_access():
    roles = frappe.get_roles()
    return (
        "Production Worker" in roles
        or "Production Manager" in roles
        or "System Manager" in roles
    )


def get_active_session():
    return frappe.db.get_value(
        "Production Session",
        {"operator": frappe.session.user, "status": "Open"},
        ["name", "opening_time", "scale"],
        as_dict=True
    )
