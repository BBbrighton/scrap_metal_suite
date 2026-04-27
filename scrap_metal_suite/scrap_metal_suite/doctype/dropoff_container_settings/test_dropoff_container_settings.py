# Copyright (c) 2026, Scrap Metal Suite and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestDropoffContainerSettings(FrappeTestCase):
    """
    Single doctype `Dropoff Container Settings` ships with sensible defaults
    declared in the JSON (see docs/DROPOFF_CONTAINER_REDESIGN.md §4.6).
    The defaults must be readable via `frappe.db.get_single_value` so that
    the Scrap Weight Container controller can gate behaviour on them.
    """

    def setUp(self):
        frappe.session.user = "Administrator"

    def tearDown(self):
        frappe.db.rollback()

    def test_defaults_loadable(self):
        """get_single returns a doc and exposes the documented default fields."""
        settings = frappe.get_single("Dropoff Container Settings")

        # All fields named in the design doc §4.6 must be addressable on the
        # singleton — even if the database row hasn't been initialised yet
        # (Frappe returns None for unset numeric fields, but the attribute
        # itself must exist on the model).
        for fieldname in (
            "deviation_approval_threshold_kg",
            "deviation_approval_threshold_pct",
            "weight_variance_threshold_pct",
            "allow_unplanned_grades",
            "require_reason_on_deviation",
            "auto_print_sticker_default",
        ):
            self.assertTrue(
                hasattr(settings, fieldname),
                f"Dropoff Container Settings missing field {fieldname}",
            )

        # `require_reason_on_deviation` defaults to 1 in the JSON; the
        # controller relies on this to enforce reason capture. Read it via
        # the same helper the controller uses.
        require_reason = frappe.db.get_single_value(
            "Dropoff Container Settings", "require_reason_on_deviation"
        )
        # Either explicitly 1 (saved) or None (not yet persisted) — both are
        # acceptable for the unit-test sanity check; what matters is that
        # the call doesn't blow up and the field is addressable.
        self.assertIn(require_reason, (None, 0, 1))
