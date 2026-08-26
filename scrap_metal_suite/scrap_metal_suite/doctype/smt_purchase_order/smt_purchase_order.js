// Copyright (c) 2026, X-DESK and contributors
// For license information, please see license.txt

frappe.ui.form.on("SMT Purchase Order", {
	refresh: function (frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Pull Items from Dropoff Finals"), function () {
				pull_items_from_dropoff_finals(frm);
			}).addClass("btn-primary");
		}
	},
	supplier: function (frm) {
		// Clear child tables when supplier changes
		if (frm.doc.supplier) {
			// Set filter for drop_off_finals to only show drawable ones for this supplier
			frm.set_query("drop_off_final", "drop_off_finals", function () {
				return {
					filters: {
						supplier: frm.doc.supplier,
						status: ["in", ["Unsettled", "Partially Settled"]]
					}
				};
			});
		}
	},
	setup: function (frm) {
		// Filter Dropoff Finals by supplier and drawable status. "Partially
		// Settled" belongs here: a delivery can be settled in instalments across
		// several PO Finals, so anything not yet fully drawn is still selectable.
		frm.set_query("drop_off_final", "drop_off_finals", function () {
			return {
				filters: {
					supplier: frm.doc.supplier || "",
					status: ["in", ["Unsettled", "Partially Settled"]]
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

// --- Pull items from Dropoff Finals -----------------------------------------
//
// Implements PRICE_LOCK_SETTLEMENT_DESIGN.md §6 step 2->4, specced in v1 and
// never built — until now every allocation row was hand-typed.
//
// Note what this deliberately does NOT do: it never fills in source_type, po or
// rate. Design decision #7 forbids automatic FIFO allocation because choosing
// which Price Lock to draw down is the accountant's business judgment. This
// removes the transcription, not the decision.

function pull_items_from_dropoff_finals(frm) {
	if (!(frm.doc.drop_off_finals || []).length) {
		frappe.msgprint({
			title: __("No Dropoff Finals Listed"),
			message: __("Add at least one Dropoff Final to the table above, then pull its items."),
			indicator: "orange"
		});
		return;
	}

	frm.call({
		doc: frm.doc,
		method: "get_pullable_items",
		freeze: true,
		freeze_message: __("Reading Dropoff Finals...")
	}).then(function (r) {
		const rows = (r && r.message) || [];
		if (!rows.length) {
			frappe.msgprint({
				title: __("Nothing Left to Pull"),
				message: __("Every wanted item on the listed Dropoff Finals is already allocated — either on this document or on another PO Final."),
				indicator: "blue"
			});
			return;
		}
		show_pull_dialog(frm, rows);
	});
}

function show_pull_dialog(frm, rows) {
	// Remember the server's figure: the grid lets the accountant type over
	// `qty` to draw only part of a line, and we still need the ceiling.
	rows.forEach(function (row) {
		row.max_qty = flt(row.qty);
	});

	const dialog = new frappe.ui.Dialog({
		title: __("Pull Items from Dropoff Finals"),
		size: "extra-large",
		fields: [
			{
				fieldname: "intro",
				fieldtype: "HTML",
				options:
					'<p class="text-muted" style="margin-bottom:10px">' +
					__("Wanted items only — returned material is never paid for. Quantities are what remains after other PO Finals and anything already allocated here. Lower a quantity to settle part of it now and the rest on a later PO Final.") +
					"</p>"
			},
			{
				fieldname: "items",
				fieldtype: "Table",
				cannot_add_rows: true,
				in_place_edit: false,
				data: rows,
				get_data: function () {
					return rows;
				},
				fields: [
					{
						fieldname: "drop_off_final",
						fieldtype: "Data",
						label: __("Dropoff Final"),
						in_list_view: 1,
						read_only: 1,
						columns: 2
					},
					{
						fieldname: "item_code",
						fieldtype: "Data",
						label: __("Item Code"),
						in_list_view: 1,
						read_only: 1,
						columns: 2
					},
					{
						fieldname: "item_name",
						fieldtype: "Data",
						label: __("Item Name"),
						in_list_view: 1,
						read_only: 1,
						columns: 2
					},
					{
						fieldname: "received_qty",
						fieldtype: "Float",
						label: __("Received"),
						precision: 3,
						in_list_view: 1,
						read_only: 1,
						columns: 1
					},
					{
						fieldname: "settled_elsewhere",
						fieldtype: "Float",
						label: __("Settled Elsewhere"),
						precision: 3,
						in_list_view: 1,
						read_only: 1,
						columns: 1
					},
					{
						fieldname: "qty",
						fieldtype: "Float",
						label: __("Pull Qty"),
						precision: 3,
						in_list_view: 1,
						reqd: 1,
						columns: 2
					},
					{ fieldname: "uom", fieldtype: "Data", hidden: 1 },
					{ fieldname: "max_qty", fieldtype: "Float", hidden: 1 }
				]
			}
		],
		primary_action_label: __("Add Allocation Rows"),
		primary_action: function () {
			const selected = dialog.fields_dict.items.grid.get_selected_children();

			if (!selected.length) {
				frappe.msgprint({
					title: __("Nothing Selected"),
					message: __("Tick the rows you want to pull."),
					indicator: "orange"
				});
				return;
			}

			// Client-side courtesy check. validate_dropoff_coverage() on the
			// server is the real gate — this just avoids a round trip.
			const over = selected.filter(function (row) {
				return flt(row.qty) > flt(row.max_qty);
			});
			if (over.length) {
				frappe.msgprint({
					title: __("Quantity Too High"),
					message: __("{0} on {1}: only {2} remains.", [
						over[0].item_code,
						over[0].drop_off_final,
						format_number(over[0].max_qty, null, 3)
					]),
					indicator: "red"
				});
				return;
			}

			let added = 0;
			selected.forEach(function (row) {
				if (flt(row.qty) <= 0) {
					return;
				}
				frm.add_child("allocations", {
					drop_off_final: row.drop_off_final,
					item_code: row.item_code,
					item_name: row.item_name,
					qty: flt(row.qty)
					// source_type / po / rate left blank on purpose — see above.
				});
				added++;
			});

			frm.refresh_field("allocations");
			dialog.hide();

			if (added) {
				frappe.show_alert({
					message: __("{0} allocation row(s) added. Set the source for each.", [added]),
					indicator: "green"
				});
			}
		}
	});

	dialog.show();
}

frappe.ui.form.on("SMT Purchase Order Allocation", {
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
			// Fetch rate from PO by reading the parent doc
			frappe.call({
				method: "frappe.client.get",
				args: {
					doctype: "SMT Price Lock",
					name: row.po
				},
				callback: function (r) {
					if (r.message && r.message.items) {
						let match = r.message.items.find(
							i => i.item_code === row.item_code
						);
						if (match) {
							frappe.model.set_value(cdt, cdn, "rate", match.po_rate);
							frappe.model.set_value(cdt, cdn, "po_item_row", match.name);
							calculate_row_amount(frm, cdt, cdn);
						}
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
