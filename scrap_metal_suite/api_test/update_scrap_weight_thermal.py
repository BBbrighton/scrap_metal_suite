"""One-shot helper: push the Scrap Weight Thermal print format from the
fixture into the live site, bypassing sync_fixtures (the format is
standard=Yes on the live site which makes Frappe refuse the update path)."""

import json
from pathlib import Path

import frappe


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "print_format.json"
TARGET = "Scrap Weight Thermal"


def run():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    row = next((r for r in data if r.get("name") == TARGET), None)
    if not row:
        print(f"missing in fixture: {TARGET}")
        return
    if not frappe.db.exists("Print Format", TARGET):
        print(f"NOT FOUND on site: {TARGET}")
        return
    frappe.db.set_value("Print Format", TARGET, "html", row["html"])
    if "css" in row and row["css"] is not None:
        frappe.db.set_value("Print Format", TARGET, "css", row["css"])
    frappe.db.commit()
    print(f"updated: {TARGET}")
