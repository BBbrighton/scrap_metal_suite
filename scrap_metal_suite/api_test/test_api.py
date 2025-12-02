# API Test Script for POS Weight Recording
# Run with: bench execute scrap_metal_suite.api_test.test_api.run_all_tests
#
# This script tests all POS API endpoints:
# 1. get_pos_profile - Get POS profile configuration
# 2. get_active_session - Check for active session
# 3. open_session - Open a new POS session
# 4. lookup_order - Search for POS orders
# 5. get_order_details - Get full order details
# 6. create_scrap_weight - Record scrap weight
# 7. get_session_weights - Get all weights for session
# 8. get_session_summary - Get session statistics
# 9. close_session - Close the session

import frappe
import json
from frappe.utils import nowdate
from .test_config import *


class APITestRunner:
    """Test runner for POS API endpoints."""

    def __init__(self):
        self.session_name = None
        self.scrap_weight_name = None
        self.order_name = None  # Document name (e.g., ORD-.YYYY.-.00001)
        self.order_id = TEST_ORDER_ID  # order_id field value for searching
        self.results = []

    def log(self, test_name, success, message=""):
        """Log test result."""
        status = "PASS" if success else "FAIL"
        self.results.append({"test": test_name, "success": success, "message": message})
        print(f"[{status}] {test_name}: {message}")

    def run_all_tests(self):
        """Run all API tests in sequence."""
        print("=" * 60)
        print("Running POS API Tests")
        print("=" * 60)

        # Find the test order created by setup (by order_id field)
        self.order_name = self.find_test_order()
        if not self.order_name:
            print("[ERROR] No test POS Order found. Run setup first:")
            print("  bench execute scrap_metal_suite.api_test.setup.setup_test_data")
            return

        print(f"Using test order: {self.order_name} (order_id: {self.order_id})")

        # Set test user context
        frappe.set_user(TEST_OPERATOR_EMAIL)

        try:
            self.test_get_pos_profile()
            self.test_get_active_session_none()
            self.test_open_session()
            self.test_get_active_session()
            self.test_lookup_order()
            self.test_get_order_details()
            self.test_create_scrap_weight()
            self.test_get_session_weights()
            self.test_get_session_summary()
            self.test_close_session()
        except Exception as e:
            print(f"\n[ERROR] Test suite failed: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            frappe.set_user("Administrator")

        # Print summary
        self.print_summary()

    def find_test_order(self):
        """Find the test POS Order created by setup (by order_id field)."""
        # Look for order with test order_id
        order = frappe.db.get_value(
            "POS Order",
            {"order_id": TEST_ORDER_ID, "status": "Pending"},
            "name"
        )
        return order

    def print_summary(self):
        """Print test results summary."""
        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)

        passed = sum(1 for r in self.results if r["success"])
        failed = sum(1 for r in self.results if not r["success"])

        print(f"Total: {len(self.results)} | Passed: {passed} | Failed: {failed}")

        if failed > 0:
            print("\nFailed Tests:")
            for r in self.results:
                if not r["success"]:
                    print(f"  - {r['test']}: {r['message']}")

        print("=" * 60)

    def test_get_pos_profile(self):
        """Test get_pos_profile API."""
        from scrap_metal_suite.api.v1.pos import get_pos_profile

        try:
            result = get_pos_profile(TEST_PROFILE)

            if result and result.get("profile_name") == TEST_PROFILE:
                items = result.get("items", [])
                if len(items) >= 2:
                    self.log("get_pos_profile", True, f"Profile loaded with {len(items)} items")
                else:
                    self.log("get_pos_profile", False, f"Expected 2+ items, got {len(items)}")
            else:
                self.log("get_pos_profile", False, "Profile not found or invalid")
        except Exception as e:
            self.log("get_pos_profile", False, str(e))

    def test_get_active_session_none(self):
        """Test get_active_session when no session exists."""
        from scrap_metal_suite.api.v1.pos import get_active_session

        try:
            result = get_active_session()

            if result is None:
                self.log("get_active_session (none)", True, "No active session as expected")
            else:
                self.log("get_active_session (none)", False, f"Unexpected session: {result}")
        except Exception as e:
            self.log("get_active_session (none)", False, str(e))

    def test_open_session(self):
        """Test open_session API."""
        from scrap_metal_suite.api.v1.pos import open_session

        try:
            result = open_session(TEST_PROFILE)

            if result and result.get("session"):
                self.session_name = result["session"]
                self.log("open_session", True, f"Session opened: {self.session_name}")
            else:
                self.log("open_session", False, "Failed to open session")
        except Exception as e:
            self.log("open_session", False, str(e))

    def test_get_active_session(self):
        """Test get_active_session when session exists."""
        from scrap_metal_suite.api.v1.pos import get_active_session

        try:
            result = get_active_session()

            if result and result.get("name") == self.session_name:
                self.log("get_active_session", True, f"Found session: {result['name']}")
            else:
                self.log("get_active_session", False, f"Session mismatch: {result}")
        except Exception as e:
            self.log("get_active_session", False, str(e))

    def test_lookup_order(self):
        """Test lookup_order API - searches by order_id field."""
        from scrap_metal_suite.api.v1.pos import lookup_order

        try:
            # Search by order_id from test config
            result = lookup_order(TEST_ORDER_ID)

            if result and len(result) > 0:
                order = result[0]
                if order.get("order_id") == TEST_ORDER_ID:
                    if order.get("supplier") == TEST_SUPPLIER:
                        self.log("lookup_order", True,
                                 f"Found order: {order['name']} (order_id: {order['order_id']})")
                    else:
                        self.log("lookup_order", False, f"Wrong supplier: {order.get('supplier')}")
                else:
                    self.log("lookup_order", False, f"Wrong order_id: {order.get('order_id')}")
            else:
                self.log("lookup_order", False, "No orders found")
        except Exception as e:
            self.log("lookup_order", False, str(e))

    def test_get_order_details(self):
        """Test get_order_details API."""
        from scrap_metal_suite.api.v1.pos import get_order_details

        try:
            result = get_order_details(self.order_name)

            if result:
                if result.get("supplier") == TEST_SUPPLIER:
                    if result.get("license_plate") == TEST_LICENSE_PLATE:
                        self.log("get_order_details", True,
                                 f"Order details loaded: {self.order_name}")
                    else:
                        self.log("get_order_details", False, f"Wrong plate: {result.get('license_plate')}")
                else:
                    self.log("get_order_details", False, f"Wrong supplier: {result.get('supplier')}")
            else:
                self.log("get_order_details", False, "Order not found")
        except Exception as e:
            self.log("get_order_details", False, str(e))

    def test_create_scrap_weight(self):
        """Test create_scrap_weight API."""
        from scrap_metal_suite.api.v1.pos import create_scrap_weight

        try:
            items = [
                {"item_code": TEST_ITEM_1, "weight": 10.5, "uom": "Kg"},
                {"item_code": TEST_ITEM_2, "weight": 5.25, "uom": "Kg"}
            ]

            result = create_scrap_weight(
                session=self.session_name,
                pos_order=self.order_name,
                items=json.dumps(items)
            )

            if result and result.get("scrap_weight"):
                self.scrap_weight_name = result["scrap_weight"]
                expected_weight = 15.75

                if abs(result.get("total_weight", 0) - expected_weight) < 0.01:
                    self.log("create_scrap_weight", True,
                             f"Weight recorded: {self.scrap_weight_name}, total: {result['total_weight']} Kg")
                else:
                    self.log("create_scrap_weight", False,
                             f"Wrong total: {result.get('total_weight')} (expected {expected_weight})")
            else:
                self.log("create_scrap_weight", False, "Failed to create scrap weight")
        except Exception as e:
            self.log("create_scrap_weight", False, str(e))

    def test_get_session_weights(self):
        """Test get_session_weights API."""
        from scrap_metal_suite.api.v1.pos import get_session_weights

        try:
            result = get_session_weights(self.session_name)

            if result and len(result) > 0:
                weight = result[0]
                if weight.get("name") == self.scrap_weight_name:
                    self.log("get_session_weights", True, f"Found {len(result)} weight record(s)")
                else:
                    self.log("get_session_weights", False, f"Wrong weight record: {weight}")
            else:
                self.log("get_session_weights", False, "No weight records found")
        except Exception as e:
            self.log("get_session_weights", False, str(e))

    def test_get_session_summary(self):
        """Test get_session_summary API."""
        from scrap_metal_suite.api.v1.pos import get_session_summary

        try:
            result = get_session_summary(self.session_name)

            if result and result.get("totals"):
                totals = result["totals"]

                if totals.get("weight_count", 0) >= 1:
                    if float(totals.get("total_weight", 0)) >= 15.0:
                        self.log("get_session_summary", True,
                                 f"Summary: {totals['weight_count']} weights, {totals['total_weight']} Kg")
                    else:
                        self.log("get_session_summary", False,
                                 f"Wrong total weight: {totals.get('total_weight')}")
                else:
                    self.log("get_session_summary", False,
                             f"Wrong weight count: {totals.get('weight_count')}")
            else:
                self.log("get_session_summary", False, "Invalid summary response")
        except Exception as e:
            self.log("get_session_summary", False, str(e))

    def test_close_session(self):
        """Test close_session API."""
        from scrap_metal_suite.api.v1.pos import close_session

        try:
            result = close_session(self.session_name)

            if result:
                # Verify session is closed
                status = frappe.db.get_value("POS Session", self.session_name, "status")
                if status == "Closed":
                    self.log("close_session", True, f"Session closed successfully")
                else:
                    self.log("close_session", False, f"Session status: {status}")
            else:
                self.log("close_session", False, "No response from close_session")
        except Exception as e:
            self.log("close_session", False, str(e))


def run_all_tests():
    """Entry point for running all tests."""
    runner = APITestRunner()
    runner.run_all_tests()
    return runner.results


if __name__ == "__main__":
    run_all_tests()
