from frappe import _


def get_data():
	return {
		"fieldname": "smt_po",
		"non_standard_fieldnames": {
			"SMT PO Final": "po",
		},
		"internal_links": {},
		"transactions": [
			{
				"label": _("Orders"),
				"items": ["POS Order"],
			},
			{
				"label": _("Settlement"),
				"items": ["SMT PO Final"],
			},
		],
		"internal_and_external_links": {
			"SMT PO Final": ["po", "allocations"],
		},
	}
