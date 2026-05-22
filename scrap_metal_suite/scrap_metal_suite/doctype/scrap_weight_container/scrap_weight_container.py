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
    docs/DROPOFF_CONTAINER_REDESIGN.md (§14.19 — Wave 10).

    Each container is one physical bag/bin/pallet weighed against a single
    grade. **Containers are immutable** — there is no in-place reweigh. To
    correct a weighing, void the container and weigh a new one. If the parent
    Dropoff already has a submitted Scrap Weight, the replacement is tagged
    `is_reweight=1` with a back-link to the voided original (`reweighed_from`).

    Item names are canonical Thai and are NEVER translated
    (see docs/BILINGUAL_GUIDE.md §2).
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

        # Wave 11: container_no removed. The canonical bag identifier is the
        # doc name (CTN-YYMM-#####). Audit chain remains via `reweighed_from`
        # / `superseded_by`. Operator-facing count = `Containers (N)` badge
        # in the journal header, computed from the active row count at render
        # time — no stored sequence number needed.

        if not self.status:
            self.status = "Active"

        if not self.operator:
            self.operator = frappe.session.user

    def before_save(self):
        """Run weight / scale validations."""
        self._validate_net_weight()
        self._validate_scale_capacity()

    # =========================================================================
    # EXPLICIT METHODS (called by API layer)
    # =========================================================================

    def record_void(self, reason, superseded_by=None):
        """
        Mark the container as Voided. Non-destructive: the row stays in the
        DB so audit + the `reweighed_from` back-link from a replacement
        container can still resolve.

        Called by `void_container`, the bulk `void_dropoff_weighing`, and the
        reweigh flow (which voids the old + inserts a new container) after
        auth has been validated.
        """
        if not reason:
            frappe.throw(_("Void reason is required"))

        self.status = "Voided"
        self.voided_reason = reason
        self.voided_at = now_datetime()
        self.voided_by = frappe.session.user
        self.superseded_by = superseded_by

        self.save()

    # =========================================================================
    # VALIDATIONS (called from before_save)
    # =========================================================================

    def _validate_net_weight(self):
        """Net weight must be strictly positive."""
        if flt(self.net_weight) <= 0:
            frappe.throw(_("Net weight must be greater than 0"))

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
