"""Regression test: the sorting variance threshold Setting must be honoured.

Background — this bug was invisible for months and there was no test to catch it.

`DropoffFinal.calculate_variance` implements a correct three-tier fallback:

    threshold = flt(self.variance_threshold_percent)   # per-document override
    if not threshold:
        threshold = flt(get_single_value(
            "Production Sorting Settings", "variance_threshold_percent")) or 5.0

But `Dropoff Final.variance_threshold_percent` carried `"default": "0.1"` in its
doctype JSON. **Frappe applies field defaults at document creation, before
validate() runs**, so the field was never empty, `flt(0.1)` was always truthy,
and the fallback branch was unreachable. A manager changing the Setting saw it
save successfully and change nothing — no error, no warning.

The fix was deleting the default. These tests guard both halves of it:

  1. the field must NOT regain a default — that alone re-breaks everything
  2. the Setting must actually reach a new document

Test 1 is the important one. It fails the moment someone re-adds the default in
the JSON, which is exactly how this broke the first time.

    bench --site <site> execute scrap_metal_suite.api_test.test_variance_threshold.run
"""

import frappe
from frappe.utils import flt

RESULTS = []


def _check(label, ok, detail=""):
    RESULTS.append((label, bool(ok), detail))


def _test_no_field_default():
    """The doc field must have no default, or the Setting is unreachable."""
    field = frappe.get_meta("Dropoff Final").get_field("variance_threshold_percent")
    default = field.default if field else "<field missing>"
    _check(
        "Dropoff Final.variance_threshold_percent has NO field default",
        not default,
        f"default={default!r} — a default here makes the Settings fallback dead code",
    )


def _test_setting_is_honoured():
    """A new Dropoff Final must adopt the Settings threshold, whatever it is.

    Uses two distinctive values so a hardcoded constant cannot pass by luck.
    Everything runs inside a savepoint and is rolled back.
    """
    src = frappe.db.get_value("Dropoff Final", {}, ["dropoff"], as_dict=True)
    item = frappe.db.get_value("Item", {}, "name")
    if not src or not item:
        _check("Settings threshold reaches a new Dropoff Final", False,
               "no existing Dropoff Final or Item to model from — cannot run")
        return

    for setting, expect_ok in ((0.5, False), (7.5, True)):
        # 1000 kg declared vs 990 kg verified = 1.00% variance.
        # Passes a 7.5% tolerance, fails a 0.5% one.
        frappe.db.savepoint("vt")
        try:
            frappe.db.set_single_value(
                "Production Sorting Settings", "variance_threshold_percent", setting
            )
            doc = frappe.new_doc("Dropoff Final")
            doc.dropoff = src.dropoff
            doc.dropoff_total_weight = 1000
            doc.append("good_items", {"item_code": item, "weight": 990})
            doc.calculate_totals()
            doc.calculate_variance()

            used = flt(doc.variance_threshold_percent)
            _check(
                f"Setting {setting} is adopted as the threshold",
                abs(used - setting) < 0.001,
                f"used={used}",
            )
            _check(
                f"1.00% variance vs {setting}% threshold -> variance_ok={expect_ok}",
                bool(doc.variance_ok) == expect_ok,
                f"variance={doc.variance_percent:.2f}% variance_ok={doc.variance_ok}",
            )
        except Exception as exc:  # noqa: BLE001
            _check(f"Setting {setting} evaluated", False, f"{type(exc).__name__}: {exc}")
        finally:
            frappe.db.rollback(save_point="vt")


def run():
    RESULTS.clear()
    _test_no_field_default()
    _test_setting_is_honoured()

    print("=" * 70)
    print("VARIANCE THRESHOLD REGRESSION TEST")
    print("=" * 70)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = len(RESULTS) - passed
    for label, ok, detail in RESULTS:
        marker = "OK " if ok else "X  "
        suffix = f"  ({detail})" if detail else ""
        print(f"  {marker}{label}{suffix}")
    print("-" * 70)
    print(f"  {passed}/{len(RESULTS)} checks passed{', ' + str(failed) + ' FAILED' if failed else ''}")
    print("=" * 70)
    return {"passed": passed, "failed": failed}
