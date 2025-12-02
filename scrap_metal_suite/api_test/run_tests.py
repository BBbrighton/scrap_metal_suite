# Main Test Runner
# Run with: bench execute scrap_metal_suite.api_test.run_tests.run

import frappe


def run(skip_setup=False, skip_cleanup=False):
    """
    Run the full POS API test suite.

    Args:
        skip_setup: Skip test data setup (use existing data)
        skip_cleanup: Skip cleanup after tests (keep test data)
    """
    from .setup import setup_test_data
    from .cleanup import cleanup_test_data
    from .test_pos_api import run_all_tests

    print("\n" + "=" * 60)
    print("POS API TEST SUITE")
    print("=" * 60)

    # Step 1: Setup
    if not skip_setup:
        print("\n[STEP 1/3] Setting up test data...\n")
        setup_test_data()
    else:
        print("\n[STEP 1/3] Skipping setup (using existing data)")

    # Step 2: Run tests
    print("\n[STEP 2/3] Running tests...\n")
    results = run_all_tests()

    # Step 3: Cleanup
    if not skip_cleanup:
        print("\n[STEP 3/3] Cleaning up test data...\n")
        cleanup_test_data()
    else:
        print("\n[STEP 3/3] Skipping cleanup (keeping test data)")

    print("\n" + "=" * 60)
    if results.failed == 0:
        print("ALL TESTS PASSED!")
    else:
        print(f"TESTS COMPLETED WITH {results.failed} FAILURES")
    print("=" * 60 + "\n")

    # Return JSON-serializable dict instead of TestResult object
    return {
        "passed": results.passed,
        "failed": results.failed,
        "errors": results.errors
    }


def setup_only():
    """Only run setup (create test data)."""
    from .setup import setup_test_data
    setup_test_data()


def cleanup_only():
    """Only run cleanup (delete test data)."""
    from .cleanup import cleanup_test_data
    cleanup_test_data()


def test_only():
    """Only run tests (no setup/cleanup)."""
    from .test_pos_api import run_all_tests
    return run_all_tests()
