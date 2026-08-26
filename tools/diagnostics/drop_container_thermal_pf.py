"""One-shot helper: delete the legacy `Scrap Weight Container Thermal` Print
Format from the live site. The container redesign now relies solely on the
sticker per-container; the customer-facing thermal receipt is rendered from the
parent Dropoff via `ใบคิวสองภาษา`.
"""

import frappe


TARGET = "Scrap Weight Container Thermal"


def run():
    if not frappe.db.exists("Print Format", TARGET):
        print(f"already absent: {TARGET}")
        return
    frappe.delete_doc("Print Format", TARGET, force=True, ignore_permissions=True)
    frappe.db.commit()
    print(f"deleted: {TARGET}")
