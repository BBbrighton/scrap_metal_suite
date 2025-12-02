# Copyright (c) 2025, Scrap Metal Suite and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class POSProfileScrap(Document):
    def validate(self):
        self.validate_items()
        self.set_display_order()

    def validate_items(self):
        """Ensure no duplicate items"""
        items = [d.item_code for d in self.items]
        if len(items) != len(set(items)):
            frappe.throw("Duplicate items are not allowed in POS Profile")

    def set_display_order(self):
        """Auto-set display order if not set"""
        for idx, item in enumerate(self.items):
            if not item.display_order:
                item.display_order = idx + 1
