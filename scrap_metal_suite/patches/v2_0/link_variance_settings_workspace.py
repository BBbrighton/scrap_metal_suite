"""Put `SMT Variance Settings` on the workspaces a manager actually opens.

Shipping the doctype is not the same as shipping a way to reach it. Frappe
only syncs a Workspace JSON when no record exists yet, so adding links to the
JSON does nothing on a site that already has these workspaces — the page stays
reachable only by typing `/app/smt-variance-settings`, which no manager will do.

Idempotent: re-running adds nothing.
"""

import frappe

TARGET = "SMT Variance Settings"
ROUTE = "smt-variance-settings"
LABEL = "Variance Thresholds"

WORKSPACES = ("SMT Production", "SMT Accounting")


def execute():
	for name in WORKSPACES:
		if not frappe.db.exists("Workspace", name):
			continue

		ws = frappe.get_doc("Workspace", name)
		changed = False

		if not any(l.link_to == TARGET for l in ws.links):
			# Accounting has no Settings card yet; Production already does.
			if not any(l.type == "Card Break" and l.label == "Settings" for l in ws.links):
				ws.append("links", {"type": "Card Break", "label": "Settings",
				                    "hidden": 0, "onboard": 0, "link_count": 0})
			ws.append("links", {
				"type": "Link", "link_type": "DocType", "link_to": TARGET,
				"label": LABEL, "hidden": 0, "onboard": 0, "is_query_report": 0,
				"link_count": 0, "dependencies": "",
			})
			changed = True

		# A URL shortcut, not a DocType one. Frappe puts a record count on every
		# DocType shortcut, and `SMT Variance Settings` is a Single — Singles keep
		# their values in `tabSingles` and have no table of their own, so the count
		# query hits a table that does not exist and the whole workspace answers
		# "Use of sub-query or function is restricted" on every visit. The link
		# still lands on the same form; it simply carries no count, which a
		# settings page never had a meaningful one for anyway.
		existing = next((s for s in ws.shortcuts
		                 if s.link_to == TARGET or s.url == f"/app/{ROUTE}"), None)
		if existing and existing.type == "DocType":
			existing.type = "URL"
			existing.url = f"/app/{ROUTE}"
			existing.link_to = None
			changed = True
		elif not existing:
			ws.append("shortcuts", {
				"type": "URL", "url": f"/app/{ROUTE}", "label": LABEL, "color": "Orange",
			})
			changed = True

		if changed:
			ws.flags.ignore_permissions = True
			ws.save()
			print(f"  {name}: added '{LABEL}' link and shortcut")

	frappe.db.commit()
	frappe.clear_cache()
