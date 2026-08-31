# Copyright (c) 2025, Scrap Metal Suite and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime

from scrap_metal_suite.scrap_metal_suite.doctype.scale.scale import release_locks_for_session


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
        if self.status == "Closed":
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
        try:
            # `use_db` writes direct — at on_trash time a get_doc + save
            # round-trip may fail because parent in-progress deletes can race
            # with related-doc lookups. The scale's audit trail isn't critical
            # for a session-cleanup release.
            release_locks_for_session(self.name, use_db=True)
        except Exception as e:
            # Don't block the trash on a side-effect failure.
            frappe.log_error(
                f"Failed to release scales on POS Session {self.name} trash: {e}",
                "POS Session on_trash scale release",
            )

    def _release_scale_lock(self):
        """Clear every scale lock pointing at this session.

        Sweeps by `in_use_by_session` instead of following `self.scale`. A
        switch_scale moves the lock to another Scale without necessarily
        rewriting `self.scale`, so following that field releases the wrong
        scale and strands the real one.

        This bit production: SES-2026-00149 closed on 2026-03-04 holding
        `ตราชั่งใหญ่` while its `scale` field said SCALE-002. The lock
        survived until it was cleared by hand on 2026-08-28, six months later,
        blocking that scale for every operator in between.

        on_trash() already swept correctly; this is the same sweep. The caller
        no longer guards on `self.scale` either - an empty field must not mean
        "nothing to release".
        """
        release_locks_for_session(self.name)
