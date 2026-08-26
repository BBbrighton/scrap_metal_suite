"""Diagnostic for two issues raised by user:
  1. CTN-2026-00023 not searchable via dropoff search bar.
  2. _TEST_SWC_Scale-01 stuck `in_use=1` even after its session was closed.
"""

import frappe


def run():
    print("=" * 78)
    print("ISSUE 1: CTN-2026-00023")
    print("=" * 78)
    exists = frappe.db.exists("Scrap Weight Container", "CTN-2026-00023")
    print(f"  Exists in DB: {exists}")
    if exists:
        doc = frappe.db.get_value(
            "Scrap Weight Container", "CTN-2026-00023",
            ["name", "dropoff", "status", "item_code", "net_weight",
             "container_no", "is_reweight", "voided_at"],
            as_dict=True,
        )
        print(f"  Doc: {doc}")
        # Try the API path used by openContainerActions.
        try:
            from scrap_metal_suite.api.v1.dropoff import get_container
            res = get_container("CTN-2026-00023")
            print(f"  get_container() OK: status={res.get('status')} dropoff={res.get('dropoff')}")
        except Exception as e:
            print(f"  get_container() FAILED: {type(e).__name__}: {e}")

    print()
    print("=" * 78)
    print("ISSUE 2: _TEST_SWC_Scale-01 stuck in_use")
    print("=" * 78)
    scale = frappe.db.get_value(
        "Scale", "_TEST_SWC_Scale-01",
        ["name", "in_use", "in_use_by_session"],
        as_dict=True,
    )
    print(f"  Scale: {scale}")
    sess_name = scale.get("in_use_by_session") if scale else None
    if sess_name:
        sess = frappe.db.get_value(
            "POS Session", sess_name,
            ["name", "operator", "status", "closing_time", "scale"],
            as_dict=True,
        )
        if sess is None:
            print(f"  Session {sess_name}: DELETED")
        else:
            print(f"  Session: {sess}")

    # Sweep ALL stuck scales again.
    print()
    print("All scales with in_use=1 + session not Open or missing:")
    in_use = frappe.get_all(
        "Scale",
        filters={"in_use": 1},
        fields=["name", "in_use_by_session"],
    )
    for sc in in_use:
        sn = sc.get("in_use_by_session")
        if not sn:
            print(f"  - {sc.name}  (no session linked)")
            continue
        if not frappe.db.exists("POS Session", sn):
            print(f"  - {sc.name}  -> {sn}  DELETED")
            continue
        sst = frappe.db.get_value("POS Session", sn, "status")
        if sst != "Open":
            print(f"  - {sc.name}  -> {sn}  status={sst}")
