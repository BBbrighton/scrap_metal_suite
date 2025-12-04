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
            ["scale_name", "scale_type", "usage_type", "location"],
            as_dict=True
        )
        if scale_info:
            session.scale_name = scale_info.scale_name
            session.scale_type = scale_info.scale_type
            session.scale_usage_type = scale_info.usage_type
            session.scale_location = scale_info.location

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
    2. If no exact match, try partial match with date filtering:
       - First try today only
       - If no results, expand to +/- 2 days

    Args:
        query: Search term (document name, order_id, or license_plate)

    Returns:
        list: Matching orders with supplier_name, order_date, license_plate, status
    """
    check_pos_operator()
    from frappe.utils import add_days

    if not query or len(query) < 2:
        return []

    fields = ["name", "order_id", "supplier", "supplier_name", "order_date", "license_plate", "status"]

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

    # Step 4: Partial match - first try today only
    today = nowdate()
    orders = frappe.db.sql("""
        SELECT
            name, order_id, supplier, supplier_name, order_date, license_plate, status
        FROM `tabPOS Order`
        WHERE
            order_date = %(today)s
            AND (
                name LIKE %(query)s
                OR order_id LIKE %(query)s
                OR license_plate LIKE %(query)s
            )
        ORDER BY order_date DESC, creation DESC
        LIMIT 10
    """, {"query": f"%{query}%", "today": today}, as_dict=True)

    if orders:
        return orders

    # Step 5: Expand to +/- 2 days if no results today
    date_start = add_days(today, -2)
    date_end = add_days(today, 2)

    orders = frappe.db.sql("""
        SELECT
            name, order_id, supplier, supplier_name, order_date, license_plate, status
        FROM `tabPOS Order`
        WHERE
            order_date BETWEEN %(date_start)s AND %(date_end)s
            AND (
                name LIKE %(query)s
                OR order_id LIKE %(query)s
                OR license_plate LIKE %(query)s
            )
        ORDER BY order_date DESC, creation DESC
        LIMIT 10
    """, {"query": f"%{query}%", "date_start": date_start, "date_end": date_end}, as_dict=True)

    return orders


@frappe.whitelist()
def get_order_details(order_id):
    """
    Get full details of a POS Order including truck weight data.

    Args:
        order_id: POS Order name

    Returns:
        dict: Order details including supplier info and truck weights
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

    return {
        "order_id": order.name,
        "supplier": order.supplier,
        "supplier_name": order.supplier_name or (supplier_data.supplier_name if supplier_data else None),
        "order_date": order.order_date,
        "license_plate": order.license_plate,
        "purchase_order": order.purchase_order,
        "notes": order.notes,
        "status": order.status,
        # Truck weight fields
        "gross_weight": order.gross_weight,
        "gross_weight_time": order.gross_weight_time,
        "tare_weight": order.tare_weight,
        "tare_weight_time": order.tare_weight_time,
        "net_truck_weight": order.net_truck_weight,
        "total_scrap_weight": order.total_scrap_weight,
        "weight_variance": order.weight_variance,
        "weight_variance_percent": order.weight_variance_percent,
        "is_truck_reweighed": order.is_truck_reweighed,
        "is_scrap_reweighed": order.is_scrap_reweighed
    }


@frappe.whitelist()
def create_scrap_weight(session, pos_order, items, remarks=None):
    """
    Record scrap weight for a POS Order.

    Allows re-weighing of already processed orders. If the order was previously
    processed, the new weight record is marked as is_reweight=1.

    Args:
        session: POS Session name (required)
        pos_order: POS Order name (required)
        items: JSON list of items [{item_code, weight, uom}]
        remarks: Optional remarks

    Returns:
        dict: {scrap_weight, total_weight, is_reweight}
    """
    check_pos_operator()
    import json

    if isinstance(items, str):
        items = json.loads(items)

    if not items:
        frappe.throw(_("At least one item is required"))

    # Validate session is open
    session_status = frappe.db.get_value("POS Session", session, "status")
    if session_status != "Open":
        frappe.throw(_("Session {0} is not open").format(session))

    # Validate POS Order exists
    order_data = frappe.db.get_value(
        "POS Order",
        pos_order,
        ["name", "supplier", "status", "license_plate"],
        as_dict=True
    )

    if not order_data:
        frappe.throw(_("POS Order {0} not found").format(pos_order))

    # Check if this is a re-weigh (order already processed)
    is_reweight = order_data.status == "Processed"

    # Build items list
    weight_items = []
    for item in items:
        item_data = {
            "item_code": item.get("item_code"),
            "weight": flt(item.get("weight")),
            "uom": item.get("uom", "Kg")
        }
        weight_items.append(item_data)

    # Create scrap weight document linked to POS Order
    scrap_weight = frappe.get_doc({
        "doctype": "Scrap Weight",
        "pos_order": pos_order,
        "supplier": order_data.supplier,
        "posting_date": nowdate(),
        "session": session,
        "remarks": remarks,
        "is_reweight": is_reweight,
        "items": weight_items
    })

    scrap_weight.insert()

    # Update POS Order - use frappe.get_doc to trigger activity tracking
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
def record_truck_weight(pos_order, weight_type, weight, remarks=None):
    """
    Record truck gross or tare weight for a POS Order.

    Args:
        pos_order: POS Order name
        weight_type: 'gross' or 'tare'
        weight: Weight in kg
        remarks: Optional remarks/notes

    Returns:
        dict: Updated order with calculated fields
    """
    check_pos_operator()

    if weight_type not in ['gross', 'tare']:
        frappe.throw(_("weight_type must be 'gross' or 'tare'"))

    weight = flt(weight)
    if weight <= 0:
        frappe.throw(_("Weight must be greater than 0"))

    order = frappe.get_doc("POS Order", pos_order)

    # Record the weight with timestamp
    if weight_type == 'gross':
        order.gross_weight = weight
        order.gross_weight_time = frappe.utils.now_datetime()
    else:
        order.tare_weight = weight
        order.tare_weight_time = frappe.utils.now_datetime()

    # Update remarks if provided (field may not exist if migration not run)
    if remarks and hasattr(order, 'truck_weight_remarks'):
        order.truck_weight_remarks = remarks

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
        "tare_weight": order.tare_weight,
        "tare_weight_time": order.tare_weight_time,
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
        fields=["name", "scale_name", "scale_type", "usage_type", "location", "max_capacity_kg", "is_active"],
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
    scale_doc = frappe.db.get_value(
        "Scale",
        scale,
        ["name", "scale_name", "is_active", "scale_type", "usage_type", "location"],
        as_dict=True
    )

    if not scale_doc:
        frappe.throw(_("Scale '{0}' not found").format(scale))

    if not scale_doc.is_active:
        frappe.throw(_("Scale '{0}' is not active").format(scale))

    # Set scale on session
    session_doc.scale = scale
    session_doc.save()

    return {
        "session": session_doc.name,
        "scale": scale_doc.name,
        "scale_name": scale_doc.scale_name,
        "scale_type": scale_doc.scale_type,
        "usage_type": scale_doc.usage_type,
        "location": scale_doc.location
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
            "name", "gross_weight", "gross_weight_time",
            "tare_weight", "tare_weight_time", "net_truck_weight",
            "total_scrap_weight", "weight_variance", "weight_variance_percent",
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
