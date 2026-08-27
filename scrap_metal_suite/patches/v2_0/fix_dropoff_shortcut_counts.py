"""Stop workspace shortcuts asking for a row count Frappe refuses to give.

Every desk page carrying a Dropoff shortcut answered:

    Use of sub-query or function is restricted

Frappe's injection guard takes the text after `count(`, splits on the first
space, and asks whether that token *contains* a blacklisted SQL keyword:

    field  = "count(`tabDropoff`.name) as total_count"
    token  = "`tabdropoff"
    "drop" in "`tabdropoff"   ->  True   ->  frappe.throw(...)

The doctype is called **Dropoff**, and `tabDropoff` contains `drop`. A row
count is read as a DROP TABLE. Nothing to do with this app's code — the same
guard fires for any doctype named Showroom, Case Study or Update Log, on any
Frappe carrying `db_query.sanitize_fields`.

The count is requested client-side, in shortcut_widget.js:

    let filters = frappe.utils.process_filter_expression(this.stats_filter);
    if (this.type == "DocType" && this.doc_view != "New" && filters) { ...count... }

`stats_filter` is stored as `'[]'`, which parses to an empty array — and an
empty array is truthy in JavaScript, so the count fires for every DocType
shortcut. Clearing `stats_filter` makes that condition false and the request
is never made. The shortcut keeps its type, its link and its label; it loses
only a number badge.

Deliberately narrow: only shortcuts whose target actually trips the guard are
touched, so every other count on the site is left working.
"""

import frappe

# Mirrors frappe.model.db_query.sanitize_fields
BLACKLISTED_KEYWORDS = [
    "select", "create", "insert", "delete", "drop", "update", "case", "show",
]


def blocked_by(doctype):
    """Keywords that make a count on this doctype's table trip the guard."""
    token = ("`tab" + (doctype or "").lower()).split(" ", 1)[0]
    return [k for k in BLACKLISTED_KEYWORDS if k in token]


def execute():
    rows = frappe.db.sql(
        """SELECT name, parent, label, link_to, stats_filter
           FROM `tabWorkspace Shortcut`
           WHERE type = 'DocType' AND link_to IS NOT NULL""",
        as_dict=True,
    )

    cleared = []
    for r in rows:
        hits = blocked_by(r.link_to)
        if not hits or not r.stats_filter:
            continue
        frappe.db.set_value(
            "Workspace Shortcut", r.name, "stats_filter", None, update_modified=False
        )
        cleared.append(f"{r.parent} / {r.label} ({r.link_to}) — would trip on {hits}")

    if cleared:
        frappe.db.commit()
        frappe.clear_cache()

    for c in cleared:
        print(f"  cleared stats_filter: {c}")
    print(f"fix_dropoff_shortcut_counts: {len(cleared)} shortcut(s) will no longer request a count")
