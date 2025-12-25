# Copyright (c) 2025, Scrap Metal Suite and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class POSOrder(Document):
    """
    POS Order DocType Controller

    Implements validations from DROPOFF_ARCHITECTURE.md Part 13 (Edge Cases)
    """

    def validate(self):
        self.calculate_contracted_weight()

    def before_cancel(self):
        """
        Edge Case 13.11: Prevent cancellation if linked to active drop-off.
        """
        # Using frappe.db.get_all to avoid SQL restriction issues
        dropoff_orders = frappe.db.get_all(
            "Dropoff Order",
            filters={"pos_order": self.name},
            fields=["parent"]
        )

        active_dropoffs = []
        for do in dropoff_orders:
            dropoff_status = frappe.db.get_value("Dropoff", do.parent, "status")
            if dropoff_status and dropoff_status not in ("Cancelled", "Closed"):
                active_dropoffs.append(do.parent)

        if active_dropoffs:
            frappe.throw(
                _("Cannot cancel: Order linked to active Drop-offs: {0}. Cancel the Drop-off(s) first.").format(
                    ", ".join(active_dropoffs)
                )
            )

    def calculate_contracted_weight(self):
        """Calculate contracted_weight from order_items."""
        total = 0
        if self.order_items:
            for item in self.order_items:
                total += flt(item.weight) if hasattr(item, "weight") else 0
        self.contracted_weight = total
