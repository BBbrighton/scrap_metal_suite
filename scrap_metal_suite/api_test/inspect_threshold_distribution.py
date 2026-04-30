"""Show distribution of variance threshold values across all Dropoffs after the
fix_variance_threshold_defaults patch."""

import frappe


def run():
    rows = frappe.db.sql(
        """
        SELECT truck_variance_threshold_percent AS t,
               indicated_variance_threshold_percent AS i,
               COUNT(*) AS n
        FROM `tabDropoff`
        GROUP BY truck_variance_threshold_percent, indicated_variance_threshold_percent
        ORDER BY n DESC
        """,
        as_dict=True,
    )
    print("threshold_distribution (truck, indicated -> count):")
    for r in rows:
        print(f"  truck={r.t!r:<10} indicated={r.i!r:<10} count={r.n}")
