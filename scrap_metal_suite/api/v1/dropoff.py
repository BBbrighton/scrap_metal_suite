# Dropoff API Endpoints
# Handles drop-off operations for POS terminal (1-truck-per-dropoff design)

import frappe
from frappe import _
from frappe.utils import flt, nowdate, now_datetime, add_to_date, get_datetime, sanitize_html
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
        "indicated_variance": dropoff_doc.indicated_variance,
        "indicated_variance_percent": dropoff_doc.indicated_variance_percent,
        "variance_ok": dropoff_doc.indicated_variance_ok
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


# NOTE: legacy `complete_dropoff` removed — replaced by container-model version
# defined in the CONTAINER MODEL (v2) section at the bottom of this file.
# See docs/DROPOFF_CONTAINER_REDESIGN.md §5.2.


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


# =============================================================================
# CONTAINER MODEL (v2 — replaces Scrap Weight)
# =============================================================================
#
# These endpoints implement the container-based weighing model from
# docs/DROPOFF_CONTAINER_REDESIGN.md. Each container is a single physical unit
# (bag/bin/pallet) holding one grade at one weight, with its own QR-tagged
# document. The Dropoff is locked to one operator session and one scale at a
# time; changes go through pause/resume/switch/reassign helpers below.
#
# IMPORTANT: item_name is canonical Thai master data — never wrap with `_()`.
# See docs/BILINGUAL_GUIDE.md §2.


def _build_container_print_urls(session, container_name):
    """Resolve sticker print URL for a container based on POS Profile flags.

    Returns a dict that may contain a `sticker` key, or be empty if the
    profile's sticker toggle is off (or no profile is set on the session).
    The per-Dropoff thermal receipt is generated separately — there is no
    per-container thermal format.
    """
    print_urls = {}
    if not session:
        return print_urls

    profile = frappe.db.get_value("POS Session", session, "pos_profile")
    if not profile:
        return print_urls

    enable_sticker = frappe.db.get_value(
        "POS Profile Scrap", profile, "enable_sticker_print"
    )
    if enable_sticker:
        print_urls["sticker"] = (
            f"/printview?doctype=Scrap%20Weight%20Container&name={container_name}"
            f"&format=Scrap%20Weight%20Container%20Sticker&no_letterhead=1"
        )
    return print_urls


def _coerce_bool(value):
    """Accept truthy strings ("1", "true") and native booleans/ints uniformly.

    JSON / form-encoded payloads deliver booleans as strings; the controller-side
    bool() of "0" is True, which we don't want.
    """
    if isinstance(value, str):
        s = value.strip().lower()
        if s in ("true", "1", "yes"):
            return True
        if s in ("false", "0", "no", ""):
            return False
        # Fall through to int conversion attempt for numeric strings.
        try:
            return bool(int(s))
        except (ValueError, TypeError):
            return False
    return bool(value)


@frappe.whitelist()
def add_container(dropoff, session, item_code, net_weight, container_type,
                  entry_method="Manual Entry", deviation_reason=None,
                  deviation_type=None, remarks=None):
    """
    Add a Scrap Weight Container to a Dropoff (the main weighing action).

    First call binds the dropoff's session/scale lock and transitions
    Scheduled → In Progress (handled by `Dropoff._acquire_container_lock`).
    Subsequent calls validate the lock and reuse the bound scale.

    Returns: dict with container, container_no, item_code, item_name,
             net_weight, is_deviation, dropoff_status, dropoff_total,
             container_count, print_urls.
    """
    check_pos_operator()

    # Validate POS Session is open and belongs to current user.
    session_data = frappe.db.get_value(
        "POS Session", session,
        ["status", "scale", "pos_profile", "operator"],
        as_dict=True
    )
    if not session_data or session_data.status != "Open":
        frappe.throw(_("Session {0} is not open").format(session))
    if session_data.operator != frappe.session.user:
        frappe.throw(_("This session does not belong to the current user"))

    _update_session_activity(session)

    # Load the dropoff and run lock validation through the controller.
    dropoff_doc = frappe.get_doc("Dropoff", dropoff)
    dropoff_doc._validate_container_lock(session)

    scale = session_data.scale
    if not scale:
        frappe.throw(_("Session {0} has no scale assigned").format(session))

    # Acquire (or no-op refresh) the lock; controller mutates in-memory only.
    dropoff_doc._acquire_container_lock(session, scale)

    # Detect deviation against the dropoff's expected items.
    expected_codes = {
        row.item for row in dropoff_doc.expected_items if row.item
    }
    is_deviation = item_code not in expected_codes

    # Validate scale capacity (mirror the existing record_scrap_weight check).
    try:
        net_weight_f = float(net_weight)
    except (ValueError, TypeError):
        frappe.throw(_("Invalid net weight"))
    if net_weight_f <= 0:
        frappe.throw(_("Net weight must be greater than 0"))

    scale_max = frappe.db.get_value("Scale", scale, "max_capacity_kg")
    if scale_max and net_weight_f > flt(scale_max):
        frappe.throw(
            _("Weight {0} exceeds scale capacity {1}").format(net_weight_f, scale_max)
        )

    sanitized_remarks = None
    if remarks:
        sanitized_remarks = sanitize_html(str(remarks).strip())[:1000]

    container = frappe.get_doc({
        "doctype": "Scrap Weight Container",
        "dropoff": dropoff,
        "session": session,
        "scale": scale,
        "operator": frappe.session.user,
        "item_code": item_code,
        # item_name auto-populated by controller before_insert (canonical Thai)
        "container_type": container_type,
        "net_weight": flt(net_weight_f),
        "entry_method": entry_method,
        "deviation_reason": deviation_reason or None,
        "deviation_type": deviation_type or None,
        "remarks": sanitized_remarks,
    })
    container.insert()

    # Save the dropoff so sync_actual_items / lock fields persist.
    dropoff_doc.save()

    print_urls = _build_container_print_urls(session, container.name)

    return {
        "success": True,
        "container": container.name,
        "container_no": container.container_no,
        "item_code": container.item_code,
        # NOTE: item_name is canonical — never translated.
        "item_name": container.item_name,
        "net_weight": container.net_weight,
        "is_deviation": container.is_deviation,
        "dropoff_status": dropoff_doc.status,
        "dropoff_total": dropoff_doc.total_actual_weight,
        "container_count": dropoff_doc.container_count,
        "print_urls": print_urls,
    }


@frappe.whitelist()
def reweigh_container(container, net_weight, reason, entry_method="Manual Entry"):
    """
    Reweigh an existing container in place. Appends a Reweigh row to the
    container's weight history; updates the dropoff aggregation.
    """
    check_pos_operator()

    container_doc = frappe.get_doc("Scrap Weight Container", container)
    container_doc.record_reweigh(flt(net_weight), reason, entry_method)

    # Re-aggregate parent dropoff totals.
    dropoff_doc = frappe.get_doc("Dropoff", container_doc.dropoff)
    dropoff_doc.save()

    print_urls = _build_container_print_urls(container_doc.session, container_doc.name)

    return {
        "success": True,
        "container": container_doc.name,
        "net_weight": container_doc.net_weight,
        "is_reweighed": container_doc.is_reweighed,
        "dropoff_total": dropoff_doc.total_actual_weight,
        "print_urls": print_urls,
    }


@frappe.whitelist()
def void_container(container, reason, superseded_by=None):
    """
    Mark a single container as Voided. Non-destructive (history preserved).
    """
    check_pos_operator()

    container_doc = frappe.get_doc("Scrap Weight Container", container)
    container_doc.record_void(reason, superseded_by)

    dropoff_doc = frappe.get_doc("Dropoff", container_doc.dropoff)
    dropoff_doc.save()

    return {
        "success": True,
        "container": container_doc.name,
        "status": "Voided",
        "dropoff_total": dropoff_doc.total_actual_weight,
    }


@frappe.whitelist()
def get_container(name):
    """
    Lookup a container by name (typically from a QR scan).

    Returns the document as a dict. `item_name` is canonical Thai and is
    rendered as-is (never wrapped with `_()`).
    """
    check_pos_operator()

    doc = frappe.get_doc("Scrap Weight Container", name)
    return doc.as_dict()


@frappe.whitelist()
def list_containers(dropoff, include_voided=False):
    """
    List containers for a dropoff, sorted by container_no ascending.

    Args:
        dropoff: Dropoff document name
        include_voided: Include status=Voided records when truthy.
    """
    check_pos_operator()

    include_voided = _coerce_bool(include_voided)

    filters = {"dropoff": dropoff}
    if not include_voided:
        filters["status"] = ["!=", "Voided"]

    rows = frappe.get_all(
        "Scrap Weight Container",
        filters=filters,
        fields=[
            "name", "container_no", "item_code", "item_name", "container_type",
            "net_weight", "status", "is_deviation", "deviation_approved_by",
            "creation", "operator",
        ],
        order_by="container_no asc",
    )
    return rows


@frappe.whitelist()
def pause_dropoff(dropoff, reason=None):
    """
    Pause an in-progress dropoff. Clears session lock; scale lock survives.
    Status: In Progress → Paused.
    """
    check_pos_operator()

    doc = frappe.get_doc("Dropoff", dropoff)
    doc.pause_weighing(reason)

    return {
        "success": True,
        "status": "Paused",
        "paused_at": doc.paused_at,
    }


@frappe.whitelist()
def resume_dropoff(dropoff, session):
    """
    Resume a paused dropoff under a new (or same) POS Session on the same
    pinned scale. Status: Paused → In Progress.
    """
    check_pos_operator()

    doc = frappe.get_doc("Dropoff", dropoff)
    doc.resume_weighing(session)

    return {
        "success": True,
        "status": "In Progress",
        "weighing_session": session,
    }


@frappe.whitelist()
def reassign_dropoff(dropoff, new_session, reason):
    """
    Audit-only reassignment of the dropoff's session lock. The new session
    must be on the same pinned scale (run switch_scale first if not).
    No role guard yet — design doc §5.2.
    """
    check_pos_operator()

    doc = frappe.get_doc("Dropoff", dropoff)
    doc.reassign_session(new_session, reason)

    return {
        "success": True,
        "weighing_session": doc.weighing_session,
        "weighing_reassigned_at": doc.weighing_reassigned_at,
    }


@frappe.whitelist()
def switch_scale(dropoff, new_scale, reason):
    """
    Audit-only scale switch. Existing containers keep their original scale
    stamp; future containers will record `new_scale`. No role guard yet.
    """
    check_pos_operator()

    doc = frappe.get_doc("Dropoff", dropoff)
    doc.switch_scale(new_scale, reason)

    return {
        "success": True,
        "weighing_scale": doc.weighing_scale,
        "weighing_scale_changed_at": doc.weighing_scale_changed_at,
    }


@frappe.whitelist()
def void_dropoff_weighing(dropoff, reason):
    """
    Void all Active containers and reset the dropoff for fresh re-weighing.
    Lock fields cleared; status reverts to Scheduled.
    """
    check_pos_operator()

    doc = frappe.get_doc("Dropoff", dropoff)

    # Snapshot the count before voiding (controller mutates them).
    voided_count = frappe.db.count(
        "Scrap Weight Container",
        {"dropoff": dropoff, "status": "Active"},
    )

    doc.void_weighing(reason)

    return {
        "success": True,
        "status": doc.status,
        "voided_count": voided_count,
    }


@frappe.whitelist()
def complete_dropoff(dropoff):
    """
    Finalise a dropoff. Validates:
      - status is In Progress (Paused → throw, must resume first)
      - no unapproved deviations
      - truck weights present (gross + tare + net)

    Status → Completed. Verification status is recomputed by the controller.
    """
    check_pos_operator()

    doc = frappe.get_doc("Dropoff", dropoff)

    if doc.status == "Paused":
        frappe.throw(_("Cannot complete: dropoff is paused"))

    if doc.status not in ("In Progress", "Completed"):
        frappe.throw(
            _("Cannot complete: status is {0}").format(doc.status)
        )

    if doc.has_unapproved_deviation:
        frappe.throw(_("Cannot complete: there are unapproved deviations"))

    if not (doc.gross_weight and doc.tare_weight and doc.net_weight):
        frappe.throw(_("Cannot complete: truck weights (gross, tare, net) are required"))

    doc.status = "Completed"
    doc.save()

    return {
        "success": True,
        "status": "Completed",
        "verification_status": doc.verification_status,
    }


@frappe.whitelist()
def approve_container_deviation(container, reason=None):
    """
    Approve a flagged deviation on a single container. No role guard yet —
    audit-only. Re-aggregates the parent dropoff so the
    `has_unapproved_deviation` flag clears.
    """
    check_pos_operator()

    container_doc = frappe.get_doc("Scrap Weight Container", container)
    container_doc.approve_deviation(reason)

    dropoff_doc = frappe.get_doc("Dropoff", container_doc.dropoff)
    dropoff_doc.save()

    return {
        "success": True,
        "container": container_doc.name,
        "approved_by": container_doc.deviation_approved_by,
        "approved_at": container_doc.deviation_approved_at,
    }


@frappe.whitelist()
def verify_dropoff(dropoff, override_reason=None):
    """
    Manually mark a dropoff as Verified. Idempotent if already Verified;
    requires `override_reason` if currently Needs Review (controller throws).
    No role guard yet — audit-only.
    """
    check_pos_operator()

    doc = frappe.get_doc("Dropoff", dropoff)
    doc.mark_verified(override_reason)

    return {
        "success": True,
        "verification_status": doc.verification_status,
        "overridden": doc.verification_overridden,
    }
