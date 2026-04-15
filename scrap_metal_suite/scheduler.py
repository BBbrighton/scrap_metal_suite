# Scheduler tasks for Scrap Metal Suite
# Cron jobs for automated maintenance

import frappe
from frappe.utils import now_datetime, add_to_date, today


def close_idle_sessions():
    """
    Close POS sessions that have been idle for more than 90 minutes.
    Runs every 15 minutes via scheduler.
    Uses document API (get_doc + save) to preserve audit trail.
    """
    idle_threshold = add_to_date(now_datetime(), minutes=-90)

    idle_sessions = frappe.db.sql("""
        SELECT name, operator, scale, last_activity, opening_time
        FROM `tabPOS Session`
        WHERE status = 'Open'
          AND COALESCE(last_activity, opening_time) < %(threshold)s
    """, {"threshold": idle_threshold}, as_dict=True)

    closed_count = 0

    for session in idle_sessions:
        try:
            doc = frappe.get_doc("POS Session", session.name)
            doc.status = "Closed"
            doc.closing_time = now_datetime()
            doc.closed_by = "Administrator"
            doc.save(ignore_permissions=True)

            if session.scale:
                scale_doc = frappe.get_doc("Scale", session.scale)
                scale_doc.in_use = 0
                scale_doc.in_use_by_session = None
                scale_doc.save(ignore_permissions=True)

            closed_count += 1
            frappe.logger().info(
                f"Auto-closed idle session {session.name} "
                f"(operator: {session.operator}, last activity: {session.last_activity})"
            )
        except Exception as e:
            frappe.logger().error(f"Error closing idle session {session.name}: {str(e)}")

    if closed_count > 0:
        frappe.db.commit()
        frappe.logger().info(f"Auto-closed {closed_count} idle POS session(s)")

    return closed_count


def close_idle_production_sessions():
    """
    Close Production Sessions idle for more than 10 minutes.
    Runs every 5 minutes via scheduler.
    Uses document API (get_doc + save) to preserve audit trail.
    """
    idle_threshold = add_to_date(now_datetime(), minutes=-10)

    idle_sessions = frappe.db.sql("""
        SELECT name, operator, scale, last_activity
        FROM `tabProduction Session`
        WHERE status = 'Open'
          AND last_activity IS NOT NULL
          AND last_activity < %(threshold)s
    """, {"threshold": idle_threshold}, as_dict=True)

    closed_count = 0

    for session in idle_sessions:
        try:
            doc = frappe.get_doc("Production Session", session.name)
            doc.status = "Closed"
            doc.closing_time = now_datetime()
            doc.closed_by = "Administrator"
            doc.save(ignore_permissions=True)

            if session.scale:
                scale_doc = frappe.get_doc("Scale", session.scale)
                scale_doc.in_use = 0
                scale_doc.in_use_by_session = None
                scale_doc.save(ignore_permissions=True)

            closed_count += 1
            frappe.logger().info(
                f"Auto-closed idle production session {session.name} "
                f"(operator: {session.operator}, last activity: {session.last_activity})"
            )
        except Exception as e:
            frappe.logger().error(f"Error closing idle production session {session.name}: {str(e)}")

    if closed_count > 0:
        frappe.db.commit()
        frappe.logger().info(f"Auto-closed {closed_count} idle production session(s)")

    return closed_count


def expire_open_pos():
    """
    Expire SMT POs that are past their expiry date.
    Only expires POs with status 'Open' — Partially Settled POs are never auto-expired.
    Runs daily at 1am via scheduler.
    """
    expired_pos = frappe.get_all(
        "SMT PO",
        filters=[
            ["status", "=", "Open"],
            ["expiry_date", "is", "set"],
            ["expiry_date", "<", today()],
            ["docstatus", "=", 1],
        ],
        pluck="name"
    )

    for po_name in expired_pos:
        try:
            frappe.db.set_value("SMT PO", po_name, {
                "status": "Expired",
                "status_date": now_datetime()
            })
            frappe.logger().info(f"Auto-expired PO {po_name}")
        except Exception as e:
            frappe.logger().error(f"Error expiring PO {po_name}: {str(e)}")

    if expired_pos:
        frappe.db.commit()
        frappe.logger().info(f"Auto-expired {len(expired_pos)} PO(s)")

    return len(expired_pos)
