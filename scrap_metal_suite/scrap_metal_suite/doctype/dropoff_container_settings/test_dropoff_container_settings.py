# Copyright (c) 2026, Scrap Metal Suite and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestDropoffContainerSettings(FrappeTestCase):
    """
    Single doctype `Dropoff Container Settings` ships with sensible defaults
    declared in the JSON. After the Wave 9 deviation move, only the
    truck-variance threshold and auto-print default remain — per-container
    deviation thresholds were retired (deviation now lives at the Dropoff
    level, see docs/DROPOFF_CONTAINER_REDESIGN.md §14.17).
    """

    def setUp(self):
        frappe.session.user = "Administrator"

    def tearDown(self):
        frappe.db.rollback()

    def test_defaults_loadable(self):
        """get_single returns a doc and exposes the documented default fields."""
        settings = frappe.get_single("Dropoff Container Settings")

        for fieldname in (
            "weight_variance_threshold_pct",
            "auto_print_sticker_default",
        ):
            self.assertTrue(
                hasattr(settings, fieldname),
                f"Dropoff Container Settings missing field {fieldname}",
            )
