# Copyright (c) 2026, SMT and contributors
# For license information, please see license.txt

"""A truck collecting goods - the mirror of a Dropoff.

The buy side and the sale side use the same weighbridge but in opposite order:

    Dropoff   arrives LOADED  -> gross, unload, -> tare (empty)
    Pickup    arrives EMPTY   -> tare,  load,   -> gross (loaded)

so on a Pickup the *second* weighing is the heavy one, and `net_weight` is what
physically left the site.

Quantity is agreed in advance and typed in, not discovered by weighing - that is
the other difference from a Dropoff, where the containers tell you what you got.
The weighbridge is therefore a *check* here rather than the source of truth: the
agreed item weights and the measured net should agree within a tolerance, and a
Pickup that drifts outside it is flagged rather than blocked.

Nothing here touches stock. Until the warehouse module exists a Pickup is a gate
record, and it does not pretend otherwise. `sales_order` and `delivery_note` are
present but unused, so that connecting them later is a mapping rather than a
migration.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime

from scrap_metal_suite.utils.variance import get_threshold


class Pickup(Document):
	def validate(self):
		self.calculate_agreed_total()
		self.calculate_net_weight()
		self.validate_gross_greater_than_tare()
		self.evaluate_variance()

	# ------------------------------------------------------------------ items

	def calculate_agreed_total(self):
		"""Sum the agreed lines. Sold by weight, so qty is already kilograms."""
		self.total_agreed_weight = sum(flt(r.qty) for r in (self.items or []))

	# ---------------------------------------------------------------- weights

	def calculate_net_weight(self):
		"""What left the site: loaded on the way out, minus empty on the way in."""
		if self.gross_weight and self.tare_weight:
			self.net_weight = flt(self.gross_weight) - flt(self.tare_weight)
		else:
			self.net_weight = None

	def validate_gross_greater_than_tare(self):
		"""A truck that leaves lighter than it arrived has a data problem.

		Blocked rather than flagged: it makes `net_weight` negative, and every
		number downstream of it meaningless.
		"""
		if not (self.gross_weight and self.tare_weight):
			return
		if flt(self.gross_weight) <= flt(self.tare_weight):
			frappe.throw(
				_("Gross weight ({0} kg) must be greater than tare weight ({1} kg). "
				  "The truck leaves loaded, so it must weigh more on the way out.").format(
					flt(self.gross_weight), flt(self.tare_weight))
			)

	# --------------------------------------------------------------- variance

	def evaluate_variance(self):
		"""Compare what was agreed against what the weighbridge measured.

		Mirrors the buy side, which checks sorted containers against the truck
		net. Sets `verification_status`; never blocks - a truck at the gate is
		not the place to settle a paperwork discrepancy.
		"""
		agreed = flt(self.total_agreed_weight)
		measured = flt(self.net_weight) if self.net_weight else 0.0

		if not agreed or not measured:
			self.weight_variance_percent = None
			self.verification_status = "Pending"
			return

		self.weight_variance_percent = abs(measured - agreed) / agreed * 100.0
		threshold = get_threshold("pickup_variance_threshold_percent")
		self.verification_status = (
			"Verified" if self.weight_variance_percent <= threshold else "Needs Review"
		)

	# ----------------------------------------------------------- status moves

	def mark_weighed_in(self, weight, scale=None, operator=None):
		"""Record the empty truck arriving."""
		self.tare_weight = flt(weight)
		self.tare_weight_time = now_datetime()
		self.tare_weight_scale = scale
		self.tare_weight_operator = operator or frappe.session.user
		if self.status == "Scheduled":
			self.status = "In Progress"

	def mark_weighed_out(self, weight, scale=None, operator=None):
		"""Record the loaded truck leaving."""
		self.gross_weight = flt(weight)
		self.gross_weight_time = now_datetime()
		self.gross_weight_scale = scale
		self.gross_weight_operator = operator or frappe.session.user
