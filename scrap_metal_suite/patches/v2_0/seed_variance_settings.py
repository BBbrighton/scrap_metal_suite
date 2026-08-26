"""Seed `SMT Variance Settings` and adopt whatever was configured before.

Tolerances used to live in four places and one of them was a literal in
`dropoff.py`. This patch creates the Single and carries across any value a
manager had actually set, so nobody's configuration is quietly reset.

Two of the old sources were never configured on this site and read 0.0. That
zero is *not* adopted: `dropoff_final.py` used to end its lookup with `or 5.0`,
so an unset Single meant sorting was really being graded at 5% while the guides
promised 0.1%. Carrying the 0.0 forward would flip that to "exact match
required" and strand every future sorting — the opposite error, equally wrong.
Where the old value is missing or zero, the documented default is used instead.

Existing Dropoff and Dropoff Final records are deliberately left alone. They
store the threshold they were judged against, and re-grading them here could
turn a past Verified into Needs Review with no human involved.
"""

import frappe
from frappe.utils import flt

from scrap_metal_suite.utils.variance import FALLBACKS

# new field <- (old single, old field)
ADOPT = {
	"sorting_variance_threshold_percent": ("Production Sorting Settings", "variance_threshold_percent"),
	"container_weight_variance_threshold_pct": ("Dropoff Container Settings", "weight_variance_threshold_pct"),
}


def execute():
	if not frappe.db.exists("DocType", "SMT Variance Settings"):
		frappe.reload_doc("scrap_metal_suite", "doctype", "smt_variance_settings")

	settings = frappe.get_single("SMT Variance Settings")

	for field, default in FALLBACKS.items():
		adopted = None
		source = "default"

		if field in ADOPT:
			old_dt, old_field = ADOPT[field]
			if frappe.db.exists("DocType", old_dt):
				try:
					old = frappe.db.get_single_value(old_dt, old_field)
				except Exception:
					old = None
				# Zero here means "never configured", not "require exact match" —
				# see the module docstring.
				if old is not None and flt(old) > 0:
					adopted = flt(old)
					source = f"{old_dt}.{old_field}"

		settings.set(field, adopted if adopted is not None else default)
		print(f"  SMT Variance Settings.{field} = {settings.get(field)}  (from {source})")

	settings.flags.ignore_permissions = True
	settings.save()
	frappe.db.commit()
	print("SMT Variance Settings seeded.")
