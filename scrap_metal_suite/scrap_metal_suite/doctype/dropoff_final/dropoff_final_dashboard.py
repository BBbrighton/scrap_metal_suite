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
				"items": ["SMT Purchase Order"],
			},
		],
		"non_standard_fieldnames": {
			"SMT Purchase Order": "drop_off_final",
		},
	}
