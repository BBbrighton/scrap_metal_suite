# Setup Test Data for POS API Tests
# Run with: bench execute scrap_metal_suite.api_test.setup.setup_test_data

import frappe
from frappe.utils import nowdate
from .test_config import *


def setup_test_data():
    """Create all test data required for POS API tests."""
    print("=" * 50)
    print("Setting up POS API test data...")
    print("=" * 50)

    create_test_users()
    create_test_item_group()
    create_test_items()
    create_test_supplier()
    create_test_price_list()
    create_test_pos_profile()
    create_test_pos_order()

    frappe.db.commit()
    print("=" * 50)
    print("Test data setup complete!")
    print("=" * 50)


def create_test_users():
    """Create test operator and manager users."""
    # Create POS Operator role if it doesn't exist
    if not frappe.db.exists("Role", "POS Operator"):
        print("Creating Role: POS Operator")
        frappe.get_doc({
            "doctype": "Role",
            "role_name": "POS Operator",
            "desk_access": 1
        }).insert(ignore_permissions=True)

    # Create POS Manager role if it doesn't exist
    if not frappe.db.exists("Role", "POS Manager"):
        print("Creating Role: POS Manager")
        frappe.get_doc({
            "doctype": "Role",
            "role_name": "POS Manager",
            "desk_access": 1
        }).insert(ignore_permissions=True)

    # Create test operator user
    if not frappe.db.exists("User", TEST_OPERATOR_EMAIL):
        print(f"Creating User: {TEST_OPERATOR_EMAIL}")
        user = frappe.get_doc({
            "doctype": "User",
            "email": TEST_OPERATOR_EMAIL,
            "first_name": TEST_OPERATOR_NAME,
            "enabled": 1,
            "new_password": TEST_OPERATOR_PASSWORD,
            "send_welcome_email": 0,
            "roles": [
                {"role": "POS Operator"},
                {"role": "System Manager"}  # For test permissions
            ]
        })
        user.insert(ignore_permissions=True)
    else:
        print(f"User '{TEST_OPERATOR_EMAIL}' already exists")

    # Create test manager user
    if not frappe.db.exists("User", TEST_MANAGER_EMAIL):
        print(f"Creating User: {TEST_MANAGER_EMAIL}")
        user = frappe.get_doc({
            "doctype": "User",
            "email": TEST_MANAGER_EMAIL,
            "first_name": TEST_MANAGER_NAME,
            "enabled": 1,
            "new_password": TEST_MANAGER_PASSWORD,
            "send_welcome_email": 0,
            "roles": [
                {"role": "POS Manager"},
                {"role": "POS Operator"},
                {"role": "System Manager"}  # For test permissions
            ]
        })
        user.insert(ignore_permissions=True)
    else:
        print(f"User '{TEST_MANAGER_EMAIL}' already exists")


def create_test_item_group():
    """Create test item group if it doesn't exist."""
    if not frappe.db.exists("Item Group", "Scrap Metal"):
        print("Creating Item Group: Scrap Metal")
        frappe.get_doc({
            "doctype": "Item Group",
            "item_group_name": "Scrap Metal",
            "parent_item_group": "All Item Groups"
        }).insert(ignore_permissions=True)
    else:
        print("Item Group 'Scrap Metal' already exists")


def create_test_items():
    """Create test items."""
    items = [
        {
            "item_code": TEST_ITEM_1,
            "item_name": TEST_ITEM_1_NAME,
            "item_group": "Scrap Metal",
            "stock_uom": "Kg",
            "is_stock_item": 1
        },
        {
            "item_code": TEST_ITEM_2,
            "item_name": TEST_ITEM_2_NAME,
            "item_group": "Scrap Metal",
            "stock_uom": "Kg",
            "is_stock_item": 1
        }
    ]

    for item_data in items:
        if not frappe.db.exists("Item", item_data["item_code"]):
            print(f"Creating Item: {item_data['item_code']}")
            frappe.get_doc({
                "doctype": "Item",
                **item_data
            }).insert(ignore_permissions=True)
        else:
            print(f"Item '{item_data['item_code']}' already exists")


def create_test_supplier():
    """Create test supplier."""
    # Ensure supplier group exists
    if not frappe.db.exists("Supplier Group", TEST_SUPPLIER_GROUP):
        print(f"Creating Supplier Group: {TEST_SUPPLIER_GROUP}")
        frappe.get_doc({
            "doctype": "Supplier Group",
            "supplier_group_name": TEST_SUPPLIER_GROUP
        }).insert(ignore_permissions=True)

    if not frappe.db.exists("Supplier", TEST_SUPPLIER):
        print(f"Creating Supplier: {TEST_SUPPLIER}")
        frappe.get_doc({
            "doctype": "Supplier",
            "supplier_name": TEST_SUPPLIER_NAME,
            "supplier_group": TEST_SUPPLIER_GROUP
        }).insert(ignore_permissions=True)

        # Rename to use our test name
        if frappe.db.exists("Supplier", TEST_SUPPLIER_NAME):
            frappe.rename_doc("Supplier", TEST_SUPPLIER_NAME, TEST_SUPPLIER, force=True)
    else:
        print(f"Supplier '{TEST_SUPPLIER}' already exists")


def create_test_price_list():
    """Create test price list (required by POS Profile)."""
    print("Checking for Price List...")
    if not frappe.db.exists("Price List", "Standard Buying"):
        print("Creating Price List: Standard Buying")
        frappe.get_doc({
            "doctype": "Price List",
            "price_list_name": "Standard Buying",
            "currency": "USD",
            "buying": 1,
            "selling": 0,
            "enabled": 1
        }).insert(ignore_permissions=True)
    else:
        print("Price List 'Standard Buying' already exists")


def create_test_pos_profile():
    """Create test POS profile with items."""
    if not frappe.db.exists("POS Profile Scrap", TEST_PROFILE):
        print(f"Creating POS Profile: {TEST_PROFILE}")
        frappe.get_doc({
            "doctype": "POS Profile Scrap",
            "profile_name": TEST_PROFILE,
            "price_list": "Standard Buying",
            "items": [
                {"item_code": TEST_ITEM_1, "display_order": 1},
                {"item_code": TEST_ITEM_2, "display_order": 2}
            ]
        }).insert(ignore_permissions=True)
    else:
        print(f"POS Profile '{TEST_PROFILE}' already exists")


def create_test_pos_order():
    """Create test POS order for weight recording."""
    # Check if order with this order_id exists
    existing = frappe.db.get_value("POS Order", {"order_id": TEST_ORDER_ID}, "name")

    if not existing:
        print(f"Creating POS Order with order_id: {TEST_ORDER_ID}")
        order = frappe.get_doc({
            "doctype": "POS Order",
            "order_id": TEST_ORDER_ID,
            "supplier": TEST_SUPPLIER,
            "order_date": nowdate(),
            "license_plate": TEST_LICENSE_PLATE,
            "status": "Pending"
        })
        order.insert(ignore_permissions=True)
        print(f"Created POS Order: {order.name} (order_id: {TEST_ORDER_ID})")
    else:
        # Reset status to Pending for testing
        frappe.db.set_value("POS Order", existing, "status", "Pending")
        print(f"POS Order with order_id '{TEST_ORDER_ID}' already exists ({existing}) - reset to Pending")


if __name__ == "__main__":
    setup_test_data()
