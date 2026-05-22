"""Patch the ใบคิวสองภาษา print format: replace the buggy posting_date+
posting_time concatenation with `creation` (always populated)."""

import frappe


OLD = (
    "frappe.utils.format_datetime("
    "sw.posting_date ~ ' ' ~ sw.posting_time, 'dd/MM/yy HH:mm') "
    "if sw.posting_date else '-'"
)
NEW = (
    "frappe.utils.format_datetime("
    "sw.creation, 'dd/MM/yy HH:mm') "
    "if sw.creation else '-'"
)


def run():
    pf = frappe.get_doc("Print Format", "ใบคิวสองภาษา")
    html = pf.html or ""
    if OLD not in html:
        print(f"OLD pattern not found in template (length {len(html)}); aborting.")
        # Dump line 478 for diagnosis.
        lines = html.split("\n")
        if len(lines) >= 478:
            print(f"line 478: {lines[477]!r}")
        return {"patched": False, "reason": "pattern not found"}

    new_html = html.replace(OLD, NEW)
    # Standard print formats are write-locked via validate(); bypass with
    # direct DB write. The fix is downstream-friendly because the same
    # Replace-OLD-with-NEW migration can be re-applied if the format is
    # re-seeded from a source file in a future commit.
    frappe.db.set_value(
        "Print Format", pf.name, "html", new_html, update_modified=True
    )
    frappe.clear_cache(doctype="Print Format")
    frappe.db.commit()

    # Verify.
    pf2 = frappe.get_doc("Print Format", "ใบคิวสองภาษา")
    contains_old = OLD in (pf2.html or "")
    contains_new = NEW in (pf2.html or "")
    print(f"After save: contains_old={contains_old} contains_new={contains_new}")
    return {"patched": True, "contains_new": contains_new}
