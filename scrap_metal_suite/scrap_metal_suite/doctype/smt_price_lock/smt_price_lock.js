// Copyright (c) 2026, X-DESK and contributors
// For license information, please see license.txt

frappe.ui.form.on("SMT Price Lock", {
	// No special setup needed — status is system-managed
});

frappe.ui.form.on("SMT Price Lock Item", {
	po_qty: function (frm, cdt, cdn) {
		calculate_row_amount(frm, cdt, cdn);
	},
	po_rate: function (frm, cdt, cdn) {
		calculate_row_amount(frm, cdt, cdn);
	},
	items_remove: function (frm) {
		calculate_totals(frm);
	}
});

function calculate_row_amount(frm, cdt, cdn) {
	let row = locals[cdt][cdn];
	row.po_amount = flt(row.po_qty * row.po_rate, 2);
	row.remaining_qty = flt(row.po_qty) - flt(row.settled_qty);
	refresh_field("po_amount", cdn, "items");
	refresh_field("remaining_qty", cdn, "items");
	calculate_totals(frm);
}

function calculate_totals(frm) {
	let total_po = 0;
	let total_settled = 0;
	(frm.doc.items || []).forEach(row => {
		total_po += flt(row.po_amount);
		total_settled += flt(row.settled_qty) * flt(row.po_rate);
	});
	frm.set_value("total_po_value", flt(total_po, 2));
	frm.set_value("total_settled_value", flt(total_settled, 2));
}
