"""Patch the Scrap Weight Container Sticker print format: drop the trailing
'Bag' row that referenced the removed container_no field. Mirrors the
Wave 11 schema cleanup (container_no eliminated). Bypass the
standard-format write-lock with frappe.db.set_value."""

import frappe


OLD = (
    '<tr><td style=\"padding: 0;\">วันที่ • Date</td>'
    '<td style=\"text-align: right; padding: 0;\">'
    '{{ frappe.utils.format_datetime(doc.creation, "yyyy-MM-dd HH:mm") }}</td></tr>\n'
    '    <tr><td style=\"padding: 0;\">Bag</td>'
    '<td style=\"text-align: right; padding: 0;\">{{ doc.container_no }}</td></tr>\n'
    '  </table>'
)
NEW = (
    '<tr><td style=\"padding: 0;\">วันที่ • Date</td>'
    '<td style=\"text-align: right; padding: 0;\">'
    '{{ frappe.utils.format_datetime(doc.creation, "yyyy-MM-dd HH:mm") }}</td></tr>\n'
    '  </table>'
)


def run():
    pf = frappe.get_doc("Print Format", "Scrap Weight Container Sticker")
    html = pf.html or ""
    if OLD not in html:
        if "doc.container_no" not in html:
            print("Already patched (no doc.container_no reference).")
            return {"patched": False, "already_clean": True}
        print("Pattern not found verbatim; manual fix needed. doc.container_no still in template.")
        return {"patched": False, "still_dirty": True}
    new_html = html.replace(OLD, NEW)
    frappe.db.set_value(
        "Print Format", pf.name, "html", new_html, update_modified=True
    )
    frappe.clear_cache(doctype="Print Format")
    frappe.db.commit()
    pf2 = frappe.get_doc("Print Format", pf.name)
    print(f"Patched. doc.container_no remaining: {'doc.container_no' in (pf2.html or '')}")
    return {"patched": True}
