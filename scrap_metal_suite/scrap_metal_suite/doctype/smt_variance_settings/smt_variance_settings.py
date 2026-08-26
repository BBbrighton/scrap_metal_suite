# Copyright (c) 2026, X-DESK and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class SMTVarianceSettings(Document):
	def validate(self):
		if flt(self.fulfillment_under_percent) > flt(self.fulfillment_over_percent):
			frappe.throw(
				_("Fulfilled From ({0}%) cannot be greater than Fulfilled Up To ({1}%).").format(
					flt(self.fulfillment_under_percent), flt(self.fulfillment_over_percent)
				)
			)
