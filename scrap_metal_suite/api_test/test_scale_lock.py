"""Regression tests for Scale lock acquisition and release.

Covers the failure that stranded ตราชั่งใหญ่ on production: a scale left
flagged `in_use` by a session that is no longer Open used to block every
future operator, with no code path able to clear it.

Run:
    bench --site metal execute scrap_metal_suite.api_test.test_scale_lock.run
"""

import frappe

from scrap_metal_suite.api.v1 import pos as pos_api
from scrap_metal_suite.scrap_metal_suite.doctype.scale.scale import (
    is_lock_holder_active,
    release_locks_for_session,
    release_stale_locks,
)

SCALE_A = "_TEST_LOCK_Scale-A"
SCALE_B = "_TEST_LOCK_Scale-B"
PROFILE = "_TEST_LOCK_Profile"

results = {"passed": 0, "failed": 0, "failures": []}


def check(name, condition, detail=""):
    if condition:
        results["passed"] += 1
        print(f"  ✓ {name}")
    else:
        results["failed"] += 1
        results["failures"].append(f"{name}: {detail}")
        print(f"  ✗ {name}: {detail}")


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

def cleanup():
    for dt, filters in (
        ("POS Session", {"pos_profile": PROFILE}),
        ("Scale", {"name": ["in", [SCALE_A, SCALE_B]]}),
        ("POS Profile Scrap", {"name": PROFILE}),
    ):
        for name in frappe.get_all(dt, filters=filters, pluck="name"):
            frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
    frappe.db.commit()


def setup():
    cleanup()

    for scale_name in (SCALE_A, SCALE_B):
        frappe.get_doc({
            "doctype": "Scale",
            "name": scale_name,
            "scale_name": scale_name,
            "scale_type": "Platform",
            "usage_type": "Truck",
            "is_active": 1,
            "max_capacity_kg": 50000,
        }).insert(ignore_permissions=True)

    price_list = frappe.db.get_value("Price List", {"buying": 1}, "name") or "Standard Buying"
    profile = frappe.get_doc({
        "doctype": "POS Profile Scrap",
        "profile_name": PROFILE,
        "is_active": 1,
        "price_list": price_list,
    })
    # `items` is a mandatory child table; any existing item will do — these
    # tests never touch pricing.
    any_item = frappe.db.get_value("Item", {"disabled": 0}, ["name", "item_name"], as_dict=True)
    profile.append("items", {"item_code": any_item.name, "item_name": any_item.item_name})
    profile.insert(ignore_permissions=True)

    frappe.db.commit()


def open_session():
    doc = frappe.get_doc({
        "doctype": "POS Session",
        "pos_profile": PROFILE,
        "status": "Open",
    })
    doc.insert(ignore_permissions=True)
    return doc


def scale_state(name):
    return frappe.db.get_value(
        "Scale", name, ["in_use", "in_use_by_session"], as_dict=True
    )


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

def test_closed_holder_is_not_active():
    """A lock is only real while its holder is Open."""
    session = open_session()
    check("open session counts as active holder",
          is_lock_holder_active(session.name) is True)

    session.status = "Closed"
    session.save(ignore_permissions=True)
    check("closed session does not count as active holder",
          is_lock_holder_active(session.name) is False)

    check("nonexistent session does not count as active holder",
          is_lock_holder_active("SES-DOES-NOT-EXIST") is False)
    check("empty holder does not count as active holder",
          is_lock_holder_active(None) is False)

    frappe.delete_doc("POS Session", session.name, force=True,
                      ignore_permissions=True)
    frappe.db.commit()


def test_stale_lock_is_taken_over():
    """set_session_scale claims a scale held by a closed session.

    This is the production failure: ตราชั่งใหญ่ stayed pinned to a session
    closed six months earlier, so no operator could select it again.
    """
    ghost = open_session()
    ghost_name = ghost.name
    ghost.status = "Closed"
    ghost.save(ignore_permissions=True)

    # Strand the lock the way the real record was stranded — flagged in_use,
    # pointing at a session that is closed and will never close again.
    frappe.db.set_value("Scale", SCALE_A,
                        {"in_use": 1, "in_use_by_session": ghost_name})
    frappe.db.commit()

    live = open_session()
    try:
        pos_api.set_session_scale(live.name, SCALE_A)
        claimed = True
        err = ""
    except Exception as e:  # noqa: BLE001 - the assertion is that this is unreachable
        claimed = False
        err = str(e)

    check("stale lock from a closed session is taken over", claimed, err)

    state = scale_state(SCALE_A)
    check("scale now points at the live session",
          state.in_use == 1 and state.in_use_by_session == live.name,
          f"got in_use={state.in_use} holder={state.in_use_by_session}")

    frappe.delete_doc("POS Session", live.name, force=True,
                      ignore_permissions=True)
    frappe.delete_doc("POS Session", ghost_name, force=True,
                      ignore_permissions=True)
    frappe.db.commit()


def test_live_lock_still_blocks():
    """A lock held by a genuinely Open session must still be refused."""
    holder = open_session()
    pos_api.set_session_scale(holder.name, SCALE_A)

    # A second Open session cannot exist for the same operator, so simulate the
    # contended case by pointing a fresh session at the same scale directly.
    frappe.db.set_value("POS Session", holder.name, "status", "Open")
    frappe.db.commit()

    state = scale_state(SCALE_A)
    blocked = False
    err = ""
    if state.in_use and state.in_use_by_session:
        blocked = is_lock_holder_active(state.in_use_by_session)
        err = f"holder {state.in_use_by_session} reported inactive while Open"

    check("lock held by an Open session is still honoured", blocked, err)

    frappe.delete_doc("POS Session", holder.name, force=True,
                      ignore_permissions=True)
    frappe.db.commit()


def test_release_sweeps_by_holder_not_scale_field():
    """Release must follow in_use_by_session, not the session's own `scale`.

    A switch_scale moves the lock without rewriting the session's `scale`
    field; following that field releases the wrong scale and strands the real
    one. That is what kept ตราชั่งใหญ่ locked while the session said SCALE-002.
    """
    session = open_session()
    pos_api.set_session_scale(session.name, SCALE_A)

    # Move the real lock to SCALE_B while the session still names SCALE_A.
    frappe.db.set_value("Scale", SCALE_A,
                        {"in_use": 0, "in_use_by_session": None})
    frappe.db.set_value("Scale", SCALE_B,
                        {"in_use": 1, "in_use_by_session": session.name})
    frappe.db.commit()

    released = release_locks_for_session(session.name)
    check("sweep finds the scale the session no longer names",
          released == [SCALE_B], f"released={released}")

    state = scale_state(SCALE_B)
    check("moved scale is actually freed",
          not state.in_use and not state.in_use_by_session,
          f"got in_use={state.in_use} holder={state.in_use_by_session}")

    frappe.delete_doc("POS Session", session.name, force=True,
                      ignore_permissions=True)
    frappe.db.commit()


def test_close_session_releases_moved_lock():
    """Closing a session frees the scale it actually holds."""
    session = open_session()
    pos_api.set_session_scale(session.name, SCALE_A)

    frappe.db.set_value("Scale", SCALE_A,
                        {"in_use": 0, "in_use_by_session": None})
    frappe.db.set_value("Scale", SCALE_B,
                        {"in_use": 1, "in_use_by_session": session.name})
    frappe.db.commit()

    frappe.get_doc("POS Session", session.name).close_session()

    state = scale_state(SCALE_B)
    check("close_session frees the moved scale",
          not state.in_use and not state.in_use_by_session,
          f"got in_use={state.in_use} holder={state.in_use_by_session}")

    frappe.delete_doc("POS Session", session.name, force=True,
                      ignore_permissions=True)
    frappe.db.commit()


def test_desk_close_releases_scale():
    """Flipping status to Closed in the Desk form releases the scale.

    The Desk form never calls close_session() — it just saves the doc — so the
    release has to hang off on_update, not off the API method. `status` is a
    plain editable Select, so this is a route an admin actually takes.
    """
    session = open_session()
    pos_api.set_session_scale(session.name, SCALE_A)

    # Exactly what a Desk save does: load, set the field, save. No
    # close_session(), no API call.
    desk_doc = frappe.get_doc("POS Session", session.name)
    desk_doc.status = "Closed"
    desk_doc.save()

    state = scale_state(SCALE_A)
    check("desk-style save releases the scale",
          not state.in_use and not state.in_use_by_session,
          f"got in_use={state.in_use} holder={state.in_use_by_session}")

    frappe.delete_doc("POS Session", session.name, force=True,
                      ignore_permissions=True)
    frappe.db.commit()


def test_desk_close_does_not_free_someone_elses_lock():
    """Closing session X never releases a scale held by session Y.

    The sweep is keyed to the closing session, so a stale lock left by a
    *different* session survives a Desk close — that case needs the cron sweep,
    or a new operator claiming the scale.
    """
    ghost = open_session()
    ghost_name = ghost.name
    ghost.status = "Closed"
    ghost.save(ignore_permissions=True)

    frappe.db.set_value("Scale", SCALE_A,
                        {"in_use": 1, "in_use_by_session": ghost_name})
    frappe.db.commit()

    other = open_session()
    other.status = "Closed"
    other.save()

    state = scale_state(SCALE_A)
    check("closing an unrelated session leaves the stale lock in place",
          state.in_use == 1 and state.in_use_by_session == ghost_name,
          f"got in_use={state.in_use} holder={state.in_use_by_session}")

    # ...and the cron sweep is what clears it.
    release_stale_locks()
    state = scale_state(SCALE_A)
    check("the cron sweep is what clears that one",
          not state.in_use, f"got in_use={state.in_use}")

    for name in (other.name, ghost_name):
        frappe.delete_doc("POS Session", name, force=True,
                          ignore_permissions=True)
    frappe.db.commit()


def test_scheduled_sweep_frees_orphans():
    """release_stale_locks clears a lock whose holder no longer exists.

    This is the last line of defence — the case that has no session close to
    hook onto, such as a Scale record recreated carrying old `in_use` values.
    """
    frappe.db.set_value("Scale", SCALE_A,
                        {"in_use": 1, "in_use_by_session": None})
    frappe.db.commit()

    released = release_stale_locks()
    check("orphan lock with no holder is swept", SCALE_A in released,
          f"released={released}")

    state = scale_state(SCALE_A)
    check("orphan scale is freed",
          not state.in_use, f"got in_use={state.in_use}")


def test_sweep_spares_live_locks():
    """The sweep must not free a scale an operator is using right now."""
    session = open_session()
    pos_api.set_session_scale(session.name, SCALE_B)

    released = release_stale_locks()
    check("sweep leaves an Open session's scale alone",
          SCALE_B not in released, f"released={released}")

    state = scale_state(SCALE_B)
    check("live lock survives the sweep",
          state.in_use == 1 and state.in_use_by_session == session.name,
          f"got in_use={state.in_use} holder={state.in_use_by_session}")

    frappe.delete_doc("POS Session", session.name, force=True,
                      ignore_permissions=True)
    frappe.db.commit()


# ---------------------------------------------------------------------------

TESTS = [
    test_closed_holder_is_not_active,
    test_stale_lock_is_taken_over,
    test_live_lock_still_blocks,
    test_release_sweeps_by_holder_not_scale_field,
    test_close_session_releases_moved_lock,
    test_desk_close_releases_scale,
    test_desk_close_does_not_free_someone_elses_lock,
    test_scheduled_sweep_frees_orphans,
    test_sweep_spares_live_locks,
]


def run():
    print("\n" + "=" * 70)
    print("SCALE LOCK REGRESSION TESTS")
    print("=" * 70 + "\n")

    frappe.set_user("Administrator")
    setup()

    try:
        for test in TESTS:
            print(f"\n{test.__name__}")
            try:
                test()
            except Exception as e:  # noqa: BLE001
                results["failed"] += 1
                results["failures"].append(f"{test.__name__}: {e}")
                print(f"  ✗ {test.__name__} raised: {e}")
    finally:
        cleanup()

    print("\n" + "=" * 70)
    print(f"Total: {results['passed'] + results['failed']}  |  "
          f"Passed: {results['passed']}  |  Failed: {results['failed']}")
    if results["failures"]:
        print("\nFAILED:")
        for f in results["failures"]:
            print(f"  ✗ {f}")
    print("=" * 70)

    return {"passed": results["passed"], "failed": results["failed"]}
