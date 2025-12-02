# POS API Tests
# Run with: bench execute scrap_metal_suite.api_test.test_pos_api.run_all_tests

import frappe
import json
from .test_config import *


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def success(self, test_name):
        self.passed += 1
        print(f"  ✓ {test_name}")

    def fail(self, test_name, error):
        self.failed += 1
        self.errors.append((test_name, error))
        print(f"  ✗ {test_name}: {error}")

    def summary(self):
        print("\n" + "=" * 50)
        print(f"Results: {self.passed} passed, {self.failed} failed")
        if self.errors:
            print("\nFailed tests:")
            for test_name, error in self.errors:
                print(f"  - {test_name}: {error}")
        print("=" * 50)


results = TestResult()


def run_all_tests():
    """Run all POS API tests."""
    global results
    results = TestResult()

    print("=" * 50)
    print("Running POS API Tests")
    print("=" * 50)

    # Set session user to test operator
    original_user = frappe.session.user
    frappe.set_user(TEST_OPERATOR_EMAIL)
    print(f"Running tests as: {TEST_OPERATOR_EMAIL}")

    # Import API module
    from scrap_metal_suite.api.v1 import pos

    print("\n1. Testing get_pos_profile...")
    test_get_pos_profile(pos)

    print("\n2. Testing lookup_supplier...")
    test_lookup_supplier(pos)

    print("\n3. Testing get_item_rate...")
    test_get_item_rate(pos)

    print("\n4. Testing session management...")
    session_name = test_session_management(pos)

    print("\n5. Testing create_purchase...")
    if session_name:
        test_create_purchase(pos, session_name)

    print("\n6. Testing get_session_purchases...")
    if session_name:
        test_get_session_purchases(pos, session_name)

    print("\n7. Testing get_session_summary...")
    if session_name:
        test_get_session_summary(pos, session_name)

    print("\n8. Testing validate_override_code...")
    test_validate_override_code(pos)

    print("\n9. Testing close_session...")
    if session_name:
        test_close_session(pos, session_name)

    # Restore original user
    frappe.set_user(original_user)

    results.summary()
    return results


def test_get_pos_profile(pos):
    """Test get_pos_profile endpoint."""
    try:
        profile = pos.get_pos_profile(TEST_PROFILE)

        assert profile["profile_name"] == TEST_PROFILE, f"Expected {TEST_PROFILE}, got {profile['profile_name']}"
        assert profile["price_list"] == TEST_PRICE_LIST, f"Expected {TEST_PRICE_LIST}, got {profile['price_list']}"
        assert len(profile["items"]) == 2, f"Expected 2 items, got {len(profile['items'])}"

        results.success("get_pos_profile returns correct data")
    except Exception as e:
        results.fail("get_pos_profile", str(e))


def test_lookup_supplier(pos):
    """Test lookup_supplier endpoint."""
    try:
        # Search by name
        suppliers = pos.lookup_supplier("TEST_POS")

        assert len(suppliers) >= 1, "Expected at least 1 supplier"
        assert any(s["name"] == TEST_SUPPLIER for s in suppliers), f"Expected to find {TEST_SUPPLIER}"

        results.success("lookup_supplier finds test supplier")
    except Exception as e:
        results.fail("lookup_supplier", str(e))

    try:
        # Search with short query should return empty
        suppliers = pos.lookup_supplier("X")
        assert len(suppliers) == 0, "Short query should return empty"

        results.success("lookup_supplier handles short queries")
    except Exception as e:
        results.fail("lookup_supplier short query", str(e))


def test_get_item_rate(pos):
    """Test get_item_rate endpoint."""
    try:
        # Test with supplier (uses supplier's price list)
        rate_info = pos.get_item_rate(TEST_ITEM_1, supplier=TEST_SUPPLIER)

        assert rate_info["rate"] == TEST_RATE_COPPER, f"Expected {TEST_RATE_COPPER}, got {rate_info['rate']}"
        assert rate_info["price_list_used"] == TEST_PRICE_LIST, f"Expected {TEST_PRICE_LIST}"

        results.success("get_item_rate returns correct rate for supplier")
    except Exception as e:
        results.fail("get_item_rate with supplier", str(e))

    try:
        # Test with explicit price list
        rate_info = pos.get_item_rate(TEST_ITEM_2, price_list=TEST_PRICE_LIST)

        assert rate_info["rate"] == TEST_RATE_ALUMINUM, f"Expected {TEST_RATE_ALUMINUM}, got {rate_info['rate']}"

        results.success("get_item_rate returns correct rate for price list")
    except Exception as e:
        results.fail("get_item_rate with price list", str(e))


def test_session_management(pos):
    """Test open_session and get_active_session."""
    session_name = None

    # First, close any existing open session
    try:
        existing = pos.get_active_session()
        if existing:
            print(f"  (Closing existing session: {existing['name']})")
            frappe.db.set_value("POS Session", existing["name"], "status", "Closed")
            frappe.db.commit()
    except:
        pass

    try:
        # Open a new session
        session = pos.open_session(TEST_PROFILE)
        session_name = session["session"]

        assert session_name is not None, "Session name should not be None"
        assert session["pos_profile"] == TEST_PROFILE, f"Expected {TEST_PROFILE}"

        results.success("open_session creates new session")
    except Exception as e:
        results.fail("open_session", str(e))
        return None

    try:
        # Get active session
        active = pos.get_active_session()

        assert active is not None, "Should have an active session"
        assert active["name"] == session_name, f"Expected {session_name}"

        results.success("get_active_session returns correct session")
    except Exception as e:
        results.fail("get_active_session", str(e))

    try:
        # Try to open another session (should fail)
        pos.open_session(TEST_PROFILE)
        results.fail("open_session duplicate", "Should have thrown error for duplicate session")
    except frappe.exceptions.ValidationError:
        results.success("open_session prevents duplicate sessions")
    except Exception as e:
        results.fail("open_session duplicate", str(e))

    return session_name


def test_create_purchase(pos, session_name):
    """Test create_purchase endpoint."""
    try:
        # Create purchase without override
        purchase = pos.create_purchase(
            session=session_name,
            supplier=TEST_SUPPLIER,
            items=json.dumps([
                {"item_code": TEST_ITEM_1, "weight": 10.5, "rate": TEST_RATE_COPPER},
                {"item_code": TEST_ITEM_2, "weight": 5.0, "rate": TEST_RATE_ALUMINUM}
            ]),
            remarks="Test purchase"
        )

        assert purchase["purchase"] is not None, "Purchase name should not be None"
        expected_amount = (10.5 * TEST_RATE_COPPER) + (5.0 * TEST_RATE_ALUMINUM)
        assert purchase["total_amount"] == expected_amount, f"Expected {expected_amount}, got {purchase['total_amount']}"
        assert purchase["total_weight"] == 15.5, f"Expected 15.5, got {purchase['total_weight']}"

        results.success("create_purchase creates transaction correctly")
    except Exception as e:
        results.fail("create_purchase", str(e))

    try:
        # Create purchase with override (without code - should fail)
        pos.create_purchase(
            session=session_name,
            supplier=TEST_SUPPLIER,
            items=json.dumps([
                {"item_code": TEST_ITEM_1, "weight": 5.0, "rate": 999.99, "override": True}
            ])
        )
        results.fail("create_purchase override without code", "Should have thrown error")
    except frappe.exceptions.ValidationError:
        results.success("create_purchase requires override code")
    except Exception as e:
        results.fail("create_purchase override validation", str(e))

    try:
        # Create purchase with override (with valid code)
        purchase = pos.create_purchase(
            session=session_name,
            supplier=TEST_SUPPLIER,
            items=json.dumps([
                {"item_code": TEST_ITEM_1, "weight": 5.0, "rate": 999.99, "override": True}
            ]),
            override_code=TEST_PIN
        )

        assert purchase["purchase"] is not None, "Purchase should be created"
        assert purchase["total_amount"] == 5.0 * 999.99, "Amount should use override rate"

        results.success("create_purchase with override code works")
    except Exception as e:
        results.fail("create_purchase with override", str(e))


def test_get_session_purchases(pos, session_name):
    """Test get_session_purchases endpoint."""
    try:
        purchases = pos.get_session_purchases(session_name)

        assert len(purchases) >= 2, f"Expected at least 2 purchases, got {len(purchases)}"
        assert all(p["supplier"] == TEST_SUPPLIER for p in purchases), "All purchases should be for test supplier"

        results.success("get_session_purchases returns correct data")
    except Exception as e:
        results.fail("get_session_purchases", str(e))


def test_get_session_summary(pos, session_name):
    """Test get_session_summary endpoint."""
    try:
        summary = pos.get_session_summary(session_name)

        assert summary["session"]["name"] == session_name, "Session name should match"
        assert summary["totals"]["purchase_count"] >= 2, "Should have at least 2 purchases"
        assert summary["totals"]["total_weight"] > 0, "Total weight should be > 0"
        assert summary["totals"]["total_amount"] > 0, "Total amount should be > 0"

        results.success("get_session_summary returns correct data")
    except Exception as e:
        results.fail("get_session_summary", str(e))


def test_validate_override_code(pos):
    """Test validate_override_code endpoint."""
    try:
        # Valid PIN
        result = pos.validate_override_code(TEST_PIN, "can_override_rate")

        assert result["valid"] == True, "Should be valid"
        assert result["user"] == TEST_AUTHORITY_USER, f"Expected {TEST_AUTHORITY_USER}"

        results.success("validate_override_code validates correct PIN")
    except Exception as e:
        results.fail("validate_override_code valid PIN", str(e))

    try:
        # Invalid PIN
        pos.validate_override_code("0000", "can_override_rate")
        results.fail("validate_override_code invalid PIN", "Should have thrown error")
    except frappe.exceptions.ValidationError:
        results.success("validate_override_code rejects invalid PIN")
    except Exception as e:
        results.fail("validate_override_code invalid PIN", str(e))


def test_close_session(pos, session_name):
    """Test close_session endpoint."""
    try:
        totals = pos.close_session(session_name)

        assert "total_purchases" in totals, "Should return total_purchases"
        assert "total_amount" in totals, "Should return total_amount"
        assert "total_weight" in totals, "Should return total_weight"
        assert totals["total_purchases"] >= 2, "Should have at least 2 purchases"

        results.success("close_session returns correct totals")
    except Exception as e:
        results.fail("close_session", str(e))

    try:
        # Verify session is closed
        active = pos.get_active_session()
        assert active is None, "Should not have active session after close"

        results.success("close_session actually closes session")
    except Exception as e:
        results.fail("close_session verification", str(e))


if __name__ == "__main__":
    run_all_tests()
