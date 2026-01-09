# Copyright (c) 2025, Scrap Metal Suite and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowtime


class ScrapWeight(Document):
    """
    Scrap Weight DocType Controller

    Implements validations from DROPOFF_ARCHITECTURE.md Part 13 (Edge Cases)
    """

    def before_insert(self):
        """Set defaults before inserting."""
        if not self.posting_time:
            self.posting_time = nowtime()

        # Auto-fill from session
        if self.session:
            session = frappe.get_doc("POS Session", self.session)
            self.operator = session.operator
            self.pos_profile = session.pos_profile


    def validate(self):
        """Validate and calculate totals."""
        self.calculate_totals()

    def calculate_totals(self):
        """Calculate total weight from items."""
        self.total_weight = 0

        for item in self.items:
            self.total_weight += flt(item.weight)

    def on_update(self):
        """Update linked Drop-off totals."""
        if self.dropoff:
            self.update_dropoff_totals()

    def on_trash(self):
        """Update linked Drop-off when this record is deleted."""
        if self.dropoff:
            self.update_dropoff_totals()

    def before_cancel(self):
        """
        Edge Case 13.13: Prevent deletion if linked to Completed drop-off.
        Phase 8A: Changed from "Closed" to "Completed".
        """
        if self.dropoff:
            dropoff_status = frappe.db.get_value("Dropoff", self.dropoff, "status")
            if dropoff_status == "Completed":
                frappe.throw(
                    _("Cannot delete Scrap Weight linked to a Completed Drop-off. Cancel the Drop-off first.")
                )

    def update_dropoff_totals(self):
        """Recalculate total_scrap_weight on the linked Drop-off."""
        try:
            dropoff = frappe.get_doc("Dropoff", self.dropoff)
            dropoff.calculate_totals()
            dropoff.flags.ignore_validate = True
            dropoff.save(ignore_permissions=True)
        except Exception:
            # Drop-off might not exist yet during creation
            pass
