// Copyright (c) 2026, X-DESK and contributors
// For license information, please see license.txt

frappe.ui.form.on("POS Order", {
	setup: function (frm) {
		// Filter SMT Price Lock by same supplier and Open/Partially Settled
		frm.set_query("smt_price_lock", function () {
			return {
				filters: {
					supplier: frm.doc.supplier || "",
					status: ["in", ["Open", "Partially Settled"]],
					docstatus: 1
				}
			};
		});
	},

	smt_price_lock: function (frm) {
		if (!frm.doc.smt_price_lock) return;

		frappe.call({
			method: "frappe.client.get",
			args: {
				doctype: "SMT Price Lock",
				name: frm.doc.smt_price_lock
			},
			callback: function (r) {
				if (!r.message) return;
				let po = r.message;

				// Auto-fill supplier if not set
				if (!frm.doc.supplier && po.supplier) {
					frm.set_value("supplier", po.supplier);
				}

				// Populate order_items from PO items
				frm.clear_table("order_items");
				(po.items || []).forEach(function (po_item) {
					if (flt(po_item.remaining_qty) > 0) {
						let row = frm.add_child("order_items");
						row.item_code = po_item.item_code;
						row.item_name = po_item.item_name;
						row.uom = po_item.uom || "Kg";
						row.weight = po_item.remaining_qty;
					}
				});
				frm.refresh_field("order_items");
				frappe.show_alert({
					message: __("Populated {0} items from SMT Price Lock", [po.items.length]),
					indicator: "green"
				});
			}
		});
	}
});
