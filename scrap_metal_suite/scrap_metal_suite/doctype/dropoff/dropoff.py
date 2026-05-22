# Copyright (c) 2025, Scrap Metal Suite and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime

from scrap_metal_suite.overrides.naming import supplier_daily_name


class Dropoff(Document):
    """
    Drop-off DocType Controller

    Implements validations from DROPOFF_ARCHITECTURE.md Part 13 (Edge Cases)
    Updated for 1-truck-per-dropoff design (license_plate on form, not child table).

    Naming: DO-{supplier_short}-YYMMDD-# where YYMMDD is the scheduled-start
    date (falls back to creation if scheduled_start is empty). Counter is
    per-supplier, per-day; grows past single digit if a supplier exceeds 9
    drop-offs in one day.
    """

    def autoname(self):
        # Use scheduled-start date when set; otherwise current time.
        on_date = self.dropoff_scheduled_start or None
        self.name = supplier_daily_name("DO", self.supplier, on_date=on_date)

    def validate(self):
        self.validate_at_least_one_order()    # Wave 9 — no walk-ins
        self.validate_single_supplier()       # Edge Case 13.3
        self.validate_no_duplicate_orders()   # Edge Case 13.12
        self.validate_expected_items_match_orders()  # Phase 8C
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
        self.calculate_grade_deviation()        # NEW: Wave 9 — replaces per-container deviation
        self.auto_transition_status()           # NEW: Phase 8A
        self.calculate_verification_status()    # NEW: Phase 8A
        self.allocate_weights_if_completed()    # UPDATED: Phase 8A

    def on_update(self):
        """After save, update linked POS Orders if we just closed."""
        self.update_pos_orders_if_closed()

    def on_cancel(self):
        """When Drop-off is cancelled, recalculate fulfillment for all linked orders"""
        self.recalculate_order_fulfillment()

    # =========================================================================
    # VALIDATIONS (Edge Cases from Part 13)
    # =========================================================================

    def validate_at_least_one_order(self):
        """Wave 9: every Dropoff is bound to at least one POS Order.

        There are no walk-in suppliers in this business — if a truck shows up
        without an existing Price Lock, the office creates one on the spot
        before scheduling the Dropoff. Empty `orders` would mean the upstream
        chain (PL → POS Order → Dropoff) was bypassed, which historically led
        to dropoffs that couldn't be settled. See
        docs/DROPOFF_CONTAINER_REDESIGN.md §14.18.
        """
        if not self.orders:
            frappe.throw(
                _(
                    "A Dropoff must be linked to at least one POS Order. "
                    "Create a Price Lock first (it auto-creates the POS Order), "
                    "then add it to this Dropoff's Linked Orders table."
                ),
                title=_("POS Order Required"),
            )

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

    def validate_expected_items_match_orders(self):
        """
        Phase 8C: Validate that expected items match linked orders.

        Rules:
        1. All expected items must exist in at least one linked order
        2. Each linked order must have at least one item in expected items
        """
        # Only validate if orders are linked
        if not self.orders:
            return

        # Get all items from all orders (union)
        all_order_items = set()
        order_items_map = {}  # Track items per order

        for order_row in self.orders:
            if not order_row.pos_order:
                continue

            items = frappe.get_all(
                "POS Order Item",
                filters={"parent": order_row.pos_order},
                fields=["item_code"]
            )

            order_item_codes = {item.item_code for item in items}
            all_order_items.update(order_item_codes)
            order_items_map[order_row.pos_order] = order_item_codes

        # Get expected items
        expected_item_codes = {row.item for row in self.expected_items if row.item}

        # Validation 1: All expected items must exist in at least one order
        for expected_item in expected_item_codes:
            if expected_item not in all_order_items:
                frappe.throw(
                    _("Item '{0}' in Expected Items is not found in any linked POS Order").format(expected_item)
                )

        # Validation 2: Each order must have at least one item in expected items
        for order_name, order_item_codes in order_items_map.items():
            if not order_item_codes.intersection(expected_item_codes):
                frappe.throw(
                    _("POS Order '{0}' is linked but none of its items are in Expected Items. Please add items from this order or remove the order link.").format(order_name)
                )

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
        Edge Case 13.21: Cannot remove orders from a Completed Drop-off.
        Phase 8A: Changed from "Closed" to "Completed".
        """
        if self.status != "Completed":
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
                _("Cannot remove orders from a Completed Drop-off: {0}").format(
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

    def auto_transition_status(self):
        """
        Auto-transition status based on data. Runs on before_save.
        Phase 8A: Simplified status flow (5 statuses with auto-transitions)

        Flow:
        - Draft → Scheduled: when has license_plate AND dropoff_scheduled_start
        - Scheduled → In Progress: when first weight recorded
        - In Progress → Completed: when all weights done (gross + tare + scrap)
        """
        if self.status == "Cancelled":
            return  # Never auto-transition cancelled

        has_gross = self.gross_weight and self.gross_weight > 0
        has_tare = self.tare_weight and self.tare_weight > 0
        has_scrap = self.total_scrap_weight and self.total_scrap_weight > 0

        # Draft → Scheduled: when has license_plate AND dropoff_scheduled_start
        if self.status == "Draft":
            if self.license_plate and self.dropoff_scheduled_start:
                self.status = "Scheduled"

        # Scheduled → In Progress: when first weight recorded
        if self.status == "Scheduled":
            if has_gross or has_tare or has_scrap:
                self.status = "In Progress"

        # In Progress → Completed: weights done AND a submitted Scrap Weight
        # receipt exists (i.e. operator has clicked Finish Container Weighing).
        # Wave 11: the SW gate prevents auto-promotion after `reopen_dropoff`
        # cancels the receipt — the dropoff stays In Progress until the
        # operator explicitly re-finishes + re-completes.
        if self.status == "In Progress":
            if has_gross and has_tare and has_scrap:
                if frappe.db.exists("Scrap Weight", {"dropoff": self.name, "docstatus": 1}):
                    self.status = "Completed"

    def calculate_verification_status(self):
        """
        Compute verification_status based on weights and variance.
        Phase 8A: Read-only informational field (doesn't affect workflow)

        Values:
        - Pending: Missing weights
        - Verified: All weights AND variance within threshold
        - Needs Review: All weights AND variance NOT ok

        If the dropoff has been manually verified via override
        (`verification_overridden=1`), keep it Verified — the override is a
        durable audit decision and must not be reset by recompute.
        """
        if self.verification_overridden:
            self.verification_status = "Verified"
            return

        has_gross = self.gross_weight and self.gross_weight > 0
        has_tare = self.tare_weight and self.tare_weight > 0
        has_scrap = self.total_scrap_weight and self.total_scrap_weight > 0

        if not (has_gross and has_tare and has_scrap):
            self.verification_status = "Pending"
        elif self.truck_variance_ok and self.indicated_variance_ok and self.grade_deviation_ok:
            self.verification_status = "Verified"
        else:
            self.verification_status = "Needs Review"

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
        Aggregate actual weighed items from Active Scrap Weight Container records.

        Source-of-truth changed (Dropoff Container Redesign §6):
        - Was: aggregated from `Scrap Weight` + `Scrap Weight Item` (caused duplication
          when each "submit" inserted a fresh full-snapshot Scrap Weight).
        - Now: aggregates from `Scrap Weight Container` where status='Active'.
          Each container is a single grade with a single net weight; reweighs mutate
          the container in place rather than creating new docs.

        Populates:
        - self.item_summary: per-grade aggregation (weight, container_count, is_expected)
        - self.total_actual_weight: sum of Active container net_weight
        - self.container_count

        NOTE: self.actual_items is DEPRECATED and intentionally left empty.

        Grade-mix deviation (Wave 9): the per-container `is_deviation` /
        `deviation_*` flags moved to `calculate_grade_deviation()` at the
        Dropoff level. The operator no longer marks individual bags as
        deviations during weighing — the deviation is an aggregate fact
        compared at completion.
        """
        if not self.name:
            return

        # Clear summary table; deprecated actual_items intentionally left empty.
        self.actual_items = []
        self.item_summary = []

        containers = self._get_active_containers()
        expected_codes = {row.item for row in self.expected_items if row.item}

        summary = {}
        total = 0.0

        for ct in containers:
            net = flt(ct.get("net_weight"))
            total += net
            code = ct.get("item_code")
            if not code:
                continue

            if code not in summary:
                summary[code] = {
                    "item_name": ct.get("item_name"),
                    "weight": 0.0,
                    "count": 0,
                    "is_expected": code in expected_codes,
                }
            summary[code]["weight"] += net
            summary[code]["count"] += 1

        for code, data in summary.items():
            self.append("item_summary", {
                "item": code,
                "item_name": data["item_name"],
                "total_weight": data["weight"],
                "container_count": data["count"],
                "is_expected": 1 if data["is_expected"] else 0,
            })

        self.total_actual_weight = total
        self.container_count = len(containers)

    def calculate_grade_deviation(self):
        """Compare expected vs actual grade *composition*; binary check.

        Grade-mix deviation lives at the Dropoff level (Wave 9 — see
        docs/DROPOFF_CONTAINER_REDESIGN.md §14.17). The operator records bags
        as plain measurements; the system surfaces "the supplier brought
        different grades than promised" only when reconciling at completion.

        This check is about COMPOSITION (which grades, not how much). The
        kg-level reconciliation is already handled by `indicated_variance`
        (total promised vs total actual) and `truck_variance` (truck net vs
        scrap total) — both with their own thresholds.

        A grade-mix deviation is recorded when:
        - any actual grade is NOT in expected_items (Unplanned), OR
        - any expected grade has ZERO containers delivered (Missing).

        Per-grade kg shortfalls (e.g. expected 1000 kg of A, got 950 kg of A)
        are NOT flagged here — that's an indicated_variance concern. The
        binary unit of deviation is "a bag of an unexpected grade" or "an
        expected grade entirely absent."

        Walk-in / unscheduled dropoffs (no `expected_items`) cannot deviate by
        definition — `grade_deviation_ok` stays 1.
        """
        expected = {row.item for row in self.expected_items if row.item}

        if not expected:
            self.grade_deviation_ok = 1
            self.grade_deviation_summary = ""
            return

        # Index actual containers by grade — keep the bag count for the summary
        # since the user's deviation unit is the bag, not the kilogram.
        actual: dict[str, dict] = {}
        for row in self.item_summary:
            if not row.item:
                continue
            actual[row.item] = {
                "item_name": row.item_name,
                "container_count": int(row.container_count or 0),
            }

        deviation = False
        lines: list[str] = []

        # Unplanned grades (actual but not expected)
        for code in sorted(set(actual) - expected):
            deviation = True
            item_name = actual[code]["item_name"] or code
            count = actual[code]["container_count"]
            lines.append(
                f"{item_name}: ไม่ได้คาด • Unplanned ({count} bag{'s' if count != 1 else ''})"
            )

        # Missing grades (expected but zero actual containers)
        for code in sorted(expected - set(actual)):
            deviation = True
            item_name = frappe.db.get_value("Item", code, "item_name") or code
            lines.append(f"{item_name}: ขาดส่ง • Missing")

        self.grade_deviation_ok = 0 if deviation else 1
        self.grade_deviation_summary = "\n".join(lines)

    def calculate_totals(self):
        """Calculate total truck weight and total scrap weight for variance check.

        Total scrap weight now sources from `total_actual_weight` (populated by
        `sync_actual_items` from Active Scrap Weight Container records). The legacy
        per-Scrap-Weight summing path is retired with the container redesign.
        """
        # Total truck weight is net weight (1-truck design)
        self.total_truck_weight = flt(self.net_weight) if self.net_weight else 0

        # Total scrap weight = sum of Active container net_weight, already computed
        # by sync_actual_items into self.total_actual_weight.
        self.total_scrap_weight = flt(self.total_actual_weight)

        # Calculate variance (Truck vs Scrap)
        if self.total_truck_weight:
            self.truck_variance = self.total_truck_weight - self.total_scrap_weight
            self.truck_variance_percent = abs(self.truck_variance / self.total_truck_weight * 100)
            self.truck_variance_ok = self.truck_variance_percent <= flt(self.truck_variance_threshold_percent or 0.1)
        else:
            self.truck_variance = 0
            self.truck_variance_percent = 0
            self.truck_variance_ok = 1

        # Phase 8B: Calculate indicated variance (Indicated vs Actual)
        self.calculate_indicated_variance()

    def calculate_indicated_variance(self):
        """
        Phase 8B: Calculate variance between indicated weight (what supplier claimed)
        and actual weight (what was actually weighed).

        Indicated weight = total_indicated_weight (sum from expected_items)
        Actual weight = total_actual_weight (sum from actual_items)
        """
        indicated = flt(self.total_indicated_weight)
        actual = flt(self.total_actual_weight)

        if indicated > 0:
            self.indicated_variance = indicated - actual
            self.indicated_variance_percent = abs(self.indicated_variance / indicated * 100)
            self.indicated_variance_ok = self.indicated_variance_percent <= flt(self.indicated_variance_threshold_percent or 0.1)
        else:
            self.indicated_variance = 0
            self.indicated_variance_percent = 0
            self.indicated_variance_ok = 1

    def allocate_weights_if_completed(self):
        """
        Allocate scrap weights to linked POS Orders when Drop-off is Completed.
        Phase 8A: Run on EVERY save when Completed (not just transition).
        Phase 8G: Per-item FIFO allocation (oldest order first).
        """
        if self.status != "Completed":
            return

        if not self.orders:
            return

        if not self.item_summary:
            return

        # Get linked POS Orders sorted by order_date (FIFO - oldest first)
        order_names = [o.pos_order for o in self.orders if o.pos_order]
        if not order_names:
            return

        orders_with_dates = []
        for order_name in order_names:
            order_date = frappe.db.get_value("POS Order", order_name, "order_date")
            orders_with_dates.append((order_name, order_date))

        # Sort by order_date (oldest first)
        orders_with_dates.sort(key=lambda x: x[1] or "9999-99-99")
        sorted_order_names = [o[0] for o in orders_with_dates]

        # Get order items for each POS Order (what they want per item)
        # Structure: {order_name: {item_code: contracted_weight}}
        order_items_map = {}
        for order_name in sorted_order_names:
            order_items = frappe.get_all(
                "POS Order Item",
                filters={"parent": order_name},
                fields=["item_code", "weight"]
            )
            order_items_map[order_name] = {
                item.item_code: flt(item.weight) for item in order_items
            }

        # Track allocations per order (for updating Dropoff Order.allocated_weight)
        order_allocations = {order_name: 0 for order_name in sorted_order_names}

        # Track per-item allocations to populate POS Order Weighed Item
        # Structure: {order_name: [{item_code, weight, scrap_weight}, ...]}
        per_item_allocations = {order_name: [] for order_name in sorted_order_names}

        # For each item in item_summary, allocate using FIFO
        for item_row in self.item_summary:
            item_code = item_row.item
            available_weight = flt(item_row.total_weight)

            if not available_weight:
                continue

            # Find source scrap_weight records for this item (for traceability)
            source_scrap_weights = []
            for actual_item in self.actual_items:
                if actual_item.item == item_code:
                    source_scrap_weights.append({
                        "scrap_weight": actual_item.scrap_weight,
                        "weight": flt(actual_item.actual_weight)
                    })

            # Allocate to orders in FIFO order
            for order_name in sorted_order_names:
                if available_weight <= 0:
                    break

                # How much does this order want of this item?
                wanted = order_items_map.get(order_name, {}).get(item_code, 0)
                if not wanted:
                    continue

                # How much has this order already received for this item?
                already_received = self._get_already_received(order_name, item_code)

                # How much more does this order need?
                still_needed = max(0, wanted - already_received)
                if still_needed <= 0:
                    continue

                # Allocate up to what's needed or available
                to_allocate = min(still_needed, available_weight)

                if to_allocate > 0:
                    # Track for Dropoff Order.allocated_weight
                    order_allocations[order_name] += to_allocate

                    # Track for POS Order Weighed Item (use first source for simplicity)
                    source_sw = source_scrap_weights[0]["scrap_weight"] if source_scrap_weights else None
                    per_item_allocations[order_name].append({
                        "item_code": item_code,
                        "item_name": item_row.item_name,
                        "weight": to_allocate,
                        "scrap_weight": source_sw
                    })

                    available_weight -= to_allocate

        # Update Dropoff Order.allocated_weight (sum of per-item allocations)
        for order_row in self.orders:
            if order_row.pos_order:
                order_row.allocated_weight = flt(order_allocations.get(order_row.pos_order, 0), 2)

        # Store per-item allocations for use in on_update
        self._per_item_allocations = per_item_allocations

    def _get_already_received(self, order_name, item_code):
        """
        Get how much of an item this order has already received from OTHER dropoffs.
        Excludes current dropoff to avoid double-counting during re-allocation.
        """
        existing = frappe.get_all(
            "POS Order Weighed Item",
            filters={
                "parent": order_name,
                "item_code": item_code,
                "dropoff": ["!=", self.name]
            },
            fields=["weight"]
        )
        return sum(flt(row.weight) for row in existing)

    def update_pos_orders_if_closed(self):
        """
        Update linked POS Orders after save if status is Completed.
        Phase 8A: Changed from "Closed" to "Completed".
        Phase 8G: Populate POS Order Weighed Item with per-item allocations.
        Called in on_update after allocations are committed to DB.
        """
        if self.status != "Completed":
            return

        # Get per-item allocations calculated in before_save
        per_item_allocations = getattr(self, "_per_item_allocations", {})

        # Populate POS Order Weighed Item for each order
        for order_row in self.orders:
            if not order_row.pos_order:
                continue

            order_name = order_row.pos_order
            allocations = per_item_allocations.get(order_name, [])

            if allocations:
                order_doc = frappe.get_doc("POS Order", order_name)

                # Remove existing entries from this dropoff (for re-allocation)
                order_doc.items = [
                    item for item in order_doc.items
                    if item.dropoff != self.name
                ]

                # Add new allocations
                for alloc in allocations:
                    order_doc.append("items", {
                        "dropoff": self.name,
                        "scrap_weight": alloc.get("scrap_weight"),
                        "item_code": alloc.get("item_code"),
                        "item_name": alloc.get("item_name"),
                        "weight": alloc.get("weight"),
                        "uom": "Kg"
                    })

                order_doc.flags.ignore_validate = True
                order_doc.save()

        # Recalculate fulfillment on each linked POS Order
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
        Phase 8G: Also removes POS Order Weighed Items from this dropoff.
        """
        for order_row in self.orders:
            if order_row.pos_order:
                # Remove weighed items from this dropoff
                order_doc = frappe.get_doc("POS Order", order_row.pos_order)
                order_doc.items = [
                    item for item in order_doc.items
                    if item.dropoff != self.name
                ]
                order_doc.flags.ignore_validate = True
                order_doc.save()

                # Recalculate fulfillment
                _recalculate_order_fulfillment(order_row.pos_order)

    # =========================================================================
    # CONTAINER REDESIGN — lock / pause / resume / audit / verification
    # See docs/DROPOFF_CONTAINER_REDESIGN.md §4.3, §5.2, §5.3
    # =========================================================================

    def _get_active_containers(self):
        """Return list of dicts for Active Scrap Weight Containers on this Dropoff.

        Used by `sync_actual_items` and any caller that needs the current truth
        of weighed material. Voided/Reweighed (superseded) containers are excluded.
        """
        if not self.name:
            return []

        return frappe.db.get_all(
            "Scrap Weight Container",
            filters={"dropoff": self.name, "status": "Active"},
            fields=[
                "name",
                "item_code",
                "item_name",
                "net_weight",
                "is_deviation",
                "deviation_approved_by",
            ],
            order_by="creation asc",
        )

    def _validate_container_lock(self, session):
        """Validate that a container can be added under the given POS Session.

        Called by the API before insert. Three checks:
        0. The Dropoff must be in a state that accepts new weighing. Completed
           and Cancelled dropoffs reject all new containers — to correct an
           individual bag the operator uses Reweigh on the bag itself, which
           handles the void+new pattern.
        1. If a session is already locked, reject any other session.
        2. If a scale is locked, the incoming session's scale must match it.
        """
        if not session:
            return

        if self.status in ("Completed", "Cancelled"):
            frappe.throw(
                _(
                    "Dropoff {0} is {1} — no new bags can be added. "
                    "To correct a bag, open it and click Reweigh."
                ).format(self.name, self.status),
                title=_("Dropoff Closed"),
            )

        if self.weighing_session and self.weighing_session != session:
            frappe.throw(
                _("Dropoff {0} is locked to session {1}. Pause and resume to switch.").format(
                    self.name, self.weighing_session
                )
            )

        if self.weighing_session:
            scale_of_session = frappe.db.get_value("POS Session", session, "scale")
            if self.weighing_scale and scale_of_session and scale_of_session != self.weighing_scale:
                frappe.throw(
                    _("Dropoff {0} requires scale {1}; current session uses {2}.").format(
                        self.name, self.weighing_scale, scale_of_session
                    )
                )

    def _acquire_container_lock(self, session, scale):
        """Bind this Dropoff to a session/scale on the first container.

        Caller (the API) is responsible for saving — this method only mutates
        the in-memory document. Idempotent if the lock is already held by the
        same session.
        """
        if not self.weighing_session:
            self.weighing_session = session
            self.weighing_scale = scale

        if self.status in ("Scheduled", "Draft"):
            self.status = "In Progress"

    def pause_weighing(self, reason=None):
        """Pause an in-progress dropoff. Clears session lock, keeps scale lock.

        Status transition: In Progress -> Paused.
        """
        if self.status != "In Progress":
            frappe.throw(_("Cannot pause: status is {0}").format(self.status))

        self.status = "Paused"
        self.weighing_session = None
        self.paused_at = now_datetime()
        self.paused_by = frappe.session.user
        self.pause_reason = reason
        # weighing_scale is intentionally retained.
        self.save()

    def resume_weighing(self, session):
        """Resume a paused dropoff under a new (or same) POS Session.

        Status transition: Paused -> In Progress.
        Refuses if the new session's scale doesn't match the pinned scale.
        """
        if self.status != "Paused":
            frappe.throw(_("Cannot resume: status is {0}").format(self.status))

        scale_of_session = frappe.db.get_value("POS Session", session, "scale")
        if self.weighing_scale and scale_of_session and scale_of_session != self.weighing_scale:
            frappe.throw(
                _(
                    "Cannot resume: this dropoff is bound to scale {0}; current session uses {1}. Run Switch Scale first."
                ).format(self.weighing_scale, scale_of_session)
            )

        self.weighing_session = session
        self.status = "In Progress"
        self.resumed_at = now_datetime()
        self.resumed_by = frappe.session.user
        self.save()

    def reassign_session(self, new_session, reason):
        """Audit-only manager override that reassigns the locked session.

        The new session must use the same scale (run switch_scale first if not).
        No role guard yet — design doc §5.2 marks this as audit-only.
        """
        scale_of_session = frappe.db.get_value("POS Session", new_session, "scale")
        if self.weighing_scale and scale_of_session and scale_of_session != self.weighing_scale:
            frappe.throw(
                _(
                    "Cannot reassign: dropoff is bound to scale {0}; session {1} uses scale {2}. Run Switch Scale first."
                ).format(self.weighing_scale, new_session, scale_of_session)
            )

        self.weighing_session = new_session
        self.weighing_reassigned_at = now_datetime()
        self.weighing_reassigned_by = frappe.session.user
        self.weighing_reassign_reason = reason
        self.save()
        self.add_comment(
            "Comment",
            _("Session reassigned to {0}: {1}").format(new_session, reason or ""),
        )

    def switch_scale(self, new_scale, reason):
        """Audit-only manager override that re-pins the dropoff to a new scale.

        Existing containers keep their original scale stamp; only future
        containers will record `new_scale`.
        """
        self.weighing_scale = new_scale
        self.weighing_scale_changed_at = now_datetime()
        self.weighing_scale_changed_by = frappe.session.user
        self.weighing_scale_change_reason = reason
        self.save()
        self.add_comment(
            "Comment",
            _("Scale switched to {0}: {1}").format(new_scale, reason or ""),
        )

    def void_weighing(self, reason):
        """Void all Active containers and reset the dropoff for fresh re-weighing.

        Status transition: any -> Scheduled. Lock fields cleared so any session
        can pick up the dropoff again.
        """
        active = frappe.get_all(
            "Scrap Weight Container",
            filters={"dropoff": self.name, "status": "Active"},
            pluck="name",
        )

        for container_name in active:
            frappe.db.set_value(
                "Scrap Weight Container",
                container_name,
                {
                    "status": "Voided",
                    "voided_reason": reason,
                    "voided_at": now_datetime(),
                    "voided_by": frappe.session.user,
                },
            )

        self.weighing_session = None
        self.weighing_scale = None
        self.status = "Scheduled"
        self.save()
        self.add_comment(
            "Comment",
            _("Weighing voided ({0} container(s)): {1}").format(len(active), reason or ""),
        )

    def mark_verified(self, override_reason=None):
        """Mark the dropoff Verified.

        Idempotent if already Verified. If currently Needs Review, an override
        reason is required and gets recorded for audit.
        """
        if self.verification_status == "Verified":
            return

        if self.verification_status == "Needs Review":
            if not override_reason:
                frappe.throw(_("Override reason required to verify a Needs-Review dropoff"))

            self.verification_status = "Verified"
            self.verification_overridden = 1
            self.verification_override_at = now_datetime()
            self.verification_override_by = frappe.session.user
            self.verification_override_reason = override_reason
            self.save()
            self.add_comment(
                "Comment",
                _("Verification override applied: {0}").format(override_reason),
            )
            return

        # Pending or other states: just save as Verified.
        self.verification_status = "Verified"
        self.save()


def _recalculate_order_fulfillment(pos_order_name):
    """
    Recalculate fulfillment from source of truth.
    Phase 8G: Per-item fulfillment calculation.
    """
    order = frappe.get_doc("POS Order", pos_order_name)

    # Remove weighed items from cancelled dropoffs
    valid_items = []
    for item in order.items:
        if item.dropoff:
            dropoff_status = frappe.db.get_value("Dropoff", item.dropoff, "status")
            if dropoff_status != "Cancelled":
                valid_items.append(item)
        else:
            valid_items.append(item)  # Keep items without dropoff link
    order.items = valid_items

    # Calculate per-item received weights
    item_received = {}  # {item_code: total_received}
    for item in order.items:
        if item.item_code:
            if item.item_code not in item_received:
                item_received[item.item_code] = 0
            item_received[item.item_code] += flt(item.weight)

    # Update received_weight on order_items and calculate per-item fulfillment
    total_received = 0
    for order_item in order.order_items:
        received = flt(item_received.get(order_item.item_code, 0))
        order_item.received_weight = received
        total_received += received

        # Calculate per-item fulfillment percentage
        contracted = flt(order_item.weight)
        if contracted > 0:
            order_item.item_fulfillment_percent = (received / contracted) * 100
        else:
            order_item.item_fulfillment_percent = 0

    order.total_received = flt(total_received)

    # Calculate overall fulfillment percentage
    contracted = flt(order.contracted_weight)
    if contracted > 0:
        order.fulfillment_percent = (order.total_received / contracted) * 100
    else:
        order.fulfillment_percent = 0

    # Determine fulfillment status
    order.fulfillment_status = _get_fulfillment_status(order.fulfillment_percent)

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


@frappe.whitelist()
def get_events(start, end, filters=None):
    """
    Get dropoff events for calendar view.

    Args:
        start: Start datetime for calendar range
        end: End datetime for calendar range
        filters: Optional additional filters

    Returns:
        list: Events for calendar display
    """
    from frappe.desk.calendar import get_event_conditions

    conditions = get_event_conditions("Dropoff", filters)

    events = frappe.db.sql("""
        SELECT
            name,
            dropoff_scheduled_start as start,
            dropoff_scheduled_end as end,
            status,
            license_plate,
            supplier_name
        FROM `tabDropoff`
        WHERE (
            (dropoff_scheduled_start BETWEEN %(start)s AND %(end)s)
            OR (dropoff_scheduled_end BETWEEN %(start)s AND %(end)s)
            OR (dropoff_scheduled_start <= %(start)s AND dropoff_scheduled_end >= %(end)s)
        )
        {conditions}
        ORDER BY dropoff_scheduled_start
    """.format(conditions=conditions), {
        "start": start,
        "end": end
    }, as_dict=True)

    # Format events for calendar display
    for event in events:
        event["title"] = f"{event.name} - {event.license_plate or 'No Plate'}"
        if event.supplier_name:
            event["title"] += f" ({event.supplier_name})"

    return events


