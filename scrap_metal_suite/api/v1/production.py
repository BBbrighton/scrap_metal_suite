# Production Sorting API Endpoints
# Handles production session management, dropoff lookup, and sorting operations

import json
import frappe
from frappe import _
from frappe.utils import flt, now_datetime, sanitize_html

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
    session.insert()

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

    # A container ID resolves to the Dropoff it belongs to.
    #
    # On the floor the worker is holding a bag with a CTN sticker on it, not a
    # dropoff docket — the sticker is what the scanner sees. Matching only
    # Dropoff name / plate / supplier meant a bag found nothing at all, with no
    # hint that the ID was valid but the wrong kind of thing.
    #
    # Exact match short-circuits (a scanner sends the whole code). A partial
    # match also works, because a human typing "CTN-2608" should see the bags
    # that matches — searching only on exact codes means everything looks
    # broken until the final character is typed.
    exact_parent = None
    if frappe.db.exists("Scrap Weight Container", query):
        exact_parent = frappe.db.get_value("Scrap Weight Container", query, "dropoff")
        if exact_parent:
            via_container = frappe.db.get_value(
                "Dropoff", {"name": exact_parent, "status": "Completed"}, fields, as_dict=True
            )
            if via_container:
                via_container["has_sorting"] = bool(frappe.db.exists(
                    "Production Sorting", {"dropoff": via_container.name}
                ))
                # Tell the UI why it landed here, so it can say "CTN-… → DO-…"
                # rather than silently showing a document nobody asked for.
                via_container["matched_container"] = query
                return [via_container]

    # Partial container match -> the distinct Completed dropoffs behind them.
    container_rows = frappe.db.sql("""
        SELECT c.name AS ctn, c.dropoff
        FROM `tabScrap Weight Container` c
        JOIN `tabDropoff` d ON d.name = c.dropoff
        WHERE c.name LIKE %(q)s AND d.status = 'Completed'
        ORDER BY c.name
        LIMIT 50
    """, {"q": f"%{query}%"}, as_dict=True)

    by_dropoff = {}
    for row in container_rows:
        by_dropoff.setdefault(row.dropoff, []).append(row.ctn)

    container_results = []
    for parent, ctns in by_dropoff.items():
        rec = frappe.db.get_value("Dropoff", parent, fields, as_dict=True)
        if not rec:
            continue
        rec["has_sorting"] = bool(frappe.db.exists("Production Sorting", {"dropoff": parent}))
        # Every matching bag, so the operator can confirm they picked the right
        # load before committing to it.
        rec["matched_container"] = ", ".join(ctns[:5]) + ("…" if len(ctns) > 5 else "")
        rec["matched_container_count"] = len(ctns)
        container_results.append(rec)

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

    # Container hits lead: if the operator typed something CTN-shaped that is
    # what they meant. Dedupe so a dropoff found both ways appears once.
    seen = {r["name"] for r in container_results}
    return container_results + [r for r in results if r.name not in seen]

@frappe.whitelist()
def search_dropoff(query):
    """Alias for lookup_dropoff for compatibility."""
    return lookup_dropoff(query)



@frappe.whitelist()
def search_containers(query, limit=25):
    """Find containers by ID, for the sorter's scan-or-type box.

    The worker is holding a bag and scanning its sticker, so the thing they
    search for is a container and the thing they expect back is that container —
    not the dropoff it happens to belong to. Selecting one then opens its whole
    dropoff, because a bag is never sorted alone.

    Only bags on Completed dropoffs are returned: sorting cannot start while
    receiving is still in progress.

    Returns:
        list[dict]: container rows carrying enough dropoff context to choose
        between them when a partial query matches several loads.
    """
    check_production_operator()

    if not query or len(str(query).strip()) < 2:
        return []

    query = str(query).strip()

    rows = frappe.db.sql("""
        SELECT c.name, c.item_code, c.item_name, c.net_weight, c.container_type,
               c.status, c.is_reweight,
               d.name AS dropoff, d.supplier_name, d.license_plate,
               d.total_actual_weight
        FROM `tabScrap Weight Container` c
        JOIN `tabDropoff` d ON d.name = c.dropoff
        WHERE d.status = 'Completed' AND c.name LIKE %(q)s
        ORDER BY (c.name = %(exact)s) DESC, c.name
        LIMIT %(lim)s
    """, {"q": f"%{query}%", "exact": query, "lim": int(limit)}, as_dict=True)

    # Flag which dropoffs already have sorting, so the operator is not surprised
    # by landing on a load someone else has started.
    seen = {}
    for r in rows:
        if r.dropoff not in seen:
            seen[r.dropoff] = bool(frappe.db.exists(
                "Production Sorting", {"dropoff": r.dropoff}
            ))
        r["has_sorting"] = seen[r.dropoff]

    return rows


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

    # The individual bags behind the aggregated source_items. A dropoff is
    # many containers, and the sorter works bag by bag — they need to see which
    # ones they are holding, not only the per-grade totals.
    containers = frappe.get_all(
        "Scrap Weight Container",
        filters={"dropoff": dropoff},
        fields=["name", "item_code", "item_name", "net_weight", "status",
                "is_reweight", "reweighed_from"],
        order_by="creation asc",
    )

    return {
        "name": doc.name,
        "supplier": doc.supplier,
        "supplier_name": doc.supplier_name,
        "license_plate": doc.license_plate,
        "total_actual_weight": flt(doc.total_actual_weight),
        "status": doc.status,
        "source_items": source_items,
        "containers": containers,
        "container_count": len([c for c in containers if c.status == "Active"]),
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



def _resolve_container(value, dropoff):
    """Validate a container reference on a sorting row.

    The sorter works bag by bag, so every output row names the container it came
    from. Guard two things the UI cannot be trusted to get right:

      * the container exists, and
      * it belongs to THIS dropoff — a mistyped or mis-scanned CTN from another
        supplier's load would otherwise silently attribute their material to
        this settlement.

    Returns the container name, or None when the row carries no container
    (rows created before per-container sorting, and any caller that has not
    been updated, must keep working).
    """
    if not value:
        return None

    parent = frappe.db.get_value("Scrap Weight Container", value, "dropoff")
    if not parent:
        frappe.throw(_("Container {0} does not exist").format(value))
    if parent != dropoff:
        frappe.throw(
            _("Container {0} belongs to Dropoff {1}, not {2}.").format(value, parent, dropoff)
        )
    return value


@frappe.whitelist()
def create_sorting(session, dropoff, good_items=None, unwanted_items=None):
    """Create a new Production Sorting record with good and unwanted items."""
    check_production_operator()

    try:
        if isinstance(good_items, str):
            good_items = json.loads(good_items)
    except (json.JSONDecodeError, ValueError):
        frappe.throw(_("Invalid data format for good items"))

    try:
        if isinstance(unwanted_items, str):
            unwanted_items = json.loads(unwanted_items)
    except (json.JSONDecodeError, ValueError):
        frappe.throw(_("Invalid data format for unwanted items"))

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

    # Validate dropoff
    dropoff_data = frappe.db.get_value("Dropoff", dropoff, ["name", "status"], as_dict=True)
    if not dropoff_data:
        frappe.throw(_("Dropoff {0} not found").format(dropoff))
    if dropoff_data.status != "Completed":
        frappe.throw(_("Dropoff {0} is not in Completed status").format(dropoff))

    # Build good items
    good_items_list = []
    for item in good_items:
        weight = flt(item.get("weight", 0))
        if weight <= 0:
            frappe.throw(_("Weight must be greater than zero for item {0}").format(
                item.get("item_code")))

        good_items_list.append({
            "container": _resolve_container(item.get("container"), dropoff),
            "item_code": item.get("item_code"),
            "uom": item.get("uom", "Kg"),
            "weight": weight,
            "remarks": sanitize_html(str(item.get("remarks", "")).strip())[:1000] if item.get("remarks") else ""
        })

    # Build unwanted items
    unwanted_items_list = []
    for item in unwanted_items:
        weight = flt(item.get("weight", 0))
        if weight <= 0:
            frappe.throw(_("Weight must be greater than zero for item {0}").format(
                item.get("item_code")))

        unwanted_items_list.append({
            "container": _resolve_container(item.get("container"), dropoff),
            "item_code": item.get("item_code"),
            "uom": item.get("uom", "Kg"),
            "weight": weight,
            "return_reason": sanitize_html(str(item.get("return_reason", "Other")).strip())[:500],
            "remarks": sanitize_html(str(item.get("remarks", "")).strip())[:1000] if item.get("remarks") else ""
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

    try:
        if isinstance(good_items, str):
            good_items = json.loads(good_items)
    except (json.JSONDecodeError, ValueError):
        frappe.throw(_("Invalid data format for good items"))

    try:
        if isinstance(unwanted_items, str):
            unwanted_items = json.loads(unwanted_items)
    except (json.JSONDecodeError, ValueError):
        frappe.throw(_("Invalid data format for unwanted items"))

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
            "remarks": sanitize_html(str(item.get("remarks", "")).strip())[:1000] if item.get("remarks") else ""
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
            "return_reason": sanitize_html(str(item.get("return_reason", "Other")).strip())[:500],
            "remarks": sanitize_html(str(item.get("remarks", "")).strip())[:1000] if item.get("remarks") else ""
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


@frappe.whitelist()
def accept_dropoff_final_variance(dropoff_final, override_reason):
    """Manager override: accept an out-of-tolerance variance on a Dropoff Final.

    `DropoffFinal.auto_complete_if_done` parks a record at "In Progress" when it
    has sorted items but the variance exceeds tolerance, and nothing else can
    move it — there was no API, no desk button, and `dropoff_final.js` calls
    `frm.disable_save()`. The only other exit is for the variance to become
    acceptable, which for a real weight discrepancy it never will. Five live
    records were stranded this way, one at 30% variance.

    This is the deliberate human decision that releases it for settlement,
    recorded with who, when and why. Mirrors
    `scrap_metal_suite.api.v1.dropoff.verify_dropoff`.

    Args:
        dropoff_final: Dropoff Final document name
        override_reason: why the discrepancy is being accepted (required)

    Returns:
        dict: success, status, verification_status, and the audit trail
    """
    check_production_operator()

    doc = frappe.get_doc("Dropoff Final", dropoff_final)
    doc.accept_variance(override_reason)

    return {
        "success": True,
        "dropoff_final": doc.name,
        "status": doc.status,
        "verification_status": doc.verification_status,
        "variance_percent": doc.variance_percent,
        "overridden_by": doc.variance_override_by,
        "overridden_at": doc.variance_override_at,
        "override_reason": doc.variance_override_reason,
    }
