from frappe import _


def get_data():
	return {
		"fieldname": "smt_price_lock",
		"non_standard_fieldnames": {
			"SMT Purchase Order": "po",
		},
		"internal_links": {},
		"transactions": [
			{
				"label": _("Orders"),
				"items": ["POS Order"],
			},
			{
				"label": _("Settlement"),
				"items": ["SMT Purchase Order"],
			},
		],
		"internal_and_external_links": {
			"SMT Purchase Order": ["po", "allocations"],
		},
	}
