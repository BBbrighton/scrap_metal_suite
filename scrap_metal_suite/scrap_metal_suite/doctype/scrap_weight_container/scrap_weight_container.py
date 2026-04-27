# Copyright (c) 2026, Scrap Metal Suite and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class ScrapWeightContainer(Document):
    """
    Scrap Weight Container Controller

    Implements the per-container weighing model defined in
    docs/DROPOFF_CONTAINER_REDESIGN.md (§4.1, §5.1, §7).

    Each container is one physical bag/bin/pallet weighed against a single
    grade. Reweigh updates this same document and appends a Container Weight
    History row; voiding is non-destructive. Item names are canonical Thai
    and are NEVER translated (see docs/BILINGUAL_GUIDE.md §2).
    """

    # =========================================================================
    # FRAMEWORK HOOKS
    # =========================================================================

    def before_insert(self):
        """Populate denormalised / defaulted fields prior to first save."""
        # item_name is canonical Thai master data - render as-is, never via _()
        if not self.item_name and self.item_code:
            self.item_name = frappe.db.get_value(
                "Item", self.item_code, "item_name"
            )

        # Sequence number within the dropoff (counts active + voided records).
        if not self.container_no and self.dropoff:
            existing = frappe.db.count(
                "Scrap Weight Container",
                filters={"dropoff": self.dropoff},
            )
            self.container_no = (existing or 0) + 1

        if not self.status:
            self.status = "Active"

        # Auto-bind expected_item if exact match against dropoff expected_items.
        if not self.expected_item and self.dropoff and self.item_code:
            expected_codes = self._get_dropoff_expected_codes()
            if self.item_code in expected_codes:
                self.expected_item = self.item_code

        if not self.operator:
            self.operator = frappe.session.user

    def before_save(self):
        """Compute deviation flag and run weight / deviation validations."""
        self._compute_is_deviation()
        self._validate_net_weight()
        self._validate_deviation_reason()
        self._validate_scale_capacity()

    def after_insert(self):
        """Append the Initial weight history row (audit trail)."""
        self.append("weight_history", {
            "weight": flt(self.net_weight),
            "recorded_at": now_datetime(),
            "recorded_by": frappe.session.user,
            "event": "Initial",
            "scale": self.scale,
            "entry_method": self.entry_method,
        })
        # API auth guard already validated; controller-internal save is safe.
        self.save(ignore_permissions=True)

    # =========================================================================
    # EXPLICIT METHODS (called by API layer)
    # =========================================================================

    def record_reweigh(self, new_weight, reason, entry_method="Manual Entry"):
        """
        Record a reweigh: append history, update weight, stamp last_reweigh_*.

        Called by `reweigh_container` API after auth has been validated.
        """
        if not reason:
            frappe.throw(_("Reweigh reason is required"))

        new_weight = flt(new_weight)
        if new_weight <= 0:
            frappe.throw(_("Net weight must be greater than 0"))

        now = now_datetime()
        user = frappe.session.user

        self.append("weight_history", {
            "weight": new_weight,
            "recorded_at": now,
            "recorded_by": user,
            "event": "Reweigh",
            "reason": reason,
            "scale": self.scale,
            "entry_method": entry_method,
        })

        self.net_weight = new_weight
        self.is_reweighed = 1
        self.last_reweigh_at = now
        self.last_reweigh_by = user
        self.last_reweigh_reason = reason
        self.entry_method = entry_method

        self.save()

    def record_void(self, reason, superseded_by=None):
        """
        Mark the container as Voided. Non-destructive: history is preserved.

        Called by `void_container` (and the bulk `void_dropoff_weighing`) APIs
        after auth has been validated.
        """
        if not reason:
            frappe.throw(_("Void reason is required"))

        self.status = "Voided"
        self.voided_reason = reason
        self.voided_at = now_datetime()
        self.voided_by = frappe.session.user
        self.superseded_by = superseded_by

        self.save()

    def approve_deviation(self, reason=None):
        """
        Approve a flagged deviation: stamp approver + timestamp.

        Called by `approve_container_deviation` API. The optional `reason` is
        recorded as a timeline comment for audit, since there is no dedicated
        approval-reason field in the schema.
        """
        self.deviation_approved_by = frappe.session.user
        self.deviation_approved_at = now_datetime()

        if reason:
            self.add_comment("Comment", text=reason)

        self.save()

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _get_dropoff_expected_codes(self):
        """Return the set of `item` codes from the parent Dropoff's
        `expected_items` child table. Empty set if the Dropoff has no
        expected items configured."""
        if not self.dropoff:
            return set()

        rows = frappe.db.get_all(
            "Dropoff Expected Item",
            filters={"parent": self.dropoff, "parenttype": "Dropoff"},
            fields=["item"],
        )
        return {row.item for row in rows if row.item}

    # =========================================================================
    # VALIDATIONS (called from before_save)
    # =========================================================================

    def _compute_is_deviation(self):
        """`is_deviation = 1` iff item_code is NOT in the dropoff's expected
        items. If the dropoff has no expected items, treat that as 'no
        expectation' and leave the flag at 0."""
        expected_codes = self._get_dropoff_expected_codes()
        if not expected_codes:
            self.is_deviation = 0
            return
        self.is_deviation = 0 if self.item_code in expected_codes else 1

    def _validate_net_weight(self):
        """Net weight must be strictly positive."""
        if flt(self.net_weight) <= 0:
            frappe.throw(_("Net weight must be greater than 0"))

    def _validate_deviation_reason(self):
        """When is_deviation is set and the global setting requires a reason,
        block save unless `deviation_reason` is provided."""
        if not self.is_deviation:
            return

        require_reason = frappe.db.get_single_value(
            "Dropoff Container Settings", "require_reason_on_deviation"
        )
        if require_reason and not (self.deviation_reason or "").strip():
            frappe.throw(_("Reason required for grade deviation"))

    def _validate_scale_capacity(self):
        """If the bound Scale declares a max_capacity_kg, refuse weights that
        exceed it."""
        if not self.scale:
            return

        max_capacity = frappe.db.get_value(
            "Scale", self.scale, "max_capacity_kg"
        )
        if not max_capacity:
            return

        if flt(self.net_weight) > flt(max_capacity):
            frappe.throw(
                _("Weight {0} exceeds scale capacity {1}").format(
                    self.net_weight, max_capacity
                )
            )
