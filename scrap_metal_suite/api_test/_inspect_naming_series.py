import frappe


def run():
    meta = frappe.get_meta("Scrap Weight Container")
    f = meta.get_field("naming_series")
    print(f"Doctype meta naming_series.options: {f.options!r}")
    print(f"Doctype autoname: {meta.autoname!r}")
    # Check tabSeries counters.
    rows = frappe.db.sql(
        "SELECT name, current FROM `tabSeries` WHERE name LIKE %s",
        ("CTN-%",), as_dict=True,
    )
    print(f"\ntabSeries rows for CTN-:")
    for r in rows:
        print(f"  - {r['name']}  current={r['current']}")
