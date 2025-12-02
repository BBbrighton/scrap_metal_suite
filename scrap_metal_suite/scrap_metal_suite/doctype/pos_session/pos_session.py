# Copyright (c) 2025, Scrap Metal Suite and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class POSSession(Document):
    def before_insert(self):
        self.opening_time = now_datetime()
        self.operator = frappe.session.user

    def validate(self):
        self.validate_open_session()

    def validate_open_session(self):
        """Ensure operator doesn't have another open session"""
        if self.status == "Open" and not self.is_new():
            return

        if self.is_new() or self.has_value_changed("status"):
            existing = frappe.db.exists(
                "POS Session",
                {
                    "operator": self.operator,
                    "status": "Open",
                    "name": ["!=", self.name or ""]
                }
            )
            if existing and self.status == "Open":
                frappe.throw(
                    _("Operator {0} already has an open session: {1}").format(
                        self.operator, existing
                    )
                )

    def close_session(self):
        """Close the session and calculate totals"""
        if self.status == "Closed":
            frappe.throw(_("Session is already closed"))

        # Calculate totals from purchases
        totals = frappe.db.sql("""
            SELECT
                COUNT(*) as total_purchases,
                COALESCE(SUM(total_amount), 0) as total_amount,
                COALESCE(SUM(total_weight), 0) as total_weight
            FROM `tabScrap Purchase`
            WHERE session = %s
        """, self.name, as_dict=True)[0]

        self.total_purchases = totals.total_purchases
        self.total_amount = totals.total_amount
        self.total_weight = totals.total_weight
        self.closing_time = now_datetime()
        self.status = "Closed"
        self.save()

        return {
            "total_purchases": self.total_purchases,
            "total_amount": self.total_amount,
            "total_weight": self.total_weight
        }
