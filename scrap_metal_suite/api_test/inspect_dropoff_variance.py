import frappe


def run():
    name = "DO-260427-00004"
    if not frappe.db.exists("Dropoff", name):
        print(f"missing: {name}")
        return
    d = frappe.get_doc("Dropoff", name)
    rows = [
        ("status", d.status),
        ("total_truck_weight", d.total_truck_weight),
        ("total_scrap_weight", d.total_scrap_weight),
        ("total_actual_weight", getattr(d, "total_actual_weight", None)),
        ("total_indicated_weight", d.total_indicated_weight),
        ("truck_variance", d.truck_variance),
        ("truck_variance_percent", d.truck_variance_percent),
        ("truck_variance_threshold_percent", d.truck_variance_threshold_percent),
        ("truck_variance_ok", d.truck_variance_ok),
        ("indicated_variance", d.indicated_variance),
        ("indicated_variance_percent", d.indicated_variance_percent),
        ("indicated_variance_threshold_percent", d.indicated_variance_threshold_percent),
        ("indicated_variance_ok", d.indicated_variance_ok),
    ]
    for k, v in rows:
        print(f"  {k:42s} = {v!r}")
