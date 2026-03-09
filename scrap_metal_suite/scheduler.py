# Scheduler tasks for Scrap Metal Suite
# Cron jobs for automated maintenance

import frappe
from frappe.utils import now_datetime, add_to_date


def close_idle_sessions():
    """
    Close POS sessions that have been idle for more than 90 minutes.
    Runs every 15 minutes via scheduler.

    Sessions are identified as idle if:
    - status = "Open"
    - last_activity < now() - 90 minutes

    When closed:
    - status set to "Closed"
    - closing_time set to now()
    - closed_by set to "Administrator" (system close)
    - Scale marked as not in use
    """
    idle_threshold = add_to_date(now_datetime(), minutes=-90)

    # Find idle sessions (check last_activity, fall back to opening_time)
    idle_sessions = frappe.db.sql("""
        SELECT name, operator, scale, last_activity, opening_time
        FROM `tabPOS Session`
        WHERE status = 'Open'
          AND COALESCE(last_activity, opening_time) < %(threshold)s
    """, {"threshold": idle_threshold}, as_dict=True)

    closed_count = 0

    for session in idle_sessions:
        try:
            # Close the session
            frappe.db.set_value("POS Session", session.name, {
                "status": "Closed",
                "closing_time": now_datetime(),
                "closed_by": "Administrator"
            })

            # Release the scale if any
            if session.scale:
                frappe.db.set_value("Scale", session.scale, {
                    "in_use": 0,
                    "in_use_by_session": None
                })

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
