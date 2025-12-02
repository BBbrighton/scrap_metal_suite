# Cleanup Test Data for POS API Tests
# Run with: bench execute scrap_metal_suite.api_test.cleanup.cleanup_test_data

import frappe
from .test_config import *


def cleanup_test_data():
    """Remove all test data created by setup."""
    print("=" * 50)
    print("Cleaning up POS API test data...")
    print("=" * 50)

    # Order matters - delete dependent records first
    cleanup_test_sessions_and_weights()
    cleanup_test_pos_orders()
    cleanup_test_pos_profile()
    cleanup_test_supplier()
    cleanup_test_items()
    cleanup_test_users()

    frappe.db.commit()
    print("=" * 50)
    print("Test data cleanup complete!")
    print("=" * 50)


def cleanup_test_sessions_and_weights():
    """Delete all test POS sessions and scrap weights."""
    # Delete scrap weights first (child of session)
    try:
        weights = frappe.get_all(
            "Scrap Weight",
            filters={"supplier": TEST_SUPPLIER},
            pluck="name"
        )
        for name in weights:
            print(f"Deleting Scrap Weight: {name}")
            frappe.delete_doc("Scrap Weight", name, force=True, ignore_permissions=True)
    except Exception as e:
        print(f"Note: Could not clean Scrap Weight - {e}")

    # Delete sessions linked to test profile
    try:
        sessions = frappe.get_all(
            "POS Session",
            filters={"pos_profile": TEST_PROFILE},
            pluck="name"
        )
        for name in sessions:
            print(f"Deleting POS Session: {name}")
            frappe.delete_doc("POS Session", name, force=True, ignore_permissions=True)
    except Exception as e:
        print(f"Note: Could not clean POS Session - {e}")


def cleanup_test_pos_orders():
    """Delete test POS Orders."""
    try:
        orders = frappe.get_all(
            "POS Order",
            filters={"supplier": TEST_SUPPLIER},
            pluck="name"
        )
        for name in orders:
            print(f"Deleting POS Order: {name}")
            frappe.delete_doc("POS Order", name, force=True, ignore_permissions=True)
    except Exception as e:
        print(f"Note: Could not clean POS Order - {e}")


def cleanup_test_pos_profile():
    """Delete test POS profile."""
    if frappe.db.exists("POS Profile Scrap", TEST_PROFILE):
        print(f"Deleting POS Profile: {TEST_PROFILE}")
        frappe.delete_doc("POS Profile Scrap", TEST_PROFILE, force=True, ignore_permissions=True)


def cleanup_test_supplier():
    """Delete test supplier."""
    if frappe.db.exists("Supplier", TEST_SUPPLIER):
        print(f"Deleting Supplier: {TEST_SUPPLIER}")
        frappe.delete_doc("Supplier", TEST_SUPPLIER, force=True, ignore_permissions=True)


def cleanup_test_items():
    """Delete test items."""
    for item_code in [TEST_ITEM_1, TEST_ITEM_2]:
        if frappe.db.exists("Item", item_code):
            print(f"Deleting Item: {item_code}")
            frappe.delete_doc("Item", item_code, force=True, ignore_permissions=True)


def cleanup_test_users():
    """Delete test users."""
    for email in [TEST_OPERATOR_EMAIL, TEST_MANAGER_EMAIL]:
        if frappe.db.exists("User", email):
            print(f"Deleting User: {email}")
            frappe.delete_doc("User", email, force=True, ignore_permissions=True)

    # Note: We don't delete the roles as they might be used elsewhere


if __name__ == "__main__":
    cleanup_test_data()
