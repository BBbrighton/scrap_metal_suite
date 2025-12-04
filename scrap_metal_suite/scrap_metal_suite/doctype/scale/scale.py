# Copyright (c) 2025, Scrap Metal Suite and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Scale(Document):
    def validate(self):
        # Ensure scale_name is uppercase for consistency
        if self.scale_name:
            self.scale_name = self.scale_name.upper().strip()

    def before_save(self):
        # If being deactivated, check if any open sessions use this scale
        if not self.is_active and self.has_value_changed('is_active'):
            open_sessions = frappe.get_all(
                "POS Session",
                filters={
                    "scale": self.name,
                    "status": "Open"
                },
                limit=1
            )
            if open_sessions:
                frappe.throw(
                    f"Cannot deactivate scale '{self.scale_name}' while it has open POS sessions. "
                    "Please close all sessions using this scale first."
                )
