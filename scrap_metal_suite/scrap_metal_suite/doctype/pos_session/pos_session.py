# Copyright (c) 2025, Scrap Metal Suite and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


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

        # Calculate totals from purchases using frappe.db.get_all
        purchases = frappe.db.get_all(
            "Scrap Purchase",
            filters={"session": self.name},
            fields=["total_amount", "total_weight"]
        )

        self.total_purchases = len(purchases)
        self.total_amount = sum(flt(p.total_amount) for p in purchases)
        self.total_weight = sum(flt(p.total_weight) for p in purchases)
        self.closing_time = now_datetime()
        self.status = "Closed"
        self.save()

        return {
            "total_purchases": self.total_purchases,
            "total_amount": self.total_amount,
            "total_weight": self.total_weight
        }

    def on_update(self):
        """Handle scale release when session is closed"""
        if self.status == "Closed" and self.scale:
            self._release_scale_lock()

    def on_trash(self):
        """Release any scale lock pointing at this session.

        Without this hook, a session deleted via `frappe.delete_doc(force=True)`
        (e.g. test cleanup) leaves the linked Scale with `in_use=1,
        in_use_by_session=<deleted name>` — a stuck lock that the next
        operator can't clear without a manual SQL fix. We sweep ALL scales
        pointing at this session, not just `self.scale`, in case a prior
        switch_scale moved the lock to a different scale.
        """
        for scale_name in frappe.get_all(
            "Scale",
            filters={"in_use_by_session": self.name},
            pluck="name",
        ):
            try:
                # Direct DB write — at on_trash time, get_doc + save round-trip
                # may fail because parent in-progress deletes can race with
                # related-doc lookups. The scale's audit trail isn't critical
                # for a session-cleanup release.
                frappe.db.set_value(
                    "Scale", scale_name,
                    {"in_use": 0, "in_use_by_session": None},
                    update_modified=False,
                )
            except Exception as e:
                # Don't block the trash on a side-effect failure.
                frappe.log_error(
                    f"Failed to release scale {scale_name} on POS Session {self.name} trash: {e}",
                    "POS Session on_trash scale release",
                )

    def _release_scale_lock(self):
        """Clear the in_use lock on the linked scale if it still points here."""
        if not self.scale:
            return
        in_use_by = frappe.db.get_value("Scale", self.scale, "in_use_by_session")
        if in_use_by == self.name:
            scale_doc = frappe.get_doc("Scale", self.scale)
            scale_doc.in_use = 0
            scale_doc.in_use_by_session = None
            scale_doc.save()
