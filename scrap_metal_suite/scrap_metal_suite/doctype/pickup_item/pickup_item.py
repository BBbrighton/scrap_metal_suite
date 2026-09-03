# Copyright (c) 2026, SMT and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class PickupItem(Document):
	"""One line of what a customer is collecting.

	Field names mirror `Delivery Note Item` (item_code, qty, uom, warehouse,
	rate) so that turning a Pickup into a Delivery Note, once stock is tracked,
	is a mapping rather than a re-entry.
	"""

	pass
