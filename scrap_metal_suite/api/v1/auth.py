# Shared authentication/authorization utilities for POS APIs

import frappe
from frappe import _


def check_pos_operator():
    """
    Check if current user has POS Operator role.
    Raises PermissionError if not authorized.
    System Manager is also allowed for admin access.
    """
    if frappe.session.user == "Guest":
        frappe.throw(_("Please login to access POS"), frappe.AuthenticationError)

    user_roles = frappe.get_roles(frappe.session.user)
    if "POS Operator" not in user_roles and "System Manager" not in user_roles:
        frappe.throw(_("Access denied. POS Operator role required."), frappe.PermissionError)
