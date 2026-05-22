# Copyright (c) 2025, Scrap Metal Suite and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime, today

from scrap_metal_suite.overrides.naming import supplier_daily_name


class ScrapWeight(Document):
    """
    Scrap Weight Controller — the customer-facing receipt for a Dropoff.

    Wave 10 redesign (DROPOFF_CONTAINER_REDESIGN.md §14.19):
    - Submittable; immutable after submit.
    - One submitted Scrap Weight per Dropoff at any time. If a reweigh
      happens post-submit, the existing receipt is cancelled and a fresh one
      is generated when the operator clicks "Finish Container Weighing"
      again. New one carries `is_amended=1` and a back-link via
      Frappe's `amended_from`.
    - Items child = per-grade aggregation (one row per item_code) snapshotted
      at submit time. Containers held by this receipt are queryable via
      `Scrap Weight Container.scrap_weight = self.name` (stamped at submit).
    - Pre-Wave-10 fields (posting_time, session, operator, pos_profile,
      scale, entry_method, photos, is_reweight) were per-event metadata for
      the old non-submittable model and have been removed.

    Use the API `finish_weighing_session` (in api/v1/dropoff.py) to generate
    or amend a Scrap Weight — don't insert directly from frontend code.
    """

    def autoname(self):
        # SW-{supplier_short}-YYMMDD-#  — matches the Dropoff family naming.
        # Use the supplier from the linked Dropoff (set via fetch_from on save,
        # but not yet present on insert; resolve directly).
        if not self.dropoff:
            frappe.throw(_("Dropoff is required to generate a Scrap Weight ID."))
        supplier = frappe.db.get_value("Dropoff", self.dropoff, "supplier")
        on_date = frappe.db.get_value("Dropoff", self.dropoff, "dropoff_scheduled_start")
        self.name = supplier_daily_name("SW", supplier, on_date=on_date)

    def before_insert(self):
        if not self.posting_date:
            self.posting_date = today()
        if not self.generated_by:
            self.generated_by = frappe.session.user
        if not self.generated_at:
            self.generated_at = now_datetime()

    def validate(self):
        self._validate_one_active_per_dropoff()
        self._calculate_totals()

    def _validate_one_active_per_dropoff(self):
        """Enforce: at most one Submitted Scrap Weight per Dropoff at a time.

        Cancelled receipts (docstatus=2) are kept in the DB for the audit
        chain, so the constraint is on docstatus=1 only.
        """
        if not self.dropoff:
            return
        existing = frappe.db.get_all(
            "Scrap Weight",
            filters={
                "dropoff": self.dropoff,
                "docstatus": 1,
                "name": ["!=", self.name or ""],
            },
            pluck="name",
        )
        if existing:
            frappe.throw(
                _("Dropoff {0} already has a submitted Scrap Weight ({1}). "
                  "Cancel it before issuing a new one.").format(
                    self.dropoff, ", ".join(existing),
                )
            )

    def _calculate_totals(self):
        total = 0.0
        bag_count = 0
        for row in self.items:
            total += flt(row.weight)
            bag_count += int(row.container_count or 0)
        self.total_weight = total
        self.total_container_count = bag_count

    def on_submit(self):
        """Stamp the link on every Active container belonging to this Dropoff
        so the receipt's `containers` queryset is reproducible after the fact.
        """
        active_containers = frappe.get_all(
            "Scrap Weight Container",
            filters={"dropoff": self.dropoff, "status": "Active"},
            pluck="name",
        )
        for ct in active_containers:
            frappe.db.set_value(
                "Scrap Weight Container", ct, "scrap_weight", self.name,
                update_modified=False,
            )

    def on_cancel(self):
        """When this receipt is cancelled (because of a reweigh, typically),
        do NOT clear the `scrap_weight` link on its containers. The link
        records 'this container was part of receipt SW-X' which remains true
        even if the receipt is now cancelled. The amended receipt stamps its
        own containers when it submits.
        """
        # Intentional no-op — preserve the audit trail on containers.
        return
