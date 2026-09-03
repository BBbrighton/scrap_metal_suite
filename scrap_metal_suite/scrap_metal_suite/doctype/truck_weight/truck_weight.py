# Copyright (c) 2025, Scrap Metal Suite and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class TruckWeight(Document):
    def validate(self):
        self.validate_exactly_one_parent()
        self.validate_weight()
        self.validate_scale_max()

    def validate_exactly_one_parent(self):
        """A weighing belongs to a delivery or a collection, never both or neither.

        `dropoff` used to be mandatory at the field level. The sale side weighs
        the same trucks on the same scale, so that field is now optional and the
        guarantee lives here instead - otherwise a weighing could end up
        attached to nothing and silently drop out of both sides' totals.
        """
        if self.dropoff and self.pickup:
            frappe.throw(_("A truck weight cannot belong to both a Dropoff and a Pickup"))
        if not self.dropoff and not self.pickup:
            frappe.throw(_("A truck weight must belong to either a Dropoff or a Pickup"))

    def validate_weight(self):
        """Ensure weight is positive"""
        if self.weight and self.weight <= 0:
            frappe.throw("Weight must be greater than zero")

    def validate_scale_max(self):
        """Ensure weight doesn't exceed scale maximum capacity"""
        if self.scale and self.weight:
            scale_doc = frappe.get_doc("Scale", self.scale)
            # Field is `max_capacity_kg` — an earlier `max_capacity` here meant
            # hasattr() was always False and the check never fired, so
            # over-capacity truck weights were accepted silently.
            if scale_doc.get("max_capacity_kg"):
                if self.weight > scale_doc.max_capacity_kg:
                    frappe.throw(
                        f"Weight {self.weight} kg exceeds scale maximum capacity of {scale_doc.max_capacity_kg} kg"
                    )

    def after_insert(self):
        """Update Dropoff with latest weight"""
        self.update_dropoff_weight()

    def on_update(self):
        """Update Dropoff when weight is modified"""
        self.update_dropoff_weight()

    def on_trash(self):
        """Clear Dropoff weight when record is deleted"""
        self.clear_dropoff_weight()

    def update_dropoff_weight(self):
        """Copy weight to Dropoff based on weight type"""
        if not self.dropoff:
            return

        dropoff = frappe.get_doc("Dropoff", self.dropoff)

        if self.weight_type == "Gross":
            dropoff.gross_weight = self.weight
            dropoff.gross_weight_scale = self.scale
            dropoff.gross_weight_time = self.weighed_at
            dropoff.gross_weight_operator = self.operator
        elif self.weight_type == "Tare":
            dropoff.tare_weight = self.weight
            dropoff.tare_weight_scale = self.scale
            dropoff.tare_weight_time = self.weighed_at
            dropoff.tare_weight_operator = self.operator

        # Recalculate net weight
        if dropoff.gross_weight and dropoff.tare_weight:
            dropoff.net_weight = dropoff.gross_weight - dropoff.tare_weight

        dropoff.flags.ignore_validate = True
        dropoff.save()

    def clear_dropoff_weight(self):
        """Clear weight from Dropoff when record is deleted"""
        if not self.dropoff:
            return

        # Check if there are other weight records of the same type
        other_weights = frappe.get_all(
            "Truck Weight",
            filters={
                "dropoff": self.dropoff,
                "weight_type": self.weight_type,
                "name": ["!=", self.name]
            },
            order_by="weighed_at desc",
            limit=1
        )

        dropoff = frappe.get_doc("Dropoff", self.dropoff)

        if other_weights:
            # Use the most recent other weight
            other = frappe.get_doc("Truck Weight", other_weights[0].name)
            if self.weight_type == "Gross":
                dropoff.gross_weight = other.weight
                dropoff.gross_weight_scale = other.scale
                dropoff.gross_weight_time = other.weighed_at
                dropoff.gross_weight_operator = other.operator
            else:
                dropoff.tare_weight = other.weight
                dropoff.tare_weight_scale = other.scale
                dropoff.tare_weight_time = other.weighed_at
                dropoff.tare_weight_operator = other.operator
        else:
            # Clear the weight fields
            if self.weight_type == "Gross":
                dropoff.gross_weight = None
                dropoff.gross_weight_scale = None
                dropoff.gross_weight_time = None
                dropoff.gross_weight_operator = None
            else:
                dropoff.tare_weight = None
                dropoff.tare_weight_scale = None
                dropoff.tare_weight_time = None
                dropoff.tare_weight_operator = None

        # Recalculate net weight
        if dropoff.gross_weight and dropoff.tare_weight:
            dropoff.net_weight = dropoff.gross_weight - dropoff.tare_weight
        else:
            dropoff.net_weight = None

        dropoff.flags.ignore_validate = True
        dropoff.save()
