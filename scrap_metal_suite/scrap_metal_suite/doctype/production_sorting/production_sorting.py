# Copyright (c) 2026, Scrap Metal Suite and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class ProductionSorting(Document):
    def validate(self):
        self.calculate_totals()
        self.check_variance()

    def before_insert(self):
        self.sorted_by = self.sorted_by or frappe.session.user
        self.populate_source_items()

    def populate_source_items(self):
        """Copy item_summary from linked Dropoff into source_items"""
        if not self.dropoff:
            return

        if self.source_items:
            return

        dropoff = frappe.get_doc("Dropoff", self.dropoff)

        if hasattr(dropoff, "item_summary"):
            for item in dropoff.item_summary:
                self.append("source_items", {
                    "item": item.item,
                    "item_name": item.item_name,
                    "total_weight": flt(item.total_weight)
                })

    def calculate_totals(self):
        """Calculate total sorted weight and variance"""
        self.total_sorted_weight = sum(
            flt(item.weight) for item in self.sorted_items
        )

        self.weight_variance = flt(self.total_sorted_weight) - flt(self.dropoff_total_weight)

        if flt(self.dropoff_total_weight):
            self.variance_percent = (
                flt(self.weight_variance) / flt(self.dropoff_total_weight)
            ) * 100
        else:
            self.variance_percent = 0

    def check_variance(self):
        """Check if variance is within threshold"""
        threshold = flt(
            frappe.db.get_single_value(
                "Production Sorting Settings", "variance_threshold_percent"
            )
        ) or 0.1

        self.variance_ok = abs(flt(self.variance_percent)) <= threshold

        if self.status in ("Completed", "Verified", "Needs Review"):
            if self.variance_ok:
                self.verification_status = "Verified"
            else:
                self.verification_status = "Needs Review"
