"""Shared utilities for Manager Portal pages."""

import frappe


def require_login(context, redirect_to="/manager"):
    """Block unauthenticated access to a manager portal page.

    These three pages (`/manager`, `/manager/price`, `/manager/world-price`)
    shipped with no auth check at all, so they returned HTTP 200 to Guest and
    rendered live business data — supplier counts and the item catalogue —
    to anyone who knew the URL. Verified against production 2026-08-21.

    Deliberately only blocks Guest, and does not gate on a role. The exposure
    was unauthenticated access; adding a role requirement here without knowing
    which roles the office actually holds risks locking out legitimate users.
    Role gating is a separate decision — see
    docs/guide/admin/80-portals-internals.md.

    Mirrors the pattern in `www/supplier/utils.py`.
    """
    context.no_cache = 1

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = f"/login?redirect-to={redirect_to}"
        raise frappe.Redirect
