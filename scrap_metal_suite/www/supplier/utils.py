"""Shared utilities for Supplier Portal pages"""

import frappe
from frappe import _


def get_supplier_context(context):
    """
    Common context setup for all supplier portal pages.
    Returns True if successful, False if error (error set in context).

    Role Priority (highest to lowest):
    1. System Manager / Administrator → /app (Desk)
    2. Manager → /manager
    3. POS Operator → /pos
    4. Supplier (with linked account) → Show portal
    5. Supplier (no linked account) → Friendly error
    6. Guest → /login
    """
    context.no_cache = 1
    context.show_sidebar = False
    context.error = None
    context.supplier = None
    context.registration = None

    # Check if user is logged in
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/supplier"
        raise frappe.Redirect

    # Get user roles
    user_roles = frappe.get_roles(frappe.session.user)

    # Priority 1: Admin/System Manager should go to Desk
    if "System Manager" in user_roles or "Administrator" in user_roles:
        frappe.local.flags.redirect_location = "/app"
        raise frappe.Redirect

    # Priority 2: Manager role (without Supplier role) goes to manager portal
    if "Manager" in user_roles and "Supplier" not in user_roles:
        frappe.local.flags.redirect_location = "/manager"
        raise frappe.Redirect

    # Priority 3: POS Operator (without Supplier role) goes to POS
    if "POS Operator" in user_roles and "Supplier" not in user_roles:
        frappe.local.flags.redirect_location = "/pos"
        raise frappe.Redirect

    # Check if user has Supplier role
    if "Supplier" not in user_roles:
        context.error = _("You do not have access to the Supplier Portal. Please contact support.")
        return False

    # Get supplier info linked to this user
    supplier_info = get_supplier_for_user(frappe.session.user)

    if not supplier_info:
        context.error = _("No supplier account linked to your user. Please contact support.")
        return False

    context.supplier = supplier_info
    context.registration = get_registration_info(supplier_info.get("name"))

    return True


def get_supplier_for_user(user):
    """
    Get the Supplier linked to a User via Contact.
    User → Contact → Supplier (via Dynamic Link)
    """
    contact = frappe.db.get_value("Contact", {"user": user}, "name")

    if not contact:
        return None

    supplier_link = frappe.db.get_value(
        "Dynamic Link",
        {
            "parent": contact,
            "parenttype": "Contact",
            "link_doctype": "Supplier"
        },
        "link_name"
    )

    if not supplier_link:
        return None

    supplier = frappe.get_doc("Supplier", supplier_link)

    return {
        "name": supplier.name,
        "supplier_name": supplier.supplier_name,
        "supplier_type": supplier.supplier_type,
        "tax_id": supplier.tax_id,
        "custom_source": supplier.get("custom_source"),
        "custom_registration_request": supplier.get("custom_registration_request")
    }


def get_registration_info(supplier_name):
    """Get the registration request info if supplier was created via webform"""
    supplier = frappe.get_doc("Supplier", supplier_name)
    registration_request = supplier.get("custom_registration_request")

    if not registration_request:
        return None

    reg = frappe.get_doc("Supplier Registration Request", registration_request)

    return {
        "name": reg.name,
        "registration_date": reg.registration_date,
        "status": reg.status,
        "approval_date": reg.approval_date
    }
