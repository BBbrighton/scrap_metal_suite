# Copyright (c) 2026, Scrap Metal Suite and contributors
# For license information, please see license.txt
#
# Unit tests for the Scrap Weight Container controller.
# Covers cases listed in docs/DROPOFF_CONTAINER_REDESIGN.md §11.1.
#
# Item names are CANONICAL THAI (BILINGUAL_GUIDE.md §2). Tests assert against
# the raw stored value — never wrap `item_name` in `_()` or expect English.

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, now_datetime, add_to_date


# Canonical Thai item names; never translated. See BILINGUAL_GUIDE.md §2.
THAI_ITEM_PRIMARY = "ทองแดงปอก"      # expected
THAI_ITEM_SECONDARY = "ทองแดงเล็ก"   # expected
THAI_ITEM_UNPLANNED = "ทองแดงสะอาด"  # NOT in expected_items → triggers grade-mix deviation at the Dropoff level (Wave 9)

TEST_PREFIX = "_TEST_SWC_"


def _ensure_item(item_name):
    """Idempotent Item factory — keyed by item_name (canonical Thai)."""
    code = frappe.db.get_value("Item", {"item_name": item_name}, "name")
    if code:
        return code

    doc = frappe.get_doc({
        "doctype": "Item",
        "item_code": item_name,           # use the Thai name as the code too
        "item_name": item_name,            # canonical, never translated
        "item_group": "Raw Material",
        "stock_uom": "Kg",
        "is_stock_item": 1,
    })
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_supplier():
    name = f"{TEST_PREFIX}Supplier"
    if frappe.db.exists("Supplier", {"supplier_name": name}):
        return frappe.db.get_value("Supplier", {"supplier_name": name}, "name")
    doc = frappe.get_doc({
        "doctype": "Supplier",
        "supplier_name": name,
        "supplier_group": "Raw Material",
    })
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_scale(name_suffix="01", max_capacity=5000):
    scale_name = f"{TEST_PREFIX}Scale-{name_suffix}"
    existing = frappe.db.get_value("Scale", {"scale_name": scale_name}, "name")
    if existing:
        # Make sure capacity matches the test's expectation.
        frappe.db.set_value("Scale", existing, "max_capacity_kg", max_capacity)
        return existing
    doc = frappe.get_doc({
        "doctype": "Scale",
        "scale_name": scale_name,
        "scale_type": "Platform",
        "usage_type": "Scrap",
        "location": "Test Bay",
        "is_active": 1,
        "max_capacity_kg": max_capacity,
        "baud_rate": 9600,
        "data_bits": 8,
        "parity": "none",
        "stop_bits": 1,
    })
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_pos_profile():
    profile_name = f"{TEST_PREFIX}Profile"
    existing = frappe.db.get_value(
        "POS Profile Scrap", {"profile_name": profile_name}, "name"
    )
    if existing:
        return existing
    price_list = frappe.db.get_value("Price List", {"buying": 1}, "name") or "Standard Buying"
    doc = frappe.get_doc({
        "doctype": "POS Profile Scrap",
        "profile_name": profile_name,
        "is_active": 1,
        "price_list": price_list,
    })
    # `items` child table is mandatory — populate with the test items.
    # POS Profile Item child uses `item_code` (Link to Item).
    for code in (THAI_ITEM_PRIMARY, THAI_ITEM_SECONDARY, THAI_ITEM_DEVIATION):
        if frappe.db.exists("Item", code):
            doc.append("items", {"item_code": code, "item_name": code})
    doc.insert(ignore_permissions=True)
    return doc.name


def _open_pos_session(profile_name, scale_name, operator="Administrator"):
    """Create an Open POS Session bound to the given scale.

    Closes any existing Open session for the operator first so each test
    can open a fresh one. We bypass the API helper because these are unit
    tests for the controller.
    """
    existing = frappe.db.get_all(
        "POS Session",
        filters={"operator": operator, "status": "Open"},
        fields=["name"],
    )
    for s in existing:
        frappe.db.set_value("POS Session", s.name, "status", "Closed")

    doc = frappe.get_doc({
        "doctype": "POS Session",
        "pos_profile": profile_name,
        "operator": operator,
        "scale": scale_name,
        "status": "Open",
        "opening_time": now_datetime(),
    })
    doc.insert(ignore_permissions=True)
    return doc.name


def _make_dropoff(supplier, expected_items):
    """Create a Dropoff in Scheduled status with the given expected items."""
    doc = frappe.get_doc({
        "doctype": "Dropoff",
        "dropoff_scheduled_start": now_datetime(),
        "dropoff_scheduled_end": add_to_date(now_datetime(), hours=2),
        "license_plate": f"{TEST_PREFIX}ABC-1234",
        "supplier": supplier,
        "status": "Scheduled",
        # Make truck-variance gating permissive; lifecycle tests below need
        # to be able to mark the dropoff Completed once truck weights are
        # populated.
        "truck_variance_threshold_percent": 100.0,
        "indicated_variance_threshold_percent": 100.0,
    })
    for code, indicated in expected_items:
        doc.append("expected_items", {
            "item": code,
            "indicated_weight": flt(indicated),
        })
    doc.insert(ignore_permissions=True)
    return doc


def _make_container(dropoff_name, session_name, scale_name, item_code,
                    net_weight, container_type="Bag",
                    operator="Administrator"):
    """Insert a Scrap Weight Container directly (bypasses the API auth guard).
    Mirrors what `add_container` does internally."""
    doc = frappe.get_doc({
        "doctype": "Scrap Weight Container",
        "dropoff": dropoff_name,
        "session": session_name,
        "scale": scale_name,
        "operator": operator,
        "item_code": item_code,
        "container_type": container_type,
        "net_weight": flt(net_weight),
        "entry_method": "Manual Entry",
    })
    doc.insert(ignore_permissions=True)
    return doc


class TestScrapWeightContainer(FrappeTestCase):
    """Unit tests for `Scrap Weight Container` controller behaviour."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        frappe.set_user("Administrator")

        # Master data — created once, shared across tests. Each test rolls
        # back its own transactional changes in tearDown.
        cls.item_primary = _ensure_item(THAI_ITEM_PRIMARY)
        cls.item_secondary = _ensure_item(THAI_ITEM_SECONDARY)
        cls.item_unplanned = _ensure_item(THAI_ITEM_UNPLANNED)
        cls.supplier = _ensure_supplier()
        cls.scale = _ensure_scale()
        cls.alt_scale = _ensure_scale(name_suffix="02")
        cls.profile = _ensure_pos_profile()
        frappe.db.commit()

    def setUp(self):
        frappe.set_user("Administrator")

        # Per-test fresh dropoff + session so each test has a clean lock.
        self.session = _open_pos_session(self.profile, self.scale)
        self.dropoff_doc = _make_dropoff(
            self.supplier,
            [
                (self.item_primary, 1000),
                (self.item_secondary, 500),
            ],
        )
        self.dropoff = self.dropoff_doc.name

    def tearDown(self):
        # Roll back all per-test mutations; setUpClass-created docs are
        # already committed and persist across tests (idempotent factories).
        frappe.db.rollback()
        frappe.set_user("Administrator")

    # ------------------------------------------------------------------
    # 1. Happy path
    # ------------------------------------------------------------------
    def test_add_container_happy_path(self):
        ctn = _make_container(
            self.dropoff, self.session, self.scale,
            self.item_primary, 250.5,
        )
        ctn.reload()

        # Field denormalisation
        self.assertEqual(ctn.dropoff, self.dropoff)
        self.assertEqual(ctn.session, self.session)
        self.assertEqual(ctn.scale, self.scale)
        self.assertEqual(ctn.item_code, self.item_primary)
        # Item name is canonical Thai master data — render verbatim.
        self.assertEqual(ctn.item_name, THAI_ITEM_PRIMARY)
        self.assertEqual(ctn.status, "Active")
        self.assertAlmostEqual(flt(ctn.net_weight), 250.5)

        # Initial weight history row appended by after_insert.
        self.assertEqual(len(ctn.weight_history), 1)
        self.assertEqual(ctn.weight_history[0].event, "Initial")
        self.assertAlmostEqual(flt(ctn.weight_history[0].weight), 250.5)

    # ------------------------------------------------------------------
    # 2. First container acquires the lock
    # ------------------------------------------------------------------
    def test_first_container_acquires_lock(self):
        # Pre-condition: no lock yet.
        self.assertFalse(self.dropoff_doc.weighing_session)
        self.assertFalse(self.dropoff_doc.weighing_scale)

        # Drive the lock-acquisition path the API uses.
        self.dropoff_doc._acquire_container_lock(self.session, self.scale)
        _make_container(
            self.dropoff, self.session, self.scale,
            self.item_primary, 100,
        )
        self.dropoff_doc.save(ignore_permissions=True)
        self.dropoff_doc.reload()

        self.assertEqual(self.dropoff_doc.weighing_session, self.session)
        self.assertEqual(self.dropoff_doc.weighing_scale, self.scale)
        self.assertEqual(self.dropoff_doc.status, "In Progress")

    # ------------------------------------------------------------------
    # 3. Second container from a different session is blocked
    # ------------------------------------------------------------------
    def test_second_container_different_session_blocked(self):
        # First session locks the dropoff.
        self.dropoff_doc._acquire_container_lock(self.session, self.scale)
        _make_container(
            self.dropoff, self.session, self.scale,
            self.item_primary, 100,
        )
        self.dropoff_doc.save(ignore_permissions=True)
        self.dropoff_doc.reload()

        # Second session on the same scale must still be rejected by the
        # lock guard (the lock is keyed on session, not scale).
        other_session = _open_pos_session(self.profile, self.scale)
        with self.assertRaises(frappe.ValidationError):
            self.dropoff_doc._validate_container_lock(other_session)

    # ------------------------------------------------------------------
    # 4. Reweigh updates weight + appends history
    # ------------------------------------------------------------------
    def test_reweigh_appends_history(self):
        ctn = _make_container(
            self.dropoff, self.session, self.scale,
            self.item_primary, 100,
        )
        ctn.record_reweigh(125.5, reason="Scale recalibrated")
        ctn.reload()

        self.assertAlmostEqual(flt(ctn.net_weight), 125.5)
        self.assertEqual(ctn.is_reweighed, 1)
        self.assertIsNotNone(ctn.last_reweigh_at)
        self.assertEqual(ctn.last_reweigh_by, frappe.session.user)
        self.assertEqual(ctn.last_reweigh_reason, "Scale recalibrated")

        # Two history rows: Initial + Reweigh
        self.assertEqual(len(ctn.weight_history), 2)
        events = [row.event for row in ctn.weight_history]
        self.assertIn("Initial", events)
        self.assertIn("Reweigh", events)

    # ------------------------------------------------------------------
    # 5. Reweigh without reason throws
    # ------------------------------------------------------------------
    def test_reweigh_without_reason_throws(self):
        ctn = _make_container(
            self.dropoff, self.session, self.scale,
            self.item_primary, 100,
        )
        with self.assertRaises(frappe.ValidationError):
            ctn.record_reweigh(150, reason="")

    # ------------------------------------------------------------------
    # 6. Void marks status Voided + audit fields
    # ------------------------------------------------------------------
    def test_void_marks_status(self):
        ctn = _make_container(
            self.dropoff, self.session, self.scale,
            self.item_primary, 100,
        )
        ctn.record_void(reason="Spillage during transfer")
        ctn.reload()

        self.assertEqual(ctn.status, "Voided")
        self.assertEqual(ctn.voided_reason, "Spillage during transfer")
        self.assertIsNotNone(ctn.voided_at)
        self.assertEqual(ctn.voided_by, frappe.session.user)

    # ------------------------------------------------------------------
    # 7. Deviation detected when grade not in expected_items
    # ------------------------------------------------------------------
    def test_unplanned_grade_flags_dropoff_grade_deviation(self):
        # Wave 9: the grade-mix deviation is a Dropoff-level concept now.
        # The container is just a measurement — `item_unplanned` is NOT in the
        # expected_items configured in setUp, so the parent Dropoff should
        # report grade_deviation_ok = 0 and a non-empty grade_deviation_summary.
        _make_container(
            self.dropoff, self.session, self.scale,
            self.item_unplanned, 50,
        )
        do = frappe.get_doc("Dropoff", self.dropoff)
        do.save(ignore_permissions=True)
        do.reload()

        self.assertEqual(do.grade_deviation_ok, 0)
        self.assertIn(THAI_ITEM_UNPLANNED, do.grade_deviation_summary)

        # Drop in some of an expected grade — still deviating because the
        # other expected grade is short.
        _make_container(
            self.dropoff, self.session, self.scale,
            self.item_primary, 200,
        )
        do.reload()
        do.save(ignore_permissions=True)
        # Container itself has no deviation field anymore — assert it's gone.
        self.assertFalse(hasattr(do, "has_unapproved_deviation"))

    # ------------------------------------------------------------------
    # 8. Aggregation excludes voided containers
    # ------------------------------------------------------------------
    def test_aggregation_excludes_voided(self):
        c1 = _make_container(
            self.dropoff, self.session, self.scale,
            self.item_primary, 100,
        )
        c2 = _make_container(
            self.dropoff, self.session, self.scale,
            self.item_primary, 200,
        )
        c3 = _make_container(
            self.dropoff, self.session, self.scale,
            self.item_secondary, 300,
        )

        # Void c2.
        c2.record_void(reason="Torn bag")

        # Re-aggregate.
        do = frappe.get_doc("Dropoff", self.dropoff)
        do.save(ignore_permissions=True)
        do.reload()

        # Only c1 (100) + c3 (300) = 400 should count.
        self.assertAlmostEqual(flt(do.total_actual_weight), 400.0)
        self.assertEqual(do.container_count, 2)

    # ------------------------------------------------------------------
    # 10. Pause clears session, keeps scale
    # ------------------------------------------------------------------
    def test_pause_clears_session_keeps_scale(self):
        self.dropoff_doc._acquire_container_lock(self.session, self.scale)
        _make_container(
            self.dropoff, self.session, self.scale,
            self.item_primary, 100,
        )
        self.dropoff_doc.save(ignore_permissions=True)
        self.dropoff_doc.reload()

        self.dropoff_doc.pause_weighing(reason="Shift change")
        self.dropoff_doc.reload()

        self.assertEqual(self.dropoff_doc.status, "Paused")
        self.assertFalse(self.dropoff_doc.weighing_session)
        # Scale lock survives pause (design §5.2 / §7.4).
        self.assertEqual(self.dropoff_doc.weighing_scale, self.scale)
        self.assertIsNotNone(self.dropoff_doc.paused_at)

    # ------------------------------------------------------------------
    # 11. Resume blocked when scale differs
    # ------------------------------------------------------------------
    def test_resume_blocked_on_scale_mismatch(self):
        self.dropoff_doc._acquire_container_lock(self.session, self.scale)
        _make_container(
            self.dropoff, self.session, self.scale,
            self.item_primary, 100,
        )
        self.dropoff_doc.save(ignore_permissions=True)
        self.dropoff_doc.reload()

        self.dropoff_doc.pause_weighing(reason="Test pause")
        self.dropoff_doc.reload()

        # New session on a DIFFERENT scale → resume must throw.
        bad_session = _open_pos_session(self.profile, self.alt_scale)
        with self.assertRaises(frappe.ValidationError):
            self.dropoff_doc.resume_weighing(bad_session)

    # ------------------------------------------------------------------
    # 12. Grade-mix deviation surfaces verification_status = Needs Review
    # ------------------------------------------------------------------
    def test_grade_mix_deviation_surfaces_needs_review(self):
        # Wave 9: completion is no longer blocked by unapproved deviations;
        # they surface via verification_status = "Needs Review" instead.
        # Manager resolves via verify_dropoff override.
        self.dropoff_doc._acquire_container_lock(self.session, self.scale)
        _make_container(
            self.dropoff, self.session, self.scale,
            self.item_unplanned, 50,
        )
        # Truck weights so complete_dropoff doesn't bail on missing values.
        self.dropoff_doc.gross_weight = 2500
        self.dropoff_doc.tare_weight = 2450
        self.dropoff_doc.save(ignore_permissions=True)
        self.dropoff_doc.reload()

        # Grade-mix deviation flag is set, but completion is NOT blocked.
        self.assertEqual(self.dropoff_doc.grade_deviation_ok, 0)

        from scrap_metal_suite.api.v1.dropoff import complete_dropoff
        result = complete_dropoff(self.dropoff)
        self.assertTrue(result["success"])
        # Variance + grade checks all roll into one verification_status flag.
        self.assertEqual(result["verification_status"], "Needs Review")
        self.assertEqual(result["grade_deviation_ok"], 0)

    # ------------------------------------------------------------------
    # 13. verify_dropoff requires override reason when Needs Review
    # ------------------------------------------------------------------
    def test_verify_dropoff_requires_override_reason_when_needs_review(self):
        # Force verification_status = "Needs Review" via direct DB write so
        # the controller's `calculate_verification_status` doesn't reset it
        # on save. This lets us exercise the override path without staging
        # a full variance failure.
        frappe.db.set_value(
            "Dropoff", self.dropoff, "verification_status", "Needs Review"
        )
        do = frappe.get_doc("Dropoff", self.dropoff)

        with self.assertRaises(frappe.ValidationError):
            do.mark_verified(override_reason=None)

        # With a reason, the override succeeds.
        do.mark_verified(override_reason="Manually verified after review")
        do.reload()
        self.assertEqual(do.verification_status, "Verified")
        self.assertEqual(do.verification_overridden, 1)
        self.assertEqual(do.verification_override_by, frappe.session.user)
        self.assertEqual(
            do.verification_override_reason,
            "Manually verified after review",
        )
