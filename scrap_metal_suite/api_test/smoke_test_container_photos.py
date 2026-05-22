"""Smoke test for Wave 11 container-level photo capture.

Verifies the schema + API path end-to-end without exercising the browser camera:

  1. A `Scrap Weight Container` accepts the `photos` Table field.
  2. `save_weight_photo` accepts `parent_doctype='Scrap Weight Container'`,
     appends a Weight Photo child row, and persists.
  3. `get_weight_photos` returns the saved photo.
  4. `list_containers` surfaces a `photo_count` field per row.
  5. `delete_weight_photo` removes it cleanly.

Run with:
  bench --site metal execute scrap_metal_suite.api_test.smoke_test_container_photos.run

This isolates the new schema/API surface so a regression here is unambiguous —
distinct from the browser-side capture flow on /pos/terminal which depends on
camera + upload_file (covered in ui_test/test_pos_terminal.py).
"""

import frappe

from scrap_metal_suite.api.v1.dropoff import (
    save_weight_photo,
    get_weight_photos,
    delete_weight_photo,
    list_containers,
)
from scrap_metal_suite.api_test.smoke_test_sticker_render import (
    _ensure_supplier,
    _ensure_item,
    _ensure_scale,
    _ensure_dropoff,
    _ensure_session,
    PREFIX,
)


def _make_container(dropoff: str, session: str, scale: str) -> str:
    c = frappe.get_doc(
        {
            "doctype": "Scrap Weight Container",
            "dropoff": dropoff,
            "session": session,
            "scale": scale,
            "operator": "Administrator",
            "item_code": _ensure_item(),
            "container_type": "Bag",
            "net_weight": 123.45,
            "entry_method": "Manual Entry",
        }
    )
    c.insert(ignore_permissions=True)
    return c.name


def _fake_photo_url() -> str:
    """Return a stable Attach-field-compatible string. save_weight_photo treats
    photo_url as opaque — it stores it on the Weight Photo row and never
    fetches it. Skipping the real File creation avoids PIL EXIF processing on
    a fake JPEG."""
    return f"/files/{PREFIX}smoke_photo.jpg"


def run():
    frappe.set_user("Administrator")

    supplier = _ensure_supplier()
    _ensure_item()
    scale = _ensure_scale()
    dropoff = _ensure_dropoff(supplier)
    session = _ensure_session(scale)

    container_name = None
    file_url = _fake_photo_url()
    photos_inserted: list[str] = []
    results: list[tuple[str, bool, str]] = []

    def add(label, ok, detail=""):
        results.append((label, ok, detail))

    try:
        container_name = _make_container(dropoff, session, scale)
        add("1. Insert container", True, container_name)

        # Verify the photos field is on the meta.
        meta = frappe.get_meta("Scrap Weight Container")
        photos_field = meta.get_field("photos")
        ok = bool(photos_field) and photos_field.fieldtype == "Table" and photos_field.options == "Weight Photo"
        add(
            "2. photos Table field is registered",
            ok,
            f"fieldtype={getattr(photos_field, 'fieldtype', None)} options={getattr(photos_field, 'options', None)}",
        )

        # Save two photos via API.
        for i in range(2):
            res = save_weight_photo(
                parent_doctype="Scrap Weight Container",
                parent_doc=container_name,
                photo_url=file_url,
                weight_type="Scrap",
                dropoff=dropoff,
                session=session,
            )
            assert res.get("success"), f"save_weight_photo returned {res}"
        # Re-read parent to capture child names for cleanup.
        parent = frappe.get_doc("Scrap Weight Container", container_name)
        photos_inserted = [p.name for p in parent.photos]
        add("3. save_weight_photo accepts container parent (x2)", len(photos_inserted) == 2, f"photos={photos_inserted}")

        # get_weight_photos returns both rows.
        photos = get_weight_photos("Scrap Weight Container", container_name)
        ok = isinstance(photos, list) and len(photos) == 2 and all(p.get("photo") == file_url for p in photos)
        add("4. get_weight_photos returns saved rows", ok, f"count={len(photos) if isinstance(photos, list) else 'n/a'}")

        # list_containers surfaces photo_count.
        rows = list_containers(dropoff=dropoff, include_voided=True)
        row = next((r for r in rows if r["name"] == container_name), None)
        ok = bool(row) and int(row.get("photo_count") or 0) == 2
        add(
            "5. list_containers exposes photo_count",
            ok,
            f"row={row}",
        )

        # delete_weight_photo removes one row.
        target = photos_inserted[0]
        del_res = delete_weight_photo("Scrap Weight Container", container_name, target)
        ok = del_res.get("success") and int(del_res.get("photo_count") or -1) == 1
        add(
            "6. delete_weight_photo removes the row",
            ok,
            f"remaining={del_res.get('photo_count')}",
        )

        # Save rejects unknown parent doctypes.
        try:
            save_weight_photo(
                parent_doctype="Bogus Doctype",
                parent_doc=container_name,
                photo_url=file_url,
            )
            add("7. save_weight_photo rejects unknown parent_doctype", False, "no exception")
        except frappe.ValidationError:
            add("7. save_weight_photo rejects unknown parent_doctype", True, "frappe.ValidationError raised")

    finally:
        # Tidy up: delete the container (cascades child Weight Photo rows).
        if container_name and frappe.db.exists("Scrap Weight Container", container_name):
            frappe.delete_doc(
                "Scrap Weight Container", container_name, force=True, ignore_permissions=True
            )
        frappe.db.commit()

    # Report.
    print("=" * 70)
    print("CONTAINER PHOTO SMOKE TEST")
    print("=" * 70)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - passed
    for label, ok, detail in results:
        marker = "OK " if ok else "X  "
        suffix = f"  ({detail})" if detail else ""
        print(f"  {marker}{label}{suffix}")
    print("-" * 70)
    print(f"  {passed}/{len(results)} checks passed{', ' + str(failed) + ' FAILED' if failed else ''}")
    print("=" * 70)
    return {"passed": passed, "failed": failed}
