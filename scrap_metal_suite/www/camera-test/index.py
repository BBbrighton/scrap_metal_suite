import frappe


def get_context(context):
    """Camera Test Page - standalone verification for the CCTV integration.

    Mirrors /scale-test: lets an operator or installer confirm the cameras are
    reachable and capturing, without touching POS operations.
    """
    context.no_cache = 1
    context.show_sidebar = False

    context.title = "Camera Configuration"

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/camera-test"
        raise frappe.Redirect

    # Same transport switch as the truck terminal: set on the cloud site, unset
    # in dev where the backend can reach the camera LAN itself.
    context.camera_agent_url = frappe.conf.get("camera_agent_url") or ""

    return context
