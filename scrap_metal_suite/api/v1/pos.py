# POS API Endpoints
# Handles POS session management, scrap weight recording, and order lookup

import frappe
from frappe import _
from frappe.utils import flt, nowdate


@frappe.whitelist()
def get_pos_profile(profile_name):
    """
    Get POS profile configuration with items to display.

    Args:
        profile_name: Name of the POS Profile Scrap

    Returns:
        dict: Profile config with items list
    """
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
    session = frappe.db.get_value(
        "POS Session",
        {"operator": frappe.session.user, "status": "Open"},
        ["name", "pos_profile", "opening_time", "total_purchases", "total_weight"],
        as_dict=True
    )

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
    Get full details of a POS Order.

    Args:
        order_id: POS Order name

    Returns:
        dict: Order details including supplier info
    """
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
        "status": order.status
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
    order_doc.save()

    return {
        "scrap_weight": scrap_weight.name,
        "total_weight": scrap_weight.total_weight,
        "order_id": pos_order,
        "is_reweight": is_reweight
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
