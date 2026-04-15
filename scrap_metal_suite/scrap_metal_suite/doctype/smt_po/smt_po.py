# Copyright (c) 2026, X-DESK and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class SMTPO(Document):
	def validate(self):
		self.validate_items()
		self.calculate_totals()

	def validate_items(self):
		if not self.items:
			frappe.throw(_("At least one item row is required"))
		for row in self.items:
			if flt(row.po_qty) <= 0:
				frappe.throw(_("Row {0}: Qty must be greater than 0").format(row.idx))
			if flt(row.po_rate) <= 0:
				frappe.throw(_("Row {0}: Rate must be greater than 0").format(row.idx))
			row.po_amount = flt(flt(row.po_qty) * flt(row.po_rate), 2)
			row.remaining_qty = flt(row.po_qty) - flt(row.settled_qty)

	def calculate_totals(self):
		self.total_po_value = flt(sum(flt(r.po_amount) for r in self.items), 2)
		self.total_settled_value = flt(
			sum(flt(r.settled_qty) * flt(r.po_rate) for r in self.items), 2
		)

	def on_submit(self):
		self.db_set("status", "Open")
		self.create_pos_order()

	def create_pos_order(self):
		"""Auto-create a POS Order from this PO."""
		pos_order = frappe.new_doc("POS Order")
		pos_order.supplier = self.supplier
		pos_order.order_date = self.po_date
		pos_order.smt_po = self.name
		pos_order.status = "Pending"

		for row in self.items:
			pos_order.append("order_items", {
				"item_code": row.item_code,
				"item_name": row.item_name,
				"uom": row.uom or "Kg",
				"weight": row.po_qty,
			})

		pos_order.insert(ignore_permissions=True)
		frappe.db.commit()
		frappe.msgprint(
			_("POS Order {0} created").format(
				frappe.utils.get_link_to_form("POS Order", pos_order.name)
			),
			alert=True,
			indicator="green"
		)

	def on_cancel(self):
		for row in self.items:
			if flt(row.settled_qty) > 0:
				frappe.throw(
					_("Cannot cancel: Row {0} ({1}) has settled quantity {2}. "
					  "Cancel related PO Finals first.").format(
						row.idx, row.item_code, row.settled_qty
					)
				)
		self.cancel_pos_orders()
		self.db_set("status", "Cancelled")

	def cancel_pos_orders(self):
		"""Cancel any POS Orders linked to this PO."""
		pos_orders = frappe.get_all(
			"POS Order",
			filters={"smt_po": self.name},
			pluck="name"
		)
		for order_name in pos_orders:
			order = frappe.get_doc("POS Order", order_name)
			if order.status == "Pending":
				order.status = "Cancelled"
				order.save(ignore_permissions=True)

	def update_settled_qty(self, item_row_name, delta_qty):
		"""Called by PO Final controller. Atomically updates settled/remaining qty."""
		# Atomic increment to prevent race conditions
		# Note: In MySQL, SET clauses are evaluated left-to-right, so
		# settled_qty in the remaining_qty expression already has the new value.
		frappe.db.sql("""
			UPDATE `tabSMT PO Item`
			SET settled_qty = settled_qty + %s,
			    remaining_qty = po_qty - settled_qty
			WHERE name = %s
		""", (delta_qty, item_row_name))

		# Post-write validation: settled_qty must not exceed po_qty
		row = frappe.db.get_value(
			"SMT PO Item", item_row_name,
			["settled_qty", "po_qty"], as_dict=True
		)
		if flt(row.settled_qty) > flt(row.po_qty):
			frappe.throw(
				_("Over-allocation: settled qty {0} exceeds PO qty {1} for {2}").format(
					row.settled_qty, row.po_qty, item_row_name
				)
			)

		self.recompute_status()

	def recompute_status(self):
		"""Recompute PO status based on settlement state of all items."""
		self.reload()
		all_settled = all(flt(r.remaining_qty, 3) <= 0 for r in self.items)
		any_settled = any(flt(r.settled_qty, 3) > 0 for r in self.items)

		if all_settled:
			status = "Fully Settled"
		elif any_settled:
			status = "Partially Settled"
		else:
			status = "Open"

		self.db_set("status", status)
