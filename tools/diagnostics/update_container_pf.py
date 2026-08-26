import json
from pathlib import Path

import frappe


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "print_format.json"
TARGETS = {"Scrap Weight Container Sticker"}


def run():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    by_name = {row["name"]: row for row in data if row.get("name") in TARGETS}
    if set(by_name) != TARGETS:
        print("Missing in fixture:", TARGETS - set(by_name))
        return
    for name, row in by_name.items():
        if not frappe.db.exists("Print Format", name):
            print(f"NOT FOUND on site: {name}")
            continue
        frappe.db.set_value("Print Format", name, "html", row["html"])
        frappe.db.set_value("Print Format", name, "css", row.get("css") or "")
        print(f"updated: {name}")
    frappe.db.commit()
