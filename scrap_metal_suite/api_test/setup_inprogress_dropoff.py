"""One-shot fixture: clean prior test data, create a fresh PL→PO→DO with an
open session and 3 containers — leaves the Dropoff in `In Progress` status so
you can poke at the three-pane terminal UI without hitting the
already-Completed lock errors."""

import frappe

from scrap_metal_suite.api_test import test_container_workflow as wf


def run():
    frappe.set_user("Administrator")

    # Clean up previous CTNWF-prefixed fixtures end-to-end.
    wf.cleanup_test_data()

    # Bootstrap masters + PL → PO → DO → session → 3 bags.
    wf.ensure_user(wf.TEST_OPERATOR, ["POS Operator", "System Manager"])
    wf.ensure_item(wf.THAI_ITEM_PRIMARY)
    wf.ensure_item(wf.THAI_ITEM_SECONDARY)
    wf.ensure_item(wf.THAI_ITEM_TERTIARY)
    supplier = wf.ensure_supplier()
    scale = wf.ensure_scale()
    profile = wf.ensure_pos_profile()

    pl_name, po_name = wf.make_price_lock(supplier, [
        (wf.THAI_ITEM_PRIMARY, 1500, 250.0),
        (wf.THAI_ITEM_SECONDARY, 800, 180.0),
        (wf.THAI_ITEM_TERTIARY, 400, 120.0),
    ])
    dropoff = wf.make_dropoff(supplier, [
        (wf.THAI_ITEM_PRIMARY, 1500),
        (wf.THAI_ITEM_SECONDARY, 800),
        (wf.THAI_ITEM_TERTIARY, 400),
    ], pos_order_name=po_name)

    # NO containers pre-added and NO session opened — leave the Dropoff in
    # Scheduled status with no scale/session lock. When you open the terminal
    # in the browser, your own session picks up the lock cleanly. This avoids
    # the "Dropoff is locked to session X" error from a pre-baked lock that
    # doesn't match your browser's session.
    frappe.db.commit()

    print("=" * 70)
    print("Three-pane terminal test fixture ready (Scheduled, unlocked)")
    print("=" * 70)
    print(f"Price Lock:  {pl_name}        →  /app/smt-price-lock/{pl_name}")
    print(f"POS Order:   {po_name}        →  /app/pos-order/{po_name}")
    print(f"Dropoff:     {dropoff.name}   →  /app/dropoff/{dropoff.name}")
    print(f"Status:      Scheduled (no containers yet, no session lock)")
    print("")
    print(f"Open the terminal at:  /pos/terminal")
    print(f"  (this picks up YOUR session automatically — no URL param needed)")
    print(f"Then enter or scan:  {dropoff.name}")
    print("")
    print("You should see:")
    print("  • LEFT pane:    Items (3 grade buttons)")
    print("  • MIDDLE pane:  Dropoff context + active grade picker + weigh card")
    print("  • RIGHT pane:   Containers journal showing the 3 bags weighed")
    print("                  • Each row: bag #, grade, weight, status badge")
    print("                  • Reweigh / Print Sticker / Void buttons per row")
    print("")
    print("Try:  pick a grade in LEFT, type a weight, hit Save & Print Sticker.")
    print("      The new bag should appear in the RIGHT pane immediately.")
