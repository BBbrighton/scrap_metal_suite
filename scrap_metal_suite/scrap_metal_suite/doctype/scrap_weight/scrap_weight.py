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
