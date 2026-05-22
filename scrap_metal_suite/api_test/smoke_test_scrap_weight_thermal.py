"""Render the newest submitted Scrap Weight via the rebound `Scrap Weight Thermal`
print format. Confirms the Wave 10 schema-rebind doesn't blow up Jinja and the
key fields render."""

import frappe
from frappe.www.printview import get_html_and_style


def run():
    # Pick a submitted SW whose Dropoff still exists.
    rows = frappe.db.get_all(
        "Scrap Weight",
        filters={"docstatus": 1},
        fields=["name", "dropoff", "docstatus", "supplier_name", "is_amended",
                "amend_reason", "amended_from", "total_weight", "total_container_count"],
        order_by="creation desc",
        limit=20,
    )
    sw = next((r for r in rows if r.dropoff and frappe.db.exists("Dropoff", r.dropoff)), None)
    if not sw:
        print("no Scrap Weight with valid Dropoff to render — run test_finish_weighing_session first with cleanup_after=False")
        return
    print(f"Rendering Scrap Weight: {sw.name}")
    for k, v in sw.items():
        print(f"  {k}: {v}")

    out = get_html_and_style(
        doc="Scrap Weight",
        name=sw.name,
        print_format="Scrap Weight Thermal",
    )
    html = out.get("html", "") if isinstance(out, dict) else str(out)

    checks = {
        "rendered (>500 chars)": len(html) > 500,
        "has SW name": sw.name in html,
        "has dropoff link": (sw.dropoff or "") in html,
        "has supplier name": (sw.supplier_name or "_NONE_") in html,
        "no unrendered jinja": "{{" not in html and "{%" not in html,
        "has at least 1 QR data URI": "data:image/png;base64" in html,
    }
    if sw.is_amended:
        checks["AMENDED watermark present"] = "ฉบับแก้ไข" in html or "AMENDED" in html
        if sw.amended_from:
            checks["amended_from reference shown"] = sw.amended_from in html

    print(f"\nRendered HTML length: {len(html)}")
    failed = []
    for label, ok in checks.items():
        print(f"  {'OK ' if ok else 'X  '} {label}")
        if not ok:
            failed.append(label)
    print(f"\n{'FAIL' if failed else 'PASS'}: Scrap Weight Thermal renders Wave 10 schema")
    return {"passed": 0 if failed else 1, "failed": len(failed)}
