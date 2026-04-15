from frappe import _


def get_data():
	return {
		"fieldname": "drop_off_final",
		"internal_links": {
			"Dropoff": ["", "dropoff"],
		},
		"transactions": [
			{
				"label": _("Source"),
				"items": ["Dropoff"],
			},
			{
				"label": _("Settlement"),
				"items": ["SMT PO Final"],
			},
		],
		"non_standard_fieldnames": {
			"SMT PO Final": "drop_off_final",
		},
	}
