# Production Sorting API Endpoints
# Handles production session management, dropoff lookup, and sorting operations

import json
import frappe
from frappe import _
from frappe.utils import flt, nowdate, now_datetime

from scrap_metal_suite.api.v1.auth import check_production_operator


@frappe.whitelist()
def open_session(scale=None):
    """Open a new Production Session for the current user."""
    check_production_operator()

    existing = frappe.db.exists(
        "Production Session",
        {"operator": frappe.session.user, "status": "Open"}
    )
    if existing:
        frappe.throw(
            _("You already have an open session: {0}. Please close it first.").format(existing)
        )

    session = frappe.get_doc({
        "doctype": "Production Session",
        "status": "Open",
        "scale": scale
    })
    session.insert(ignore_permissions=True)

    return {
        "session": session.name,
        "operator": session.operator,
        "opening_time": session.opening_time
    }


@frappe.whitelist()
def close_session(session):
    """Close a Production Session and calculate totals."""
    check_production_operator()
    session_doc = frappe.get_doc("Production Session", session)

    if session_doc.operator != frappe.session.user:
        user_roles = frappe.get_roles(frappe.session.user)
        if "Production Manager" not in user_roles and "System Manager" not in user_roles:
            frappe.throw(_("You can only close your own sessions"))

    return session_doc.close_session()


@frappe.whitelist()
def get_active_session():
    """Get the current user's active (open) Production Session."""
    check_production_operator()

    session = frappe.db.get_value(
        "Production Session",
        {"operator": frappe.session.user, "status": "Open"},
        ["name", "opening_time", "total_sortings", "total_weight_sorted", "scale"],
        as_dict=True
    )

    if session and session.scale:
        scale_info = frappe.db.get_value(
            "Scale", session.scale,
            ["scale_name", "scale_type", "usage_type", "location", "max_capacity_kg",
             "baud_rate", "data_bits", "parity", "stop_bits", "flow_control",
             "protocol_detected", "unit_conversion_factor", "signal_unit"],
            as_dict=True
        )
        if scale_info:
            session.update({
                "scale_name": scale_info.scale_name,
                "scale_type": scale_info.scale_type,
                "baud_rate": scale_info.baud_rate,
                "data_bits": scale_info.data_bits,
                "parity": scale_info.parity,
                "stop_bits": scale_info.stop_bits,
                "flow_control": scale_info.flow_control,
                "protocol_detected": scale_info.protocol_detected,
                "unit_conversion_factor": scale_info.unit_conversion_factor,
                "signal_unit": scale_info.signal_unit,
            })

    return session


@frappe.whitelist()
def update_session_activity(session):
    """Heartbeat — update last_activity timestamp."""
    check_production_operator()

    session_data = frappe.db.get_value(
        "Production Session", session, ["status", "operator"], as_dict=True
    )
    if not session_data:
        frappe.throw(_("Session {0} not found").format(session))
    if session_data.status != "Open":
        return {"success": False, "message": "Session is not open"}
    if session_data.operator != frappe.session.user:
        frappe.throw(_("This session does not belong to you"))

    frappe.db.set_value(
        "Production Session", session, "last_activity",
        now_datetime(), update_modified=False
    )
    return {"success": True}


@frappe.whitelist()
def get_session_summary(session):
    """Get summary statistics for a Production Session."""
    check_production_operator()

    session_doc = frappe.db.get_value(
        "Production Session", session,
        ["name", "operator", "opening_time", "status", "total_sortings", "total_weight_sorted", "scale"],
        as_dict=True
    )
    if not session_doc:
        frappe.throw(_("Session {0} not found").format(session))

    # Live count from Production Sorting records
    totals = frappe.db.sql("""
        SELECT
            COUNT(*) as sorting_count,
            COALESCE(SUM(total_weight), 0) as total_weight
        FROM `tabProduction Sorting`
        WHERE session = %s
    """, session, as_dict=True)[0]

    return {
        "session": session_doc,
        "totals": totals
    }


@frappe.whitelist()
def set_session_scale(session, scale):
    """Assign a scale to a Production Session."""
    check_production_operator()

    session_doc = frappe.get_doc("Production Session", session)

    if session_doc.operator != frappe.session.user:
        user_roles = frappe.get_roles(frappe.session.user)
        if "System Manager" not in user_roles:
            frappe.throw(_("You can only modify your own sessions"))

    if session_doc.scale:
        frappe.throw(_("Scale already set for this session."))

    scale_data = frappe.db.get_value(
        "Scale", scale,
        ["name", "scale_name", "is_active", "in_use", "in_use_by_session",
         "scale_type", "usage_type", "location"],
        as_dict=True
    )
    if not scale_data:
        frappe.throw(_("Scale '{0}' not found").format(scale))
    if not scale_data.is_active:
        frappe.throw(_("Scale '{0}' is not active").format(scale))
    if scale_data.in_use and scale_data.in_use_by_session:
        frappe.throw(_("Scale '{0}' is already in use by session {1}").format(
            scale, scale_data.in_use_by_session))

    session_doc.scale = scale
    session_doc.save()

    scale_doc = frappe.get_doc("Scale", scale)
    scale_doc.in_use = 1
    scale_doc.in_use_by_session = session
    scale_doc.save()

    return {
        "session": session_doc.name,
        "scale": scale_data.name,
        "scale_name": scale_data.scale_name,
        "scale_type": scale_data.scale_type,
    }


@frappe.whitelist()
def lookup_dropoff(query):
    """Search for completed Dropoffs by name, license plate, or supplier."""
    check_production_operator()

    if not query or len(query) < 2:
        return []

    fields = [
        "name", "supplier", "supplier_name", "license_plate",
        "total_actual_weight", "status", "creation"
    ]

    # Exact match by name first
    exact = frappe.db.get_value(
        "Dropoff", {"name": query, "status": "Completed"}, fields, as_dict=True
    )
    if exact:
        exact["has_sorting"] = bool(frappe.db.exists(
            "Production Sorting", {"dropoff": exact.name}
        ))
        return [exact]

    # Partial search
    results = frappe.db.sql("""
        SELECT name, supplier, supplier_name, license_plate,
               total_actual_weight, status, creation
        FROM `tabDropoff`
        WHERE status = 'Completed'
          AND (
              name LIKE %(q)s
              OR license_plate LIKE %(q)s
              OR supplier_name LIKE %(q)s
          )
        ORDER BY creation DESC
        LIMIT 10
    """, {"q": f"%{query}%"}, as_dict=True)

    for r in results:
        r["has_sorting"] = bool(frappe.db.exists(
            "Production Sorting", {"dropoff": r.name}
        ))

    return results

@frappe.whitelist()
def search_dropoff(query):
    """Alias for lookup_dropoff for compatibility."""
    return lookup_dropoff(query)


@frappe.whitelist()
def get_dropoff_for_sorting(dropoff):
    """Get Dropoff details including item_summary for sorting."""
    check_production_operator()

    doc = frappe.get_doc("Dropoff", dropoff)

    source_items = []
    if hasattr(doc, "item_summary"):
        for item in doc.item_summary:
            source_items.append({
                "item": item.item,
                "item_name": item.item_name,
                "total_weight": flt(item.total_weight)
            })

    existing_sorting = frappe.db.get_value(
        "Production Sorting", {"dropoff": dropoff},
        ["name", "status", "verification_status"], as_dict=True
    )

    return {
        "name": doc.name,
        "supplier": doc.supplier,
        "supplier_name": doc.supplier_name,
        "license_plate": doc.license_plate,
        "total_actual_weight": flt(doc.total_actual_weight),
        "status": doc.status,
        "source_items": source_items,
        "existing_sorting": existing_sorting
    }


@frappe.whitelist()
def get_allowed_items():
    """Get items from allowed Item Groups (from Production Sorting Settings)."""
    check_production_operator()

    settings = frappe.get_single("Production Sorting Settings")
    if not settings.allowed_item_groups:
        return []

    allowed_groups = [row.item_group for row in settings.allowed_item_groups]

    items = frappe.get_all(
        "Item",
        filters={
            "item_group": ["in", allowed_groups],
            "disabled": 0
        },
        fields=["item_code", "item_name", "item_group", "stock_uom"],
        order_by="item_group, item_name"
    )

    # Group by item_group for the UI
    groups = {}
    for item in items:
        g = item.item_group
        if g not in groups:
            groups[g] = []
        groups[g].append(item)

    return {
        "items": items,
        "groups": groups,
        "group_names": sorted(groups.keys())
    }


@frappe.whitelist()
def create_sorting(session, dropoff, good_items=None, unwanted_items=None):
    """Create a new Production Sorting record with good and unwanted items."""
    check_production_operator()

    if isinstance(good_items, str):
        good_items = json.loads(good_items)
    if isinstance(unwanted_items, str):
        unwanted_items = json.loads(unwanted_items)

    good_items = good_items or []
    unwanted_items = unwanted_items or []

    if not good_items and not unwanted_items:
        frappe.throw(_("At least one good or unwanted item is required"))

    # Validate session
    session_data = frappe.db.get_value(
        "Production Session", session,
        ["status", "operator"], as_dict=True
    )
    if not session_data or session_data.status != "Open":
        frappe.throw(_("Session is not open"))
    if session_data.operator != frappe.session.user:
        frappe.throw(_("This session does not belong to you"))

    # Build good items
    good_items_list = []
    for item in good_items:
        weight = flt(item.get("weight", 0))
        if weight <= 0:
            frappe.throw(_("Weight must be greater than zero for item {0}").format(
                item.get("item_code")))

        good_items_list.append({
            "item_code": item.get("item_code"),
            "uom": item.get("uom", "Kg"),
            "weight": weight,
            "remarks": item.get("remarks", "")
        })

    # Build unwanted items
    unwanted_items_list = []
    for item in unwanted_items:
        weight = flt(item.get("weight", 0))
        if weight <= 0:
            frappe.throw(_("Weight must be greater than zero for item {0}").format(
                item.get("item_code")))

        unwanted_items_list.append({
            "item_code": item.get("item_code"),
            "uom": item.get("uom", "Kg"),
            "weight": weight,
            "return_reason": item.get("return_reason", "Other"),
            "remarks": item.get("remarks", "")
        })

    sorting = frappe.get_doc({
        "doctype": "Production Sorting",
        "dropoff": dropoff,
        "session": session,
        "status": "Draft",
        "good_items": good_items_list,
        "unwanted_items": unwanted_items_list
    })
    sorting.insert()
    sorting.submit()  # Submit to trigger Dropoff Final update

    return {
        "name": sorting.name,
        "status": sorting.status,
        "total_good_weight": sorting.total_good_weight,
        "total_unwanted_weight": sorting.total_unwanted_weight,
        "total_weight": sorting.total_weight
    }
@frappe.whitelist()
def update_sorting(sorting_name, good_items=None, unwanted_items=None):
    """Update good and unwanted items on an existing Production Sorting record."""
    check_production_operator()

    if isinstance(good_items, str):
        good_items = json.loads(good_items)
    if isinstance(unwanted_items, str):
        unwanted_items = json.loads(unwanted_items)

    good_items = good_items or []
    unwanted_items = unwanted_items or []

    sorting = frappe.get_doc("Production Sorting", sorting_name)

    if sorting.docstatus == 1:
        frappe.throw(_("Cannot edit a submitted sorting record"))
    if sorting.docstatus == 2:
        frappe.throw(_("Cannot edit a cancelled sorting record"))

    # Verify ownership
    if sorting.operator != frappe.session.user:
        user_roles = frappe.get_roles(frappe.session.user)
        if "Production Manager" not in user_roles and "System Manager" not in user_roles:
            frappe.throw(_("You can only edit your own sorting records"))

    # Update good items
    sorting.good_items = []
    for item in good_items:
        weight = flt(item.get("weight", 0))
        if weight <= 0:
            frappe.throw(_("Weight must be greater than zero for item {0}").format(
                item.get("item_code")))

        sorting.append("good_items", {
            "item_code": item.get("item_code"),
            "uom": item.get("uom", "Kg"),
            "weight": weight,
            "remarks": item.get("remarks", "")
        })

    # Update unwanted items
    sorting.unwanted_items = []
    for item in unwanted_items:
        weight = flt(item.get("weight", 0))
        if weight <= 0:
            frappe.throw(_("Weight must be greater than zero for item {0}").format(
                item.get("item_code")))

        sorting.append("unwanted_items", {
            "item_code": item.get("item_code"),
            "uom": item.get("uom", "Kg"),
            "weight": weight,
            "return_reason": item.get("return_reason", "Other"),
            "remarks": item.get("remarks", "")
        })

    sorting.save()

    return {
        "name": sorting.name,
        "status": sorting.status,
        "total_good_weight": sorting.total_good_weight,
        "total_unwanted_weight": sorting.total_unwanted_weight,
        "total_weight": sorting.total_weight
    }
@frappe.whitelist()
def complete_sorting(sorting_name):
    """Submit a Production Sorting record (triggers Dropoff Final update)."""
    check_production_operator()

    sorting = frappe.get_doc("Production Sorting", sorting_name)

    if not sorting.good_items and not sorting.unwanted_items:
        frappe.throw(_("Cannot submit sorting with no items"))

    if sorting.docstatus == 1:
        frappe.throw(_("Sorting is already submitted"))
    if sorting.docstatus == 2:
        frappe.throw(_("Cannot submit a cancelled sorting record"))

    # Verify ownership
    if sorting.operator != frappe.session.user:
        user_roles = frappe.get_roles(frappe.session.user)
        if "Production Manager" not in user_roles and "System Manager" not in user_roles:
            frappe.throw(_("You can only submit your own sorting records"))

    sorting.submit()

    return {
        "name": sorting.name,
        "status": sorting.status,
        "total_good_weight": sorting.total_good_weight,
        "total_unwanted_weight": sorting.total_unwanted_weight,
        "total_weight": sorting.total_weight
    }
@frappe.whitelist()
def get_sorting_for_dropoff(dropoff):
    """Check if a sorting record exists for a dropoff."""
    check_production_operator()

    sorting = frappe.db.get_value(
        "Production Sorting",
        {"dropoff": dropoff},
        ["name", "status", "verification_status", "total_weight"],
        as_dict=True
    )
    return sorting


@frappe.whitelist()
def get_scales(usage_type=None):
    """Get list of scales — reuses POS pattern."""
    check_production_operator()

    filters = {}
    if usage_type:
        filters["usage_type"] = usage_type

    return frappe.get_all(
        "Scale",
        filters=filters,
        fields=[
            "name", "scale_name", "scale_type", "usage_type", "location",
            "max_capacity_kg", "is_active", "in_use", "in_use_by_session",
            "baud_rate", "data_bits", "parity", "stop_bits", "flow_control",
            "protocol_detected", "unit_conversion_factor", "signal_unit"
        ],
        order_by="scale_name asc"
    )


def update_dropoff_final(dropoff):
    """
    Helper function to create or update Dropoff Final for a given dropoff.
    Called automatically when Production Sorting is submitted/cancelled.
    """
    if not dropoff:
        return

    # Check if Dropoff Final exists
    existing = frappe.db.exists("Dropoff Final", {"dropoff": dropoff})

    if existing:
        # Update existing
        dropoff_final = frappe.get_doc("Dropoff Final", existing)
        dropoff_final.save()
        return dropoff_final.name
    else:
        # Create new
        dropoff_final = frappe.get_doc({
            "doctype": "Dropoff Final",
            "dropoff": dropoff
        })
        dropoff_final.insert()
        return dropoff_final.name


@frappe.whitelist()
def get_dropoff_final_status(dropoff):
    """Get the status of Dropoff Final for a dropoff."""
    check_production_operator()

    dropoff_final = frappe.db.get_value(
        "Dropoff Final",
        {"dropoff": dropoff},
        ["name", "status", "total_good_weight", "total_unwanted_weight", 
         "total_verified_weight", "weight_variance", "variance_ok", "verification_status"],
        as_dict=True
    )

    if dropoff_final:
        # Get count of sorting sessions
        sorting_count = frappe.db.count("Production Sorting", {
            "dropoff": dropoff,
            "docstatus": 1
        })
        dropoff_final["sorting_count"] = sorting_count

    return dropoff_final
