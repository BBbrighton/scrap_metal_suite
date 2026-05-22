"""Inspect the reweigh chain for the user's DO-TEST3-260501-1 bags so we
can tell whether 00025 was Voided directly or Reweighed-into 00026."""

import frappe


def run():
    rows = frappe.get_all(
        "Scrap Weight Container",
        filters={"dropoff": "DO-TEST3-260501-1"},
        fields=[
            "name", "container_no", "status", "is_reweight",
            "reweighed_from", "superseded_by", "voided_reason",
            "voided_at", "creation", "item_code",
        ],
        order_by="creation asc",
    )
    print(f"Containers on DO-TEST3-260501-1 ({len(rows)}):\n")
    for r in rows:
        print(
            f"  {r.name}  no={r.container_no}  status={r.status:<8}  "
            f"item={r.item_code}  is_reweight={r.is_reweight}  "
            f"reweighed_from={r.reweighed_from}  "
            f"superseded_by={r.superseded_by}  "
            f"voided_reason={r.voided_reason!r}"
        )
    print()

    # Also check MAX(container_no) right now (what next fresh bag would get).
    max_no = frappe.db.sql(
        "SELECT MAX(container_no) FROM `tabScrap Weight Container` WHERE dropoff=%s",
        ("DO-TEST3-260501-1",),
    )[0][0]
    print(f"Current MAX(container_no) on dropoff: {max_no}")
    print(f"Next FRESH bag would get: {(max_no or 0) + 1}")
