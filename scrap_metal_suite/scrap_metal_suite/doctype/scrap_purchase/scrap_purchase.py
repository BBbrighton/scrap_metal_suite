# Copyright (c) 2025, Scrap Metal Suite and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, nowtime, flt


class ScrapPurchase(Document):
    def before_insert(self):
        if not self.posting_time:
            self.posting_time = nowtime()

        # Auto-fill from session if provided
        if self.session:
            session = frappe.get_doc("POS Session", self.session)
            self.operator = session.operator
            self.pos_profile = session.pos_profile

    def validate(self):
        self.validate_session()
        self.calculate_item_amounts()
        self.calculate_totals()

    def validate_session(self):
        """Ensure session is open if provided"""
        if self.session:
            status = frappe.db.get_value("POS Session", self.session, "status")
            if status == "Closed":
                frappe.throw(_("Cannot add purchase to a closed session"))

    def calculate_item_amounts(self):
        """Calculate amount for each item"""
        for item in self.items:
            item.amount = flt(item.weight) * flt(item.rate)

    def calculate_totals(self):
        """Calculate total weight and amount"""
        self.total_weight = sum(flt(item.weight) for item in self.items)
        self.total_amount = sum(flt(item.amount) for item in self.items)
