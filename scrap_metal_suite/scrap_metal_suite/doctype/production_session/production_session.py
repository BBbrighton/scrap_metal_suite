# Copyright (c) 2026, Scrap Metal Suite and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime

from scrap_metal_suite.scrap_metal_suite.doctype.scale.scale import release_locks_for_session


class ProductionSession(Document):
    def before_insert(self):
        self.opening_time = now_datetime()
        self.operator = self.operator or frappe.session.user

    def validate(self):
        self.validate_open_session()

    def validate_open_session(self):
        """Ensure operator doesn't have another open session"""
        if self.status == "Open" and not self.is_new():
            return

        if self.is_new() or self.has_value_changed("status"):
            existing = frappe.db.exists(
                "Production Session",
                {
                    "operator": self.operator,
                    "status": "Open",
                    "name": ["!=", self.name or ""]
                }
            )
            if existing and self.status == "Open":
                frappe.throw(
                    _("Operator {0} already has an open production session: {1}").format(
                        self.operator, existing
                    )
                )

    def close_session(self):
        """Close the session and calculate totals"""
        if self.status == "Closed":
            frappe.throw(_("Session is already closed"))

        # Calculate totals from production sortings
        sortings = frappe.db.get_all(
            "Production Sorting",
            filters={"session": self.name},
            fields=["total_weight"]
        )

        self.total_sortings = len(sortings)
        self.total_weight_sorted = sum(flt(s.total_weight) for s in sortings)
        self.closing_time = now_datetime()
        self.closed_by = frappe.session.user
        self.status = "Closed"
        self.save()

        return {
            "total_sortings": self.total_sortings,
            "total_weight_sorted": self.total_weight_sorted
        }

    def on_update(self):
        """Handle scale release when session is closed.

        Sweeps by `in_use_by_session` rather than following `self.scale`: an
        empty `scale` field must not be read as "nothing to release", and a
        lock can sit on a scale this session no longer names. Same reasoning as
        POS Session._release_scale_lock, where following `self.scale` stranded
        a production scale for six months.
        """
        if self.status == "Closed":
            release_locks_for_session(self.name)
