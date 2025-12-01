"""Supplier DocType overrides and hooks"""

import frappe


def set_source_on_manual_create(doc, method=None):
    """
    Set source field when supplier is created manually.
    If source is not already set (e.g., by webform approval), set it to 'Manual'.
    """
    if not doc.get("custom_source"):
        doc.custom_source = "Manual"
