# Demo data seeder — builds the full chain UP TO a settled-ready Dropoff Final,
# so the SMT Purchase Order settlement flow can be exercised by hand in the desk.
#
#   Price Lock -> POS Order -> Dropoff -> Containers -> Production Sorting
#                                                            -> Dropoff Final (Unsettled)
#
# Everything is built through the real APIs, not direct DB writes, so the data
# is indistinguishable from a genuine day's work.
#
#   bench --site metal execute scrap_metal_suite.api_test.seed_settlement_demo.run
#   bench --site metal execute scrap_metal_suite.api_test.seed_settlement_demo.cleanup
#
# The scenario is shaped deliberately to exercise v2 partial settlement:
#
#   * 1,380 kg of good material across THREE items, so one Dropoff Final can be
#     drawn down by several PO Finals.
#   * ทองแดงเกรดบี (Grade B) is produced by SORTING and has NO Price Lock — a
#     downgrade. It can only be settled as a Spot line (design UC-4).
#   * 20 kg of unwanted material, which must never appear in the pull dialog and
#     must never be paid for.

import json

import frappe
from frappe.utils import add_to_date, now_datetime

PREFIX = "_DEMO_"
SUPPLIER_NAME = f"{PREFIX}Siam Metal Trading"
SUPPLIER_SHORT = "DEMO"

# Canonical Thai item names — never translated (see feedback_never_translate_item_names).
ITEM_CU_A = "ทองแดงเกรดเอ"
ITEM_CU_B = "ทองแดงเกรดบี"
ITEM_ALU = "อลูมิเนียมแผ่น"

# Bags as they come off the truck: (item, kg)
CONTAINERS = [
    (ITEM_CU_A, 200),
    (ITEM_CU_A, 200),
    (ITEM_CU_A, 200),
    (ITEM_CU_A, 200),
    (ITEM_CU_A, 200),
    (ITEM_ALU, 200),
    (ITEM_ALU, 200),
]

TRUCK_GROSS = 5400.0
TRUCK_TARE = 4000.0  # net 1400 == the seven bags


# ---------------------------------------------------------------------------
# Master data
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
    existing = frappe.db.get_value("Supplier", {"supplier_name": SUPPLIER_NAME}, "name")
    if existing:
        # short_code drives every docname in the chain (PLO-DEMO-..., DO-DEMO-...)
        if frappe.db.get_value("Supplier", existing, "short_code") != SUPPLIER_SHORT:
            frappe.db.set_value("Supplier", existing, "short_code", SUPPLIER_SHORT)
        return existing
    doc = frappe.get_doc({
        "doctype": "Supplier",
        "supplier_name": SUPPLIER_NAME,
        "supplier_group": "Raw Material",
        "short_code": SUPPLIER_SHORT,
    })
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_scale():
    name = f"{PREFIX}Scale"
    existing = frappe.db.get_value("Scale", {"scale_name": name}, "name")
    if existing:
        return existing
    doc = frappe.get_doc({
        "doctype": "Scale",
        "scale_name": name,
        "scale_type": "Platform",
        "usage_type": "Scrap",
        "location": "Demo Bay",
        "is_active": 1,
        "max_capacity_kg": 5000,
        "baud_rate": 9600,
        "data_bits": 8,
        "parity": "none",
        "stop_bits": 1,
    })
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_profile(items):
    name = f"{PREFIX}Profile"
    existing = frappe.db.get_value("POS Profile Scrap", {"profile_name": name}, "name")
    if existing:
        return existing
    price_list = frappe.db.get_value("Price List", {"buying": 1}, "name") or "Standard Buying"
    doc = frappe.get_doc({
        "doctype": "POS Profile Scrap",
        "profile_name": name,
        "is_active": 1,
        "price_list": price_list,
        "enable_sticker_print": 1,
    })
    for code in items:
        doc.append("items", {"item_code": code, "item_name": code})
    doc.insert(ignore_permissions=True)
    return doc.name


def _open_pos_session(profile, scale):
    for s in frappe.get_all("POS Session", filters={"operator": "Administrator", "status": "Open"}):
        prior = frappe.get_doc("POS Session", s.name)
        try:
            prior.close_session()
        except Exception:
            prior.status = "Closed"
            prior.save(ignore_permissions=True)
    frappe.db.commit()

    doc = frappe.get_doc({
        "doctype": "POS Session",
        "pos_profile": profile,
        "operator": "Administrator",
        "scale": scale,
        "status": "Open",
        "opening_time": now_datetime(),
    })
    doc.insert(ignore_permissions=True)
    return doc.name


def _open_production_session():
    for s in frappe.get_all("Production Session", filters={"operator": "Administrator", "status": "Open"}):
        frappe.db.set_value("Production Session", s.name, "status", "Closed")
    frappe.db.commit()

    from scrap_metal_suite.api.v1 import production as papi
    # NB: open_session returns {"session": ...}, not {"name": ...}
    return papi.open_session()["session"]


# ---------------------------------------------------------------------------
# The chain
# ---------------------------------------------------------------------------

def run():
    """Entry point. Wraps _seed() so real errors are visible.

    `bench execute` calls the target, and if that raises it retries via a bare
    `eval(method + "(...)")`, which fails with a bare
    `NameError: name 'scrap_metal_suite' is not defined` — masking whatever
    actually went wrong. Printing the traceback here keeps the real cause.
    """
    import traceback
    try:
        return _seed()
    except Exception:
        print("\n!!! SEED FAILED !!!")
        traceback.print_exc()
        raise


def _seed():
    frappe.set_user("Administrator")

    from scrap_metal_suite.api.v1 import dropoff as dapi
    from scrap_metal_suite.api.v1 import production as papi

    print("=" * 72)
    print("SEEDING SETTLEMENT DEMO DATA  (Price Lock -> ... -> Dropoff Final)")
    print("=" * 72)

    cu_a = _ensure_item(ITEM_CU_A)
    cu_b = _ensure_item(ITEM_CU_B)
    alu = _ensure_item(ITEM_ALU)
    supplier = _ensure_supplier()
    scale = _ensure_scale()
    profile = _ensure_profile([cu_a, cu_b, alu])
    session = _open_pos_session(profile, scale)
    print(f"  master data ok — supplier {supplier} (short_code {SUPPLIER_SHORT})")

    # --- 1. Price Lock. Note there is NO lock for Grade B: it only comes into
    #        existence during sorting, so it has to be settled as Spot.
    pl = frappe.get_doc({
        "doctype": "SMT Price Lock",
        "supplier": supplier,
        "po_date": now_datetime(),
        "notes": "Demo lock — Grade B is deliberately uncovered, settle it as Spot.",
        "items": [
            {"item_code": cu_a, "po_qty": 1000, "po_rate": 300},
            {"item_code": alu, "po_qty": 400, "po_rate": 75},
        ],
    })
    pl.insert(ignore_permissions=True)
    pl.submit()
    pos_order = frappe.db.get_value("POS Order", {"smt_price_lock": pl.name}, "name")
    print(f"  1. Price Lock   {pl.name}  (1,000 kg Cu-A @ 300 + 400 kg Alu @ 75 = ฿337,500)")
    print(f"  2. POS Order    {pos_order}  (auto-created on submit)")

    # --- 3. Dropoff, bound to that order (Wave 9: no walk-ins)
    dropoff = frappe.get_doc({
        "doctype": "Dropoff",
        "supplier": supplier,
        "status": "Scheduled",
        "license_plate": f"{PREFIX}70-1234",
        "dropoff_scheduled_start": now_datetime(),
        "dropoff_scheduled_end": add_to_date(now_datetime(), hours=3),
        "orders": [{"pos_order": pos_order}],
    })
    dropoff.append("expected_items", {"item": cu_a, "indicated_weight": 1000})
    dropoff.append("expected_items", {"item": alu, "indicated_weight": 400})
    dropoff.insert(ignore_permissions=True)
    frappe.db.commit()
    print(f"  3. Dropoff      {dropoff.name}")

    # --- 4. Weigh the bags
    containers = []
    for item_code, kg in CONTAINERS:
        res = dapi.add_container(
            dropoff=dropoff.name,
            session=session,
            item_code=item_code,
            net_weight=kg,
            container_type="Bag",
            entry_method="Manual Entry",
        )
        containers.append({"name": res["container"], "item": item_code, "kg": kg})
    frappe.db.commit()
    print(f"  4. Containers   {len(containers)} bags, {sum(c['kg'] for c in containers):,.0f} kg")

    # --- 5. Close weighing, record the truck, complete
    dapi.finish_weighing_session(dropoff=dropoff.name)
    do = frappe.get_doc("Dropoff", dropoff.name)
    do.gross_weight = TRUCK_GROSS
    do.tare_weight = TRUCK_TARE
    do.save(ignore_permissions=True)
    frappe.db.commit()

    dapi.complete_dropoff(dropoff=dropoff.name)
    do = frappe.get_doc("Dropoff", dropoff.name)
    if do.verification_status == "Needs Review":
        dapi.verify_dropoff(dropoff=dropoff.name, override_reason="Demo data — variance accepted")
    frappe.db.commit()
    do = frappe.get_doc("Dropoff", dropoff.name)
    print(f"  5. Truck        {TRUCK_GROSS:,.0f} - {TRUCK_TARE:,.0f} = {TRUCK_GROSS - TRUCK_TARE:,.0f} kg net"
          f"  |  Dropoff {do.status} / {do.verification_status}")

    # --- 6. Sort, per container. Bag 5 is where the downgrade happens: 200 kg
    #        of Cu-A in, 100 Cu-A + 80 Cu-B + 20 dirt out.
    good_items = []
    unwanted_items = []
    for idx, c in enumerate(containers):
        if c["item"] == ITEM_ALU:
            good_items.append({"container": c["name"], "item_code": alu, "weight": c["kg"], "uom": "Kg"})
        elif idx == 4:
            good_items.append({"container": c["name"], "item_code": cu_a, "weight": 100, "uom": "Kg"})
            good_items.append({"container": c["name"], "item_code": cu_b, "weight": 80, "uom": "Kg"})
            unwanted_items.append({
                "container": c["name"], "item_code": cu_a, "weight": 20, "uom": "Kg",
                "return_reason": "Contamination", "remarks": "Dirt and moisture",
            })
        else:
            good_items.append({"container": c["name"], "item_code": cu_a, "weight": c["kg"], "uom": "Kg"})

    prod_session = _open_production_session()
    sorting = papi.create_sorting(
        session=prod_session,
        dropoff=dropoff.name,
        good_items=json.dumps(good_items),
        unwanted_items=json.dumps(unwanted_items),
    )
    frappe.db.commit()
    print(f"  6. Sorting      {sorting['name']}  good {sorting['total_good_weight']:,.0f} kg"
          f" / unwanted {sorting['total_unwanted_weight']:,.0f} kg")

    # --- 7. Dropoff Final is created automatically on sorting submit
    dfl_name = frappe.db.get_value("Dropoff Final", {"dropoff": dropoff.name}, "name")
    dfl = frappe.get_doc("Dropoff Final", dfl_name)
    print(f"  7. Dropoff Final {dfl.name}   status = {dfl.status}")
    print()
    print("  Ready to settle:")
    for row in dfl.good_items:
        print(f"      {row.item_name:<20} {row.weight:>9,.3f} kg   remaining {row.remaining_qty:>9,.3f} kg")
    for row in dfl.unwanted_items:
        print(f"      {row.item_name:<20} {row.weight:>9,.3f} kg   (unwanted — never paid)")

    print()
    print("=" * 72)
    print("NEXT — exercise partial settlement by hand:")
    print(f"  1. New SMT Purchase Order, supplier = {SUPPLIER_NAME}")
    print(f"  2. Add {dfl.name} to 'Dropoff Finals Drawn From'")
    print("  3. Click 'Pull Items from Dropoff Finals'")
    print("  4. Pull only PART of the copper (e.g. 500 of 900) and submit")
    print(f"     -> {dfl.name} becomes 'Partially Settled', not 'Settled'")
    print("  5. Make a second SMT Purchase Order and pull the rest")
    print(f"     -> {ITEM_CU_B} has no Price Lock, so it must go in as Spot")
    print("=" * 72)

    payload = {
        "supplier": supplier,
        "price_lock": pl.name,
        "pos_order": pos_order,
        "dropoff": dropoff.name,
        "sorting": sorting["name"],
        "dropoff_final": dfl.name,
        "dfl_status": dfl.status,
        "good_items": [
            {"item": r.item_code, "weight": r.weight, "remaining": r.remaining_qty}
            for r in dfl.good_items
        ],
    }
    return payload


# ---------------------------------------------------------------------------

def cleanup():
    """Remove everything this seeder created, in reverse dependency order."""
    frappe.set_user("Administrator")
    supplier = frappe.db.get_value("Supplier", {"supplier_name": SUPPLIER_NAME}, "name")
    if not supplier:
        print("nothing to clean")
        return

    def _wipe(doctype, filters, cancel_first=False):
        for name in frappe.get_all(doctype, filters=filters, pluck="name"):
            try:
                if cancel_first:
                    doc = frappe.get_doc(doctype, name)
                    if doc.docstatus == 1:
                        doc.flags.ignore_links = True
                        doc.cancel()
                frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
            except Exception as e:
                print(f"  skip {doctype} {name}: {str(e)[:90]}")

    _wipe("SMT Purchase Order", {"supplier": supplier}, cancel_first=True)
    _wipe("Purchase Invoice", {"supplier": supplier}, cancel_first=True)

    for do in frappe.get_all("Dropoff", filters={"supplier": supplier}, pluck="name"):
        _wipe("Dropoff Final", {"dropoff": do})
        _wipe("Production Sorting", {"dropoff": do}, cancel_first=True)
        _wipe("Scrap Weight", {"dropoff": do}, cancel_first=True)
        _wipe("Scrap Weight Container", {"dropoff": do}, cancel_first=True)
    _wipe("Dropoff", {"supplier": supplier})
    _wipe("POS Order", {"supplier": supplier}, cancel_first=True)

    for name in frappe.get_all("SMT Price Lock", filters={"supplier": supplier}, pluck="name"):
        try:
            doc = frappe.get_doc("SMT Price Lock", name)
            if doc.docstatus == 1:
                for row in doc.items:
                    frappe.db.set_value("SMT Price Lock Item", row.name,
                                        {"settled_qty": 0, "remaining_qty": row.po_qty})
                doc.reload()
                doc.cancel()
            frappe.delete_doc("SMT Price Lock", name, force=True, ignore_permissions=True)
        except Exception as e:
            print(f"  skip Price Lock {name}: {str(e)[:90]}")

    _wipe("POS Session", {"pos_profile": ["like", f"%{PREFIX}%"]})
    _wipe("POS Profile Scrap", {"profile_name": ["like", f"%{PREFIX}%"]})
    _wipe("Scale", {"scale_name": ["like", f"%{PREFIX}%"]})
    _wipe("Supplier", {"name": supplier})

    frappe.db.commit()
    print("demo data removed (Thai items left in place — they are shared master data)")
