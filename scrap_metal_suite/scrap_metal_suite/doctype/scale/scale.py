# Copyright (c) 2025, Scrap Metal Suite and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Scale(Document):
    def validate(self):
        # Ensure scale_name is uppercase for consistency
        if self.scale_name:
            self.scale_name = self.scale_name.upper().strip()

    def before_save(self):
        # If being deactivated, check if any open sessions use this scale
        if not self.is_active and self.has_value_changed('is_active'):
            open_sessions = frappe.get_all(
                "POS Session",
                filters={
                    "scale": self.name,
                    "status": "Open"
                },
                limit=1
            )
            if open_sessions:
                frappe.throw(
                    f"Cannot deactivate scale '{self.scale_name}' while it has open POS sessions. "
                    "Please close all sessions using this scale first."
                )


def is_lock_holder_active(session_name):
    """Is `session_name` a session that could still be weighing on a scale?

    A lock is only real while the session holding it is Open. Anything else —
    a Closed session, or a name that no longer resolves to a session at all —
    is a leftover, not a conflict.

    `Scale.in_use_by_session` is a Link to POS Session, but
    `api/v1/production.py` writes Production Session names into it, so check
    both doctypes before calling a holder gone.
    """
    if not session_name:
        return False

    for doctype in ("POS Session", "Production Session"):
        if frappe.db.get_value(doctype, session_name, "status") == "Open":
            return True

    return False


def release_locks_for_session(session_name, use_db=False):
    """Clear every Scale lock pointing at `session_name`.

    Sweeps by `in_use_by_session` rather than following a session's own `scale`
    field: a switch_scale moves the lock without necessarily rewriting `scale`,
    so following that field releases the wrong scale and strands the real one.
    An empty `scale` must not be read as "nothing to release" either.

    `use_db` writes through `frappe.db.set_value` instead of the document API,
    for callers (on_trash) where a get_doc round-trip can race.

    Returns the list of scales released.
    """
    released = []

    for scale_name in frappe.get_all(
        "Scale",
        filters={"in_use_by_session": session_name},
        pluck="name",
    ):
        if use_db:
            frappe.db.set_value(
                "Scale", scale_name,
                {"in_use": 0, "in_use_by_session": None},
                update_modified=False,
            )
        else:
            scale_doc = frappe.get_doc("Scale", scale_name)
            scale_doc.in_use = 0
            scale_doc.in_use_by_session = None
            scale_doc.save()

        released.append(scale_name)

    return released


def release_stale_locks():
    """Release every Scale whose lock is held by a session that isn't Open.

    Nothing else in the app can clear such a lock: the release paths all key
    off a session being closed *now*, so a lock that outlives that moment —
    a record restored or recreated carrying old `in_use` values, a session
    closed by a path that skipped the hook — is permanent until someone edits
    the database by hand. This is the unattended sweep that makes it
    self-healing, run from the idle-session cron. (The other route is a new
    operator claiming the scale: set_session_scale releases that one holder
    directly rather than sweeping everything.)

    Returns the list of scales released.
    """
    released = []

    for scale in frappe.get_all(
        "Scale",
        filters={"in_use": 1},
        fields=["name", "in_use_by_session"],
    ):
        if is_lock_holder_active(scale.in_use_by_session):
            continue

        frappe.db.set_value(
            "Scale", scale.name,
            {"in_use": 0, "in_use_by_session": None},
        )
        released.append(scale.name)

    return released
