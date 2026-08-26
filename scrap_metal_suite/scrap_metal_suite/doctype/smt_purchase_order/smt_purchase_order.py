# Copyright (c) 2026, X-DESK and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from scrap_metal_suite.overrides.naming import supplier_monthly_name


class SMTPurchaseOrder(Document):
	def autoname(self):
		# Operator-supplied reference wins; otherwise SPO-{supplier_short}-YYMM-###.
		if self.custom_reference:
			self.name = self.custom_reference
			return
		self.name = supplier_monthly_name("SPO", self.supplier)

	def validate(self):
		self.validate_supplier_consistency()
		self.validate_allocations()
		self.validate_dropoff_coverage()
		self.calculate_drawn_weights()
		self.calculate_totals()

	def validate_supplier_consistency(self):
		"""Every referenced Dropoff Final and PO must belong to self.supplier and be Unsettled."""
		for row in self.drop_off_finals:
			dof = frappe.db.get_value(
				"Dropoff Final", row.drop_off_final,
				["supplier", "status"], as_dict=True
			)
			if dof.supplier != self.supplier:
				frappe.throw(
					_("Row {0}: Dropoff Final {1} belongs to supplier {2}, "
					  "not {3}").format(row.idx, row.drop_off_final, dof.supplier, self.supplier)
				)
			if dof.status == "Settled":
				frappe.throw(
					_("Row {0}: Dropoff Final {1} is already settled. "
					  "Cancel the existing PO Final first.").format(row.idx, row.drop_off_final)
				)

		for row in self.allocations:
			if row.source_type == "PO" and row.po:
				po_supplier = frappe.db.get_value("SMT Price Lock", row.po, "supplier")
				if po_supplier != self.supplier:
					frappe.throw(
						_("Allocation row {0}: PO {1} belongs to supplier {2}, "
						  "not {3}").format(row.idx, row.po, po_supplier, self.supplier)
					)

	def validate_allocations(self):
		"""Validate each allocation row."""
		# Track how much we're allocating against each PO item row in this PO Final
		po_item_allocations = {}  # {po_item_row_name: total_qty_allocated}

		# Valid dropoff finals in this document
		valid_dofs = set(r.drop_off_final for r in self.drop_off_finals)

		for row in self.allocations:
			if flt(row.qty) <= 0:
				frappe.throw(_("Allocation row {0}: Qty must be greater than 0").format(row.idx))

			# Dropoff Final must be in the drop_off_finals table
			if row.drop_off_final not in valid_dofs:
				frappe.throw(
					_("Allocation row {0}: Dropoff Final {1} is not in the "
					  "Dropoff Finals table above").format(row.idx, row.drop_off_final)
				)

			if row.source_type == "PO":
				if not row.po:
					frappe.throw(
						_("Allocation row {0}: PO is required when source is PO").format(row.idx)
					)

				# PO must be in valid status
				po_status = frappe.db.get_value("SMT Price Lock", row.po, "status")
				if po_status not in ("Open", "Partially Settled"):
					frappe.throw(
						_("Allocation row {0}: PO {1} has status {2}, "
						  "cannot allocate against it").format(row.idx, row.po, po_status)
					)

				# Find the matching PO item row
				po_item = self._get_po_item_row(row)
				row.po_item_row = po_item.name

				# Force rate from PO — no override allowed
				row.rate = po_item.po_rate

				# Track allocation against this PO item row
				key = po_item.name
				po_item_allocations.setdefault(key, 0)
				po_item_allocations[key] += flt(row.qty)

				# Check we're not over-allocating
				if po_item_allocations[key] > flt(po_item.remaining_qty):
					frappe.throw(
						_("Allocation row {0}: Total allocation of {1} against PO {2} "
						  "item {3} exceeds remaining qty {4}").format(
							row.idx, po_item_allocations[key],
							row.po, row.item_code, po_item.remaining_qty
						)
					)

			elif row.source_type == "Spot":
				if flt(row.rate) <= 0:
					frappe.throw(
						_("Allocation row {0}: Rate must be greater than 0 for Spot").format(row.idx)
					)

			# Calculate amount
			row.amount = flt(flt(row.qty) * flt(row.rate), 2)

	def _get_po_item_row(self, alloc_row):
		"""Find the matching item row in the PO for this allocation."""
		po_items = frappe.get_all(
			"SMT Price Lock Item",
			filters={"parent": alloc_row.po, "item_code": alloc_row.item_code},
			fields=["name", "item_code", "po_qty", "po_rate", "settled_qty", "remaining_qty"]
		)
		if not po_items:
			frappe.throw(
				_("Allocation row {0}: Item {1} not found in PO {2}").format(
					alloc_row.idx, alloc_row.item_code, alloc_row.po
				)
			)
		# If multiple rows of same item in PO, use po_item_row hint if set
		if alloc_row.po_item_row:
			for pi in po_items:
				if pi.name == alloc_row.po_item_row:
					return pi
		return po_items[0]

	def validate_dropoff_coverage(self):
		"""This document's draw, plus what other submitted PO Finals already took,
		must not exceed what the Dropoff Final actually holds.

		v1 demanded exact equality — a Dropoff Final was closed in full, by one PO
		Final, or not at all. v2 relaxes that to an upper bound so a single
		delivery can be settled in instalments across several PO Finals.

		A useful side effect: a partially allocated PO Final is now a valid
		draft. Under the equality rule `validate()` threw on every save until the
		last row was filled in, so an accountant could not save work in progress.

		See docs/PRICE_LOCK_SETTLEMENT_DESIGN.md §16.4.
		"""
		for dof_row in self.drop_off_finals:
			dof_name = dof_row.drop_off_final

			# Get actual good items from Dropoff Final
			dof_items = frappe.get_all(
				"Dropoff Final Good Item",
				filters={"parent": dof_name},
				fields=["item_code", "weight"]
			)
			dof_item_map = {}
			for item in dof_items:
				dof_item_map.setdefault(item.item_code, 0)
				dof_item_map[item.item_code] += flt(item.weight)

			# Sum allocations for this Dropoff Final
			alloc_map = {}
			for row in self.allocations:
				if row.drop_off_final == dof_name:
					alloc_map.setdefault(row.item_code, 0)
					alloc_map[row.item_code] += flt(row.qty)

			# Under an upper bound rather than an equality, drawing zero is
			# arithmetically valid — but a row in the selector table that draws
			# nothing asserts a relationship this document does not have.
			if not alloc_map:
				frappe.throw(
					_("Dropoff Final {0} is listed above but nothing is allocated "
					  "from it. Pull its items or remove the row.").format(dof_name)
				)

			# What OTHER submitted PO Finals have already drawn from this delivery
			settled_elsewhere = self.get_settled_elsewhere(dof_name)

			for item_code, allocated in alloc_map.items():
				# No allocations for items not in the Dropoff Final
				if item_code not in dof_item_map:
					frappe.throw(
						_("Allocation references item {0} in Dropoff Final {1}, "
						  "but that item is not in the Dropoff Final").format(
							item_code, dof_name
						)
					)

				available = flt(dof_item_map[item_code], 3)
				elsewhere = flt(settled_elsewhere.get(item_code, 0), 3)
				remaining = flt(available - elsewhere, 3)
				drawn = flt(allocated, 3)

				if drawn > remaining:
					frappe.throw(
						_("Dropoff Final {0}, item {1}: this document draws {2} kg "
						  "but only {3} kg remains ({4} kg received, {5} kg already "
						  "settled by other PO Finals).").format(
							dof_name, item_code, drawn, remaining, available, elsewhere
						)
					)

	def get_settled_elsewhere(self, dof_name):
		"""Qty per item already drawn from this Dropoff Final by OTHER submitted PO Finals.

		Excludes this document by name so re-validating a submitted doc doesn't
		count its own rows twice. A cancelled PO Final has docstatus 2 and drops
		out here automatically, which is what returns its share to the pool.
		"""
		rows = frappe.get_all(
			"SMT Purchase Order Allocation",
			filters={
				"drop_off_final": dof_name,
				"parenttype": "SMT Purchase Order",
				"parent": ["!=", self.name],
				"docstatus": 1,
			},
			fields=["item_code", "qty"],
		)
		settled = {}
		for row in rows:
			settled[row.item_code] = flt(settled.get(row.item_code, 0)) + flt(row.qty)
		return settled

	def calculate_drawn_weights(self):
		"""Stamp each selector row with what THIS document draws from that delivery.

		`total_weight` is fetched from the Dropoff Final and is its entire good
		weight — under partial settlement that is no longer what this document
		settles, and printing it on ใบสั่งซื้อ would hand the supplier a figure
		far larger than what they are being paid for.
		"""
		drawn = {}
		for row in self.allocations:
			drawn[row.drop_off_final] = flt(drawn.get(row.drop_off_final, 0)) + flt(row.qty)

		for dof_row in self.drop_off_finals:
			dof_row.drawn_weight = flt(drawn.get(dof_row.drop_off_final, 0), 3)

	def calculate_totals(self):
		self.total_po_value = flt(
			sum(flt(r.amount) for r in self.allocations if r.source_type == "PO"), 2
		)
		self.total_spot_value = flt(
			sum(flt(r.amount) for r in self.allocations if r.source_type == "Spot"), 2
		)
		self.total_amount = flt(self.total_po_value + self.total_spot_value, 2)

	def on_submit(self):
		self.update_po_settlement()
		self.sync_dropoff_finals()
		self.create_draft_purchase_invoice()
		self.db_set("status", "Submitted")

	def update_po_settlement(self):
		"""Increment settled_qty on each PO item row."""
		for row in self.allocations:
			if row.source_type == "PO" and row.po:
				po_doc = frappe.get_doc("SMT Price Lock", row.po)
				po_doc.update_settled_qty(row.po_item_row, flt(row.qty))

	def sync_dropoff_finals(self):
		"""Re-derive each referenced Dropoff Final's settlement ledger.

		Used by BOTH on_submit and on_cancel — this method does no arithmetic of
		its own, it just saves the Dropoff Final and lets
		`DropoffFinal.apply_settlement_ledger()` recompute settled/remaining qty
		and status from the submitted allocations. By the time either hook runs,
		this document's docstatus is already committed, so the recompute sees the
		correct picture in both directions.

		That symmetry is the point. v1 had `mark_dropoff_finals_settled` stamping
		status=Settled and `revert_dropoff_finals` stamping it back to Unsettled;
		under partial settlement the revert was a double-payment vector — cancel
		one of two PO Finals drawing on the same delivery and the whole Dropoff
		Final returned to the pool while the other document still held a
		submitted, invoiced claim on part of it.

		`ignore_permissions` because accountants hold read-only on Dropoff Final
		per PRICE_LOCK_SETTLEMENT_DESIGN.md §9.2 — the write is a system
		consequence of settling, not a user edit.
		"""
		for dof_row in self.drop_off_finals:
			dof = frappe.get_doc("Dropoff Final", dof_row.drop_off_final)
			dof.save(ignore_permissions=True)

	def create_draft_purchase_invoice(self):
		"""Create a Draft Purchase Invoice from the allocation rows."""
		pi = frappe.new_doc("Purchase Invoice")
		pi.supplier = self.supplier
		pi.posting_date = self.final_date

		for row in self.allocations:
			pi.append("items", {
				"item_code": row.item_code,
				"qty": row.qty,
				"rate": row.rate,
				"uom": "Kg",
			})

		pi.insert(ignore_permissions=True)
		self.db_set("purchase_invoice", pi.name)

	def before_cancel(self):
		"""Handle PI cleanup before Frappe's link check runs."""
		self.handle_purchase_invoice()
		# After deleting draft PI, skip Frappe's link check for the now-deleted PI
		self.flags.ignore_links = True

	def on_cancel(self):
		self.revert_po_settlement()
		self.sync_dropoff_finals()
		self.db_set("status", "Cancelled")

	def revert_po_settlement(self):
		"""Decrement settled_qty on each PO item row."""
		for row in self.allocations:
			if row.source_type == "PO" and row.po:
				po_doc = frappe.get_doc("SMT Price Lock", row.po)
				po_doc.update_settled_qty(row.po_item_row, -flt(row.qty))

	@frappe.whitelist()
	def get_pullable_items(self):
		"""Wanted items still available to draw, for the pull dialog.

		Good items only — unwanted material is returned to the supplier, never
		paid for, and `validate_dropoff_coverage` correspondingly only ever looks
		at `Dropoff Final Good Item`.

		Returns rows already net of (a) what other submitted PO Finals have drawn
		and (b) what this document has allocated so far, so re-clicking the button
		after adding another Dropoff Final never duplicates existing work. Rows
		with nothing left are omitted entirely.

		Deliberately returns no `source_type`, `po` or `rate`: design decision #7
		forbids automatic FIFO allocation. Choosing which Price Lock to draw down
		is the accountant's judgment — the button removes the transcription, not
		the decision.
		"""
		already_here = {}
		for row in self.allocations:
			key = (row.drop_off_final, row.item_code)
			already_here[key] = flt(already_here.get(key, 0)) + flt(row.qty)

		pullable = []
		for dof_row in self.drop_off_finals:
			dof_name = dof_row.drop_off_final
			if not dof_name:
				continue

			settled_elsewhere = self.get_settled_elsewhere(dof_name)

			for item in frappe.get_all(
				"Dropoff Final Good Item",
				filters={"parent": dof_name, "parenttype": "Dropoff Final"},
				fields=["item_code", "item_name", "weight", "uom"],
				order_by="idx asc",
			):
				received = flt(item.weight, 3)
				elsewhere = flt(settled_elsewhere.get(item.item_code, 0), 3)
				here = flt(already_here.get((dof_name, item.item_code), 0), 3)
				remaining = flt(received - elsewhere - here, 3)

				if remaining <= 0:
					continue

				pullable.append({
					"drop_off_final": dof_name,
					"item_code": item.item_code,
					"item_name": item.item_name,
					"uom": item.uom or "Kg",
					"received_qty": received,
					"settled_elsewhere": elsewhere,
					"already_allocated": here,
					"qty": remaining,
				})

		return pullable

	def handle_purchase_invoice(self):
		"""Delete draft PI or block if submitted."""
		if self.purchase_invoice:
			pi_name = self.purchase_invoice
			pi_docstatus = frappe.db.get_value("Purchase Invoice", pi_name, "docstatus")

			if pi_docstatus == 1:
				frappe.throw(
					_("Cannot cancel: Purchase Invoice {0} is submitted. "
					  "Cancel the Purchase Invoice first.").format(pi_name)
				)
			elif pi_docstatus == 0:
				# Clear the link first, then delete — avoids LinkExistsError
				self.db_set("purchase_invoice", None)
				frappe.delete_doc("Purchase Invoice", pi_name,
								 force=True, ignore_permissions=True)
			else:
				self.db_set("purchase_invoice", None)
