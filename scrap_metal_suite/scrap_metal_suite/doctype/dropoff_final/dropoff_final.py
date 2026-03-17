# Copyright (c) 2026, X-DESK and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class DropoffFinal(Document):
	def before_save(self):
		"""Calculate all fields before saving"""
		self.aggregate_from_sortings()
		self.calculate_totals()
		self.calculate_variance()
		self.set_verification_status()
		self.auto_complete_if_done()

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

		# Dictionaries to aggregate by item_code
		good_items_dict = {}
		unwanted_items_dict = {}

		# Aggregate from each sorting session
		for sorting_rec in sortings:
			sorting = frappe.get_doc("Production Sorting", sorting_rec.name)

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

		self.variance_ok = self.variance_percent <= flt(self.variance_threshold_percent)

	def set_verification_status(self):
		"""Set verification status based on variance"""
		if not self.good_items and not self.unwanted_items:
			self.verification_status = "Pending"
		elif self.variance_ok:
			self.verification_status = "Verified"
		else:
			self.verification_status = "Needs Review"

	def auto_complete_if_done(self):
		"""Auto-complete if all items sorted and variance OK"""
		if self.status == "Completed":
			return  # Already completed

		# Check if we have items and variance is OK
		if (self.good_items or self.unwanted_items) and self.variance_ok:
			# Check if sorted weight is close to dropoff weight (within 0.1%)
			if flt(self.total_verified_weight) >= flt(self.dropoff_total_weight) * 0.999:
				self.status = "Completed"
				self.verification_status = "Verified"
				self.completed_at = now_datetime()
				self.completed_by = frappe.session.user
			else:
				self.status = "In Progress"
		elif self.good_items or self.unwanted_items:
			self.status = "In Progress"
