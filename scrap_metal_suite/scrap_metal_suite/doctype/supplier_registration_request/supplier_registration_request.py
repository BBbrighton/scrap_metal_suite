"""Supplier Registration Request DocType Controller"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate, now_datetime


class SupplierRegistrationRequest(Document):
    def validate(self):
        self.validate_email()

    def validate_email(self):
        """Check if email is already registered"""
        if self.is_new():
            existing = frappe.db.exists(
                "Supplier Registration Request",
                {"email": self.email, "status": ["in", ["Pending Approval", "Approved"]], "name": ["!=", self.name]}
            )
            if existing:
                frappe.throw(_("A registration request with this email already exists."))

    def before_submit(self):
        """Set status to Pending Approval on submit"""
        self.status = "Pending Approval"

    @frappe.whitelist()
    def approve(self):
        """Approve the registration and create a Supplier"""
        if self.status != "Pending Approval":
            frappe.throw(_("Only requests with 'Pending Approval' status can be approved."))

        # Create the Supplier
        supplier = self._create_supplier()

        # Create Address
        if self.address_line_1:
            self._create_address(supplier.name)

        # Create Contact
        self._create_contact(supplier.name)

        # Update registration request
        self.status = "Approved"
        self.approved_by = frappe.session.user
        self.approval_date = now_datetime()
        self.linked_supplier = supplier.name
        self.save(ignore_permissions=True)

        frappe.msgprint(
            _("Supplier {0} has been created successfully.").format(supplier.name),
            title=_("Registration Approved"),
            indicator="green"
        )

        return supplier.name

    @frappe.whitelist()
    def reject(self, reason):
        """Reject the registration request"""
        if self.status != "Pending Approval":
            frappe.throw(_("Only requests with 'Pending Approval' status can be rejected."))

        if not reason:
            frappe.throw(_("Please provide a reason for rejection."))

        self.status = "Rejected"
        self.rejection_reason = reason
        self.approved_by = frappe.session.user
        self.approval_date = now_datetime()
        self.save(ignore_permissions=True)

        frappe.msgprint(
            _("Registration request has been rejected."),
            title=_("Registration Rejected"),
            indicator="red"
        )

    def _create_supplier(self):
        """Create a new Supplier from registration data"""
        supplier = frappe.new_doc("Supplier")
        supplier.supplier_name = self.company_name
        supplier.supplier_type = self.supplier_type
        supplier.tax_id = self.tax_id
        # Set source to Webform since created from registration request
        supplier.custom_source = "Webform"
        supplier.custom_registration_request = self.name

        # Set supplier group (default if exists)
        default_group = frappe.db.get_single_value("Buying Settings", "supplier_group")
        if default_group:
            supplier.supplier_group = default_group
        else:
            # Use first available supplier group
            groups = frappe.get_all("Supplier Group", limit=1)
            if groups:
                supplier.supplier_group = groups[0].name

        supplier.insert(ignore_permissions=True)
        return supplier

    def _create_address(self, supplier_name):
        """Create an Address linked to the Supplier"""
        address = frappe.new_doc("Address")
        address.address_title = self.company_name
        address.address_type = "Billing"
        address.address_line1 = self.address_line_1
        address.address_line2 = self.address_line_2
        address.city = self.city
        address.state = self.state
        address.pincode = self.postal_code
        address.country = self.country
        address.phone = self.phone
        address.email_id = self.email
        address.is_primary_address = 1
        address.is_shipping_address = 1

        address.append("links", {
            "link_doctype": "Supplier",
            "link_name": supplier_name
        })

        address.insert(ignore_permissions=True)
        return address

    def _create_contact(self, supplier_name):
        """Create a Contact linked to the Supplier"""
        # Split contact person name
        name_parts = (self.contact_person or "").split(" ", 1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        contact = frappe.new_doc("Contact")
        contact.first_name = first_name
        contact.last_name = last_name
        contact.is_primary_contact = 1

        if self.email:
            contact.append("email_ids", {
                "email_id": self.email,
                "is_primary": 1
            })

        if self.mobile:
            contact.append("phone_nos", {
                "phone": self.mobile,
                "is_primary_mobile_no": 1
            })

        if self.phone:
            contact.append("phone_nos", {
                "phone": self.phone,
                "is_primary_phone": 1
            })

        contact.append("links", {
            "link_doctype": "Supplier",
            "link_name": supplier_name
        })

        contact.insert(ignore_permissions=True)
        return contact


@frappe.whitelist(allow_guest=True)
def submit_registration(data):
    """
    Public API endpoint to submit a supplier registration request.
    Called from the public registration form.
    """
    import json

    if isinstance(data, str):
        data = json.loads(data)

    # Validate required fields
    required_fields = ["company_name", "supplier_type", "contact_person", "email", "mobile", "address_line_1", "city", "country"]
    for field in required_fields:
        if not data.get(field):
            frappe.throw(_("Field '{0}' is required.").format(field))

    # Check for existing registration
    existing = frappe.db.exists(
        "Supplier Registration Request",
        {"email": data.get("email"), "status": ["in", ["Pending Approval", "Approved"]]}
    )
    if existing:
        frappe.throw(_("A registration with this email already exists."))

    # Create the registration request
    doc = frappe.new_doc("Supplier Registration Request")

    # Map fields
    field_mapping = [
        "company_name", "supplier_type", "tax_id", "business_registration_number",
        "contact_person", "email", "phone", "mobile",
        "address_line_1", "address_line_2", "city", "state", "postal_code", "country",
        "materials_supplied", "bank_name", "bank_account_number", "bank_branch",
        "bank_account_name", "notes"
    ]

    for field in field_mapping:
        if data.get(field):
            doc.set(field, data.get(field))

    doc.status = "Draft"
    doc.registration_date = nowdate()
    doc.insert(ignore_permissions=True)
    doc.submit()

    return {
        "success": True,
        "message": _("Thank you for registering! Your application is under review."),
        "registration_id": doc.name
    }
