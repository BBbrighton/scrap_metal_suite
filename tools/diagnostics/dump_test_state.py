"""One-shot diagnostic: dump all test fixtures left in the DB after an
end-to-end run with cleanup skipped. Useful for verifying what the test
suite actually persisted before reaching for `bench mariadb`.

Run:
  bench --site metal execute scrap_metal_suite.api_test.dump_test_state.run
"""

import frappe


def run():
    prefixes = ["_TEST_UI_", "_TEST_DESK_", "_TEST_FWS_", "_TEST_CTNWF_", "_TEST_PR_"]

    def by_prefix(dt, field, fields):
        rows = []
        for p in prefixes:
            rows += frappe.get_all(
                dt, filters={field: ["like", f"%{p}%"]}, fields=fields
            )
        return rows

    print("=" * 78)
    print("END-TO-END TEST DB STATE (cleanup skipped)")
    print("=" * 78)

    # Suppliers
    sups = by_prefix("Supplier", "supplier_name", ["name", "short_code"])
    print(f"\nSuppliers ({len(sups)}):")
    for s in sups:
        print(f"  - {s.name}  short_code={s.short_code}")

    # Dropoffs (filter by license_plate prefix)
    dos = []
    for p in prefixes:
        dos += frappe.get_all(
            "Dropoff",
            filters={"license_plate": ["like", f"%{p}%"]},
            fields=[
                "name", "status", "license_plate", "supplier",
                "container_count", "total_actual_weight", "verification_status",
            ],
            order_by="creation desc",
        )
    # also non-prefixed test dropoffs (DO-TEST-, DO-TEST2-, etc.) named via short_code
    extra = frappe.get_all(
        "Dropoff",
        filters={"name": ["like", "DO-TEST%"]},
        fields=[
            "name", "status", "license_plate", "supplier",
            "container_count", "total_actual_weight", "verification_status",
        ],
        order_by="creation desc",
    )
    seen = {d.name for d in dos}
    for e in extra:
        if e.name not in seen:
            dos.append(e)
            seen.add(e.name)

    print(f"\nDropoffs ({len(dos)}):")
    for d in dos:
        print(
            f"  - {d.name}  status={d.status}  bags={d.container_count}  "
            f"net={d.total_actual_weight}kg  verif={d.verification_status}  "
            f"plate={d.license_plate}"
        )

    # Containers attached to those dropoffs
    do_names = [d.name for d in dos]
    if do_names:
        rows = frappe.db.sql(
            """
            SELECT c.name, c.dropoff, c.container_no, c.item_code,
                   c.net_weight, c.status,
                   (SELECT COUNT(*) FROM `tabWeight Photo` p
                      WHERE p.parent=c.name
                        AND p.parenttype='Scrap Weight Container') AS photos
            FROM `tabScrap Weight Container` c
            WHERE c.dropoff IN %(dos)s
            ORDER BY c.dropoff, c.container_no
            """,
            {"dos": do_names},
            as_dict=True,
        )
    else:
        rows = []
    print(f"\nContainers ({len(rows)}):")
    for c in rows:
        print(
            f"  - {c.name}  drop={c.dropoff}  no={c.container_no}  "
            f"{c.item_code}  {c.net_weight}kg  {c.status}  photos={c.photos}"
        )

    # Scrap Weights for those dropoffs
    if do_names:
        sws = frappe.get_all(
            "Scrap Weight",
            filters={"dropoff": ["in", do_names]},
            fields=["name", "dropoff", "docstatus", "is_amended", "amended_from"],
            order_by="creation",
        )
    else:
        sws = []
    print(f"\nScrap Weights ({len(sws)}):")
    for s in sws:
        ds_label = {0: "Draft", 1: "Submitted", 2: "Cancelled"}.get(s.docstatus, "?")
        amend = f" AMEND_OF {s.amended_from}" if s.is_amended else ""
        print(f"  - {s.name}  drop={s.dropoff}  {ds_label}{amend}")

    # SMT Price Locks + POS Orders linked to test suppliers
    sup_names = [s.name for s in sups]
    if sup_names:
        pls = frappe.get_all(
            "SMT Price Lock",
            filters={"supplier": ["in", sup_names]},
            fields=["name", "docstatus", "supplier"],
        )
        pos = frappe.get_all(
            "POS Order",
            filters={"supplier": ["in", sup_names]},
            fields=["name", "docstatus", "supplier"],
        )
    else:
        pls = []
        pos = []
    print(f"\nSMT Price Locks ({len(pls)}):")
    for p in pls:
        ds_label = {0: "Draft", 1: "Submitted", 2: "Cancelled"}.get(p.docstatus, "?")
        print(f"  - {p.name}  {ds_label}  supplier={p.supplier}")
    print(f"\nPOS Orders ({len(pos)}):")
    for p in pos:
        ds_label = {0: "Draft", 1: "Submitted", 2: "Cancelled"}.get(p.docstatus, "?")
        print(f"  - {p.name}  {ds_label}  supplier={p.supplier}")

    # Open admin sessions
    sess = frappe.get_all(
        "POS Session",
        filters={"operator": "Administrator", "status": "Open"},
        fields=["name", "scale", "operator", "status"],
    )
    print(f"\nOpen Admin POS Sessions ({len(sess)}):")
    for s in sess:
        print(f"  - {s.name}  scale={s.scale}")

    # All test scales + their lock state
    scales = by_prefix(
        "Scale", "scale_name",
        ["name", "usage_type", "in_use", "in_use_by_session"],
    )
    print(f"\nTest Scales ({len(scales)}):")
    for s in scales:
        print(
            f"  - {s.name}  usage={s.usage_type}  "
            f"in_use={s.in_use}  by={s.in_use_by_session}"
        )

    # Stuck-scale sweep (in_use=1 with bad/missing session)
    in_use = frappe.get_all(
        "Scale",
        filters={"in_use": 1},
        fields=["name", "in_use_by_session"],
    )
    stuck = []
    for sc in in_use:
        sess_name = sc.get("in_use_by_session")
        if not sess_name:
            stuck.append((sc.name, "no session linked"))
        elif not frappe.db.exists("POS Session", sess_name):
            stuck.append((sc.name, f"session {sess_name} deleted"))
        else:
            sst = frappe.db.get_value("POS Session", sess_name, "status")
            if sst != "Open":
                stuck.append((sc.name, f"session {sess_name} status={sst}"))
    print(f"\nStuck Scales ({len(stuck)}):")
    for n, reason in stuck:
        print(f"  - {n}  ({reason})")

    print("=" * 78)
    return {
        "suppliers": len(sups),
        "dropoffs": len(dos),
        "containers": len(rows),
        "scrap_weights": len(sws),
        "price_locks": len(pls),
        "pos_orders": len(pos),
        "open_sessions": len(sess),
        "test_scales": len(scales),
        "stuck_scales": len(stuck),
    }
