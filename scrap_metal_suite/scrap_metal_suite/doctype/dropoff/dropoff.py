# Copyright (c) 2025, Scrap Metal Suite and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class Dropoff(Document):
    """
    Drop-off DocType Controller

    Implements validations from DROPOFF_ARCHITECTURE.md Part 13 (Edge Cases)
    Updated for 1-truck-per-dropoff design (license_plate on form, not child table)
    """

    def validate(self):
        self.validate_single_supplier()       # Edge Case 13.3
        self.validate_no_duplicate_orders()   # Edge Case 13.12
        self.validate_date_not_changed()      # Edge Case 13.16
        self.validate_scheduled_times()       # Ensure end > start
        self.validate_closed_immutable()      # Edge Case 13.21
        self.validate_weight_removal()        # Edge Case 13.22 (adapted)
        self.validate_cancellation_reason()   # Part 10.2
        self.validate_tare_less_than_gross()  # Edge Case 13.20
        self.calculate_indicated_total()      # Sum expected items

    def before_save(self):
        self.set_supplier_from_orders()
        self.calculate_net_weight()
        self.sync_actual_items()
        self.calculate_totals()
        self.allocate_weights_if_closing()

    def on_update(self):
        """After save, update linked POS Orders if we just closed."""
        self.update_pos_orders_if_closed()

    def on_cancel(self):
        """When Drop-off is cancelled, recalculate fulfillment for all linked orders"""
        self.recalculate_order_fulfillment()

    # =========================================================================
    # VALIDATIONS (Edge Cases from Part 13)
    # =========================================================================

    def validate_single_supplier(self):
        """
        Edge Case 13.3: All orders in a Drop-off must be from the same supplier.
        """
        if not self.orders:
            return

        suppliers = set()
        for row in self.orders:
            order_supplier = frappe.db.get_value("POS Order", row.pos_order, "supplier")
            if order_supplier:
                suppliers.add(order_supplier)

        if len(suppliers) > 1:
            frappe.throw(
                _("All orders in a Drop-off must be from the same supplier. Found: {0}").format(
                    ", ".join(suppliers)
                )
            )

    def validate_no_duplicate_orders(self):
        """
        Edge Case 13.12: Same order cannot be linked multiple times.
        """
        if not self.orders:
            return

        orders = [o.pos_order for o in self.orders if o.pos_order]
        if len(orders) != len(set(orders)):
            frappe.throw(_("Same order cannot be linked multiple times to the same Drop-off"))

    def validate_date_not_changed(self):
        """
        Edge Case 13.16: Lock dropoff_scheduled_start once status moves past Draft/Scheduled.
        """
        if self.status not in ["Draft", "Scheduled"]:
            if self.has_value_changed("dropoff_scheduled_start"):
                frappe.throw(_("Cannot change scheduled start time after weighing has started"))

    def validate_scheduled_times(self):
        """Ensure scheduled end is after scheduled start."""
        if self.dropoff_scheduled_start and self.dropoff_scheduled_end:
            from frappe.utils import get_datetime
            start = get_datetime(self.dropoff_scheduled_start)
            end = get_datetime(self.dropoff_scheduled_end)

            if end <= start:
                frappe.throw(_("Scheduled End must be after Scheduled Start"))

    def validate_closed_immutable(self):
        """
        Edge Case 13.21: Cannot remove orders from a Closed Drop-off.
        """
        if self.status != "Closed":
            return

        old_doc = self.get_doc_before_save()
        if not old_doc:
            return

        # Check if orders were removed
        old_orders = {o.pos_order for o in old_doc.orders}
        new_orders = {o.pos_order for o in self.orders}
        removed = old_orders - new_orders

        if removed:
            frappe.throw(
                _("Cannot remove orders from a Closed Drop-off: {0}").format(
                    ", ".join(removed)
                )
            )

    def validate_weight_removal(self):
        """
        Edge Case 13.22 (adapted for 1-truck design): Cannot clear license plate if weights recorded.
        """
        old_doc = self.get_doc_before_save()
        if not old_doc:
            return

        # Check if license plate is being removed while weights exist
        if old_doc.license_plate and not self.license_plate:
            if old_doc.gross_weight or old_doc.tare_weight:
                frappe.throw(
                    _("Cannot remove license plate - weights already recorded. Cancel the Drop-off instead.")
                )

        # Check if license plate changed while weights recorded
        if old_doc.license_plate and self.license_plate:
            if old_doc.license_plate != self.license_plate:
                if old_doc.gross_weight or old_doc.tare_weight:
                    frappe.throw(
                        _("Cannot change license plate from {0} - weights already recorded. Cancel the Drop-off instead.").format(
                            old_doc.license_plate
                        )
                    )

    def validate_tare_less_than_gross(self):
        """
        Edge Case 13.20: Tare weight must be less than gross weight.
        """
        if self.gross_weight and self.tare_weight:
            if self.tare_weight >= self.gross_weight:
                frappe.throw(
                    _("Tare weight ({0} kg) must be less than gross weight ({1} kg)").format(
                        self.tare_weight, self.gross_weight
                    )
                )

    def validate_cancellation_reason(self):
        """
        Part 10.2: Cancellation requires a reason.
        """
        if self.status == "Cancelled":
            if not self.cancellation_reason:
                frappe.throw(_("Cancellation reason is required"))

            # Set cancellation metadata if not already set
            if not self.cancelled_by:
                self.cancelled_by = frappe.session.user
            if not self.cancelled_at:
                self.cancelled_at = now_datetime()

    def calculate_indicated_total(self):
        """
        Sum total_indicated_weight from expected_items child table.
        """
        if self.expected_items:
            self.total_indicated_weight = sum(
                flt(item.indicated_weight) for item in self.expected_items
            )
        else:
            self.total_indicated_weight = 0

    # =========================================================================
    # BEFORE SAVE LOGIC
    # =========================================================================

    def set_supplier_from_orders(self):
        """Auto-set supplier from the first linked order."""
        if self.orders and not self.supplier:
            first_order = self.orders[0]
            if first_order.pos_order:
                self.supplier = frappe.db.get_value(
                    "POS Order", first_order.pos_order, "supplier"
                )

    def calculate_net_weight(self):
        """Calculate net weight from gross and tare (1-truck design)."""
        if self.gross_weight and self.tare_weight:
            self.net_weight = flt(self.gross_weight) - flt(self.tare_weight)
        elif self.gross_weight and not self.tare_weight:
            self.net_weight = None  # Cannot calculate without tare
        else:
            self.net_weight = None

    def sync_actual_items(self):
        """
        Fetch actual weighed items from linked Scrap Weight records.
        Populates the actual_items child table and item_summary (aggregated by item).
        """
        if not self.name:
            return

        # Clear existing tables
        self.actual_items = []
        self.item_summary = []

        # Get all Scrap Weight records linked to this dropoff
        scrap_weights = frappe.db.get_all(
            "Scrap Weight",
            filters={"dropoff": self.name},
            fields=["name"]
        )

        total_actual = 0
        # Dictionary to aggregate by item
        item_totals = {}  # {item_code: {"item_name": str, "weight": float, "count": int}}

        for sw in scrap_weights:
            # Get items from each Scrap Weight
            items = frappe.db.get_all(
                "Scrap Weight Item",
                filters={"parent": sw.name},
                fields=["item_code", "item_name", "weight"]
            )
            for item in items:
                weight = flt(item.weight)

                # Add to actual_items (detailed view)
                self.append("actual_items", {
                    "scrap_weight": sw.name,
                    "item": item.item_code,
                    "item_name": item.item_name,
                    "actual_weight": weight
                })
                total_actual += weight

                # Aggregate by item
                if item.item_code not in item_totals:
                    item_totals[item.item_code] = {
                        "item_name": item.item_name,
                        "weight": 0,
                        "count": 0
                    }
                item_totals[item.item_code]["weight"] += weight
                item_totals[item.item_code]["count"] += 1

        # Populate item_summary from aggregated data
        for item_code, data in item_totals.items():
            self.append("item_summary", {
                "item": item_code,
                "item_name": data["item_name"],
                "total_weight": data["weight"],
                "weigh_count": data["count"]
            })

        self.total_actual_weight = total_actual

    def calculate_totals(self):
        """Calculate total truck weight and total scrap weight for variance check."""
        # Total truck weight is net weight (1-truck design)
        self.total_truck_weight = flt(self.net_weight) if self.net_weight else 0

        # Calculate total scrap weight from linked Scrap Weight records
        if self.name:
            scrap_weights = frappe.db.get_all(
                "Scrap Weight",
                filters={"dropoff": self.name},
                fields=["total_weight"]
            )
            total_scrap = sum(flt(sw.total_weight) for sw in scrap_weights)
        else:
            total_scrap = 0

        self.total_scrap_weight = flt(total_scrap)

        # Calculate variance
        if self.total_truck_weight:
            self.truck_variance = self.total_truck_weight - self.total_scrap_weight
            self.truck_variance_percent = abs(self.truck_variance / self.total_truck_weight * 100)
            self.variance_ok = self.truck_variance_percent <= flt(self.variance_threshold_percent or 0.01)
        else:
            self.truck_variance = 0
            self.truck_variance_percent = 0
            self.variance_ok = 1

    def allocate_weights_if_closing(self):
        """
        Allocate scrap weights to linked POS Orders when Drop-off is closing.
        Called in before_save so allocations are saved with the document.
        """
        old_doc = self.get_doc_before_save()
        old_status = old_doc.status if old_doc else None

        # Only allocate when transitioning TO Closed status
        if self.status != "Closed" or old_status == "Closed":
            return

        if not self.orders:
            return

        total_scrap = flt(self.total_scrap_weight)
        if not total_scrap:
            return

        # Calculate total contracted weight across all orders
        total_contracted = 0
        order_contracts = {}  # {pos_order: contracted_weight}

        for order_row in self.orders:
            if order_row.pos_order:
                contracted = flt(frappe.db.get_value(
                    "POS Order", order_row.pos_order, "contracted_weight"
                ))
                order_contracts[order_row.pos_order] = contracted
                total_contracted += contracted

        # Allocate weights to child table rows
        for order_row in self.orders:
            if order_row.pos_order:
                if total_contracted > 0:
                    # Pro-rata allocation
                    ratio = order_contracts[order_row.pos_order] / total_contracted
                    order_row.allocated_weight = flt(total_scrap * ratio, 2)
                else:
                    # Equal split if no contracted weights
                    order_row.allocated_weight = flt(total_scrap / len(self.orders), 2)

    def update_pos_orders_if_closed(self):
        """
        Update linked POS Orders after save if status is Closed.
        Called in on_update after allocations are committed to DB.
        """
        if self.status != "Closed":
            return

        # Update fulfillment on each linked POS Order
        for order_row in self.orders:
            if order_row.pos_order:
                _recalculate_order_fulfillment(order_row.pos_order)

    # =========================================================================
    # FULFILLMENT SYNC (Edge Case 13.4)
    # =========================================================================

    def recalculate_order_fulfillment(self):
        """
        Edge Case 13.4: When Drop-off is cancelled, recalculate fulfillment
        for all linked orders from source of truth (non-cancelled drop-offs).
        """
        for order_row in self.orders:
            if order_row.pos_order:
                _recalculate_order_fulfillment(order_row.pos_order)


def _recalculate_order_fulfillment(pos_order_name):
    """
    Recalculate fulfillment from source of truth (non-cancelled drop-offs).
    Called when a Drop-off is cancelled.
    """
    order = frappe.get_doc("POS Order", pos_order_name)

    # Sum allocated_weight from ALL non-cancelled Drop-offs for this order
    dropoff_orders = frappe.db.get_all(
        "Dropoff Order",
        filters={"pos_order": pos_order_name},
        fields=["parent", "allocated_weight"]
    )

    # Filter to only non-cancelled drop-offs
    total_received = 0
    for do in dropoff_orders:
        dropoff_status = frappe.db.get_value("Dropoff", do.parent, "status")
        if dropoff_status != "Cancelled":
            total_received += flt(do.allocated_weight)

    order.total_received = flt(total_received)

    # Calculate fulfillment percentage
    contracted = flt(order.contracted_weight)
    if contracted > 0:
        order.fulfillment_percent = (order.total_received / contracted) * 100
    else:
        order.fulfillment_percent = 0

    # Determine fulfillment status
    order.fulfillment_status = _get_fulfillment_status(order.fulfillment_percent)

    # Update dropoff_status
    order.dropoff_status = _get_order_dropoff_status(pos_order_name)

    order.flags.ignore_validate = True
    order.save()


def _get_fulfillment_status(percent):
    """
    Determine fulfillment status based on percentage.
    Reference: Part 2.5 of DROPOFF_ARCHITECTURE.md
    """
    if percent == 0:
        return "Pending"
    elif percent < 98:
        return "Partial"
    elif percent <= 102:
        return "Fulfilled"
    else:
        return "Over-delivered"


def _get_order_dropoff_status(pos_order_name):
    """
    Edge Case 13.5: Calculate dropoff_status for POS Order.
    """
    dropoff_orders = frappe.db.get_all(
        "Dropoff Order",
        filters={"pos_order": pos_order_name},
        fields=["parent"]
    )

    if not dropoff_orders:
        return "No Drop-off"

    # Get status of each non-cancelled dropoff
    statuses = []
    for do in dropoff_orders:
        dropoff_status = frappe.db.get_value("Dropoff", do.parent, "status")
        if dropoff_status and dropoff_status != "Cancelled":
            statuses.append(dropoff_status)

    if not statuses:
        return "No Drop-off"

    if "Closed" in statuses:
        return "Received"
    elif any(s in ["Weighing", "Unloading", "Verified"] for s in statuses):
        return "In Progress"
    elif "Scheduled" in statuses:
        return "Scheduled"
    else:
        return "No Drop-off"
