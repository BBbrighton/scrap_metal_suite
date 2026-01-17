# Dropoff API Endpoints
# Handles drop-off operations for POS terminal (1-truck-per-dropoff design)

import frappe
from frappe import _
from frappe.utils import flt, nowdate, now_datetime, add_to_date, get_datetime
import json

from scrap_metal_suite.api.v1.auth import check_pos_operator


def _update_session_activity(session):
    """Update last_activity timestamp for session timeout tracking."""
    if session:
        frappe.db.set_value("POS Session", session, "last_activity", now_datetime(), update_modified=False)


def _count_dropoff_orders(parent):
    """
    Count Dropoff Order child records using raw SQL to bypass SQL sanitizer.
    The "Dropoff Order" table name triggers Frappe SQL injection protection
    because it contains "drop".
    """
    result = frappe.db.sql(
        "SELECT COUNT(*) FROM `tabDropoff Order` WHERE parent = %s",
        (parent,)
    )
    return result[0][0] if result else 0


# Phase 8A: Auto-transition removed - now handled in dropoff.py controller


# =============================================================================
# PHASE 8C: AUTO-POPULATE EXPECTED ITEMS
# =============================================================================

@frappe.whitelist()
def get_items_from_orders(order_names):
    """
    Phase 8C: Get all items from given POS Orders (for auto-populating expected items).

    Security: Checks if user has read permission on each POS Order before fetching items.

    Args:
        order_names: JSON array of POS Order names

    Returns:
        list: Unique items from all orders [{item_code, item_name, parent}, ...]
    """
    if isinstance(order_names, str):
        order_names = json.loads(order_names)

    if not order_names:
        return []

    # Security: Check if user has permission to read each order
    for order_name in order_names:
        if not frappe.has_permission("POS Order", "read", order_name):
            frappe.throw(_("No permission to read POS Order: {0}").format(order_name))

    # Fetch items from all orders
    items = frappe.get_all(
        "POS Order Item",
        filters={"parent": ["in", order_names]},
        fields=["item_code", "item_name", "parent"]
    )

    return items


# =============================================================================
# SEARCH & LOOKUP
# =============================================================================

@frappe.whitelist()
def lookup_dropoff(query):
    """
    Search for Drop-offs by ID or license plate.

    Args:
        query: Search term (DO-YYMMDD-XXX or license plate)

    Returns:
        list: Matching drop-offs with status, order_count
    """
    check_pos_operator()

    if not query or len(query.strip()) < 2:
        return []

    # Trim whitespace/tabs from query
    query = query.strip()

    # Try exact match first
    exact = frappe.db.get_value(
        "Dropoff",
        {"name": query},
        ["name", "dropoff_scheduled_start", "license_plate", "supplier_name", "status"],
        as_dict=True
    )
    if exact:
        exact["order_count"] = _count_dropoff_orders(exact.name)
        return [exact]

    # Try license plate exact match
    plate_match = frappe.db.get_value(
        "Dropoff",
        {"license_plate": query},
        ["name", "dropoff_scheduled_start", "license_plate", "supplier_name", "status"],
        as_dict=True
    )
    if plate_match:
        plate_match["order_count"] = _count_dropoff_orders(plate_match.name)
        return [plate_match]

    # Partial search within recent dates (+/- 3 days)
    from frappe.utils import get_datetime
    today = nowdate()
    date_start = get_datetime(add_to_date(today, days=-3)).replace(hour=0, minute=0, second=0)
    date_end = get_datetime(add_to_date(today, days=3)).replace(hour=23, minute=59, second=59)

    dropoffs = frappe.db.sql("""
        SELECT name, dropoff_scheduled_start, license_plate, supplier_name, status
        FROM `tabDropoff`
        WHERE dropoff_scheduled_start >= %(start)s
          AND dropoff_scheduled_start <= %(end)s
          AND (name LIKE %(q)s OR license_plate LIKE %(q)s)
        ORDER BY dropoff_scheduled_start DESC, creation DESC
        LIMIT 10
    """, {"start": date_start, "end": date_end, "q": f"%{query}%"}, as_dict=True)

    for d in dropoffs:
        d["order_count"] = _count_dropoff_orders(d.name)

    return dropoffs


@frappe.whitelist()
def get_dropoff_by_qr(qr_data):
    """
    Parse QR code data and return dropoff details.

    Args:
        qr_data: QR content - URL or dropoff ID
                 e.g., "https://site.com/dropoff/DO-251226-00001" or "DO-251226-00001"

    Returns:
        dict: Dropoff details or error
    """
    check_pos_operator()

    if not qr_data:
        return {"error": "Empty QR data"}

    # Extract dropoff ID from URL if needed
    dropoff_id = qr_data.strip()
    if "/dropoff/" in dropoff_id:
        dropoff_id = dropoff_id.split("/dropoff/")[-1].split("?")[0].strip()

    if not dropoff_id:
        return {"error": "Invalid QR format"}

    # Check if dropoff exists
    if not frappe.db.exists("Dropoff", dropoff_id):
        return {"error": f"Dropoff '{dropoff_id}' not found"}

    # Return full details
    return get_dropoff_details(dropoff_id)


@frappe.whitelist()
def get_dropoff_details(dropoff):
    """
    Get full details of a Drop-off for terminal display.

    Args:
        dropoff: Dropoff document name

    Returns:
        dict: Complete dropoff info including truck weights, orders, scrap weights
    """
    check_pos_operator()

    doc = frappe.get_doc("Dropoff", dropoff)

    # Get linked orders with details
    orders = []
    for order_row in doc.orders:
        order_data = frappe.db.get_value(
            "POS Order",
            order_row.pos_order,
            ["name", "supplier_name", "contracted_weight", "total_received",
             "fulfillment_percent", "fulfillment_status"],
            as_dict=True
        )
        if order_data:
            order_data["allocated_weight"] = order_row.allocated_weight
            orders.append(order_data)

    # Get scrap weight records
    scrap_weights = frappe.get_all(
        "Scrap Weight",
        filters={"dropoff": dropoff},
        fields=["name", "total_weight", "posting_date", "posting_time", "is_reweight"],
        order_by="creation asc"
    )

    for sw in scrap_weights:
        sw["items_count"] = frappe.db.count("Scrap Weight Item", {"parent": sw.name})
        # Get photos for this scrap weight
        sw["photos"] = frappe.get_all(
            "Weight Photo",
            filters={"parent": sw.name, "parenttype": "Scrap Weight"},
            fields=["name", "photo", "file_name", "captured_at", "weight_type"],
            order_by="idx asc"
        )

    # Get expected items from Dropoff's expected_items child table
    expected_items = frappe.get_all(
        "Dropoff Expected Item",
        filters={"parent": doc.name},
        fields=["item", "item_name", "indicated_weight"],
        order_by="idx asc"
    )
    # Map fields for frontend compatibility
    for item in expected_items:
        item["item_code"] = item.pop("item", "")
        item["weight"] = item.pop("indicated_weight", 0)
        item["uom"] = "Kg"  # Default UOM

    # Check for existing scrap weight (for reweight scenario)
    existing_scrap_weight = None
    if scrap_weights:
        # Get the latest non-reweight scrap weight for editing
        for sw in reversed(scrap_weights):
            if not sw.get("is_reweight"):
                existing_scrap_weight = sw.name
                break
        # If all are reweights, get the latest one
        if not existing_scrap_weight:
            existing_scrap_weight = scrap_weights[-1].name

    # Get truck weight records with photos
    truck_weights = frappe.get_all(
        "Truck Weight",
        filters={"dropoff": dropoff},
        fields=["name", "weight", "weight_type", "weighed_at", "is_reweight"],
        order_by="creation asc"
    )

    for tw in truck_weights:
        # Get photos for this truck weight
        tw["photos"] = frappe.get_all(
            "Weight Photo",
            filters={"parent": tw.name, "parenttype": "Truck Weight"},
            fields=["name", "photo", "file_name", "captured_at", "weight_type"],
            order_by="idx asc"
        )

    return {
        "name": doc.name,
        "dropoff_scheduled_start": doc.dropoff_scheduled_start,
        "dropoff_scheduled_end": doc.dropoff_scheduled_end,
        "license_plate": doc.license_plate,
        "supplier": doc.supplier,
        "supplier_name": doc.supplier_name,
        "status": doc.status,
        "truck_variance_threshold_percent": doc.truck_variance_threshold_percent,
        "indicated_variance_threshold_percent": doc.indicated_variance_threshold_percent,
        "total_indicated_weight": doc.total_indicated_weight,
        # Truck weights (inline)
        "gross_weight": doc.gross_weight,
        "gross_weight_time": doc.gross_weight_time,
        "gross_weight_scale": doc.gross_weight_scale,
        "gross_weight_operator": doc.gross_weight_operator,
        "tare_weight": doc.tare_weight,
        "tare_weight_time": doc.tare_weight_time,
        "tare_weight_scale": doc.tare_weight_scale,
        "tare_weight_operator": doc.tare_weight_operator,
        "net_weight": doc.net_weight,
        "truck_remarks": doc.truck_remarks,
        "is_reweighed": doc.is_reweighed,
        # Truck weight records with photos
        "truck_weights": truck_weights,
        # Orders
        "orders": orders,
        "order_count": len(orders),
        # Scrap weights
        "scrap_weights": scrap_weights,
        "total_scrap_weight": doc.total_scrap_weight,
        # Expected items (from orders)
        "expected_items": expected_items,
        "existing_scrap_weight": existing_scrap_weight,
        # Verification
        "total_truck_weight": doc.total_truck_weight,
        "truck_variance": doc.truck_variance,
        "truck_variance_percent": doc.truck_variance_percent,
        "truck_variance_ok": doc.truck_variance_ok,
        "indicated_variance_ok": doc.indicated_variance_ok
    }


# =============================================================================
# TRUCK WEIGHT RECORDING
# =============================================================================

@frappe.whitelist()
def record_truck_weight(dropoff, weight_type, weight, scale=None, session=None,
                        remarks=None, reweight_reason=None, entry_method=None):
    """
    Record gross or tare weight for the dropoff truck.
    Updates existing Truck Weight record if one exists, otherwise creates new.
    (Similar pattern to Scrap Weight reweight handling)

    Args:
        dropoff: Dropoff document name
        weight_type: 'gross' or 'tare'
        weight: Weight in kg
        scale: Scale name (optional)
        session: POS Session name (optional, for audit)
        remarks: Optional remarks for this weighing
        reweight_reason: Required if updating existing weight (reweight scenario)
        entry_method: 'Scale (Auto)' or 'Manual Entry' (Phase 8D)

    Returns:
        dict: Updated weights, status, truck_weight_record name, is_reweight flag
    """
    check_pos_operator()

    if weight_type not in ["gross", "tare"]:
        frappe.throw(_("weight_type must be 'gross' or 'tare'"))

    # Validate weight
    try:
        weight = float(weight)
    except (ValueError, TypeError):
        frappe.throw(_("Invalid weight value"))

    if weight <= 0:
        frappe.throw(_("Weight must be greater than 0"))

    # Validate scale capacity if provided
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

    # Update session activity
    _update_session_activity(session)

    # Get session info for audit
    session_data = None
    if session:
        session_data = frappe.db.get_value(
            "POS Session", session, ["pos_profile", "scale"], as_dict=True
        )

    # Sanitize remarks
    sanitized_remarks = None
    if remarks:
        from frappe.utils import sanitize_html
        sanitized_remarks = sanitize_html(str(remarks).strip())[:1000]

    sanitized_reweight_reason = None
    if reweight_reason:
        from frappe.utils import sanitize_html
        sanitized_reweight_reason = sanitize_html(str(reweight_reason).strip())[:500]

    weight = flt(weight)
    now = now_datetime()
    weight_type_cap = weight_type.capitalize()  # 'Gross' or 'Tare'

    # Check if Truck Weight record already exists for this dropoff + weight_type
    existing_tw = frappe.get_all(
        "Truck Weight",
        filters={"dropoff": dropoff, "weight_type": weight_type_cap},
        fields=["name"],
        order_by="creation desc",
        limit=1
    )

    is_reweight = False

    if existing_tw:
        # UPDATE existing Truck Weight record
        truck_weight = frappe.get_doc("Truck Weight", existing_tw[0].name)

        # Require reweight reason when updating
        if not sanitized_reweight_reason:
            frappe.throw(_("Reweight reason is required when updating an existing weight"))

        truck_weight.weight = weight
        truck_weight.weighed_at = now
        truck_weight.scale = scale or (session_data.scale if session_data else None)
        truck_weight.entry_method = entry_method or "Manual Entry"  # Phase 8D
        truck_weight.operator = frappe.session.user
        truck_weight.remarks = sanitized_remarks
        truck_weight.is_reweight = 1
        truck_weight.reweight_reason = sanitized_reweight_reason
        truck_weight.reweight_at = now
        truck_weight.reweight_by = frappe.session.user
        truck_weight.save()
        is_reweight = True
    else:
        # CREATE new Truck Weight record
        truck_weight = frappe.get_doc({
            "doctype": "Truck Weight",
            "dropoff": dropoff,
            "weight_type": weight_type_cap,
            "weight": weight,
            "weighed_at": now,
            "scale": scale or (session_data.scale if session_data else None),
            "entry_method": entry_method or "Manual Entry",  # Phase 8D
            "operator": frappe.session.user,
            "session": session,
            "pos_profile": session_data.pos_profile if session_data else None,
            "remarks": sanitized_remarks,
            "is_reweight": 0
        })
        truck_weight.insert()

    # Update dropoff document
    doc = frappe.get_doc("Dropoff", dropoff)

    if weight_type == "gross":
        doc.gross_weight = weight
        doc.gross_weight_time = now
        doc.gross_weight_scale = scale or (session_data.scale if session_data else None)
        doc.gross_weight_operator = frappe.session.user
    else:
        doc.tare_weight = weight
        doc.tare_weight_time = now
        doc.tare_weight_scale = scale or (session_data.scale if session_data else None)
        doc.tare_weight_operator = frappe.session.user

    # Mark dropoff as reweighed if this was a reweight
    if is_reweight:
        doc.is_reweighed = 1

    # Phase 8A: Auto-transition now handled in controller (dropoff.py before_save)
    doc.save()

    return {
        "dropoff": doc.name,
        "status": doc.status,
        "gross_weight": doc.gross_weight,
        "gross_weight_time": doc.gross_weight_time,
        "tare_weight": doc.tare_weight,
        "tare_weight_time": doc.tare_weight_time,
        "net_weight": doc.net_weight,
        "truck_weight_record": truck_weight.name,
        "is_reweight": is_reweight,
        "total_scrap_weight": doc.total_scrap_weight,
        "truck_variance": doc.truck_variance,
        "truck_variance_percent": doc.truck_variance_percent
    }


@frappe.whitelist()
def mark_truck_reweighed(dropoff, reason):
    """
    Mark dropoff truck as reweighed.

    Args:
        dropoff: Dropoff document name
        reason: Reason for reweight

    Returns:
        dict: Success status
    """
    check_pos_operator()

    if not reason:
        frappe.throw(_("Reweight reason is required"))

    doc = frappe.get_doc("Dropoff", dropoff)
    doc.is_reweighed = 1
    doc.reweight_reason = reason
    doc.reweight_by = frappe.session.user
    doc.reweight_at = now_datetime()
    doc.save()

    return {
        "success": True,
        "is_reweighed": 1,
        "reweight_reason": reason
    }


@frappe.whitelist()
def save_truck_remarks(dropoff, remarks=None):
    """
    Save remarks for truck.

    Args:
        dropoff: Dropoff document name
        remarks: Text remarks

    Returns:
        dict: Success status
    """
    check_pos_operator()

    doc = frappe.get_doc("Dropoff", dropoff)

    if remarks:
        from frappe.utils import sanitize_html
        doc.truck_remarks = sanitize_html(str(remarks).strip())[:2000]

    doc.save()

    return {"success": True, "truck_remarks": doc.truck_remarks}


@frappe.whitelist()
def save_truck_photo(dropoff, photo, weight_type=None):
    """
    Attach photo to Truck Weight record using Frappe's File system.

    This allows multiple photos per weighing (scale display, truck, license plate).
    Photos are attached as File documents linked to the Truck Weight record.

    Args:
        dropoff: Dropoff document name
        photo: File URL from upload_file API (e.g., '/files/truck_photo_DO-XXX_Gross_123.jpg')
        weight_type: 'Gross' or 'Tare' - which weighing to attach photo to

    Returns:
        dict: Success status with photo URL, truck_weight record, and attachment_count

    Naming Convention (set by UI):
        truck_photo_{dropoff}_{weight_type}_{timestamp}.jpg
        Example: truck_photo_DO-24.12.28-00001_Gross_1735380000000.jpg
    """
    check_pos_operator()

    if not weight_type:
        frappe.throw(_("weight_type is required (Gross or Tare)"))

    # Find the latest Truck Weight record for this dropoff and weight type
    truck_weight = frappe.get_all(
        "Truck Weight",
        filters={"dropoff": dropoff, "weight_type": weight_type},
        fields=["name"],
        order_by="weighed_at desc",
        limit=1
    )

    if not truck_weight:
        frappe.throw(_("No {0} weight record found for this dropoff").format(weight_type))

    truck_weight_name = truck_weight[0].name

    # Find the File record by file_url and link it to Truck Weight
    file_doc = frappe.get_all(
        "File",
        filters={"file_url": photo},
        fields=["name"],
        limit=1
    )

    if file_doc:
        # Update the File to attach it to the Truck Weight record
        frappe.db.set_value("File", file_doc[0].name, {
            "attached_to_doctype": "Truck Weight",
            "attached_to_name": truck_weight_name
        })
    else:
        # File not found - create attachment record
        frappe.get_doc({
            "doctype": "File",
            "file_url": photo,
            "attached_to_doctype": "Truck Weight",
            "attached_to_name": truck_weight_name,
            "is_private": 0
        }).insert(ignore_permissions=True)

    # Count total attachments for this Truck Weight
    attachment_count = frappe.db.count("File", {
        "attached_to_doctype": "Truck Weight",
        "attached_to_name": truck_weight_name
    })

    return {
        "success": True,
        "truck_weight": truck_weight_name,
        "weight_type": weight_type,
        "photo_url": photo,
        "attachment_count": attachment_count
    }


# =============================================================================
# SCRAP WEIGHT RECORDING
# =============================================================================

@frappe.whitelist()
def record_scrap_weight(session, dropoff, items, remarks=None,
                        existing_scrap_weight=None, reweight_reason=None, entry_method=None):
    """
    Record scrap weight for a drop-off.

    Args:
        session: POS Session name (required)
        dropoff: Dropoff document name (required)
        items: JSON list [{item_code, weight, uom}]
        remarks: Optional text
        existing_scrap_weight: For reweight - update this doc
        reweight_reason: Required if reweighting
        entry_method: 'Scale (Auto)' or 'Manual Entry' (Phase 8D)

    Returns:
        dict: scrap_weight name, totals, variance info
    """
    check_pos_operator()

    if isinstance(items, str):
        items = json.loads(items)

    if not items:
        frappe.throw(_("At least one item is required"))

    # Validate session
    session_data = frappe.db.get_value(
        "POS Session", session,
        ["status", "scale", "pos_profile", "operator"],
        as_dict=True
    )
    if not session_data or session_data.status != "Open":
        frappe.throw(_("Session {0} is not open").format(session))

    if session_data.operator != frappe.session.user:
        frappe.throw(_("This session does not belong to the current user"))

    # Update session activity
    _update_session_activity(session)

    # Validate dropoff exists
    if not frappe.db.exists("Dropoff", dropoff):
        frappe.throw(_("Dropoff {0} not found").format(dropoff))

    # Get scale max capacity
    scale_max = None
    if session_data.scale:
        scale_max = frappe.db.get_value("Scale", session_data.scale, "max_capacity_kg")

    # Build items list with validation
    weight_items = []
    for item in items:
        item_code = item.get("item_code")

        try:
            weight = float(item.get("weight", 0))
        except (ValueError, TypeError):
            frappe.throw(_("Invalid weight for item {0}").format(item_code))

        if weight <= 0:
            frappe.throw(_("Weight must be > 0 for item {0}").format(item_code))

        if scale_max and weight > scale_max:
            frappe.throw(_("Weight {0} exceeds scale capacity {1}").format(weight, scale_max))

        weight_items.append({
            "item_code": item_code,
            "weight": flt(weight),
            "uom": item.get("uom", "Kg")
        })

    # Sanitize remarks
    sanitized_remarks = None
    if remarks:
        from frappe.utils import sanitize_html
        sanitized_remarks = sanitize_html(str(remarks).strip())[:1000]

    sanitized_reweight_reason = None
    if reweight_reason:
        from frappe.utils import sanitize_html
        sanitized_reweight_reason = sanitize_html(str(reweight_reason).strip())[:500]

    is_reweight = False

    if existing_scrap_weight:
        # UPDATE existing
        scrap_weight = frappe.get_doc("Scrap Weight", existing_scrap_weight)
        scrap_weight.items = []
        for item_data in weight_items:
            scrap_weight.append("items", item_data)

        scrap_weight.entry_method = entry_method or "Manual Entry"  # Phase 8D
        scrap_weight.is_reweight = 1
        scrap_weight.reweight_reason = sanitized_reweight_reason
        scrap_weight.reweight_at = now_datetime()
        scrap_weight.reweight_by = frappe.session.user
        scrap_weight.remarks = sanitized_remarks
        scrap_weight.save()
        is_reweight = True
    else:
        # CREATE new
        scrap_weight = frappe.get_doc({
            "doctype": "Scrap Weight",
            "dropoff": dropoff,
            "posting_date": nowdate(),
            "session": session,
            "pos_profile": session_data.pos_profile,
            "scale": session_data.scale,
            "entry_method": entry_method or "Manual Entry",  # Phase 8D
            "remarks": sanitized_remarks,
            "is_reweight": 0,
            "items": weight_items
        })
        scrap_weight.insert()

    # Reload dropoff to get updated totals (controller syncs on save)
    dropoff_doc = frappe.get_doc("Dropoff", dropoff)

    # Auto-transition status
    # Phase 8A: Auto-transition now handled in controller (dropoff.py before_save)
    dropoff_doc.save()

    return {
        "scrap_weight": scrap_weight.name,
        "total_weight": scrap_weight.total_weight,
        "is_reweight": is_reweight,
        "dropoff_status": dropoff_doc.status,
        "dropoff_total_scrap": dropoff_doc.total_scrap_weight,
        "truck_variance": dropoff_doc.truck_variance,
        "truck_variance_percent": dropoff_doc.truck_variance_percent,
        "variance_ok": dropoff_doc.variance_ok
    }


@frappe.whitelist()
def load_scrap_weight(scrap_weight_id):
    """
    Load existing Scrap Weight for editing (reweight).

    Args:
        scrap_weight_id: Scrap Weight document name

    Returns:
        dict: Scrap weight data with items
    """
    check_pos_operator()

    sw = frappe.get_doc("Scrap Weight", scrap_weight_id)

    items = []
    for item in sw.items:
        items.append({
            "item_code": item.item_code,
            "item_name": item.item_name,
            "weight": item.weight,
            "uom": item.uom
        })

    return {
        "name": sw.name,
        "dropoff": sw.dropoff,
        "items": items,
        "remarks": sw.remarks,
        "is_reweight": sw.is_reweight
    }


# =============================================================================
# VERIFICATION & COMPLETION
# =============================================================================

@frappe.whitelist()
def get_dropoff_verification(dropoff):
    """
    Get verification summary for completion screen.

    Args:
        dropoff: Dropoff document name

    Returns:
        dict: Complete verification data with can_complete flag
    """
    check_pos_operator()

    doc = frappe.get_doc("Dropoff", dropoff)

    # Get scrap records
    scrap_records = frappe.get_all(
        "Scrap Weight",
        filters={"dropoff": dropoff},
        fields=["name", "total_weight", "is_reweight", "posting_date", "posting_time"],
        order_by="creation asc"
    )

    # Get orders with fulfillment info
    orders = []
    for order_row in doc.orders:
        order_data = frappe.db.get_value(
            "POS Order",
            order_row.pos_order,
            ["name", "supplier_name", "contracted_weight", "total_received",
             "fulfillment_percent", "fulfillment_status"],
            as_dict=True
        )
        if order_data:
            order_data["allocated_weight"] = order_row.allocated_weight
            orders.append(order_data)

    # Determine if can complete
    blockers = []

    if not doc.gross_weight:
        blockers.append("Missing gross weight")
    if not doc.tare_weight:
        blockers.append("Missing tare weight")
    if not doc.total_scrap_weight:
        blockers.append("No scrap weights recorded")
    if not doc.truck_variance_ok:
        blockers.append(f"Truck variance {doc.truck_variance_percent:.2f}% exceeds threshold {doc.truck_variance_threshold_percent}%")
    if not doc.indicated_variance_ok:
        blockers.append(f"Indicated variance {doc.indicated_variance_percent:.2f}% exceeds threshold {doc.indicated_variance_threshold_percent}%")
    if doc.status == "Completed":
        blockers.append("Already completed")
    if doc.status == "Cancelled":
        blockers.append("Dropoff is cancelled")

    # Phase 8A: Can complete from "In Progress" status (auto-transitions to Completed when all weights done)
    can_complete = len(blockers) == 0 and doc.status in ["In Progress", "Completed"]

    return {
        "dropoff": doc.name,
        "status": doc.status,
        # Truck
        "license_plate": doc.license_plate,
        "gross_weight": doc.gross_weight,
        "tare_weight": doc.tare_weight,
        "net_weight": doc.net_weight,
        "is_reweighed": doc.is_reweighed,
        # Scrap
        "scrap_records": scrap_records,
        "total_scrap_weight": doc.total_scrap_weight,
        # Phase 8B: Dual Variance
        "total_truck_weight": doc.total_truck_weight,
        "truck_variance": doc.truck_variance,
        "truck_variance_percent": doc.truck_variance_percent,
        "truck_variance_threshold_percent": doc.truck_variance_threshold_percent,
        "truck_variance_ok": doc.truck_variance_ok,
        "total_indicated_weight": doc.total_indicated_weight,
        "total_actual_weight": doc.total_actual_weight,
        "indicated_variance": doc.indicated_variance,
        "indicated_variance_percent": doc.indicated_variance_percent,
        "indicated_variance_threshold_percent": doc.indicated_variance_threshold_percent,
        "indicated_variance_ok": doc.indicated_variance_ok,
        # Orders
        "orders": orders,
        # Completion
        "can_complete": can_complete,
        "completion_blockers": blockers
    }


@frappe.whitelist()
def complete_dropoff(dropoff):
    """
    Complete dropoff - set status to Closed, allocate weights to orders.

    Args:
        dropoff: Dropoff document name

    Returns:
        dict: Completion result with updated orders
    """
    check_pos_operator()

    doc = frappe.get_doc("Dropoff", dropoff)

    # Phase 8A: Validate can complete (status will auto-transition to Completed)
    if doc.status not in ["In Progress", "Completed"]:
        frappe.throw(_("Can only complete dropoff from In Progress status. Current: {0}").format(doc.status))

    if not doc.gross_weight or not doc.tare_weight:
        frappe.throw(_("Both gross and tare weights are required"))

    if not doc.total_scrap_weight:
        frappe.throw(_("No scrap weights recorded"))

    # Phase 8A: Set status to Completed - auto-transition in controller will handle this
    # But we force it here for the API to ensure it's completed
    doc.status = "Completed"
    doc.save()

    # Get updated order info
    orders_updated = []
    for order_row in doc.orders:
        order_data = frappe.db.get_value(
            "POS Order",
            order_row.pos_order,
            ["name", "total_received", "fulfillment_percent", "fulfillment_status"],
            as_dict=True
        )
        if order_data:
            order_data["allocated_weight"] = order_row.allocated_weight
            orders_updated.append(order_data)

    return {
        "dropoff": doc.name,
        "status": "Completed",
        "orders_updated": orders_updated
    }


# =============================================================================
# PHOTO HANDLING
# =============================================================================

@frappe.whitelist()
def save_weight_photo(parent_doctype, parent_doc, photo_url, weight_type=None,
                      dropoff=None, session=None):
    """
    Save a photo to the Weight Photo child table.

    This endpoint adds photos to either Scrap Weight or Truck Weight documents.
    Photos are stored as Attach fields in the Weight Photo child table.

    Args:
        parent_doctype: "Scrap Weight" or "Truck Weight"
        parent_doc: The parent document name (e.g., "WGT-24.12.28-00001")
        photo_url: File URL from upload_file API (e.g., '/files/weight_photo_xxx.jpg')
        weight_type: Optional - "Scrap", "Truck Gross", or "Truck Tare"
        dropoff: Optional - Dropoff document name for quick lookup
        session: Optional - POS Session name for quick lookup

    Returns:
        dict: Success status with photo count
    """
    check_pos_operator()

    # Validate parent_doctype
    if parent_doctype not in ["Scrap Weight", "Truck Weight"]:
        frappe.throw(_("parent_doctype must be 'Scrap Weight' or 'Truck Weight'"))

    # Validate parent_doc exists
    if not frappe.db.exists(parent_doctype, parent_doc):
        frappe.throw(_("{0} '{1}' not found").format(parent_doctype, parent_doc))

    # Get the parent document
    parent = frappe.get_doc(parent_doctype, parent_doc)

    # Extract file name from URL
    file_name = photo_url.split("/")[-1] if photo_url else None

    # Add photo to child table
    parent.append("photos", {
        "photo": photo_url,
        "file_name": file_name,
        "captured_at": now_datetime(),
        "weight_type": weight_type,
        "parent_doctype": parent_doctype,
        "parent_doc": parent_doc,
        "dropoff": dropoff or parent.dropoff,
        "session": session or getattr(parent, "session", None)
    })

    parent.save()

    # Count photos
    photo_count = len(parent.photos)

    return {
        "success": True,
        "parent_doctype": parent_doctype,
        "parent_doc": parent_doc,
        "photo_url": photo_url,
        "photo_count": photo_count
    }


@frappe.whitelist()
def get_weight_photos(parent_doctype, parent_doc):
    """
    Get all photos for a weight document.

    Args:
        parent_doctype: "Scrap Weight" or "Truck Weight"
        parent_doc: The parent document name

    Returns:
        list: Photo records with URLs and metadata
    """
    check_pos_operator()

    if parent_doctype not in ["Scrap Weight", "Truck Weight"]:
        frappe.throw(_("parent_doctype must be 'Scrap Weight' or 'Truck Weight'"))

    if not frappe.db.exists(parent_doctype, parent_doc):
        return []

    photos = frappe.get_all(
        "Weight Photo",
        filters={"parent": parent_doc, "parenttype": parent_doctype},
        fields=["name", "photo", "file_name", "captured_at", "weight_type"],
        order_by="idx asc"
    )

    return photos


@frappe.whitelist()
def delete_weight_photo(parent_doctype, parent_doc, photo_name):
    """
    Delete a photo from the Weight Photo child table.

    Args:
        parent_doctype: "Scrap Weight" or "Truck Weight"
        parent_doc: The parent document name
        photo_name: The Weight Photo child row name

    Returns:
        dict: Success status with remaining photo count
    """
    check_pos_operator()

    if parent_doctype not in ["Scrap Weight", "Truck Weight"]:
        frappe.throw(_("parent_doctype must be 'Scrap Weight' or 'Truck Weight'"))

    if not frappe.db.exists(parent_doctype, parent_doc):
        frappe.throw(_("{0} '{1}' not found").format(parent_doctype, parent_doc))

    parent = frappe.get_doc(parent_doctype, parent_doc)

    # Find and remove the photo row
    photo_found = False
    for i, photo in enumerate(parent.photos):
        if photo.name == photo_name:
            parent.photos.remove(photo)
            photo_found = True
            break

    if not photo_found:
        frappe.throw(_("Photo not found"))

    parent.save()

    return {
        "success": True,
        "photo_count": len(parent.photos)
    }
