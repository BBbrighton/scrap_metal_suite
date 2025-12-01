"""Context for Supplier Registration Form page"""

import frappe

no_cache = 1


def get_context(context):
    context.no_cache = 1
    context.show_sidebar = False
    context.title = "Supplier Registration"

    # Get list of countries for dropdown (ignore permissions for guest access)
    context.countries = frappe.get_all(
        "Country",
        fields=["name"],
        order_by="name",
        ignore_permissions=True
    )

    return context
