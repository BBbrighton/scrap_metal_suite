"""Set the permission baseline once, then leave the site alone.

Permissions did not travel with the code: a `git pull` gives you Python, while
roles stay in the database. That is how `POS Operator` came to be missing from
Truck Weight on production — an operator can weigh a truck once and never
reweigh it, with no error naming the cause.

**Why a patch and not a fixture.** Shipping these rows as a fixture does carry
them, but it also re-applies them on *every* `bench migrate`. Measured on a
restored production copy: a row the fixture ships is silently reverted on each
migrate, while a row added locally survives. So a manager who grants someone an
extra permission next month would lose it at the next deploy, with nothing said.
That is a worse failure than the one being fixed, because it is invisible and it
repeats.

A patch runs once, recorded in Patch Log. It establishes the baseline on this
deploy and on any fresh install, and after that the site owns its own
permissions — which is the correct division: what the app *needs* to function is
set here, what the business *decides* stays with the business.

To re-apply after someone has broken permissions, delete this patch's Patch Log
row and run `bench migrate`, or call `execute()` directly.

Idempotent and additive: it grants, never revokes, so re-running cannot take
away anything a site has chosen to add.
"""

import frappe

# (doctype, role, {permission: 1}) — merged onto any existing row, else created.
GRANTS = [
    # --- Receiving -------------------------------------------------------
    # Custom DocPerm rows REPLACE standard permissions rather than adding to
    # them, so adding SMT Manager through the Role Permission Manager silently
    # dropped POS Operator from these two.
    ("Dropoff",      "POS Operator", {"read": 1, "write": 1, "create": 1}),
    ("Truck Weight", "POS Operator", {"read": 1, "write": 1, "create": 1}),

    # Scrap Weight is submittable, and reweighing submits and cancels it.
    # No role held either permission — System Manager included.
    ("Scrap Weight", "POS Operator",   {"submit": 1, "cancel": 1}),
    ("Scrap Weight", "SMT Manager",    {"submit": 1, "cancel": 1, "amend": 1}),
    ("Scrap Weight", "System Manager", {"submit": 1, "cancel": 1, "amend": 1}),

    # --- Sorting ---------------------------------------------------------
    # open_session() inserts without elevated rights and only Production
    # Manager held create, so the role that does the sorting could not start.
    ("Production Session", "Production Worker", {"read": 1, "write": 1, "create": 1}),
    ("Production Session", "System Manager",    {"read": 1, "write": 1, "create": 1, "delete": 1}),

    # Reopen is implemented as doc.cancel(). Nobody held cancel, so the
    # reason-required reopen flow could never run. Cancelling submitted work is
    # a supervisor decision, which is what that design already assumed.
    ("Production Sorting", "Production Manager", {"cancel": 1, "amend": 1}),
    ("Production Sorting", "System Manager",     {"cancel": 1, "amend": 1}),

    # --- Settlement ------------------------------------------------------
    # Neither accounting role could read the one document settlement exists to
    # close. This is why the settlement suite sat at 28 of 37.
    ("Dropoff Final", "SMT Accountant",         {"read": 1}),
    ("Dropoff Final", "SMT Accounting Manager", {"read": 1}),
    ("Dropoff Final", "SMT Manager",            {"read": 1}),
]


def execute():
    granted, skipped = [], []
    for dt, role, perms in GRANTS:
        if not frappe.db.exists("DocType", dt):
            skipped.append(f"{dt} (doctype missing)")
            continue
        if not frappe.db.exists("Role", role):
            skipped.append(f"{role} (role missing)")
            continue

        name = frappe.db.get_value(
            "Custom DocPerm", {"parent": dt, "role": role, "permlevel": 0}
        )
        if name:
            doc = frappe.get_doc("Custom DocPerm", name)
            added = [k for k, v in perms.items() if v and not doc.get(k)]
            if not added:
                continue
            for k, v in perms.items():
                if v:
                    doc.set(k, v)          # grant only; never revoke
            doc.flags.ignore_permissions = True
            doc.save(ignore_permissions=True)
            granted.append(f"{dt} / {role}: +{','.join(added)}")
        else:
            row = {"doctype": "Custom DocPerm", "parent": dt, "parenttype": "DocType",
                   "parentfield": "permissions", "permlevel": 0, "role": role, "read": 1}
            row.update(perms)
            frappe.get_doc(row).insert(ignore_permissions=True)
            granted.append(f"{dt} / {role}: created {sorted(k for k, v in perms.items() if v)}")

    frappe.db.commit()
    frappe.clear_cache()

    for g in granted:
        print(f"  {g}")
    for s in skipped:
        print(f"  skipped {s}")
    print(f"baseline_permissions: {len(granted)} granted, {len(skipped)} skipped")
