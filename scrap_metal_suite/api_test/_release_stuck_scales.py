"""One-shot: release scales whose `in_use_by_session` points at a deleted or
non-Open POS Session. Mirrors the new POSSession.on_trash hook for legacy
data left behind by test cleanups that bypassed the hook.
"""

import frappe


def run():
    in_use = frappe.get_all(
        "Scale",
        filters={"in_use": 1},
        fields=["name", "in_use_by_session"],
    )
    released = []
    for sc in in_use:
        sn = sc.get("in_use_by_session")
        reason = None
        if not sn:
            reason = "no session linked"
        elif not frappe.db.exists("POS Session", sn):
            reason = f"session {sn} deleted"
        else:
            sst = frappe.db.get_value("POS Session", sn, "status")
            if sst != "Open":
                reason = f"session {sn} status={sst}"
        if reason:
            frappe.db.set_value(
                "Scale", sc.name,
                {"in_use": 0, "in_use_by_session": None},
                update_modified=False,
            )
            released.append((sc.name, reason))
    frappe.db.commit()
    print(f"Released {len(released)} stuck scales:")
    for n, r in released:
        print(f"  - {n}  ({r})")
    return {"released": [n for n, _ in released]}
