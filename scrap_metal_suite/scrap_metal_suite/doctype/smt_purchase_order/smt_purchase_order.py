# Copyright (c) 2026, X-DESK and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class SMTPurchaseOrder(Document):
	def autoname(self):
		if self.custom_reference:
			self.name = self.custom_reference

	def validate(self):
		self.validate_supplier_consistency()
		self.validate_allocations()
		self.validate_dropoff_coverage()
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
		"""Sum of allocations per item per Dropoff Final must equal the Dropoff Final's qty."""
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

			# Every item in the Dropoff Final must be fully allocated
			for item_code, weight in dof_item_map.items():
				allocated = flt(alloc_map.get(item_code, 0), 3)
				expected = flt(weight, 3)
				if allocated != expected:
					frappe.throw(
						_("Dropoff Final {0}: Item {1} has {2} kg but only {3} kg "
						  "allocated. All items must be fully allocated.").format(
							dof_name, item_code, expected, allocated
						)
					)

			# No allocations for items not in the Dropoff Final
			for item_code in alloc_map:
				if item_code not in dof_item_map:
					frappe.throw(
						_("Allocation references item {0} in Dropoff Final {1}, "
						  "but that item is not in the Dropoff Final").format(
							item_code, dof_name
						)
					)

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
		self.mark_dropoff_finals_settled()
		self.create_draft_purchase_invoice()
		self.db_set("status", "Submitted")

	def update_po_settlement(self):
		"""Increment settled_qty on each PO item row."""
		for row in self.allocations:
			if row.source_type == "PO" and row.po:
				po_doc = frappe.get_doc("SMT Price Lock", row.po)
				po_doc.update_settled_qty(row.po_item_row, flt(row.qty))

	def mark_dropoff_finals_settled(self):
		"""Mark each Dropoff Final as Settled."""
		for dof_row in self.drop_off_finals:
			frappe.db.set_value("Dropoff Final", dof_row.drop_off_final, {
				"status": "Settled",
				"po_final": self.name,
				"settled_by": frappe.session.user,
				"settled_at": now_datetime()
			})

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
		self.revert_dropoff_finals()
		self.db_set("status", "Cancelled")

	def revert_po_settlement(self):
		"""Decrement settled_qty on each PO item row."""
		for row in self.allocations:
			if row.source_type == "PO" and row.po:
				po_doc = frappe.get_doc("SMT Price Lock", row.po)
				po_doc.update_settled_qty(row.po_item_row, -flt(row.qty))

	def revert_dropoff_finals(self):
		"""Revert Dropoff Finals to Unsettled."""
		for dof_row in self.drop_off_finals:
			frappe.db.set_value("Dropoff Final", dof_row.drop_off_final, {
				"status": "Unsettled",
				"po_final": None,
				"settled_by": None,
				"settled_at": None
			})

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
