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
		from scrap_metal_suite.api.v1.production import update_dropoff_final
		dropoff_final_name = update_dropoff_final(self.dropoff)
		if dropoff_final_name:
			frappe.msgprint(
				_("Dropoff Final {0} updated").format(dropoff_final_name),
				alert=True
			)

	def on_cancel(self):
		"""Update Dropoff Final when cancelled"""
		from scrap_metal_suite.api.v1.production import update_dropoff_final
		update_dropoff_final(self.dropoff)
