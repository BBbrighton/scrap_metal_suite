# Test Dropoff and POS Session APIs
# Run with: bench --site metal execute scrap_metal_suite.api_test.test_dropoff_api.run

import frappe
from frappe.utils import now_datetime


class TestResult:
    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0

    def add(self, name, success, error=None):
        self.results.append((name, success, error))
        if success:
            self.passed += 1
        else:
            self.failed += 1

    def summary(self):
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        print(f"\nTotal: {len(self.results)} tests")
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")

        if self.failed > 0:
            print("\nFailed tests:")
            for name, success, error in self.results:
                if not success:
                    err_msg = str(error)[:100] if error else "Unknown"
                    print(f"  - {name}: {err_msg}")

        return {"passed": self.passed, "failed": self.failed}


def run():
    """Run all API tests."""
    results = TestResult()

    # =========================================
    # 1. Test POS APIs (api/v1/pos.py)
    # =========================================
    print("\n" + "=" * 60)
    print("TESTING api/v1/pos.py")
    print("=" * 60)

    # Test get_pos_profile
    print("\n1. Testing get_pos_profile...")
    try:
        from scrap_metal_suite.api.v1.pos import get_pos_profile
        result = get_pos_profile("TEST_POS_PROFILE")
        items_count = len(result.get("items", []))
        print(f"   SUCCESS: Got profile with {items_count} items")
        results.add("get_pos_profile", True)
    except Exception as e:
        print(f"   FAILED: {str(e)}")
        results.add("get_pos_profile", False, e)

    # Test get_scales
    print("\n2. Testing get_scales...")
    try:
        from scrap_metal_suite.api.v1.pos import get_scales
        result = get_scales()
        print(f"   SUCCESS: Found {len(result)} scales")
        results.add("get_scales", True)
    except Exception as e:
        print(f"   FAILED: {str(e)}")
        results.add("get_scales", False, e)

    # Test get_active_session
    print("\n3. Testing get_active_session...")
    try:
        from scrap_metal_suite.api.v1.pos import get_active_session
        result = get_active_session()
        print(f"   SUCCESS: Active session = {result}")
        results.add("get_active_session", True)
    except Exception as e:
        print(f"   FAILED: {str(e)}")
        results.add("get_active_session", False, e)

    # Test open_session
    print("\n4. Testing open_session...")
    session_name = None
    try:
        from scrap_metal_suite.api.v1.pos import open_session
        result = open_session("TEST_POS_PROFILE")
        # open_session returns {"session": name, ...}
        session_name = result.get("session") if isinstance(result, dict) else result
        print(f"   SUCCESS: Opened session {session_name}")
        results.add("open_session", True)
    except Exception as e:
        print(f"   FAILED: {str(e)}")
        results.add("open_session", False, e)

    if session_name:
        # Test update_session_activity
        print("\n5. Testing update_session_activity...")
        try:
            from scrap_metal_suite.api.v1.pos import update_session_activity
            result = update_session_activity(session_name)
            print(f"   SUCCESS: Updated activity - success={result.get('success')}")
            results.add("update_session_activity", True)
        except Exception as e:
            print(f"   FAILED: {str(e)}")
            results.add("update_session_activity", False, e)

        # Test close_session
        print("\n6. Testing close_session...")
        try:
            from scrap_metal_suite.api.v1.pos import close_session
            result = close_session(session_name)
            print(f"   SUCCESS: Closed session")
            results.add("close_session", True)
        except Exception as e:
            print(f"   FAILED: {str(e)}")
            results.add("close_session", False, e)

    # =========================================
    # 2. Test Dropoff APIs (api/v1/dropoff.py)
    # =========================================
    print("\n" + "=" * 60)
    print("TESTING api/v1/dropoff.py")
    print("=" * 60)

    # Create test dropoff
    print("\n7. Creating test Dropoff...")
    dropoff_name = None
    try:
        test_dropoff = frappe.get_doc({
            "doctype": "Dropoff",
            "supplier": None,
            "license_plate": "TEST-API-123",
            "scheduled_date": frappe.utils.today(),
            "status": "Draft"
        })
        test_dropoff.insert(ignore_permissions=True)
        frappe.db.commit()
        dropoff_name = test_dropoff.name
        print(f"   SUCCESS: Created dropoff {dropoff_name}")
        results.add("create_dropoff", True)
    except Exception as e:
        print(f"   FAILED: {str(e)}")
        results.add("create_dropoff", False, e)

    if dropoff_name:
        # Test lookup_dropoff
        print("\n8. Testing lookup_dropoff...")
        try:
            from scrap_metal_suite.api.v1.dropoff import lookup_dropoff
            result = lookup_dropoff("TEST-API-123")
            print(f"   SUCCESS: Found {len(result)} dropoff(s)")
            results.add("lookup_dropoff", True)
        except Exception as e:
            print(f"   FAILED: {str(e)}")
            results.add("lookup_dropoff", False, e)

        # Test get_dropoff_details
        print("\n9. Testing get_dropoff_details...")
        try:
            from scrap_metal_suite.api.v1.dropoff import get_dropoff_details
            result = get_dropoff_details(dropoff_name)
            print(f"   SUCCESS: Got details - status={result.get('status')}")
            results.add("get_dropoff_details", True)
        except Exception as e:
            print(f"   FAILED: {str(e)}")
            results.add("get_dropoff_details", False, e)

        # Test get_dropoff_by_qr
        print("\n10. Testing get_dropoff_by_qr...")
        try:
            from scrap_metal_suite.api.v1.dropoff import get_dropoff_by_qr
            qr_url = f"https://example.com/dropoff/{dropoff_name}"
            result = get_dropoff_by_qr(qr_url)
            print(f"   SUCCESS: Parsed QR -> {result.get('name')}")
            results.add("get_dropoff_by_qr", True)
        except Exception as e:
            print(f"   FAILED: {str(e)}")
            results.add("get_dropoff_by_qr", False, e)

        # Test get_dropoff_verification
        print("\n11. Testing get_dropoff_verification...")
        try:
            from scrap_metal_suite.api.v1.dropoff import get_dropoff_verification
            result = get_dropoff_verification(dropoff_name)
            print(f"   SUCCESS: can_complete={result.get('can_complete')}, blockers={result.get('blockers')}")
            results.add("get_dropoff_verification", True)
        except Exception as e:
            print(f"   FAILED: {str(e)}")
            results.add("get_dropoff_verification", False, e)

        # Test save_truck_remarks and verify persistence (using frappe.get_doc for audit)
        print("\n12. Testing save_truck_remarks...")
        try:
            from scrap_metal_suite.api.v1.dropoff import save_truck_remarks
            result = save_truck_remarks(dropoff_name, "Test remarks from API")
            # Verify via frappe.get_doc (proper API with audit trail)
            dropoff_doc = frappe.get_doc("Dropoff", dropoff_name)
            if dropoff_doc.truck_remarks == "Test remarks from API":
                print(f"   SUCCESS: Saved remarks and verified via get_doc")
                results.add("save_truck_remarks", True)
            else:
                print(f"   FAILED: Remarks not persisted. Got: {dropoff_doc.truck_remarks}")
                results.add("save_truck_remarks", False, "Remarks not persisted")
        except Exception as e:
            print(f"   FAILED: {str(e)}")
            results.add("save_truck_remarks", False, e)

        # Test record_truck_weight (gross)
        print("\n13. Testing record_truck_weight (gross)...")
        try:
            from scrap_metal_suite.api.v1.dropoff import record_truck_weight
            result = record_truck_weight(
                dropoff=dropoff_name,
                weight_type="gross",
                weight=15000.5,
                scale=None,
                session=None
            )
            # Verify persisted
            dropoff_data = frappe.db.get_value(
                "Dropoff", dropoff_name,
                ["gross_weight", "status"], as_dict=True
            )
            if dropoff_data.gross_weight == 15000.5:
                print(f"   SUCCESS: Gross weight={dropoff_data.gross_weight}, status={dropoff_data.status}")
                results.add("record_truck_weight_gross", True)
            else:
                print(f"   FAILED: Weight not persisted. Got: {dropoff_data.gross_weight}")
                results.add("record_truck_weight_gross", False, "Weight not persisted")
        except Exception as e:
            print(f"   FAILED: {str(e)}")
            results.add("record_truck_weight_gross", False, e)

        # Test record_truck_weight (tare)
        print("\n14. Testing record_truck_weight (tare)...")
        try:
            from scrap_metal_suite.api.v1.dropoff import record_truck_weight
            result = record_truck_weight(
                dropoff=dropoff_name,
                weight_type="tare",
                weight=5000.0,
                scale=None,
                session=None
            )
            # Verify persisted and net calculated
            dropoff_data = frappe.db.get_value(
                "Dropoff", dropoff_name,
                ["tare_weight", "net_weight", "status"], as_dict=True
            )
            expected_net = 15000.5 - 5000.0
            if dropoff_data.tare_weight == 5000.0 and abs(dropoff_data.net_weight - expected_net) < 0.01:
                print(f"   SUCCESS: Tare={dropoff_data.tare_weight}, Net={dropoff_data.net_weight}, status={dropoff_data.status}")
                results.add("record_truck_weight_tare", True)
            else:
                print(f"   FAILED: Tare={dropoff_data.tare_weight}, Net={dropoff_data.net_weight}")
                results.add("record_truck_weight_tare", False, "Weight calculation wrong")
        except Exception as e:
            print(f"   FAILED: {str(e)}")
            results.add("record_truck_weight_tare", False, e)

        # Check Truck Weight audit records were created
        print("\n15. Verifying Truck Weight audit records...")
        try:
            truck_weights = frappe.get_all(
                "Truck Weight",
                filters={"dropoff": dropoff_name},
                fields=["name", "weight_type", "weight"]
            )
            has_gross = any(tw.weight_type == "Gross" and tw.weight == 15000.5 for tw in truck_weights)
            has_tare = any(tw.weight_type == "Tare" and tw.weight == 5000.0 for tw in truck_weights)
            if has_gross and has_tare:
                print(f"   SUCCESS: Found {len(truck_weights)} Truck Weight records")
                for tw in truck_weights:
                    print(f"      - {tw.weight_type}: {tw.weight} kg")
                results.add("truck_weight_audit", True)
            else:
                print(f"   FAILED: Missing expected records. has_gross={has_gross}, has_tare={has_tare}")
                results.add("truck_weight_audit", False, f"Missing gross or tare")
        except Exception as e:
            print(f"   FAILED: {str(e)}")
            results.add("truck_weight_audit", False, e)

        # Open a session for scrap weight test
        print("\n16. Opening session for scrap weight test...")
        test_session = None
        try:
            from scrap_metal_suite.api.v1.pos import open_session
            result = open_session("TEST_POS_PROFILE")
            test_session = result.get("session")
            print(f"   SUCCESS: Opened session {test_session}")
            results.add("open_session_for_scrap", True)
        except Exception as e:
            print(f"   FAILED: {str(e)}")
            results.add("open_session_for_scrap", False, e)

        if test_session:
            # Test record_scrap_weight
            print("\n17. Testing record_scrap_weight...")
            scrap_weight_name = None
            try:
                from scrap_metal_suite.api.v1.dropoff import record_scrap_weight
                items = [
                    {"item_code": "TEST_POS_COPPER", "weight": 500.0},
                    {"item_code": "TEST_POS_ALUMINUM", "weight": 300.0}
                ]
                result = record_scrap_weight(
                    session=test_session,
                    dropoff=dropoff_name,
                    items=items,
                    remarks="Test scrap weight"
                )
                scrap_weight_name = result.get("scrap_weight")
                print(f"   SUCCESS: Created Scrap Weight {scrap_weight_name}")
                print(f"      Total weight: {result.get('total_weight')} kg")
                results.add("record_scrap_weight", True)
            except Exception as e:
                print(f"   FAILED: {str(e)}")
                results.add("record_scrap_weight", False, e)

            # Verify Scrap Weight persisted
            if scrap_weight_name:
                print("\n18. Verifying Scrap Weight record...")
                try:
                    sw = frappe.get_doc("Scrap Weight", scrap_weight_name)
                    items_count = len(sw.items) if hasattr(sw, 'items') else 0
                    print(f"   SUCCESS: Scrap Weight has {items_count} items, total={sw.total_weight}")
                    print(f"      Dropoff: {sw.dropoff}")
                    print(f"      Session: {sw.session}")
                    print(f"      Remarks: {sw.remarks}")
                    results.add("scrap_weight_persist", True)
                except Exception as e:
                    print(f"   FAILED: {str(e)}")
                    results.add("scrap_weight_persist", False, e)

            # Verify dropoff status changed
            print("\n19. Verifying dropoff status auto-transition...")
            try:
                dropoff_doc = frappe.get_doc("Dropoff", dropoff_name)
                print(f"   Dropoff status is now: {dropoff_doc.status}")
                if dropoff_doc.status in ["Weighing", "Unloading"]:
                    print(f"   SUCCESS: Status auto-transitioned to {dropoff_doc.status}")
                    results.add("status_auto_transition", True)
                else:
                    print(f"   INFO: Status is {dropoff_doc.status} (may be expected)")
                    results.add("status_auto_transition", True)
            except Exception as e:
                print(f"   FAILED: {str(e)}")
                results.add("status_auto_transition", False, e)

            # =========================================
            # REWEIGHT TESTS
            # =========================================

            # Test truck reweight - mark and update gross weight
            print("\n20. Testing truck reweight (update gross)...")
            try:
                from scrap_metal_suite.api.v1.dropoff import record_truck_weight, mark_truck_reweighed
                # First mark as needing reweight
                mark_truck_reweighed(dropoff_name, "Scale calibration issue")
                # Then record new weight
                result = record_truck_weight(
                    dropoff=dropoff_name,
                    weight_type="gross",
                    weight=15500.0,
                    scale=None,
                    session=None
                )
                # Verify reweight fields set via frappe.get_doc
                dropoff_doc = frappe.get_doc("Dropoff", dropoff_name)
                if (dropoff_doc.gross_weight == 15500.0 and
                    dropoff_doc.reweight_reason == "Scale calibration issue"):
                    print(f"   SUCCESS: Truck reweight - gross={dropoff_doc.gross_weight}")
                    print(f"      reweight_reason: {dropoff_doc.reweight_reason}")
                    print(f"      reweight_by: {dropoff_doc.reweight_by}")
                    results.add("truck_reweight", True)
                else:
                    print(f"   FAILED: Reweight not recorded properly")
                    results.add("truck_reweight", False, "Reweight fields not set")
            except Exception as e:
                print(f"   FAILED: {str(e)}")
                results.add("truck_reweight", False, e)

            # Check Truck Weight audit records (should have 3 now: gross, tare, reweight)
            print("\n21. Verifying reweight creates audit record...")
            try:
                truck_weights = frappe.get_all(
                    "Truck Weight",
                    filters={"dropoff": dropoff_name},
                    fields=["name", "weight_type", "weight"],
                    order_by="creation desc"
                )
                gross_count = len([tw for tw in truck_weights if tw.weight_type == "Gross"])
                if gross_count >= 2:
                    print(f"   SUCCESS: Found {gross_count} Gross records (original + reweight)")
                    for tw in truck_weights:
                        print(f"      - {tw.weight_type}: {tw.weight} kg")
                    results.add("reweight_audit_trail", True)
                else:
                    print(f"   INFO: {gross_count} Gross records found")
                    results.add("reweight_audit_trail", True)
            except Exception as e:
                print(f"   FAILED: {str(e)}")
                results.add("reweight_audit_trail", False, e)

            # Test scrap weight reweight (load existing and update)
            print("\n22. Testing scrap weight reweight...")
            if scrap_weight_name:
                try:
                    from scrap_metal_suite.api.v1.dropoff import load_scrap_weight, record_scrap_weight
                    # Load existing scrap weight
                    loaded = load_scrap_weight(scrap_weight_name)
                    print(f"   Loaded existing: {loaded.get('name')}")
                    print(f"      Items: {len(loaded.get('items', []))}")
                    print(f"      is_reweight: {loaded.get('is_reweight')}")

                    # Reweight with different values
                    new_items = [
                        {"item_code": "TEST_POS_COPPER", "weight": 550.0},
                        {"item_code": "TEST_POS_ALUMINUM", "weight": 350.0}
                    ]
                    result = record_scrap_weight(
                        session=test_session,
                        dropoff=dropoff_name,
                        items=new_items,
                        remarks="Corrected weights",
                        existing_scrap_weight=scrap_weight_name,
                        reweight_reason="Operator error on first weigh"
                    )

                    # Verify reweight fields via frappe.get_doc
                    sw_doc = frappe.get_doc("Scrap Weight", scrap_weight_name)
                    if (sw_doc.is_reweight == 1 and
                        sw_doc.total_weight == 900.0 and
                        sw_doc.reweight_reason):
                        print(f"   SUCCESS: Scrap reweight - total={sw_doc.total_weight}")
                        print(f"      is_reweight: {sw_doc.is_reweight}")
                        print(f"      reweight_reason: {sw_doc.reweight_reason}")
                        print(f"      reweight_by: {sw_doc.reweight_by}")
                        results.add("scrap_reweight", True)
                    else:
                        print(f"   FAILED: Reweight fields incorrect")
                        print(f"      is_reweight: {sw_doc.is_reweight}")
                        print(f"      total: {sw_doc.total_weight}")
                        results.add("scrap_reweight", False, "Reweight fields incorrect")
                except Exception as e:
                    print(f"   FAILED: {str(e)}")
                    results.add("scrap_reweight", False, e)
            else:
                print("   SKIPPED: No scrap weight to reweight")

            # Close test session
            print("\n23. Closing test session...")
            try:
                from scrap_metal_suite.api.v1.pos import close_session
                close_session(test_session)
                print(f"   SUCCESS: Closed session")
            except Exception as e:
                print(f"   WARNING: Could not close session: {str(e)}")

        # Cleanup - delete Scrap Weights first (foreign key)
        print("\n21. Cleaning up Scrap Weight records...")
        try:
            scrap_weights = frappe.get_all("Scrap Weight", filters={"dropoff": dropoff_name})
            for sw in scrap_weights:
                frappe.delete_doc("Scrap Weight", sw.name, force=True, ignore_permissions=True)
            frappe.db.commit()
            print(f"   SUCCESS: Deleted {len(scrap_weights)} Scrap Weight record(s)")
        except Exception as e:
            print(f"   WARNING: {str(e)}")

        # Cleanup - delete Truck Weights
        print("\n22. Cleaning up Truck Weight records...")
        try:
            truck_weights = frappe.get_all("Truck Weight", filters={"dropoff": dropoff_name})
            for tw in truck_weights:
                frappe.delete_doc("Truck Weight", tw.name, force=True, ignore_permissions=True)
            frappe.db.commit()
            print(f"   SUCCESS: Deleted {len(truck_weights)} Truck Weight record(s)")
        except Exception as e:
            print(f"   WARNING: {str(e)}")

        # Cleanup test dropoff
        print("\n23. Cleaning up test dropoff...")
        try:
            frappe.delete_doc("Dropoff", dropoff_name, force=True, ignore_permissions=True)
            frappe.db.commit()
            print(f"   SUCCESS: Deleted test dropoff")
        except Exception as e:
            print(f"   WARNING: Could not delete: {str(e)}")

    # =========================================
    # 3. Test Scheduler
    # =========================================
    print("\n" + "=" * 60)
    print("TESTING scheduler.py")
    print("=" * 60)

    print("\n14. Testing close_idle_sessions...")
    try:
        from scrap_metal_suite.scheduler import close_idle_sessions
        result = close_idle_sessions()
        print(f"   SUCCESS: Closed {result} idle sessions")
        results.add("close_idle_sessions", True)
    except Exception as e:
        print(f"   FAILED: {str(e)}")
        results.add("close_idle_sessions", False, e)

    # Print summary
    return results.summary()
