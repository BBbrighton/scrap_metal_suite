# Copyright (c) 2025, Scrap Metal Suite and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.password import check_password, update_password


class POSAuthorityCode(Document):
    def validate(self):
        self.validate_pin_format()

    def validate_pin_format(self):
        """Ensure PIN is numeric and at least 4 digits"""
        if self.pin_code and not self.pin_code.isdigit():
            frappe.throw(_("PIN Code must contain only numbers"))
        if self.pin_code and len(self.pin_code) < 4:
            frappe.throw(_("PIN Code must be at least 4 digits"))

    @staticmethod
    def verify_pin(pin_code, permission=None):
        """
        Verify a PIN code and optionally check permission.

        Args:
            pin_code: The PIN to verify
            permission: Optional permission to check (can_override_rate, can_void_purchase, etc.)

        Returns:
            dict: {valid: bool, user: str, user_full_name: str} or raises exception
        """
        if not pin_code:
            frappe.throw(_("PIN Code is required"))

        # Find authority codes and check PIN
        authorities = frappe.get_all(
            "POS Authority Code",
            fields=["name", "user", "user_full_name", "pin_code",
                    "can_override_rate", "can_void_purchase", "can_close_any_session"]
        )

        for auth in authorities:
            # Get the actual PIN value
            stored_pin = frappe.utils.password.get_decrypted_password(
                "POS Authority Code", auth.name, "pin_code"
            )

            if stored_pin == pin_code:
                # PIN matches, check permission if specified
                if permission and not auth.get(permission):
                    frappe.throw(
                        _("User {0} does not have permission: {1}").format(
                            auth.user_full_name, permission
                        )
                    )

                return {
                    "valid": True,
                    "user": auth.user,
                    "user_full_name": auth.user_full_name
                }

        frappe.throw(_("Invalid PIN Code"))
