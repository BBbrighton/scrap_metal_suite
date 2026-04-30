"""
Backfill snapshot fields on existing Scrap Weight Container records.

The container redesign (see docs/DROPOFF_CONTAINER_REDESIGN.md) added four
denormalised fields to Scrap Weight Container so the printed sticker — and any
downstream report — has supplier identity, truck plate, and operator name
without joining back to Dropoff or User:

    supplier        (Link  → Supplier, fetch_from "dropoff.supplier")
    supplier_name   (Data,            fetch_from "dropoff.supplier_name")
    license_plate   (Data,            fetch_from "dropoff.license_plate")
    operator_name   (Data,            fetch_from "operator.full_name")

`fetch_from` only auto-populates on insert/save of new records. This patch
fills the four columns on the rows that pre-date the schema change.

Idempotent: only updates rows where the target field is currently NULL/empty.
"""

import frappe


def execute():
    rows = frappe.db.sql(
        """
        SELECT name, dropoff, operator,
               supplier, supplier_name, license_plate, operator_name
        FROM `tabScrap Weight Container`
        """,
        as_dict=True,
    )

    if not rows:
        print("backfill_container_snapshot_fields: no containers to backfill")
        return

    dropoff_cache: dict[str, dict] = {}
    user_cache: dict[str, str | None] = {}
    updated = 0

    for row in rows:
        updates: dict[str, str | None] = {}

        if row.dropoff and not (row.supplier and row.supplier_name and row.license_plate):
            if row.dropoff not in dropoff_cache:
                dropoff_cache[row.dropoff] = (
                    frappe.db.get_value(
                        "Dropoff",
                        row.dropoff,
                        ["supplier", "supplier_name", "license_plate"],
                        as_dict=True,
                    )
                    or {}
                )
            d = dropoff_cache[row.dropoff]
            if d.get("supplier") and not row.supplier:
                updates["supplier"] = d["supplier"]
            if d.get("supplier_name") and not row.supplier_name:
                updates["supplier_name"] = d["supplier_name"]
            if d.get("license_plate") and not row.license_plate:
                updates["license_plate"] = d["license_plate"]

        if row.operator and not row.operator_name:
            if row.operator not in user_cache:
                user_cache[row.operator] = frappe.db.get_value(
                    "User", row.operator, "full_name"
                )
            full_name = user_cache[row.operator]
            if full_name:
                updates["operator_name"] = full_name

        if updates:
            for fieldname, value in updates.items():
                frappe.db.set_value(
                    "Scrap Weight Container",
                    row.name,
                    fieldname,
                    value,
                    update_modified=False,
                )
            updated += 1

    frappe.db.commit()
    print(
        f"backfill_container_snapshot_fields: updated {updated} of {len(rows)} containers"
    )
