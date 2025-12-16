# POS API Endpoints
# Handles POS session management, scrap weight recording, and order lookup

import frappe
from frappe import _
from frappe.utils import flt, nowdate


def check_pos_operator():
    """
    Check if current user has POS Operator role.
    Raises PermissionError if not authorized.
    System Manager is also allowed for admin access.
    """
    if frappe.session.user == "Guest":
        frappe.throw(_("Please login to access POS"), frappe.AuthenticationError)

    user_roles = frappe.get_roles(frappe.session.user)
    if "POS Operator" not in user_roles and "System Manager" not in user_roles:
        frappe.throw(_("Access denied. POS Operator role required."), frappe.PermissionError)


def _calculate_variance(order):
    """
    Calculate weight variance between truck net weight and scrap weight.
    Internal function - not exposed as API.

    Variance = Net Truck Weight - Total Scrap Weight
    Positive variance = more weight on truck scale (normal due to moisture, debris)
    Negative variance = more weight on scrap scale (possible issue)
    """
    if order.net_truck_weight and order.total_scrap_weight:
        order.weight_variance = flt(order.net_truck_weight) - flt(order.total_scrap_weight)

        # Calculate percentage (avoid division by zero)
        if order.net_truck_weight > 0:
            order.weight_variance_percent = (order.weight_variance / order.net_truck_weight) * 100
        else:
            order.weight_variance_percent = 0


@frappe.whitelist()
def get_pos_profile(profile_name):
    """
    Get POS profile configuration with items to display.

    Args:
        profile_name: Name of the POS Profile Scrap

    Returns:
        dict: Profile config with items list
    """
    check_pos_operator()
    profile = frappe.get_doc("POS Profile Scrap", profile_name)

    return {
        "profile_name": profile.profile_name,
        "warehouse": profile.warehouse,
        "items": [
            {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "display_order": item.display_order
            }
            for item in sorted(profile.items, key=lambda x: x.display_order or 0)
        ]
    }


@frappe.whitelist()
def get_active_session():
    """
    Get the current user's active (open) POS session.

    Returns:
        dict: Session details or None if no active session
    """
    check_pos_operator()
    session = frappe.db.get_value(
        "POS Session",
        {"operator": frappe.session.user, "status": "Open"},
        ["name", "pos_profile", "opening_time", "total_purchases", "total_weight", "scale"],
        as_dict=True
    )

    # If session has a scale, get scale details
    if session and session.scale:
        scale_info = frappe.db.get_value(
            "Scale",
            session.scale,
            ["scale_name", "scale_type", "usage_type", "location", "max_capacity_kg"],
            as_dict=True
        )
        if scale_info:
            session.scale_name = scale_info.scale_name
            session.scale_type = scale_info.scale_type
            session.scale_usage_type = scale_info.usage_type
            session.scale_location = scale_info.location
            session.scale_max_capacity_kg = scale_info.max_capacity_kg  # CLIENT-SIDE VALIDATION: Include max capacity

    return session


@frappe.whitelist()
def open_session(pos_profile):
    """
    Open a new POS session for the current user.

    Args:
        pos_profile: Name of the POS Profile Scrap to use

    Returns:
        dict: New session details
    """
    check_pos_operator()
    # Check for existing open session
    existing = frappe.db.exists(
        "POS Session",
        {"operator": frappe.session.user, "status": "Open"}
    )

    if existing:
        frappe.throw(
            _("You already have an open session: {0}. Please close it first.").format(existing)
        )

    # Create new session
    session = frappe.get_doc({
        "doctype": "POS Session",
        "pos_profile": pos_profile,
        "status": "Open"
    })
    session.insert()

    return {
        "session": session.name,
        "pos_profile": session.pos_profile,
        "operator": session.operator,
        "opening_time": session.opening_time
    }


@frappe.whitelist()
def close_session(session):
    """
    Close a POS session and calculate totals.

    Args:
        session: Name of the POS Session to close

    Returns:
        dict: Session totals
    """
    check_pos_operator()
    session_doc = frappe.get_doc("POS Session", session)

    # Verify ownership or authority
    if session_doc.operator != frappe.session.user:
        # Check if user has authority to close any session
        # For now, just block - can add authority check later
        frappe.throw(_("You can only close your own sessions"))

    return session_doc.close_session()


@frappe.whitelist()
def lookup_order(query):
    """
    Search for POS Orders by document name, order_id, or license_plate.

    Search logic:
    1. First try exact match on name, order_id, or license_plate (no date restriction)
    2. If no exact match, try partial match with dropoff_date within +/- 2 days

    Args:
        query: Search term (document name, order_id, or license_plate)

    Returns:
        list: Matching orders with supplier_name, order_date, dropoff_date, license_plate, status
    """
    check_pos_operator()
    from frappe.utils import add_days

    if not query or len(query) < 2:
        return []

    fields = ["name", "order_id", "supplier", "supplier_name", "order_date", "dropoff_date", "license_plate", "status"]

    # Step 1: Try exact match on name (document ID)
    exact_by_name = frappe.db.get_value(
        "POS Order",
        {"name": query},
        fields,
        as_dict=True
    )
    if exact_by_name:
        return [exact_by_name]

    # Step 2: Try exact match on order_id
    exact_by_order_id = frappe.db.get_value(
        "POS Order",
        {"order_id": query},
        fields,
        as_dict=True
    )
    if exact_by_order_id:
        return [exact_by_order_id]

    # Step 3: Try exact match on license_plate
    exact_by_plate = frappe.db.get_value(
        "POS Order",
        {"license_plate": query},
        fields,
        as_dict=True
    )
    if exact_by_plate:
        return [exact_by_plate]

    # Step 4: Partial match - search within +/- 2 days of dropoff_date
    today = nowdate()
    date_start = add_days(today, -2)
    date_end = add_days(today, 2)

    orders = frappe.db.sql("""
        SELECT
            name, order_id, supplier, supplier_name, order_date, dropoff_date, license_plate, status
        FROM `tabPOS Order`
        WHERE
            dropoff_date BETWEEN %(date_start)s AND %(date_end)s
            AND (
                name LIKE %(query)s
                OR order_id LIKE %(query)s
                OR license_plate LIKE %(query)s
            )
        ORDER BY dropoff_date DESC, creation DESC
        LIMIT 10
    """, {"query": f"%{query}%", "date_start": date_start, "date_end": date_end}, as_dict=True)

    return orders


@frappe.whitelist()
def get_order_details(order_id):
    """
    Get full details of a POS Order including truck weight data and order items.

    Args:
        order_id: POS Order name

    Returns:
        dict: Order details including supplier info, truck weights, and order items
    """
    check_pos_operator()
    order = frappe.get_doc("POS Order", order_id)

    # Get supplier details
    supplier_data = frappe.db.get_value(
        "Supplier",
        order.supplier,
        ["supplier_name"],
        as_dict=True
    )

    # Get order items (indicated/promised items from supplier)
    order_items = []
    if hasattr(order, 'order_items') and order.order_items:
        for item in order.order_items:
            order_items.append({
                "item_code": item.item_code,
                "item_name": item.item_name,
                "uom": item.uom,
                "weight": item.weight  # Indicated weight
            })

    # Check for existing scrap weight for this order + current session's scale
    existing_scrap_weight = None
    session = frappe.db.get_value(
        "POS Session",
        {"operator": frappe.session.user, "status": "Open"},
        ["name", "scale"],
        as_dict=True
    )
    if session and session.scale:
        existing_scrap_weight = frappe.db.get_value(
            "Scrap Weight",
            {"pos_order": order.name, "scale": session.scale},
            "name"
        )

    return {
        "order_id": order.name,
        "supplier": order.supplier,
        "supplier_name": order.supplier_name or (supplier_data.supplier_name if supplier_data else None),
        "order_date": order.order_date,
        "dropoff_date": getattr(order, 'dropoff_date', None),
        "license_plate": order.license_plate,
        "purchase_order": order.purchase_order,
        "notes": order.notes,
        "status": order.status,
        # Order items (indicated by supplier)
        "order_items": order_items,
        # Existing scrap weight for this order+scale (for reweight)
        "existing_scrap_weight": existing_scrap_weight,
        # Scale fields
        "scrap_scale": getattr(order, 'scrap_scale', None),
        # Truck weight fields
        "gross_weight": order.gross_weight,
        "gross_weight_time": order.gross_weight_time,
        "gross_weight_scale": getattr(order, 'gross_weight_scale', None),
        "tare_weight": order.tare_weight,
        "tare_weight_time": order.tare_weight_time,
        "tare_weight_scale": getattr(order, 'tare_weight_scale', None),
        "net_truck_weight": order.net_truck_weight,
        "total_scrap_weight": order.total_scrap_weight,
        "weight_variance": order.weight_variance,
        "weight_variance_percent": order.weight_variance_percent,
        "is_truck_reweighed": order.is_truck_reweighed,
        "is_scrap_reweighed": order.is_scrap_reweighed
    }


@frappe.whitelist()
def load_scrap_weight(scrap_weight_id):
    """
    Load existing Scrap Weight items into cart for editing (reweight).

    Args:
        scrap_weight_id: Scrap Weight document name

    Returns:
        dict: Scrap weight data with items for loading into cart
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
        "pos_order": sw.pos_order,
        "items": items,
        "remarks": sw.remarks,
        "is_reweight": sw.is_reweight
    }


@frappe.whitelist()
def create_scrap_weight(session, pos_order, items, remarks=None,
                        existing_scrap_weight=None, reweight_reason=None):
    """
    Record or update scrap weight for a POS Order.

    If existing_scrap_weight is provided, updates the existing document.
    Otherwise creates a new one.

    Args:
        session: POS Session name (required)
        pos_order: POS Order name (required)
        items: JSON list of items [{item_code, weight, uom}]
        remarks: Optional remarks
        existing_scrap_weight: Optional - if provided, updates this document instead of creating new
        reweight_reason: Optional - reason for reweight (required if is_reweight)

    Returns:
        dict: {scrap_weight, total_weight, is_reweight}
    """
    check_pos_operator()
    import json

    if isinstance(items, str):
        items = json.loads(items)

    if not items:
        frappe.throw(_("At least one item is required"))

    # Validate session is open and get scale
    session_data = frappe.db.get_value(
        "POS Session",
        session,
        ["status", "scale", "pos_profile", "operator"],
        as_dict=True
    )
    if not session_data or session_data.status != "Open":
        frappe.throw(_("Session {0} is not open").format(session))

    # SECURITY FIX: Verify session belongs to current user
    if session_data.operator != frappe.session.user:
        frappe.throw(_("This session does not belong to the current user"))

    # Get scale's max capacity from database for validation
    scale_max_capacity = None
    scale_name = None
    if session_data.scale:
        scale_info = frappe.db.get_value("Scale", session_data.scale,
                                        ["max_capacity_kg", "scale_name"], as_dict=True)
        if scale_info:
            scale_max_capacity = scale_info.max_capacity_kg
            scale_name = scale_info.scale_name

    # Validate POS Order exists
    order_data = frappe.db.get_value(
        "POS Order",
        pos_order,
        ["name", "supplier", "status", "license_plate"],
        as_dict=True
    )

    if not order_data:
        frappe.throw(_("POS Order {0} not found").format(pos_order))

    # Build items list with SECURITY FIX: proper weight validation
    weight_items = []
    for item in items:
        item_code = item.get("item_code")

        # SECURITY FIX: Validate weight value
        try:
            weight = float(item.get("weight", 0))
        except (ValueError, TypeError):
            frappe.throw(_("Invalid weight value for item {0}").format(item_code))

        # SECURITY FIX: Weight must be greater than zero
        if weight <= 0:
            frappe.throw(_("Weight must be greater than zero for item {0}").format(item_code))

        # SECURITY FIX: Weight must not exceed scale capacity
        if scale_max_capacity and weight > scale_max_capacity:
            frappe.throw(_("Weight {0} kg exceeds scale {1} maximum capacity of {2} kg").format(
                weight, scale_name, scale_max_capacity))

        item_data = {
            "item_code": item_code,
            "weight": flt(weight),
            "uom": item.get("uom", "Kg")
        }
        weight_items.append(item_data)

    # SECURITY FIX: Sanitize remarks to prevent XSS
    sanitized_remarks = None
    if remarks:
        from frappe.utils import sanitize_html
        sanitized_remarks = sanitize_html(str(remarks).strip())
        if len(sanitized_remarks) > 1000:
            frappe.throw(_("Remarks exceed maximum length of {0} characters").format(1000))

    # SECURITY FIX: Sanitize reweight_reason to prevent XSS
    sanitized_reweight_reason = None
    if reweight_reason:
        from frappe.utils import sanitize_html
        sanitized_reweight_reason = sanitize_html(str(reweight_reason).strip())
        if len(sanitized_reweight_reason) > 500:
            frappe.throw(_("Reweight reason exceed maximum length of {0} characters").format(500))

    is_reweight = False

    if existing_scrap_weight:
        # UPDATE existing document
        scrap_weight = frappe.get_doc("Scrap Weight", existing_scrap_weight)

        # Clear existing items and add new ones
        scrap_weight.items = []
        for item_data in weight_items:
            scrap_weight.append("items", item_data)

        # Mark as reweight
        scrap_weight.is_reweight = 1
        scrap_weight.reweight_reason = sanitized_reweight_reason
        scrap_weight.reweight_at = frappe.utils.now_datetime()
        scrap_weight.reweight_by = frappe.session.user
        scrap_weight.remarks = sanitized_remarks

        scrap_weight.save()
        is_reweight = True
    else:
        # CREATE new document
        scrap_weight = frappe.get_doc({
            "doctype": "Scrap Weight",
            "pos_order": pos_order,
            "supplier": order_data.supplier,
            "posting_date": nowdate(),
            "session": session,
            "pos_profile": session_data.pos_profile,
            "scale": session_data.scale,
            "remarks": sanitized_remarks,
            "is_reweight": 0,
            "items": weight_items
        })
        scrap_weight.insert()

    # Update POS Order
    order_doc = frappe.get_doc("POS Order", pos_order)
    order_doc.status = "Processed"
    order_doc.processed_by = frappe.session.user
    order_doc.processed_time = frappe.utils.now_datetime()

    # Update total scrap weight on order (sum of all scrap weights)
    total_scrap = frappe.db.sql("""
        SELECT COALESCE(SUM(total_weight), 0) as total
        FROM `tabScrap Weight`
        WHERE pos_order = %s
    """, pos_order, as_dict=True)[0].total
    order_doc.total_scrap_weight = flt(total_scrap)

    # Calculate variance if truck weights exist
    if order_doc.net_truck_weight:
        _calculate_variance(order_doc)

    order_doc.save()

    return {
        "scrap_weight": scrap_weight.name,
        "total_weight": scrap_weight.total_weight,
        "order_id": pos_order,
        "is_reweight": is_reweight,
        "total_scrap_weight": order_doc.total_scrap_weight,
        "weight_variance": order_doc.weight_variance,
        "weight_variance_percent": order_doc.weight_variance_percent
    }


@frappe.whitelist()
def get_session_weights(session):
    """
    Get all scrap weights for a session.

    Args:
        session: POS Session name

    Returns:
        list: Scrap weights with details
    """
    check_pos_operator()

    # Verify user owns this session or is System Manager
    session_operator = frappe.db.get_value("POS Session", session, "operator")
    if not session_operator:
        frappe.throw(_("Session {0} not found").format(session))

    user_roles = frappe.get_roles(frappe.session.user)
    if session_operator != frappe.session.user and "System Manager" not in user_roles:
        frappe.throw(_("You can only view your own session data"), frappe.PermissionError)

    weights = frappe.get_all(
        "Scrap Weight",
        filters={"session": session},
        fields=[
            "name", "supplier", "supplier_name", "pos_order",
            "total_weight", "posting_date", "posting_time"
        ],
        order_by="creation desc"
    )

    return weights


@frappe.whitelist()
def get_session_summary(session):
    """
    Get summary statistics for a session.

    Args:
        session: POS Session name

    Returns:
        dict: Session summary with totals
    """
    check_pos_operator()
    totals = frappe.db.sql("""
        SELECT
            COUNT(*) as weight_count,
            COALESCE(SUM(total_weight), 0) as total_weight
        FROM `tabScrap Weight`
        WHERE session = %s
    """, session, as_dict=True)[0]

    session_doc = frappe.db.get_value(
        "POS Session",
        session,
        ["name", "pos_profile", "operator", "opening_time", "status"],
        as_dict=True
    )

    return {
        "session": session_doc,
        "totals": totals
    }


@frappe.whitelist()
def record_truck_weight(pos_order, weight_type, weight, scale=None, remarks=None):
    """
    Record truck gross or tare weight for a POS Order.

    Args:
        pos_order: POS Order name
        weight_type: 'gross' or 'tare'
        weight: Weight in kg
        scale: Scale name used for this weighing (optional)
        remarks: Optional remarks/notes

    Returns:
        dict: Updated order with calculated fields
    """
    check_pos_operator()

    if weight_type not in ['gross', 'tare']:
        frappe.throw(_("weight_type must be 'gross' or 'tare'"))

    # SECURITY FIX: Validate weight value properly
    try:
        weight = float(weight)
    except (ValueError, TypeError):
        frappe.throw(_("Invalid weight value"))

    if weight <= 0:
        frappe.throw(_("Weight must be greater than 0"))

    # SECURITY FIX: Get scale's max capacity from database for validation
    scale_max_capacity = None
    scale_name = None
    if scale:
        scale_info = frappe.db.get_value("Scale", scale,
                                        ["max_capacity_kg", "scale_name"], as_dict=True)
        if not scale_info:
            frappe.throw(_("Scale not found: {0}").format(scale))
        scale_max_capacity = scale_info.max_capacity_kg
        scale_name = scale_info.scale_name

        # SECURITY FIX: Weight must not exceed scale capacity
        if scale_max_capacity and weight > scale_max_capacity:
            frappe.throw(_("Weight {0} kg exceeds scale {1} maximum capacity of {2} kg").format(
                weight, scale_name, scale_max_capacity))

    weight = flt(weight)

    order = frappe.get_doc("POS Order", pos_order)

    # Record the weight with timestamp and scale
    if weight_type == 'gross':
        order.gross_weight = weight
        order.gross_weight_time = frappe.utils.now_datetime()
        if scale:
            order.gross_weight_scale = scale
    else:
        order.tare_weight = weight
        order.tare_weight_time = frappe.utils.now_datetime()
        if scale:
            order.tare_weight_scale = scale

    # SECURITY FIX: Update remarks with XSS sanitization
    if remarks and hasattr(order, 'truck_weight_remarks'):
        from frappe.utils import sanitize_html
        sanitized_remarks = sanitize_html(str(remarks).strip())
        if len(sanitized_remarks) > 1000:
            frappe.throw(_("Remarks exceed maximum length of {0} characters").format(1000))
        order.truck_weight_remarks = sanitized_remarks

    # Calculate net truck weight if both weights are available
    if order.gross_weight and order.tare_weight:
        order.net_truck_weight = flt(order.gross_weight) - flt(order.tare_weight)

        # Calculate variance if scrap weight exists
        if order.total_scrap_weight:
            _calculate_variance(order)

    order.save()

    return {
        "order_id": order.name,
        "gross_weight": order.gross_weight,
        "gross_weight_time": order.gross_weight_time,
        "gross_weight_scale": getattr(order, 'gross_weight_scale', None),
        "tare_weight": order.tare_weight,
        "tare_weight_time": order.tare_weight_time,
        "tare_weight_scale": getattr(order, 'tare_weight_scale', None),
        "net_truck_weight": order.net_truck_weight,
        "total_scrap_weight": getattr(order, 'total_scrap_weight', None),
        "weight_variance": getattr(order, 'weight_variance', None),
        "weight_variance_percent": getattr(order, 'weight_variance_percent', None),
        "truck_weight_remarks": getattr(order, 'truck_weight_remarks', None)
    }


@frappe.whitelist()
def save_truck_remarks(pos_order, remarks):
    """
    Save remarks for truck weighing.

    Args:
        pos_order: POS Order name
        remarks: Remarks text

    Returns:
        dict: Success status
    """
    check_pos_operator()

    order = frappe.get_doc("POS Order", pos_order)

    if not hasattr(order, 'truck_weight_remarks'):
        frappe.throw(_("truck_weight_remarks field not found. Please run 'bench migrate' to update the database."))

    order.truck_weight_remarks = remarks
    order.save()

    return {
        "success": True,
        "remarks": order.truck_weight_remarks
    }


@frappe.whitelist()
def update_total_scrap_weight(pos_order):
    """
    Recalculate total scrap weight from all Scrap Weight records for an order.
    Called after scrap weights are recorded.

    Args:
        pos_order: POS Order name

    Returns:
        dict: Updated totals and variance
    """
    check_pos_operator()

    # Sum all scrap weights for this order
    total = frappe.db.sql("""
        SELECT COALESCE(SUM(total_weight), 0) as total
        FROM `tabScrap Weight`
        WHERE pos_order = %s
    """, pos_order, as_dict=True)[0].total

    order = frappe.get_doc("POS Order", pos_order)
    order.total_scrap_weight = flt(total)

    # Calculate variance if net truck weight exists
    if order.net_truck_weight:
        _calculate_variance(order)

    order.save()

    return {
        "order_id": order.name,
        "total_scrap_weight": order.total_scrap_weight,
        "net_truck_weight": order.net_truck_weight,
        "weight_variance": order.weight_variance,
        "weight_variance_percent": order.weight_variance_percent
    }


@frappe.whitelist()
def mark_reweighed(pos_order, reweight_type):
    """
    Mark an order as having been reweighed (truck or scrap).

    Args:
        pos_order: POS Order name
        reweight_type: 'truck' or 'scrap'

    Returns:
        dict: Updated flags
    """
    check_pos_operator()

    if reweight_type not in ['truck', 'scrap']:
        frappe.throw(_("reweight_type must be 'truck' or 'scrap'"))

    order = frappe.get_doc("POS Order", pos_order)

    if reweight_type == 'truck':
        order.is_truck_reweighed = 1
    else:
        order.is_scrap_reweighed = 1

    order.save()

    return {
        "order_id": order.name,
        "is_truck_reweighed": order.is_truck_reweighed,
        "is_scrap_reweighed": order.is_scrap_reweighed
    }


@frappe.whitelist()
def get_scales(usage_type=None, scale_type=None):
    """
    Get list of all scales with their status.
    Active scales are selectable, inactive are greyed out.

    Args:
        usage_type: Filter by usage type - 'Scrap' or 'Truck' (recommended)
        scale_type: Optional filter by scale type (e.g., 'Weighbridge', 'Platform')

    Returns:
        list: Scales with name, type, location, is_active
    """
    check_pos_operator()

    filters = {}
    if usage_type:
        filters["usage_type"] = usage_type
    if scale_type:
        filters["scale_type"] = scale_type

    scales = frappe.get_all(
        "Scale",
        filters=filters,
        fields=["name", "scale_name", "scale_type", "usage_type", "location", "max_capacity_kg", "is_active", "in_use", "in_use_by_session"],
        order_by="scale_name asc"
    )

    return scales


@frappe.whitelist()
def get_scale_by_id(scale_id):
    """
    Get scale details by ID (used after QR scan).
    Extracts scale name from URL if needed.

    Args:
        scale_id: Scale name or URL containing scale name

    Returns:
        dict: Scale details or error
    """
    check_pos_operator()

    # Extract scale name from URL if needed
    # URL format: https://yoursite.com/scale/SCALE-001
    if '/scale/' in scale_id:
        scale_id = scale_id.split('/scale/')[-1].split('?')[0].strip()

    # Clean up the scale ID
    scale_id = scale_id.strip().upper()

    if not scale_id:
        return {"error": "Invalid scale ID"}

    # Try to find scale
    scale = frappe.db.get_value(
        "Scale",
        {"scale_name": scale_id},
        ["name", "scale_name", "scale_type", "usage_type", "location", "max_capacity_kg", "is_active"],
        as_dict=True
    )

    if not scale:
        # Also try by document name
        scale = frappe.db.get_value(
            "Scale",
            scale_id,
            ["name", "scale_name", "scale_type", "usage_type", "location", "max_capacity_kg", "is_active"],
            as_dict=True
        )

    if not scale:
        return {"error": f"Scale '{scale_id}' not found"}

    if not scale.is_active:
        return {"error": f"Scale '{scale.scale_name}' is not active", "scale": scale}

    return {"scale": scale}


@frappe.whitelist()
def set_session_scale(session, scale):
    """
    Set the scale for a POS session.
    Can only be set once per session.
    Marks the scale as in_use to prevent other sessions from using it.

    Args:
        session: POS Session name
        scale: Scale name

    Returns:
        dict: Updated session info
    """
    check_pos_operator()

    session_doc = frappe.get_doc("POS Session", session)

    # Verify ownership
    if session_doc.operator != frappe.session.user:
        user_roles = frappe.get_roles(frappe.session.user)
        if "System Manager" not in user_roles:
            frappe.throw(_("You can only modify your own sessions"))

    # Check if scale already set
    if session_doc.scale:
        frappe.throw(_("Scale already set for this session. Close session and open a new one to use a different scale."))

    # Validate scale exists and is active
    scale_data = frappe.db.get_value(
        "Scale",
        scale,
        ["name", "scale_name", "is_active", "in_use", "in_use_by_session", "scale_type", "usage_type", "location"],
        as_dict=True
    )

    if not scale_data:
        frappe.throw(_("Scale '{0}' not found").format(scale))

    if not scale_data.is_active:
        frappe.throw(_("Scale '{0}' is not active").format(scale))

    # Check if scale is already in use by another session
    if scale_data.in_use and scale_data.in_use_by_session:
        frappe.throw(_("Scale '{0}' is already in use by session {1}").format(scale, scale_data.in_use_by_session))

    # Set scale on session
    session_doc.scale = scale
    session_doc.save()

    # Mark scale as in use (use get_doc for activity tracking)
    scale_doc = frappe.get_doc("Scale", scale)
    scale_doc.in_use = 1
    scale_doc.in_use_by_session = session
    scale_doc.save()

    return {
        "session": session_doc.name,
        "scale": scale_data.name,
        "scale_name": scale_data.scale_name,
        "scale_type": scale_data.scale_type,
        "usage_type": scale_data.usage_type,
        "location": scale_data.location
    }


@frappe.whitelist()
def get_weight_verification(pos_order):
    """
    Get weight verification summary for an order including scrap weight records.

    Args:
        pos_order: POS Order name

    Returns:
        dict: All weight data with verification status and scrap records
    """
    check_pos_operator()

    order = frappe.db.get_value(
        "POS Order",
        pos_order,
        [
            "name", "scrap_scale",
            "gross_weight", "gross_weight_scale", "gross_weight_time",
            "tare_weight", "tare_weight_scale", "tare_weight_time",
            "net_truck_weight", "total_scrap_weight",
            "weight_variance", "weight_variance_percent",
            "is_truck_reweighed", "is_scrap_reweighed",
            "truck_weight_remarks", "truck_weight_photo"
        ],
        as_dict=True
    )

    if not order:
        frappe.throw(_("POS Order {0} not found").format(pos_order))

    # Get scrap weight records for this order
    scrap_records = frappe.get_all(
        "Scrap Weight",
        filters={"pos_order": pos_order},
        fields=["name", "total_weight", "posting_date", "posting_time", "is_reweight"],
        order_by="creation asc"
    )

    # Determine verification status
    variance_threshold = 2.0  # 2% tolerance
    variance_ok = True
    if order.weight_variance_percent is not None:
        variance_ok = abs(order.weight_variance_percent) <= variance_threshold

    return {
        **order,
        "scrap_records": scrap_records,
        "variance_threshold": variance_threshold,
        "variance_ok": variance_ok,
        "has_truck_weights": bool(order.gross_weight and order.tare_weight),
        "has_scrap_weights": bool(order.total_scrap_weight)
    }
