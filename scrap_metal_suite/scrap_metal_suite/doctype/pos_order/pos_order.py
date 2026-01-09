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
        self.update_status()

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

    def update_status(self):
        """
        Auto-transition status based on fulfillment progress.

        Status transitions:
        - Pending: No weights received yet (total_received = 0)
        - Processing: Partial weights received (0 < total_received < contracted_weight)
        - Processed: Fully or over-fulfilled (total_received >= contracted_weight)
        - Cancelled: Manually set, not auto-transitioned
        """
        # Don't auto-transition if already cancelled
        if self.status == "Cancelled":
            return

        total_received = flt(self.total_received)
        contracted = flt(self.contracted_weight)

        if total_received == 0:
            # No weights received yet
            if self.status not in ["Pending", "Cancelled"]:
                self.status = "Pending"
        elif contracted > 0 and total_received >= contracted:
            # Fully fulfilled or over-fulfilled
            if self.status != "Processed":
                self.status = "Processed"
        elif total_received > 0:
            # Partial fulfillment
            if self.status != "Processing":
                self.status = "Processing"
