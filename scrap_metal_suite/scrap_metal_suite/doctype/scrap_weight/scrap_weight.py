# Copyright (c) 2025, Chotiputsilp.r@gmail.com and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, nowtime


class ScrapWeight(Document):
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
        """Update linked POS Order with weighed items."""
        if self.pos_order:
            self.update_pos_order_items()

    def on_trash(self):
        """Update linked POS Order when this record is deleted."""
        if self.pos_order:
            self.update_pos_order_items(exclude_self=True)

    def update_pos_order_items(self, exclude_self=False):
        """Sync all weighed items from Scrap Weight records to POS Order."""
        pos_order = frappe.get_doc("POS Order", self.pos_order)

        # Get all Scrap Weight records linked to this POS Order
        filters = {"pos_order": self.pos_order}
        if exclude_self:
            filters["name"] = ["!=", self.name]

        scrap_weights = frappe.get_all(
            "Scrap Weight",
            filters=filters,
            fields=["name"],
            order_by="posting_date asc, posting_time asc"
        )

        # Clear existing weighed items
        pos_order.set("items", [])
        total_weight = 0

        # Add items from each Scrap Weight record
        for sw in scrap_weights:
            sw_doc = frappe.get_doc("Scrap Weight", sw.name)
            for item in sw_doc.items:
                pos_order.append("items", {
                    "scrap_weight": sw.name,
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "weight": item.weight,
                    "uom": item.uom
                })
                total_weight += flt(item.weight)

        # Update total scrap weight
        pos_order.total_scrap_weight = total_weight

        # Save without triggering full validation
        pos_order.flags.ignore_validate = True
        pos_order.save(ignore_permissions=True)
