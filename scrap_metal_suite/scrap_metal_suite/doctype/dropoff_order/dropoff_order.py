# Copyright (c) 2025, Scrap Metal Suite and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class DropoffOrder(Document):
    """Dropoff Order child table - links Drop-off to POS Orders (M:M relationship)."""
    pass
