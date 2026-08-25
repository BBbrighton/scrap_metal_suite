"""Camera Test Page - standalone verification for the CCTV integration.

Mirrors /scale-test: lets an operator or installer confirm the cameras are
reachable and capturing, without touching POS operations.
"""

import frappe

from scrap_metal_suite.utils.assets import asset_version

no_cache = 1

# Assets this page hand-links via plain <link>/<script> tags, relative to
# the app's public/ dir. Kept in sync with the tags in the template.
_LINKED_ASSETS = (
    "js/pos-translations.js",
    "js/pos-core.js",
    "js/camera_client.js",
)


def get_context(context):
    context.no_cache = 1
    context.show_sidebar = False
    context.asset_v = asset_version(_LINKED_ASSETS)

    context.title = "Camera Configuration"

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/camera-test"
        raise frappe.Redirect

    # Same transport switch as the truck terminal: set on the cloud site, unset
    # in dev where the backend can reach the camera LAN itself.
    context.camera_agent_url = frappe.conf.get("camera_agent_url") or ""

    return context
