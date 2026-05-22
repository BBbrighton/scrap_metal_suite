"""Verify the new CTN-YYMM-#### naming series is in effect by inserting a
container and checking its name format."""

import re
import frappe

from scrap_metal_suite.api_test.smoke_test_sticker_render import (
    _ensure_supplier, _ensure_item, _ensure_scale,
    _ensure_dropoff, _ensure_session,
)


def run():
    frappe.set_user("Administrator")

    supplier = _ensure_supplier()
    _ensure_item()
    scale = _ensure_scale()
    dropoff = _ensure_dropoff(supplier)
    session = _ensure_session(scale)

    c = frappe.get_doc({
        "doctype": "Scrap Weight Container",
        "dropoff": dropoff,
        "session": session,
        "scale": scale,
        "operator": "Administrator",
        "item_code": _ensure_item(),
        "container_type": "Bag",
        "net_weight": 1.0,
        "entry_method": "Manual Entry",
    })
    c.insert(ignore_permissions=True)

    name = c.name
    pattern_yymm = re.compile(r"^CTN-\d{4}-\d{5}$")
    yymm_ok = bool(pattern_yymm.match(name))

    # Specifically: positions 4-8 should be a valid YYMM (year-month).
    # "26" + "05" → 2605 (May 2026). Reject "2026" (the old YYYY format).
    parts = name.split("-")
    yymm_value = parts[1] if len(parts) >= 3 else ""
    is_yymm_not_yyyy = (
        len(yymm_value) == 4
        and yymm_value[:2] in {"24", "25", "26", "27", "28", "29"}  # plausible YY
        and yymm_value[2:] in {f"{m:02d}" for m in range(1, 13)}  # plausible MM
    )

    print("=" * 70)
    print(f"Inserted container: {name}")
    print(f"  matches CTN-NNNN-NNNNN pattern: {yymm_ok}")
    print(f"  YYMM segment ({yymm_value!r}) is a valid year+month: {is_yymm_not_yyyy}")
    print("=" * 70)

    # Cleanup the test container.
    frappe.delete_doc(
        "Scrap Weight Container", name,
        force=True, ignore_permissions=True,
    )
    frappe.db.commit()

    return {"name": name, "format_ok": yymm_ok and is_yymm_not_yyyy}
