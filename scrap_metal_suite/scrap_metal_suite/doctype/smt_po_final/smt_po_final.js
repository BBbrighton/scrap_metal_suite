// Copyright (c) 2026, X-DESK and contributors
// For license information, please see license.txt

frappe.ui.form.on("SMT PO Final", {
	supplier: function (frm) {
		// Clear child tables when supplier changes
		if (frm.doc.supplier) {
			// Set filter for drop_off_finals to only show Unsettled for this supplier
			frm.set_query("drop_off_final", "drop_off_finals", function () {
				return {
					filters: {
						supplier: frm.doc.supplier,
						status: "Unsettled"
					}
				};
			});
		}
	},
	setup: function (frm) {
		// Filter Dropoff Finals by supplier and Unsettled status
		frm.set_query("drop_off_final", "drop_off_finals", function () {
			return {
				filters: {
					supplier: frm.doc.supplier || "",
					status: "Unsettled"
				}
			};
		});

		// Filter POs in allocation rows by supplier and open status
		frm.set_query("po", "allocations", function () {
			return {
				filters: {
					supplier: frm.doc.supplier || "",
					status: ["in", ["Open", "Partially Settled"]],
					docstatus: 1
				}
			};
		});
	}
});

frappe.ui.form.on("SMT PO Final Allocation", {
	source_type: function (frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.source_type === "Spot") {
			// Clear PO fields for spot
			frappe.model.set_value(cdt, cdn, "po", "");
			frappe.model.set_value(cdt, cdn, "po_item_row", "");
			frappe.model.set_value(cdt, cdn, "rate", 0);
		}
	},
	po: function (frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.source_type === "PO" && row.po && row.item_code) {
			// Fetch rate from PO item row
			frappe.call({
				method: "frappe.client.get_list",
				args: {
					doctype: "SMT PO Item",
					filters: {
						parent: row.po,
						item_code: row.item_code
					},
					fields: ["name", "po_rate", "remaining_qty"],
					limit_page_length: 1
				},
				callback: function (r) {
					if (r.message && r.message.length > 0) {
						let po_item = r.message[0];
						frappe.model.set_value(cdt, cdn, "rate", po_item.po_rate);
						frappe.model.set_value(cdt, cdn, "po_item_row", po_item.name);
						calculate_row_amount(frm, cdt, cdn);
					}
				}
			});
		}
	},
	qty: function (frm, cdt, cdn) {
		calculate_row_amount(frm, cdt, cdn);
	},
	rate: function (frm, cdt, cdn) {
		calculate_row_amount(frm, cdt, cdn);
	},
	allocations_remove: function (frm) {
		calculate_totals(frm);
	}
});

function calculate_row_amount(frm, cdt, cdn) {
	let row = locals[cdt][cdn];
	row.amount = flt(row.qty * row.rate, 2);
	refresh_field("amount", cdn, "allocations");
	calculate_totals(frm);
}

function calculate_totals(frm) {
	let total_po = 0;
	let total_spot = 0;
	(frm.doc.allocations || []).forEach(row => {
		let amt = flt(row.amount);
		if (row.source_type === "PO") {
			total_po += amt;
		} else {
			total_spot += amt;
		}
	});
	frm.set_value("total_po_value", flt(total_po, 2));
	frm.set_value("total_spot_value", flt(total_spot, 2));
	frm.set_value("total_amount", flt(total_po + total_spot, 2));
}
