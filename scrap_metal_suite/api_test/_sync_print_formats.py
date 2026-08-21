"""Sync every Scrap Metal Suite print format from the fixture into the live DB.

Standard print formats are write-locked by `validate()`, so this bypasses the
document API with `frappe.db.set_value` — the same approach as
`_patch_print_format.py` and `_patch_sticker.py`, but driven off the fixture
instead of hardcoded find/replace pairs, so it stays correct as templates change.

Why it is needed at all: `bench migrate` re-imports a Print Format fixture only
when the fixture's `modified` is newer than the installed record. That is easy
to get wrong by hand, and on sites where the fixture is not re-imported the DB
silently keeps the old template.

Covers, as of 2026-08-21:
  - thermal legibility fix (Scrap Weight / Truck Weight / Container Sticker):
    greyscale text and sub-10px Thai replaced with solid black at a 10px floor
  - bilingual queue timestamp fix (ใบคิวสองภาษา): `posting_date ~ posting_time`
    replaced with `generated_at`, because Wave 10 removed `posting_time` and the
    concat raised ParserError on every render

Re-runnable and idempotent — formats already matching the fixture are skipped.

    bench --site <site> execute scrap_metal_suite.api_test._sync_print_formats.run
"""

import json
import os

import frappe


def _fixture_path():
    return os.path.join(
        frappe.get_app_path("scrap_metal_suite"), "fixtures", "print_format.json"
    )


def run(only=None):
    """Sync formats from fixture to DB.

    Args:
        only: optional format name, or comma-separated names, to limit the sync.
    """
    with open(_fixture_path(), encoding="utf-8") as fh:
        fixture = json.load(fh)

    wanted = None
    if only:
        wanted = {n.strip() for n in only.split(",")} if isinstance(only, str) else set(only)

    patched, already, missing = [], [], []

    for src in fixture:
        name = src.get("name")
        if not name or (wanted and name not in wanted):
            continue
        if not frappe.db.exists("Print Format", name):
            missing.append(f"{name}: not installed on this site")
            continue

        want_html = src.get("html") or ""
        if not want_html:
            continue

        live_html = frappe.db.get_value("Print Format", name, "html") or ""
        if live_html == want_html:
            already.append(name)
            continue

        frappe.db.set_value("Print Format", name, "html", want_html, update_modified=True)
        patched.append(name)

    if patched:
        frappe.clear_cache(doctype="Print Format")
        frappe.db.commit()

    for name in patched:
        print(f"  + patched  {name}")
    for name in already:
        print(f"  = current  {name}")
    for msg in missing:
        print(f"  ! skipped  {msg}")

    print(f"\npatched={len(patched)} already_current={len(already)} skipped={len(missing)}")
    return {"patched": patched, "already": already, "skipped": missing}
