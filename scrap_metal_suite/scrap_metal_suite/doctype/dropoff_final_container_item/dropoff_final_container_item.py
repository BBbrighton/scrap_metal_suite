# Copyright (c) 2026, Scrap Metal Suite and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class DropoffFinalContainerItem(Document):
    """Per-bag detail on a Dropoff Final: what arrived, and what it sorted into.

    One received container can produce several rows — a 100 kg bag of Grade A
    may sort into 90 kg Grade A, 9 kg Grade B and 1 kg of tare — so
    `received_weight` repeats across the rows of one container. Sum distinct
    containers, not rows, when totalling the received side.

    Every field is read-only: the received side is copied from the immutable
    Scrap Weight Container, and the sorted side from submitted Production
    Sorting rows. The table is rebuilt by
    DropoffFinal.aggregate_from_sortings().
    """
    pass
