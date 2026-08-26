"""List which workspaces (in DB, not just JSON) link to the Dropoff doctype."""

import frappe


def run():
    rows = frappe.db.sql(
        "SELECT name, parent, link_to, label "
        "FROM `tabWorkspace Link` WHERE link_to = 'Dropoff'",
        as_dict=True,
    )
    print(f"Workspace Links pointing at Dropoff: {len(rows)}")
    for r in rows:
        print(f"  workspace={r['parent']:<25}  label={r['label']:<25}  link_to={r['link_to']}")

    # Also list the most recent dropoffs so the user can find their fresh fixtures.
    recent = frappe.db.get_all(
        "Dropoff",
        fields=["name", "supplier_name", "status", "verification_status",
                "license_plate", "creation"],
        order_by="creation desc",
        limit=5,
    )
    print("\nLatest 5 Dropoffs in DB:")
    for r in recent:
        print(f"  {r.name:<25} {r.status:<12} {r.verification_status:<14} {r.license_plate or '-':<25} {r.supplier_name}")

    # And the matching Scrap Weights and Containers.
    sws = frappe.db.get_all(
        "Scrap Weight",
        fields=["name", "dropoff", "docstatus", "is_amended", "amended_from",
                "total_weight", "total_container_count"],
        order_by="creation desc",
        limit=5,
    )
    print("\nLatest 5 Scrap Weights:")
    for r in sws:
        st = {0: "Draft", 1: "Submitted", 2: "Cancelled"}[r.docstatus]
        print(f"  {r.name:<25} dropoff={r.dropoff:<25} {st:<10} amended={r.is_amended} from={r.amended_from or '-'}")
