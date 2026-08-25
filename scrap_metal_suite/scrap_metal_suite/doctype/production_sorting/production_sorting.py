# Copyright (c) 2026, Scrap Metal Suite and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime, nowtime


class ProductionSorting(Document):
	def validate(self):
		self.calculate_totals()

	def before_insert(self):
		if not self.posting_time:
			self.posting_time = nowtime()
		if not self.operator:
			self.operator = frappe.session.user
		self.populate_source_items()

	def populate_source_items(self):
		"""Copy item_summary from linked Dropoff into source_items"""
		if not self.dropoff:
			return

		if self.source_items:
			return

		dropoff = frappe.get_doc("Dropoff", self.dropoff)

		if hasattr(dropoff, "item_summary"):
			for item in dropoff.item_summary:
				self.append("source_items", {
					"item": item.item,
					"item_name": item.item_name,
					"total_weight": flt(item.total_weight)
				})

	def calculate_totals(self):
		"""Calculate total good weight, unwanted weight, and total"""
		self.total_good_weight = sum(
			flt(item.weight) for item in self.good_items
		)

		self.total_unwanted_weight = sum(
			flt(item.weight) for item in self.unwanted_items
		)

		self.total_weight = self.total_good_weight + self.total_unwanted_weight

	def on_submit(self):
		"""Trigger Dropoff Final update after submission"""
		self._mark_containers_sorted()

		from scrap_metal_suite.api.v1.production import update_dropoff_final
		dropoff_final_name = update_dropoff_final(self.dropoff)
		if dropoff_final_name:
			frappe.msgprint(
				_("Dropoff Final {0} updated").format(dropoff_final_name),
				alert=True
			)

	def on_cancel(self):
		"""Update Dropoff Final when cancelled"""
		self._mark_containers_sorted(undo=True)

		from scrap_metal_suite.api.v1.production import update_dropoff_final
		update_dropoff_final(self.dropoff)

	def _mark_containers_sorted(self, undo=False):
		"""Stamp the bags this sorting consumed.

		Written to `sorting_status` / `sorted_in`, deliberately NOT to the
		container's `status`. `status` records whether the bag physically
		exists and counts toward the received weight: `Dropoff.sync_actual_items`,
		`ScrapWeight`, and finish_weighing_session all sum containers
		`WHERE status = 'Active'`. Moving a sorted bag out of Active would drop
		it from `total_actual_weight`, taking the dropoff variance and
		settlement with it. Sorting does not change what the supplier delivered.

		On cancel the stamp is lifted only where it still points at this
		record, so reopening one sorting cannot clear a bag another sorting
		legitimately owns.
		"""
		names = {row.container for row in (list(self.good_items) + list(self.unwanted_items))
		         if row.get("container")}
		if not names:
			return

		for name in names:
			if undo:
				if frappe.db.get_value("Scrap Weight Container", name, "sorted_in") != self.name:
					continue
				values = {"sorting_status": "Not Sorted", "sorted_in": None}
			else:
				values = {"sorting_status": "Sorted", "sorted_in": self.name}

			frappe.db.set_value("Scrap Weight Container", name, values,
			                    update_modified=False)
