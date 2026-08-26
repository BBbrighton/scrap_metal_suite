"""Simulate the OLD vs NEW JS threshold logic against DO-260427-00004's saved
values. Confirms the *100 fix correctly flags the 23% variance as breach.
"""

import frappe


def _classify(variance_percent: float, threshold: float) -> str:
    if variance_percent <= threshold:
        return "OK / within tolerance"
    if variance_percent <= threshold * 2:
        return "WARNING"
    return "ERROR / exceeds tolerance"


def run():
    name = "DO-260427-00004"
    d = frappe.get_doc("Dropoff", name)

    truck_pct = d.truck_variance_percent or 0
    truck_thresh_saved = d.truck_variance_threshold_percent or 0.1
    indicated_pct = d.indicated_variance_percent or 0
    indicated_thresh_saved = d.indicated_variance_threshold_percent or 0.1

    # OLD (buggy) JS: threshold = (saved || 0.001) * 100
    old_truck = (truck_thresh_saved or 0.001) * 100
    old_indicated = (indicated_thresh_saved or 0.001) * 100
    # NEW (fixed) JS: threshold = saved || 0.1
    new_truck = truck_thresh_saved or 0.1
    new_indicated = indicated_thresh_saved or 0.1

    print(f"Dropoff:                 {name}")
    print(f"truck_variance_percent:  {truck_pct}%")
    print(f"truck_threshold_saved:   {truck_thresh_saved}%")
    print(f"indicated_variance_pct:  {indicated_pct}%")
    print(f"indicated_thresh_saved:  {indicated_thresh_saved}%")
    print()
    print("Truck variance vs threshold:")
    print(f"  OLD JS (threshold = {old_truck:>6.2f}%):  {_classify(truck_pct, old_truck)}")
    print(f"  NEW JS (threshold = {new_truck:>6.2f}%):  {_classify(truck_pct, new_truck)}")
    print(f"  SERVER (truck_variance_ok):           {'OK' if d.truck_variance_ok else 'NOT OK'}")
    print()
    print("Indicated variance vs threshold:")
    print(f"  OLD JS (threshold = {old_indicated:>6.2f}%):  {_classify(indicated_pct, old_indicated)}")
    print(f"  NEW JS (threshold = {new_indicated:>6.2f}%):  {_classify(indicated_pct, new_indicated)}")
    print(f"  SERVER (indicated_variance_ok):       {'OK' if d.indicated_variance_ok else 'NOT OK'}")
    print()
    server_truck_ok = bool(d.truck_variance_ok)
    server_indicated_ok = bool(d.indicated_variance_ok)
    new_truck_ok = truck_pct <= new_truck
    new_indicated_ok = indicated_pct <= new_indicated
    if server_truck_ok == new_truck_ok and server_indicated_ok == new_indicated_ok:
        print("PASS: NEW JS classification now agrees with server-side truck_variance_ok / indicated_variance_ok")
    else:
        print("FAIL: NEW JS still disagrees with server")
