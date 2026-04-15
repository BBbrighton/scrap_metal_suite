from frappe import _


def get_data():
	return {
		"fieldname": "smt_po_final",
		"internal_links": {
			"SMT PO": ["allocations", "po"],
			"Dropoff Final": ["drop_off_finals", "drop_off_final"],
		},
		"transactions": [
			{
				"label": _("Settlement"),
				"items": ["SMT PO", "Dropoff Final"],
			},
			{
				"label": _("Accounting"),
				"items": ["Purchase Invoice"],
			},
		],
	}
