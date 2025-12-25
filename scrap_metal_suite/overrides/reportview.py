# Copyright (c) 2025, Scrap Metal Suite and contributors
# For license information, please see license.txt

"""
Override for frappe.desk.reportview.get_count

The Dropoff doctype name contains "drop" which triggers Frappe's SQL injection
protection in sanitize_fields() because "drop" is a blacklisted keyword.

This override handles the Dropoff case specially while falling back to the
standard behavior for all other doctypes.
"""

import frappe
from frappe.desk import reportview as rv


@frappe.whitelist()
@frappe.read_only()
def get_count():
    """
    Custom get_count that handles Dropoff doctype specially.

    For Dropoff workspace badge (fields is empty), we use count(name)
    to avoid the sanitizer issue with "tabDropoff" containing "drop".
    """
    # reportview.get_count() reads request params from form_dict
    args = frappe._dict(frappe.local.form_dict or {})
    doctype = args.get("doctype")

    # normalize json strings (API sends strings)
    if isinstance(args.get("filters"), str):
        args.filters = frappe.parse_json(args.filters) or []
    if isinstance(args.get("fields"), str):
        args.fields = frappe.parse_json(args.fields) or []

    # Workspace badge scenario: fields is empty
    if doctype == "Dropoff" and not args.get("fields"):
        # Use frappe.db.count which doesn't go through sanitize_fields
        filters = args.get("filters") or {}
        return frappe.db.count("Dropoff", filters=filters)

    # Fallback to standard behavior for all other doctypes/cases
    return rv.get_count()
