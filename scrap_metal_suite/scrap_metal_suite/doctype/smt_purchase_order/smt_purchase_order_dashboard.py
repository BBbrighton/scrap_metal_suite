from frappe import _


def get_data():
	return {
		"fieldname": "smt_purchase_order",
		"internal_links": {
			"SMT Price Lock": ["allocations", "po"],
			"Dropoff Final": ["drop_off_finals", "drop_off_final"],
			"Purchase Invoice": ["", "purchase_invoice"],
		},
		"transactions": [
			{
				"label": _("Settlement"),
				"items": ["SMT Price Lock", "Dropoff Final"],
			},
			{
				"label": _("Accounting"),
				"items": ["Purchase Invoice"],
			},
		],
	}
