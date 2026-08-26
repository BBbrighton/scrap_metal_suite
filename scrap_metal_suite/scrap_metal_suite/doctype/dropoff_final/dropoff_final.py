# Copyright (c) 2026, X-DESK and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime

from scrap_metal_suite.utils.variance import get_threshold


class DropoffFinal(Document):
	def before_save(self):
		"""Calculate all fields before saving"""
		self.aggregate_from_sortings()
		self.calculate_totals()
		self.calculate_variance()
		self.set_verification_status()
		self.auto_complete_if_done()
		self.apply_settlement_ledger()

	def aggregate_from_sortings(self):
		"""Aggregate all Production Sorting records for this dropoff"""
		if not self.dropoff:
			return

		# Get all submitted Production Sorting records for this dropoff
		sortings = frappe.get_all(
			"Production Sorting",
			filters={"dropoff": self.dropoff, "docstatus": 1},
			fields=["name"]
		)

		if not sortings:
			return

		# Clear existing items
		self.good_items = []
		self.unwanted_items = []
		self.container_items = []

		# Received side, read live from the containers. These are immutable —
		# sorting never restates what the supplier delivered — so this is a
		# lookup, not a stored snapshot that could drift.
		received = {
			c.name: c
			for c in frappe.get_all(
				"Scrap Weight Container",
				filters={"dropoff": self.dropoff},
				fields=["name", "container_type", "item_code", "item_name", "net_weight"],
			)
		}

		# Dictionaries to aggregate by item_code
		good_items_dict = {}
		unwanted_items_dict = {}

		# Aggregate from each sorting session
		for sorting_rec in sortings:
			sorting = frappe.get_doc("Production Sorting", sorting_rec.name)

			# Per-container detail: one received bag can produce several rows
			# (90 kg Grade A + 9 kg Grade B + 1 kg tare from a single 100 kg
			# bag), so this table is deliberately NOT aggregated. The per-grade
			# tables below still are, and settlement continues to read those.
			# Grouped by container, not by classification. A bag's outputs
			# belong together — both for reading and because anything counting
			# "the first row of a container" (the print format does) needs them
			# consecutive.
			tagged = [("Good", i) for i in sorting.good_items if i.get("container")]
			tagged += [("Unwanted", i) for i in sorting.unwanted_items if i.get("container")]
			tagged.sort(key=lambda pair: (pair[1].container, pair[0]))

			for classification, item in tagged:
					src = received.get(item.container)
					self.append("container_items", {
						"container": item.container,
						"container_type": src.container_type if src else None,
						"received_item_code": src.item_code if src else None,
						"received_item_name": src.item_name if src else None,
						"received_weight": flt(src.net_weight) if src else 0,
						"sorted_item_code": item.item_code,
						"sorted_item_name": item.item_name,
						"sorted_weight": flt(item.weight),
						"classification": classification,
						"return_reason": item.get("return_reason"),
						"production_sorting": sorting.name,
						"remarks": item.get("remarks"),
					})

			# Aggregate good items
			for item in sorting.good_items:
				if item.item_code not in good_items_dict:
					good_items_dict[item.item_code] = {
						"item_code": item.item_code,
						"item_name": item.item_name,
						"weight": 0,
						"uom": item.uom
					}
				good_items_dict[item.item_code]["weight"] += flt(item.weight)

			# Aggregate unwanted items (by item_code + return_reason)
			for item in sorting.unwanted_items:
				key = f"{item.item_code}_{item.return_reason}"
				if key not in unwanted_items_dict:
					unwanted_items_dict[key] = {
						"item_code": item.item_code,
						"item_name": item.item_name,
						"weight": 0,
						"uom": item.uom,
						"return_reason": item.return_reason
					}
				unwanted_items_dict[key]["weight"] += flt(item.weight)

		# Append aggregated items to child tables
		for item_data in good_items_dict.values():
			self.append("good_items", item_data)

		for item_data in unwanted_items_dict.values():
			self.append("unwanted_items", item_data)

		# Update sorting sessions list
		self.sorting_sessions = ", ".join([s.name for s in sortings])

	def calculate_totals(self):
		"""Calculate total weights"""
		self.total_good_weight = sum(flt(row.weight) for row in self.good_items)
		self.total_unwanted_weight = sum(flt(row.weight) for row in self.unwanted_items)
		self.total_verified_weight = self.total_good_weight + self.total_unwanted_weight

	def calculate_variance(self):
		"""Calculate variance between dropoff weight and sorted weight"""
		self.weight_variance = flt(self.dropoff_total_weight) - flt(self.total_verified_weight)

		if flt(self.dropoff_total_weight) > 0:
			self.variance_percent = abs(self.weight_variance / self.dropoff_total_weight) * 100
		else:
			self.variance_percent = 0

		# Stamp the tolerance onto the document the first time it is judged, then
		# keep using that stored number. A manager raising the global threshold
		# must not silently re-grade a Dropoff Final that was already assessed —
		# a past Verified result stays reproducible.
		#
		# The old code fell back to a bare `or 5.0` here, so an unconfigured
		# `Production Sorting Settings` quietly graded everything at 5% while
		# the guides promised 0.1%.
		if not self.variance_threshold_percent:
			self.variance_threshold_percent = get_threshold("sorting_variance_threshold_percent")
		self.variance_ok = self.variance_percent <= flt(self.variance_threshold_percent)

	def set_verification_status(self):
		"""Set verification status based on variance.

		A manager override wins: once `variance_overridden` is set, this must not
		drag the record back to "Needs Review" on the next save, or the override
		would be silently undone and the document would re-strand itself.
		Mirrors `Dropoff.calculate_verification_status`, which respects
		`verification_overridden` the same way.
		"""
		if self.variance_overridden:
			self.verification_status = "Verified"
			return

		if not self.good_items and not self.unwanted_items:
			self.verification_status = "Pending"
		elif self.variance_ok:
			self.verification_status = "Verified"
		else:
			self.verification_status = "Needs Review"

	def accept_variance(self, override_reason=None):
		"""Manager override: accept an out-of-tolerance variance and release
		this Dropoff Final for settlement.

		`auto_complete_if_done` parks a record at "In Progress" when it has
		sorted items but `variance_ok` is false, and nothing else can move it —
		no API, no button, and the desk form calls `frm.disable_save()`. The
		only other way out is for the variance itself to become acceptable,
		which for a genuine weight discrepancy it never will.

		This is the deliberate human decision that closes it, recorded with who,
		when and why. Mirrors `Dropoff.mark_verified`.

		Idempotent: re-running on an already-overridden record is a no-op.
		"""
		if self.status in ("Settled", "Cancelled"):
			frappe.throw(
				_("Cannot override variance on a {0} Dropoff Final").format(self.status)
			)

		if self.variance_overridden:
			return

		if not override_reason:
			frappe.throw(_("Override reason required to accept an out-of-tolerance variance"))

		self.variance_overridden = 1
		self.variance_override_by = frappe.session.user
		self.variance_override_at = now_datetime()
		self.variance_override_reason = override_reason

		self.verification_status = "Verified"
		self.status = "Unsettled"
		if not self.completed_at:
			self.completed_at = now_datetime()
			self.completed_by = frappe.session.user

		self.save(ignore_permissions=True)
		self.add_comment(
			"Comment",
			_("Variance override applied ({0}%): {1}").format(
				flt(self.variance_percent, 2), override_reason
			),
		)

	def auto_complete_if_done(self):
		"""Auto-set to Unsettled if sorting is done and variance is within threshold"""
		# "Partially Settled" belongs in this guard for the same reason "Settled"
		# does: money has already moved against this document, so sorting
		# progress must not walk the status backwards. apply_settlement_ledger()
		# owns every settlement status from here on.
		if self.status in ("Unsettled", "Partially Settled", "Settled"):
			return

		if (self.good_items or self.unwanted_items) and self.variance_ok:
			self.status = "Unsettled"
			self.verification_status = "Verified"
			self.completed_at = now_datetime()
			self.completed_by = frappe.session.user
		elif self.good_items or self.unwanted_items:
			self.status = "In Progress"

	def apply_settlement_ledger(self):
		"""Derive per-item settled/remaining qty from submitted PO Final allocations.

		MUST run last in `before_save`. `aggregate_from_sortings()` has just
		cleared and rebuilt `self.good_items`, so anything stamped earlier would
		already be gone — and because Dropoff Final is not submittable, that
		rebuild happens on every save for the life of the document.

		That is exactly why these numbers are DERIVED rather than stored and
		incremented. The Price Lock pattern (`update_settled_qty`, an atomic SQL
		increment) works there because `SMT Price Lock Item` rows are frozen
		source data on a submitted document; `Dropoff Final Good Item` rows are a
		regenerated aggregate, so a stored ledger on them would be silently
		destroyed the next time production submitted another sorting session.

		Recomputing from `SMT Purchase Order Allocation` — the real join table —
		means the ledger cannot drift, needs no backfill for existing records,
		and makes PO Final submit/cancel idempotent.

		See docs/PRICE_LOCK_SETTLEMENT_DESIGN.md §16.2.
		"""
		# Baseline: nothing settled. Applies to brand-new documents and to any
		# item whose allocations were later cancelled.
		for row in self.good_items:
			row.settled_qty = 0
			row.remaining_qty = flt(row.weight, 3)

		if self.is_new():
			return

		allocations = frappe.get_all(
			"SMT Purchase Order Allocation",
			filters={
				"drop_off_final": self.name,
				"parenttype": "SMT Purchase Order",
				"docstatus": 1,
			},
			fields=["item_code", "qty", "parent"],
			order_by="creation asc",
		)

		settled_by_item = {}
		documents = []
		for alloc in allocations:
			settled_by_item[alloc.item_code] = (
				flt(settled_by_item.get(alloc.item_code, 0)) + flt(alloc.qty)
			)
			if alloc.parent not in documents:
				documents.append(alloc.parent)

		for row in self.good_items:
			row.settled_qty = flt(settled_by_item.get(row.item_code, 0), 3)
			row.remaining_qty = flt(flt(row.weight) - flt(row.settled_qty), 3)

		self.settlement_documents = ", ".join(documents)
		# Kept for backwards compatibility only — under partial settlement a
		# single Link cannot express the relationship. `settlement_documents`
		# is the complete answer.
		self.po_final = documents[-1] if documents else None

		self.derive_settlement_status()

	def derive_settlement_status(self):
		"""Set status from the ledger. Only ever touches settlement statuses."""
		if self.status in ("Draft", "In Progress", "Cancelled"):
			# Sorting is not finished yet; nothing can have been settled anyway.
			return

		any_settled = any(flt(r.settled_qty, 3) > 0 for r in self.good_items)
		fully_settled = bool(self.good_items) and all(
			flt(r.remaining_qty, 3) <= 0 for r in self.good_items
		)

		if fully_settled:
			self.status = "Settled"
			if not self.settled_at:
				self.settled_at = now_datetime()
				self.settled_by = frappe.session.user
		elif any_settled:
			self.status = "Partially Settled"
			self.settled_at = None
			self.settled_by = None
		else:
			self.status = "Unsettled"
			self.settled_at = None
			self.settled_by = None
