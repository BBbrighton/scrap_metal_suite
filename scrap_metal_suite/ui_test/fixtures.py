# Fixture factories for UI tests.
#
# Each factory is callable via `bench --site <site> execute
# scrap_metal_suite.ui_test.fixtures.<fn>` from the conftest helper.
# This keeps test setup transactional and reusable across UI tests.

import json

import frappe
from frappe.utils import flt, now_datetime, add_to_date


TEST_PREFIX = "_TEST_UI_"

# Canonical Thai item names — never translated.
THAI_ITEM_PRIMARY = "ทองแดงปอก"
THAI_ITEM_SECONDARY = "ทองแดงเล็ก"


# ---------------------------------------------------------------------------
# Idempotent factories
# ---------------------------------------------------------------------------

def _ensure_item(item_name):
    code = frappe.db.get_value("Item", {"item_name": item_name}, "name")
    if code:
        return code
    doc = frappe.get_doc({
        "doctype": "Item",
        "item_code": item_name,
        "item_name": item_name,
        "item_group": "Raw Material",
        "stock_uom": "Kg",
        "is_stock_item": 1,
    })
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_supplier():
    name = f"{TEST_PREFIX}Supplier"
    if frappe.db.exists("Supplier", {"supplier_name": name}):
        return frappe.db.get_value("Supplier", {"supplier_name": name}, "name")
    doc = frappe.get_doc({
        "doctype": "Supplier",
        "supplier_name": name,
        "supplier_group": "Raw Material",
    })
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_scale(suffix="01", max_capacity=5000):
    """Scrap-usage scale → /pos/terminal (where the Container UI now lives).

    terminal.py redirects sessions on Truck-usage scales to /pos/truck, so a
    Scrap scale is what we want for the container weighing flow.

    All writes go through the document API (validate hooks fire); no direct
    db.set_value.
    """
    scale_name = f"{TEST_PREFIX}Scale-{suffix}"
    existing = frappe.db.get_value("Scale", {"scale_name": scale_name}, "name")
    if existing:
        doc = frappe.get_doc("Scale", existing)
        doc.max_capacity_kg = max_capacity
        doc.usage_type = "Scrap"
        doc.save(ignore_permissions=True)
        return existing
    doc = frappe.get_doc({
        "doctype": "Scale",
        "scale_name": scale_name,
        "scale_type": "Platform",
        "usage_type": "Scrap",
        "location": "Test Bay",
        "is_active": 1,
        "max_capacity_kg": max_capacity,
        "baud_rate": 9600,
        "data_bits": 8,
        "parity": "none",
        "stop_bits": 1,
    })
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_pos_profile(items):
    profile_name = f"{TEST_PREFIX}Profile"
    existing = frappe.db.get_value(
        "POS Profile Scrap", {"profile_name": profile_name}, "name"
    )
    if existing:
        return existing
    price_list = (
        frappe.db.get_value("Price List", {"buying": 1}, "name")
        or "Standard Buying"
    )
    doc = frappe.get_doc({
        "doctype": "POS Profile Scrap",
        "profile_name": profile_name,
        "is_active": 1,
        "price_list": price_list,
        # Enable sticker print so add_container returns print_urls.sticker.
        "enable_sticker_print": 1,
    })
    for code in items:
        if frappe.db.exists("Item", code):
            doc.append("items", {"item_code": code, "item_name": code})
    doc.insert(ignore_permissions=True)
    return doc.name


def _open_admin_session(profile, scale):
    """Close any open session for Administrator, then open a fresh one.

    All writes via document API — uses POSSession.close_session() (the
    controller method) to close existing sessions, then a fresh insert.
    """
    operator = "Administrator"
    for s in frappe.db.get_all(
        "POS Session", filters={"operator": operator, "status": "Open"}
    ):
        prior = frappe.get_doc("POS Session", s.name)
        try:
            prior.close_session()
        except Exception:
            # Fallback: explicit save with status=Closed (still goes through
            # validate, but skips close_session's totals calculation if it
            # complains about the test data).
            prior.status = "Closed"
            prior.save(ignore_permissions=True)
    frappe.db.commit()

    doc = frappe.get_doc({
        "doctype": "POS Session",
        "pos_profile": profile,
        "operator": operator,
        "scale": scale,
        "status": "Open",
        "opening_time": now_datetime(),
    })
    doc.insert(ignore_permissions=True)
    return doc.name


# ---------------------------------------------------------------------------
# Public seed methods (callable via `bench execute`)
# ---------------------------------------------------------------------------

def _ensure_price_lock_with_order(supplier, items_with_prices):
    """Submit a PL → POS Order chain for the seeded supplier.

    Wave 9 forbids walk-in dropoffs, so every Dropoff fixture must link to a
    POS Order. The PL's `on_submit` hook auto-creates the POS Order. Returns
    `(price_lock_name, pos_order_name)`.
    `items_with_prices` is a list of `(item_code, qty_kg, rate)` tuples.
    """
    pl = frappe.get_doc({
        "doctype": "SMT Price Lock",
        "supplier": supplier,
        "po_date": now_datetime(),
        "items": [
            {"item_code": code, "po_qty": qty, "po_rate": rate}
            for code, qty, rate in items_with_prices
        ],
    })
    pl.insert(ignore_permissions=True)
    pl.submit()
    po_name = frappe.db.get_value("POS Order", {"smt_price_lock": pl.name}, "name")
    if not po_name:
        frappe.throw(f"Auto POS Order not created for SMT Price Lock {pl.name}")
    return pl.name, po_name


def seed_pos_truck_scenario():
    """Seed for `test_pos_truck.py::test_add_container_happy_path`.

    Creates a full PL → POS Order → Dropoff chain (Wave 9 invariant: no
    walk-ins) + items, supplier, scale, profile, open Administrator session.
    Returns JSON with the created names.
    """
    cleanup_ui_test_data()

    item_a = _ensure_item(THAI_ITEM_PRIMARY)
    item_b = _ensure_item(THAI_ITEM_SECONDARY)
    supplier = _ensure_supplier()
    scale = _ensure_scale()
    profile = _ensure_pos_profile([item_a, item_b])
    session = _open_admin_session(profile, scale)

    pl_name, po_name = _ensure_price_lock_with_order(
        supplier,
        [
            (item_a, 500, 250.0),
            (item_b, 300, 180.0),
        ],
    )

    dropoff = frappe.get_doc({
        "doctype": "Dropoff",
        "dropoff_scheduled_start": now_datetime(),
        "dropoff_scheduled_end": add_to_date(now_datetime(), hours=2),
        "license_plate": f"{TEST_PREFIX}UI-1234",
        "supplier": supplier,
        "status": "Scheduled",
        "truck_variance_threshold_percent": 100.0,
        "indicated_variance_threshold_percent": 100.0,
        "orders": [{"pos_order": po_name}],
    })
    dropoff.append("expected_items", {"item": item_a, "indicated_weight": 500})
    dropoff.append("expected_items", {"item": item_b, "indicated_weight": 300})
    dropoff.insert(ignore_permissions=True)
    frappe.db.commit()

    payload = {
        "dropoff": dropoff.name,
        "supplier": supplier,
        "session": session,
        "scale": scale,
        "profile": profile,
        "item_a": item_a,
        "item_b": item_b,
        "price_lock": pl_name,
        "pos_order": po_name,
    }
    print("SEED_RESULT:" + json.dumps(payload))
    return payload


def seed_desk_dropoff_needs_review():
    """Seed for `test_desk_dropoff.py::test_mark_verified_override`.

    Drives a Dropoff into `verification_status = "Needs Review"` via
    legitimate state transitions only — no direct DB writes:

      1. insert dropoff as Scheduled with one expected item (500 kg)
      2. open a POS session, weigh ~480 kg via add_container API
         (creates a 4% variance against the 500 kg indicated)
      3. save gross + tare on the dropoff so calculate_net_weight derives
         500 kg net; the auto-transition then promotes status to Completed
      4. calculate_verification_status sees both truck and indicated
         variance fail the 0.1% threshold → flags Needs Review

    Returns the dropoff name.
    """
    from scrap_metal_suite.api.v1.dropoff import add_container

    cleanup_ui_test_data()

    item_a = _ensure_item(THAI_ITEM_PRIMARY)
    supplier = _ensure_supplier()
    scale = _ensure_scale()
    profile = _ensure_pos_profile([item_a])
    session = _open_admin_session(profile, scale)

    # Wave 9 invariant: every Dropoff binds to at least one POS Order.
    _, po_name = _ensure_price_lock_with_order(
        supplier,
        [(item_a, 500, 250.0)],
    )

    dropoff = frappe.get_doc({
        "doctype": "Dropoff",
        "dropoff_scheduled_start": now_datetime(),
        "dropoff_scheduled_end": add_to_date(now_datetime(), hours=2),
        "license_plate": f"{TEST_PREFIX}UI-DESK",
        "supplier": supplier,
        "status": "Scheduled",
        "truck_variance_threshold_percent": 0.1,
        "indicated_variance_threshold_percent": 0.1,
        "orders": [{"pos_order": po_name}],
    })
    dropoff.append("expected_items", {"item": item_a, "indicated_weight": 500})
    dropoff.insert(ignore_permissions=True)
    frappe.db.commit()

    # Weigh 480 kg via the legitimate API path → 4% variance vs indicated.
    add_container(
        dropoff=dropoff.name,
        session=session,
        item_code=item_a,
        net_weight=480.0,
        container_type="Bag",
    )

    # Apply truck weights via document save() so all hooks fire:
    # gross/tare → net=500 → auto-transition to Completed → variance check
    # → verification_status = "Needs Review".
    do = frappe.get_doc("Dropoff", dropoff.name)
    do.gross_weight = 1500
    do.tare_weight = 1000
    do.save(ignore_permissions=True)
    frappe.db.commit()

    payload = {"dropoff": dropoff.name}
    print("SEED_RESULT:" + json.dumps(payload))
    return payload


def cleanup_ui_test_data():
    """Wipe UI test artefacts. Idempotent. Order matters for FKs."""
    # Find test dropoffs by license_plate prefix.
    test_dropoffs = [
        d.name for d in frappe.db.get_all(
            "Dropoff",
            filters={"license_plate": ["like", f"%{TEST_PREFIX}%"]},
            fields=["name"],
        )
    ]

    # 1. Containers attached to test dropoffs (FK back to Dropoff).
    if test_dropoffs:
        for c in frappe.db.get_all(
            "Scrap Weight Container",
            filters={"dropoff": ["in", test_dropoffs]},
            fields=["name"],
        ):
            try:
                frappe.delete_doc(
                    "Scrap Weight Container", c.name,
                    force=True, ignore_permissions=True, delete_permanently=True,
                )
            except Exception as e:
                print(f"Cleanup skipped Container/{c.name}: {e}")

    # 2. Test dropoffs.
    for name in test_dropoffs:
        try:
            frappe.delete_doc(
                "Dropoff", name,
                force=True, ignore_permissions=True, delete_permanently=True,
            )
        except Exception as e:
            print(f"Cleanup skipped Dropoff/{name}: {e}")

    # 2a. Test POS Orders + SMT Price Locks (Wave 9 chain). Filter by supplier
    # carrying our prefix; cancel before delete.
    test_suppliers = [
        s.name for s in frappe.db.get_all(
            "Supplier",
            filters={"supplier_name": ["like", f"%{TEST_PREFIX}%"]},
            fields=["name"],
        )
    ]
    if test_suppliers:
        for po in frappe.db.get_all(
            "POS Order",
            filters={"supplier": ["in", test_suppliers]},
            fields=["name", "docstatus"],
        ):
            try:
                if int(po.docstatus or 0) == 1:
                    frappe.get_doc("POS Order", po.name).cancel()
                frappe.delete_doc(
                    "POS Order", po.name,
                    force=True, ignore_permissions=True, delete_permanently=True,
                )
            except Exception as e:
                print(f"Cleanup skipped POS Order/{po.name}: {e}")
        for pl in frappe.db.get_all(
            "SMT Price Lock",
            filters={"supplier": ["in", test_suppliers]},
            fields=["name", "docstatus"],
        ):
            try:
                if int(pl.docstatus or 0) == 1:
                    frappe.get_doc("SMT Price Lock", pl.name).cancel()
                frappe.delete_doc(
                    "SMT Price Lock", pl.name,
                    force=True, ignore_permissions=True, delete_permanently=True,
                )
            except Exception as e:
                print(f"Cleanup skipped SMT Price Lock/{pl.name}: {e}")

    # 3. Open Administrator sessions — close via document API (no
    #    direct DB writes), then delete.
    for s in frappe.db.get_all(
        "POS Session", filters={"operator": "Administrator"}, fields=["name"]
    ):
        try:
            frappe.delete_doc(
                "POS Session", s.name,
                force=True, ignore_permissions=True, delete_permanently=True,
            )
        except Exception as e:
            print(f"Cleanup skipped POS Session/{s.name}: {e}")

    # 4. Test profile, scale, supplier.
    targets = [
        ("POS Profile Scrap", {"profile_name": ["like", f"%{TEST_PREFIX}%"]}),
        ("Scale", {"scale_name": ["like", f"%{TEST_PREFIX}%"]}),
        ("Supplier", {"supplier_name": ["like", f"%{TEST_PREFIX}%"]}),
    ]
    for dt, filters in targets:
        for d in frappe.db.get_all(dt, filters=filters, fields=["name"]):
            try:
                frappe.delete_doc(
                    dt, d.name,
                    force=True, ignore_permissions=True, delete_permanently=True,
                )
            except Exception as e:
                print(f"Cleanup skipped {dt}/{d.name}: {e}")

    frappe.db.commit()
