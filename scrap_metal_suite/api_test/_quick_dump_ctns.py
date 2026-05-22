import frappe


def run():
    rows = frappe.get_all(
        "Scrap Weight Container",
        filters={
            "dropoff": [
                "in",
                [
                    "DO-TEST2-260501-4",
                    "DO-TEST-260501-53",
                    "DO-TEST3-260501-1",
                    "DO-TESTPR-260501-1",
                    "DO-260501-00001",
                ],
            ]
        },
        fields=["name", "dropoff", "container_no", "item_code", "net_weight", "status"],
        order_by="dropoff, container_no",
    )
    print(f"\nContainers across all test dropoffs ({len(rows)}):")
    for r in rows:
        print(
            f"  - {r.name}  drop={r.dropoff}  no={r.container_no}  "
            f"{r.item_code}  {r.net_weight}kg  {r.status}"
        )
    return len(rows)
