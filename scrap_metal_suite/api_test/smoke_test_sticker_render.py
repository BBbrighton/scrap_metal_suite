"""Smoke test: spin up a minimal Dropoff + Container, render the sticker print
format, assert all 6 required fields plus a valid QR data URI are present, and
clean up. Self-contained so it runs without depending on workflow-test
leftovers."""

import frappe
from frappe.www.printview import get_html_and_style


PREFIX = "_TEST_PR_"


def _ensure_supplier() -> str:
    name = f"{PREFIX}Supplier"
    if frappe.db.exists("Supplier", name):
        return name
    s = frappe.get_doc({
        "doctype": "Supplier",
        "supplier_name": name,
        "supplier_group": frappe.db.get_value("Supplier Group", {}, "name") or "All Supplier Groups",
        "supplier_type": "Company",
    })
    s.insert(ignore_permissions=True)
    return s.name


def _ensure_item() -> str:
    code = f"{PREFIX}ทองแดงปอก"
    if frappe.db.exists("Item", code):
        return code
    grp = frappe.db.get_value("Item Group", {}, "name") or "All Item Groups"
    uom = frappe.db.get_value("UOM", {}, "name") or "Kg"
    i = frappe.get_doc({
        "doctype": "Item",
        "item_code": code,
        "item_name": code,  # canonical Thai = code
        "item_group": grp,
        "stock_uom": uom,
    })
    i.insert(ignore_permissions=True)
    return code


def _ensure_scale() -> str:
    name = f"{PREFIX}Scale-01"
    if frappe.db.exists("Scale", name):
        return name
    s = frappe.get_doc({
        "doctype": "Scale",
        "scale_id": name,
        "scale_name": name,
        "max_capacity_kg": 5000,
    })
    s.insert(ignore_permissions=True)
    return s.name


def _ensure_dropoff(supplier: str) -> str:
    existing = frappe.db.get_value(
        "Dropoff",
        {"supplier": supplier, "status": ["in", ["Scheduled", "In Progress"]]},
        "name",
    )
    if existing:
        return existing
    d = frappe.get_doc({
        "doctype": "Dropoff",
        "supplier": supplier,
        "license_plate": f"{PREFIX}PLATE-99",
        "dropoff_scheduled_start": frappe.utils.now_datetime(),
        "status": "Scheduled",
    })
    d.insert(ignore_permissions=True)
    return d.name


def _ensure_session(scale: str) -> str:
    operator = "Administrator"
    profile = frappe.db.get_value("POS Profile Scrap", {"is_active": 1}, "name")
    if not profile:
        # Minimal profile.
        item = _ensure_item()
        price_list = frappe.db.get_value("Price List", {"buying": 1}, "name") or "Standard Buying"
        p = frappe.get_doc({
            "doctype": "POS Profile Scrap",
            "profile_name": f"{PREFIX}Profile",
            "is_active": 1,
            "price_list": price_list,
            "enable_sticker_print": 1,
        })
        p.append("items", {"item_code": item, "item_name": item})
        p.insert(ignore_permissions=True)
        profile = p.name
    # Close any prior open session for the operator (one-open-per-operator).
    for s in frappe.db.get_all(
        "POS Session", filters={"operator": operator, "status": "Open"}
    ):
        frappe.db.set_value(
            "POS Session", s.name, "status", "Closed", update_modified=False
        )
    s = frappe.get_doc({
        "doctype": "POS Session",
        "operator": operator,
        "pos_profile": profile,
        "scale": scale,
        "opening_amount": 0,
        "status": "Open",
    })
    s.insert(ignore_permissions=True)
    return s.name


def _check_html(html: str, ctn: dict) -> tuple[bool, dict]:
    has_img = "<img" in html
    has_data_uri = "data:image/png;base64" in html
    has_unrendered_jinja = "qr_src(" in html or "qr_data_uri(" in html
    date_source = ctn["last_reweigh_at"] if ctn.get("is_reweighed") and ctn.get("last_reweigh_at") else ctn["creation"]
    fields = {
        "1. Drop-off ID": ctn["dropoff"] in html,
        "2. Supplier name": bool(ctn.get("supplier_name")) and ctn["supplier_name"] in html,
        "3. Date": date_source.strftime("%Y-%m-%d") in html,
        "4. Item name": ctn["item_name"] in html,
        "5. Operator name": (ctn.get("operator_name") or ctn.get("operator") or "") in html,
        "6. License plate": bool(ctn.get("license_plate")) and ctn["license_plate"] in html,
    }
    ok = has_img and has_data_uri and not has_unrendered_jinja and all(fields.values())
    return ok, {
        "<img>": has_img,
        "data:image/png;base64": has_data_uri,
        "no unrendered jinja": not has_unrendered_jinja,
        **fields,
    }


def run():
    supplier = _ensure_supplier()
    _ = _ensure_item()
    scale = _ensure_scale()
    dropoff = _ensure_dropoff(supplier)
    session = _ensure_session(scale)

    container = None
    try:
        c = frappe.get_doc({
            "doctype": "Scrap Weight Container",
            "dropoff": dropoff,
            "session": session,
            "scale": scale,
            "operator": "Administrator",
            "item_code": _ensure_item(),
            "container_type": "Bag",
            "net_weight": 246.4,
            "entry_method": "Manual Entry",
        })
        c.insert(ignore_permissions=True)
        container = c.name

        ctn = frappe.db.get_value(
            "Scrap Weight Container",
            container,
            [
                "name", "dropoff", "supplier", "supplier_name", "license_plate",
                "operator", "operator_name", "item_name", "creation",
                "is_reweighed", "last_reweigh_at",
            ],
            as_dict=True,
        )

        print(f"Container: {container}")
        for k, v in ctn.items():
            print(f"  {k}: {v}")

        out = get_html_and_style(
            doc="Scrap Weight Container",
            name=container,
            print_format="Scrap Weight Container Sticker",
        )
        html = out.get("html", "") if isinstance(out, dict) else str(out)
        ok, results = _check_html(html, ctn)
        print(f"\nRendered HTML length: {len(html)}")
        for label, passed in results.items():
            print(f"  {'OK ' if passed else 'X  '} {label}")
        print(f"\n{'PASS' if ok else 'FAIL'}: sticker render with all 6 required fields")
    finally:
        if container and frappe.db.exists("Scrap Weight Container", container):
            frappe.delete_doc("Scrap Weight Container", container, force=True, ignore_permissions=True)
        # Leave dropoff/session/supplier/scale intact for re-runs.
        frappe.db.commit()
