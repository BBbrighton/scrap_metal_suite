# Copyright (c) 2026, SMT and contributors
# For license information, please see license.txt

"""One lookup for both directions of trade.

The weighbridge does not care which way the goods are going: a truck arrives, is
weighed twice, and leaves. What differs is the order of the two weighings and
what the difference is checked against.

    Dropoff (buy)   arrives LOADED  -> gross, unload, -> tare (empty)
    Pickup  (sell)  arrives EMPTY   -> tare,  load,   -> gross (loaded)

So the terminal is one screen, and what it scans decides how it behaves. This
module answers "what is this truck here for?" - the rest of the terminal reads
`doctype` off the answer and adapts.

Called a *visit* rather than a work order: ERPNext already has a `Work Order`
doctype for manufacturing, and colliding with it would confuse every future
reader.
"""

import frappe
from frappe.utils import add_to_date, get_datetime, nowdate

from scrap_metal_suite.api.v1.auth import check_pos_operator

# How far either side of today a partial search will look.
SEARCH_WINDOW_DAYS = 3


def _dropoff_rows(query, exact_only=False):
    fields = "name, dropoff_scheduled_start AS scheduled, license_plate, supplier_name AS party_name, status"
    if exact_only:
        return frappe.db.sql(
            "SELECT {0} FROM `tabDropoff` WHERE name = %(q)s OR license_plate = %(q)s".format(fields),
            {"q": query}, as_dict=True)

    today = nowdate()
    start = get_datetime(add_to_date(today, days=-SEARCH_WINDOW_DAYS)).replace(hour=0, minute=0, second=0)
    end = get_datetime(add_to_date(today, days=SEARCH_WINDOW_DAYS)).replace(hour=23, minute=59, second=59)
    return frappe.db.sql("""
        SELECT {0} FROM `tabDropoff`
        WHERE dropoff_scheduled_start >= %(start)s AND dropoff_scheduled_start <= %(end)s
          AND (name LIKE %(q)s OR license_plate LIKE %(q)s)
        ORDER BY dropoff_scheduled_start DESC, creation DESC LIMIT 10
    """.format(fields), {"start": start, "end": end, "q": "%{0}%".format(query)}, as_dict=True)


def _pickup_rows(query, exact_only=False):
    fields = "name, scheduled_start AS scheduled, license_plate, customer_name AS party_name, status"
    if exact_only:
        return frappe.db.sql(
            "SELECT {0} FROM `tabPickup` WHERE name = %(q)s OR license_plate = %(q)s".format(fields),
            {"q": query}, as_dict=True)

    today = nowdate()
    start = get_datetime(add_to_date(today, days=-SEARCH_WINDOW_DAYS)).replace(hour=0, minute=0, second=0)
    end = get_datetime(add_to_date(today, days=SEARCH_WINDOW_DAYS)).replace(hour=23, minute=59, second=59)
    # A Pickup may be booked without a scheduled time; a delivery always has one.
    # Falling back to `creation` keeps same-day walk-up collections findable.
    return frappe.db.sql("""
        SELECT {0} FROM `tabPickup`
        WHERE COALESCE(scheduled_start, creation) >= %(start)s
          AND COALESCE(scheduled_start, creation) <= %(end)s
          AND (name LIKE %(q)s OR license_plate LIKE %(q)s)
        ORDER BY COALESCE(scheduled_start, creation) DESC, creation DESC LIMIT 10
    """.format(fields), {"start": start, "end": end, "q": "%{0}%".format(query)}, as_dict=True)


@frappe.whitelist()
def lookup_visit(query):
    """Find what a truck is here for, on either side of the yard.

    Searches deliveries and collections together. Every row carries its own
    `doctype`, so the terminal never has to guess.

    A plate can legitimately match both - the same truck can deliver in the
    morning and collect in the afternoon - so this returns every match rather
    than picking one. Guessing wrong would weigh a truck against the wrong
    document, and the mistake would not surface until settlement.

    Args:
        query: document name (DO-... / PU-...) or a license plate

    Returns:
        list: rows of {doctype, name, scheduled, license_plate, party_name, status}
    """
    check_pos_operator()

    if not query or len(query.strip()) < 2:
        return []
    query = query.strip()

    # Exact first, across both sides, so a scanned QR resolves in one step.
    rows = []
    for doctype, fn in (("Dropoff", _dropoff_rows), ("Pickup", _pickup_rows)):
        for r in fn(query, exact_only=True):
            r["doctype"] = doctype
            rows.append(r)
    if rows:
        return rows

    for doctype, fn in (("Dropoff", _dropoff_rows), ("Pickup", _pickup_rows)):
        for r in fn(query):
            r["doctype"] = doctype
            rows.append(r)

    rows.sort(key=lambda r: (r.get("scheduled") or ""), reverse=True)
    return rows[:10]


@frappe.whitelist()
def get_visit_flow(doctype):
    """How the terminal should behave for this kind of visit.

    Kept on the server so the two sides cannot drift apart in the UI: the order
    of the weighings is a property of the trade, not of the screen.
    """
    check_pos_operator()

    if doctype == "Dropoff":
        return {
            "doctype": "Dropoff",
            "direction": "in",
            "first_weight": "gross",   # arrives loaded
            "second_weight": "tare",   # leaves empty
            "party_label": "Supplier",
            "record_method": "scrap_metal_suite.api.v1.dropoff.record_truck_weight",
            "party_field": "dropoff",
        }
    if doctype == "Pickup":
        return {
            "doctype": "Pickup",
            "direction": "out",
            "first_weight": "tare",    # arrives empty
            "second_weight": "gross",  # leaves loaded
            "party_label": "Customer",
            "record_method": "scrap_metal_suite.api.v1.pickup.record_pickup_weight",
            "party_field": "pickup",
            "print_format": "ใบชั่งน้ำหนักขาออก",
        }

    frappe.throw(frappe._("Unknown visit type: {0}").format(doctype))
