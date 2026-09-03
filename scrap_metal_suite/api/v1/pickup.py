# Copyright (c) 2026, SMT and contributors
# For license information, please see license.txt

"""Sale-side weighbridge API - the mirror of `dropoff.record_truck_weight`.

A collection reverses the delivery flow: the truck arrives EMPTY and is weighed
(tare), loads, then leaves LOADED and is weighed again (gross). So `net_weight`
is what physically left the site, and the second weighing is the heavy one.

Deliberately mirrors dropoff.py's shape - same argument names, same validation
order, same reweight rules - so that an operator's muscle memory and a
developer's expectations both carry across from one side to the other.
"""

import frappe
from frappe import _
from frappe.utils import flt, now_datetime, sanitize_html

from scrap_metal_suite.api.v1.auth import check_pos_operator
from scrap_metal_suite.api.v1.dropoff import _update_session_activity


def _validate_weight_against_scale(weight, scale):
    """Shared checks: a real number, positive, and within the scale's range."""
    try:
        weight = float(weight)
    except (ValueError, TypeError):
        frappe.throw(_("Invalid weight value"))

    if weight <= 0:
        frappe.throw(_("Weight must be greater than 0"))

    if scale:
        scale_info = frappe.db.get_value(
            "Scale", scale, ["max_capacity_kg", "scale_name"], as_dict=True
        )
        if not scale_info:
            frappe.throw(_("Scale not found: {0}").format(scale))
        if scale_info.max_capacity_kg and weight > scale_info.max_capacity_kg:
            frappe.throw(_("Weight {0} kg exceeds scale {1} capacity of {2} kg").format(
                weight, scale_info.scale_name, scale_info.max_capacity_kg
            ))

    return weight


@frappe.whitelist()
def record_pickup_weight(pickup, weight_type, weight, scale=None, session=None,
                         remarks=None, reweight_reason=None, entry_method=None):
    """Record the empty (tare) or loaded (gross) weight for a collection.

    Args:
        pickup: Pickup document name
        weight_type: 'tare' (arriving empty) or 'gross' (leaving loaded)
        weight: Weight in kg
        scale: Scale name (optional)
        session: POS Session name (optional, for audit)
        remarks: Free text (optional)
        reweight_reason: Required when replacing a weight already recorded
        entry_method: 'Scale (Auto)' or 'Manual Entry'

    Returns:
        dict: weights, net, variance, verification status and the Truck Weight name
    """
    check_pos_operator()

    if weight_type not in ["gross", "tare"]:
        frappe.throw(_("weight_type must be 'gross' or 'tare'"))

    weight = _validate_weight_against_scale(weight, scale)

    if not frappe.db.exists("Pickup", pickup):
        frappe.throw(_("Pickup not found: {0}").format(pickup))

    _update_session_activity(session)

    session_data = None
    if session:
        session_data = frappe.db.get_value(
            "POS Session", session, ["scale", "pos_profile"], as_dict=True
        )

    now = now_datetime()
    sanitized_remarks = sanitize_html(remarks) if remarks else None
    sanitized_reweight_reason = sanitize_html(reweight_reason) if reweight_reason else None

    doc = frappe.get_doc("Pickup", pickup)

    # A Pickup is weighed empty on the way in and loaded on the way out. Taking
    # them out of order means someone weighed the wrong truck or pressed the
    # wrong button, and the numbers that follow would be nonsense.
    if weight_type == "gross" and not doc.tare_weight:
        frappe.throw(_(
            "Weigh the empty truck in before weighing it out. "
            "Without the tare there is nothing to subtract."
        ))

    existing = frappe.get_all(
        "Truck Weight",
        filters={"pickup": pickup, "weight_type": weight_type.title()},
        fields=["name"], limit=1,
    )

    is_reweight = False
    if existing:
        if not sanitized_reweight_reason:
            frappe.throw(_("Reweight reason is required when updating an existing weight"))

        tw = frappe.get_doc("Truck Weight", existing[0].name)
        tw.weight = weight
        tw.weighed_at = now
        tw.scale = scale or (session_data.scale if session_data else None)
        tw.entry_method = entry_method or "Manual Entry"
        tw.operator = frappe.session.user
        tw.remarks = sanitized_remarks
        tw.is_reweight = 1
        tw.reweight_reason = sanitized_reweight_reason
        tw.reweight_at = now
        tw.reweight_by = frappe.session.user
        tw.save()
        is_reweight = True
    else:
        tw = frappe.get_doc({
            "doctype": "Truck Weight",
            "pickup": pickup,
            "license_plate": doc.license_plate,
            "weight_type": weight_type.title(),
            "weighed_at": now,
            "weight": weight,
            "scale": scale or (session_data.scale if session_data else None),
            "entry_method": entry_method or "Manual Entry",
            "operator": frappe.session.user,
            "remarks": sanitized_remarks,
            "session": session,
            "pos_profile": session_data.pos_profile if session_data else None,
        })
        tw.insert()

    scale_used = scale or (session_data.scale if session_data else None)
    if weight_type == "tare":
        doc.mark_weighed_in(weight, scale=scale_used, operator=frappe.session.user)
    else:
        doc.mark_weighed_out(weight, scale=scale_used, operator=frappe.session.user)

    if session and not doc.session:
        doc.session = session
        if session_data:
            doc.pos_profile = session_data.pos_profile

    doc.save()

    return {
        "pickup": doc.name,
        "weight_type": weight_type,
        "tare_weight": doc.tare_weight,
        "gross_weight": doc.gross_weight,
        "net_weight": doc.net_weight,
        "total_agreed_weight": doc.total_agreed_weight,
        "weight_variance_percent": doc.weight_variance_percent,
        "verification_status": doc.verification_status,
        "status": doc.status,
        "truck_weight_record": tw.name,
        "is_reweight": is_reweight,
    }


@frappe.whitelist()
def complete_pickup(pickup):
    """Close a collection once the loaded truck has been weighed out.

    Mirrors the buy side: a variance outside tolerance sets `verification_status`
    to "Needs Review" rather than refusing to close. Holding a truck at the gate
    over a paperwork discrepancy helps nobody.
    """
    check_pos_operator()

    doc = frappe.get_doc("Pickup", pickup)

    if doc.status == "Cancelled":
        frappe.throw(_("Cannot complete: this pickup was cancelled"))
    if not doc.tare_weight or not doc.gross_weight:
        frappe.throw(_("Both weights are needed before a pickup can be completed"))

    doc.status = "Completed"
    doc.save()

    return {
        "pickup": doc.name,
        "status": doc.status,
        "net_weight": doc.net_weight,
        "total_agreed_weight": doc.total_agreed_weight,
        "weight_variance_percent": doc.weight_variance_percent,
        "verification_status": doc.verification_status,
    }


@frappe.whitelist()
def get_pickup_details(pickup):
    """Everything the terminal needs to render one collection."""
    check_pos_operator()

    doc = frappe.get_doc("Pickup", pickup)

    # Same shape the buy side returns, so the terminal renders photos through
    # exactly the code it already uses.
    truck_weights = frappe.get_all(
        "Truck Weight",
        filters={"pickup": pickup},
        fields=["name", "weight", "weight_type", "weighed_at", "is_reweight"],
        order_by="creation asc",
    )
    for tw in truck_weights:
        tw["photos"] = frappe.get_all(
            "Weight Photo",
            filters={"parent": tw.name, "parenttype": "Truck Weight"},
            fields=["name", "photo", "file_name", "captured_at", "weight_type"],
            order_by="idx asc",
        )

    return {
        "truck_weights": truck_weights,
        "name": doc.name,
        "customer": doc.customer,
        "customer_name": doc.customer_name,
        "license_plate": doc.license_plate,
        "driver_name": doc.driver_name,
        "driver_id": doc.driver_id,
        "status": doc.status,
        "items": [
            {"item_code": r.item_code, "item_name": r.item_name,
             "qty": flt(r.qty), "uom": r.uom}
            for r in (doc.items or [])
        ],
        "total_agreed_weight": doc.total_agreed_weight,
        "tare_weight": doc.tare_weight,
        "tare_weight_time": doc.tare_weight_time,
        "gross_weight": doc.gross_weight,
        "gross_weight_time": doc.gross_weight_time,
        "net_weight": doc.net_weight,
        "weight_variance_percent": doc.weight_variance_percent,
        "verification_status": doc.verification_status,
    }
