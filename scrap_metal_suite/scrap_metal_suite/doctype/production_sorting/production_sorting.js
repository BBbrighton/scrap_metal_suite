// Copyright (c) 2026, X-DESK and contributors
// For license information, please see license.txt

frappe.ui.form.on('Production Sorting', {
	refresh: function(frm) {
		// Add custom buttons
		if (frm.doc.docstatus === 1 && frm.doc.status === 'Completed') {
			frm.add_custom_button(__('View Dropoff Final'), function() {
				frappe.call({
					method: 'scrap_metal_suite.api.v1.production.get_dropoff_final_status',
					args: { dropoff: frm.doc.dropoff },
					callback: function(r) {
						if (r.message && r.message.name) {
							frappe.set_route('Form', 'Dropoff Final', r.message.name);
						} else {
							frappe.msgprint(__('Dropoff Final not found'));
						}
					}
				});
			});
		}

		// Set field properties
		frm.set_df_property('good_items', 'cannot_add_rows', frm.doc.docstatus === 1);
		frm.set_df_property('good_items', 'cannot_delete_rows', frm.doc.docstatus === 1);
		frm.set_df_property('unwanted_items', 'cannot_add_rows', frm.doc.docstatus === 1);
		frm.set_df_property('unwanted_items', 'cannot_delete_rows', frm.doc.docstatus === 1);
	},

	dropoff: function(frm) {
		if (frm.doc.dropoff) {
			// Fetch dropoff details
			frappe.call({
				method: 'frappe.client.get',
				args: {
					doctype: 'Dropoff',
					name: frm.doc.dropoff
				},
				callback: function(r) {
					if (r.message) {
						frm.set_value('dropoff_total_weight', r.message.total_actual_weight);
						frm.set_value('license_plate', r.message.license_plate);
						frm.set_value('supplier', r.message.supplier);
						frm.set_value('supplier_name', r.message.supplier_name);

						// Populate source items if they exist
						if (r.message.item_summary && !frm.doc.source_items.length) {
							frm.clear_table('source_items');
							r.message.item_summary.forEach(function(item) {
								let child = frm.add_child('source_items');
								child.item = item.item;
								child.item_name = item.item_name;
								child.total_weight = item.total_weight;
							});
							frm.refresh_field('source_items');
						}
					}
				}
			});

			// Check if Dropoff Final exists
			frappe.call({
				method: 'scrap_metal_suite.api.v1.production.get_dropoff_final_status',
				args: { dropoff: frm.doc.dropoff },
				callback: function(r) {
					if (r.message && r.message.name) {
						let msg = __('Dropoff Final {0} exists: {1} sorting session(s), Status: {2}',
							[r.message.name, r.message.sorting_count || 0, r.message.status]);
						frm.dashboard.add_comment(msg, 'blue', true);
					}
				}
			});
		}
	},

	before_save: function(frm) {
		// Calculate totals (backup in case server-side fails)
		calculate_totals(frm);
	}
});

// Good Items child table
frappe.ui.form.on('Production Sorting Good Item', {
	weight: function(frm, cdt, cdn) {
		calculate_totals(frm);
	},

	good_items_remove: function(frm) {
		calculate_totals(frm);
	}
});

// Unwanted Items child table
frappe.ui.form.on('Production Sorting Unwanted Item', {
	weight: function(frm, cdt, cdn) {
		calculate_totals(frm);
	},

	unwanted_items_remove: function(frm) {
		calculate_totals(frm);
	},

	return_reason: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (!row.return_reason) {
			frappe.model.set_value(cdt, cdn, 'return_reason', 'Other');
		}
	}
});

function calculate_totals(frm) {
	let total_good = 0;
	let total_unwanted = 0;

	// Sum good items
	(frm.doc.good_items || []).forEach(function(item) {
		total_good += flt(item.weight);
	});

	// Sum unwanted items
	(frm.doc.unwanted_items || []).forEach(function(item) {
		total_unwanted += flt(item.weight);
	});

	// Set totals
	frm.set_value('total_good_weight', total_good);
	frm.set_value('total_unwanted_weight', total_unwanted);
	frm.set_value('total_weight', total_good + total_unwanted);

	// Show warning if total doesn't match dropoff
	if (frm.doc.dropoff_total_weight) {
		let dropoff_total = flt(frm.doc.dropoff_total_weight);
		let sorted_total = total_good + total_unwanted;
		let variance = Math.abs(dropoff_total - sorted_total);
		let variance_percent = dropoff_total > 0 ? (variance / dropoff_total) * 100 : 0;

		if (variance_percent > 0.1) {
			let msg = __('Total weight ({0} kg) does not match dropoff weight ({1} kg). Variance: {2} kg ({3}%)',
				[sorted_total.toFixed(3), dropoff_total.toFixed(3), variance.toFixed(3), variance_percent.toFixed(2)]);
			frm.dashboard.set_headline_alert(msg, 'orange');
		} else {
			frm.dashboard.clear_headline();
		}
	}
}
