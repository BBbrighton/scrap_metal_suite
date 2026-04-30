import frappe
from frappe.www.printview import get_html_and_style


CONTAINER_NAME = None  # auto-pick the most recent container if not set


def _check(html: str, fmt: str, ctn: dict):
    print(f"\n=== {fmt} (len={len(html)}) ===")
    has_img = "<img" in html
    has_data_uri = "data:image/png;base64" in html
    has_unrendered_jinja = "qr_src(" in html or "qr_data_uri(" in html

    # 6 required sticker fields (per PR spec):
    #   1. Drop-off ID  2. Supplier name  3. Date
    #   4. Item name    5. Operator       6. Truck plate
    # Date semantics: last_reweigh_at if reweighed, else creation.
    date_source = ctn["last_reweigh_at"] if ctn.get("is_reweighed") and ctn.get("last_reweigh_at") else ctn["creation"]
    required = {
        "1. Drop-off ID": ctn["dropoff"] in html,
        "2. Supplier name": (ctn.get("supplier_name") or "") in html and bool(ctn.get("supplier_name")),
        "3. Date": date_source.strftime("%Y-%m-%d") in html,
        "4. Item name": ctn["item_name"] in html,
        "5. Operator name": (ctn.get("operator_name") or ctn.get("operator") or "") in html,
        "6. License plate": (ctn.get("license_plate") or "") in html and bool(ctn.get("license_plate")),
    }

    print("has <img:                ", has_img)
    print("has data:image/png;base64:", has_data_uri)
    print("unrendered jinja leaked: ", has_unrendered_jinja)
    for label, ok in required.items():
        print(f"  {label}: {'OK' if ok else 'MISSING'}")

    return has_img and has_data_uri and not has_unrendered_jinja and all(required.values())


def _pick_container() -> str | None:
    if CONTAINER_NAME and frappe.db.exists("Scrap Weight Container", CONTAINER_NAME):
        return CONTAINER_NAME
    # Prefer one with snapshot fields populated; otherwise any container.
    for filters in (
        {"supplier_name": ["!=", ""], "license_plate": ["!=", ""]},
        {},
    ):
        rows = frappe.db.get_all(
            "Scrap Weight Container",
            filters=filters,
            fields=["name"],
            order_by="creation desc",
            limit=1,
        )
        if rows:
            return rows[0].name
    return None


def run():
    name = _pick_container()
    if not name:
        print("SKIP: no Scrap Weight Container in DB (run after the workflow test, or use a non-cleanup fixture)")
        return
    ctn = frappe.db.get_value(
        "Scrap Weight Container",
        name,
        [
            "name",
            "dropoff",
            "supplier",
            "supplier_name",
            "license_plate",
            "operator",
            "operator_name",
            "item_name",
            "creation",
            "is_reweighed",
            "last_reweigh_at",
        ],
        as_dict=True,
    )
    print(f"Picked container: {name}")
    print("Container snapshot:")
    for k, v in ctn.items():
        print(f"  {k}: {v}")

    fmt = "Scrap Weight Container Sticker"
    out = get_html_and_style(
        doc="Scrap Weight Container",
        name=name,
        print_format=fmt,
    )
    html = out.get("html", "") if isinstance(out, dict) else str(out)
    ok = _check(html, fmt, ctn)
    print("\n=== RESULT ===")
    if not ok:
        print(f"FAILED: {fmt}")
    else:
        print("PASS: sticker renders with all 6 required fields + valid QR")
