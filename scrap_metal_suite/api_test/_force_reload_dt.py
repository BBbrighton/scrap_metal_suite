"""Force-reload Scrap Weight Container doctype from JSON."""

import frappe
from frappe.modules.utils import sync_customizations  # noqa: F401
from frappe.modules.import_file import import_file_by_path


def run():
    # Show current DB modified.
    db_modified = frappe.db.get_value("DocType", "Scrap Weight Container", "modified")
    print(f"DB modified before:  {db_modified}")

    # Force reload from JSON.
    frappe.reload_doctype("Scrap Weight Container", force=True)

    db_modified_after = frappe.db.get_value("DocType", "Scrap Weight Container", "modified")
    print(f"DB modified after:   {db_modified_after}")

    # Refresh meta cache and read the option.
    frappe.clear_cache(doctype="Scrap Weight Container")
    meta = frappe.get_meta("Scrap Weight Container")
    f = meta.get_field("naming_series")
    print(f"Reloaded naming_series.options: {f.options!r}")
    frappe.db.commit()
