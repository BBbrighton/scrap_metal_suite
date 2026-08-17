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

    # CCTV transport. Set on the cloud site, where the server cannot reach the
    # camera LAN, so the terminal talks to the on-site capture agent instead:
    #   bench --site <site> set-config camera_agent_url "http://127.0.0.1:8787"
    # Left unset in dev / on-prem, where the backend fetches the camera itself.
    context.camera_agent_url = frappe.conf.get("camera_agent_url") or ""

    return context


def has_pos_access():
    """Check if current user has POS access."""
    roles = frappe.get_roles()
    return "POS Operator" in roles or "POS Manager" in roles or "System Manager" in roles
