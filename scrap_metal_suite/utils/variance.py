"""One place to read the yard's tolerances.

Every threshold used to live somewhere different — two on the Dropoff itself
with no global at all, one on `Production Sorting Settings`, one on `Dropoff
Container Settings`, and the fulfilment bands hardcoded in `dropoff.py`. A
manager could not change most of them without a developer.

`SMT Variance Settings` is now the single source. Callers ask for a key and
get a number; nobody reads the Single directly.

**Zero is a real answer, but "never configured" is not.** A manager who types
`0` means "require an exact match", and that is honoured. A Single that was
never written must fall back to the documented default instead.

Telling those two apart needs care: `frappe.db.get_single_value` returns
`0.0` — not `None` — for a numeric field with no row in `tabSingles`, so a
plain `is None` check cannot see the difference. `get_singles_dict` only
returns fields that actually have a row, so membership in it is the honest
test. This matters: `dropoff_final.py` used to end its lookup with `or 5.0`,
so an unconfigured Single silently graded sorting at 5% while the guides
promised 0.1%.
"""

import frappe
from frappe.utils import flt

SETTINGS = "SMT Variance Settings"

# Used only when the field has never been written — not when a manager has
# deliberately set a value, including zero.
FALLBACKS = {
	"truck_variance_threshold_percent": 0.1,
	"indicated_variance_threshold_percent": 0.1,
	"sorting_variance_threshold_percent": 0.1,
	"container_weight_variance_threshold_pct": 0.1,
	"fulfillment_under_percent": 98.0,
	"fulfillment_over_percent": 102.0,
}


def _configured():
	"""Fields that actually have a row in `tabSingles`, as a dict.

	Returns an empty dict when the doctype does not exist yet, which happens
	during install and in patches that run before this one.
	"""
	try:
		return frappe.db.get_singles_dict(SETTINGS) or {}
	except Exception:
		return {}


def get_threshold(key):
	"""Return one tolerance.

	Args:
		key (str): a fieldname from `SMT Variance Settings`.

	Returns:
		float: the configured value — including a deliberate ``0`` — or the
		documented default when that field was never configured.
	"""
	if key not in FALLBACKS:
		raise KeyError(f"unknown variance key {key!r}; expected one of {sorted(FALLBACKS)}")

	configured = _configured()
	if key not in configured or configured[key] in (None, ""):
		return FALLBACKS[key]
	return flt(configured[key])


def get_all_thresholds():
	"""Every tolerance at once, for screens that display them together."""
	configured = _configured()
	return {
		key: (flt(configured[key]) if key in configured and configured[key] not in (None, "") else default)
		for key, default in FALLBACKS.items()
	}
