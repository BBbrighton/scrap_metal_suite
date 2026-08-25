"""
Fix Dropoff variance-threshold defaults.

Background
----------
`Dropoff.truck_variance_threshold_percent` and `indicated_variance_threshold_percent`
are Frappe `Percent` fields — stored as the percent number directly (e.g. `1.0`
means 1%, matching how the controller compares it).

The original schema declared `default: "0.001"` with description "default 0.1%",
i.e. the author was treating the value as a fraction (0.001 = 0.1%) but the
field is read as a literal percent everywhere — so `0.001` was effectively
`0.001%`, an absurdly tight near-zero threshold that flags any non-zero variance
as breach.

Fix
---
- Schema defaults updated `0.001` → `0.1` (this patch only updates DB rows)
- Controller fallbacks updated `or 0.001` → `or 0.1`
- This patch backfills existing Dropoffs whose threshold is NULL, 0, or 0.001
  to the new default 0.1, then re-runs `calculate_totals` so
  `truck_variance_ok` / `indicated_variance_ok` get re-evaluated against the
  corrected threshold.

Idempotent: only touches rows where the threshold matches the stale-default
shapes. Safe to re-run.
"""

import frappe
from frappe.utils import flt


STALE_VALUES = (None, 0, 0.0, 0.001)
NEW_DEFAULT = 0.1


def execute():
    rows = frappe.db.sql(
        """
        SELECT name, truck_variance_threshold_percent, indicated_variance_threshold_percent,
               total_truck_weight, total_actual_weight, total_indicated_weight,
               truck_variance_ok, indicated_variance_ok
        FROM `tabDropoff`
        """,
        as_dict=True,
    )

    if not rows:
        print("fix_variance_threshold_defaults: no dropoffs to scan")
        return

    updated = 0
    recomputed = 0
    failed = 0
    for row in rows:
        updates: dict[str, float] = {}

        # Only touch rows that took a stale-default shape.
        if flt(row.truck_variance_threshold_percent) in (0, 0.001) or row.truck_variance_threshold_percent is None:
            updates["truck_variance_threshold_percent"] = NEW_DEFAULT

        if flt(row.indicated_variance_threshold_percent) in (0, 0.001) or row.indicated_variance_threshold_percent is None:
            updates["indicated_variance_threshold_percent"] = NEW_DEFAULT

        if not updates:
            continue

        for fieldname, value in updates.items():
            frappe.db.set_value(
                "Dropoff", row.name, fieldname, value, update_modified=False
            )
        updated += 1

        # Recompute variance flags so existing dropoffs reflect the correct
        # ok/breach verdict against the new threshold. Skip rows with no
        # weight data (nothing to recompute).
        if row.total_truck_weight or row.total_indicated_weight:
            try:
                doc = frappe.get_doc("Dropoff", row.name)
                # calculate_totals() computes the truck variance AND calls
                # calculate_indicated_variance(). There is no
                # calculate_truck_variance() on Dropoff — calling it raised
                # AttributeError into the except below, so this patch reported
                # success while recomputing nothing.
                doc.calculate_totals()
                # Persist just the recomputed flags + percentages without
                # re-running full save() (avoids re-validating the whole doc
                # on stale data).
                for f in (
                    "truck_variance",
                    "truck_variance_percent",
                    "truck_variance_ok",
                    "indicated_variance",
                    "indicated_variance_percent",
                    "indicated_variance_ok",
                    "total_scrap_weight",
                ):
                    frappe.db.set_value(
                        "Dropoff",
                        row.name,
                        f,
                        getattr(doc, f),
                        update_modified=False,
                    )
                recomputed += 1
            except Exception:
                failed += 1
                frappe.log_error(
                    frappe.get_traceback(),
                    f"fix_variance_threshold_defaults: recompute failed for {row.name}",
                )

    frappe.db.commit()
    print(
        f"fix_variance_threshold_defaults: updated thresholds on {updated} of {len(rows)} dropoffs; "
        f"recomputed variance flags on {recomputed}"
    )
    # Every recompute failing still left the counters looking plausible and the
    # patch "successful" — the only signal was a zero that nobody reads. Say it
    # loudly instead.
    if failed:
        print(
            f"  WARNING: {failed} dropoff(s) failed to recompute and kept their "
            f"previous variance verdict against the NEW threshold. See Error Log "
            f"entries titled 'fix_variance_threshold_defaults: recompute failed'."
        )
