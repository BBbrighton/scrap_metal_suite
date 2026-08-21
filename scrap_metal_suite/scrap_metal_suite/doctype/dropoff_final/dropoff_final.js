// Copyright (c) 2026, X-DESK and contributors
// For license information, please see license.txt

frappe.ui.form.on('Dropoff Final', {
	refresh: function(frm) {
		// Add custom buttons
		if (frm.doc.dropoff) {
			frm.add_custom_button(__('View Dropoff'), function() {
				frappe.set_route('Form', 'Dropoff', frm.doc.dropoff);
			});

			// Show all sorting sessions
			if (frm.doc.sorting_sessions) {
				frm.add_custom_button(__('View Sorting Sessions'), function() {
					frappe.route_options = {
						'dropoff': frm.doc.dropoff,
						'docstatus': 1
					};
					frappe.set_route('List', 'Production Sorting');
				});
			}
		}

		// Show status indicator
		if (frm.doc.status === 'Completed' && frm.doc.variance_ok) {
			frm.dashboard.set_headline_alert(
				__('Dropoff sorting completed and verified ✓'),
				'green'
			);
		} else if (frm.doc.status === 'In Progress') {
			frm.dashboard.set_headline_alert(
				__('Sorting in progress - {0} kg sorted of {1} kg total ({2}%)',
					[
						frm.doc.total_verified_weight.toFixed(2),
						frm.doc.dropoff_total_weight.toFixed(2),
						((frm.doc.total_verified_weight / frm.doc.dropoff_total_weight) * 100).toFixed(1)
					]),
				'blue'
			);
		} else if (frm.doc.verification_status === 'Needs Review') {
			frm.dashboard.set_headline_alert(
				__('Variance exceeds threshold - needs manager review'),
				'orange'
			);
		}

		// Manager override — the only way out of "In Progress".
		//
		// auto_complete_if_done() parks a record here when it has sorted items
		// but the variance exceeds tolerance. Nothing else can move it: every
		// field is read-only and the form is save-disabled below, so without
		// this button the document is stranded and can never be settled.
		if (frm.doc.status === 'In Progress' && !frm.doc.variance_overridden) {
			frm.add_custom_button(__('Accept Variance & Release'), function() {
				frappe.prompt(
					[{
						fieldname: 'override_reason',
						fieldtype: 'Small Text',
						label: __('Why is this discrepancy acceptable?'),
						reqd: 1,
					}],
					function(values) {
						frappe.call({
							method: 'scrap_metal_suite.api.v1.production.accept_dropoff_final_variance',
							args: {
								dropoff_final: frm.doc.name,
								override_reason: values.override_reason,
							},
							freeze: true,
							freeze_message: __('Applying override…'),
							callback: function(r) {
								if (r.message && r.message.success) {
									frappe.show_alert({
										message: __('Released for settlement'),
										indicator: 'green',
									}, 5);
									frm.reload_doc();
								}
							},
						});
					},
					__('Accept Variance of {0}%', [flt(frm.doc.variance_percent).toFixed(2)]),
					__('Accept & Release')
				);
			}).addClass('btn-warning');
		}

		if (frm.doc.variance_overridden) {
			frm.dashboard.set_headline_alert(
				__('Variance of {0}% accepted by {1} — {2}', [
					flt(frm.doc.variance_percent).toFixed(2),
					frm.doc.variance_override_by,
					frm.doc.variance_override_reason,
				]),
				'orange'
			);
		}

		// Show summary stats
		show_summary_stats(frm);

		// All fields are read-only (auto-populated)
		frm.disable_save();
	},

	dropoff: function(frm) {
		if (frm.doc.dropoff && !frm.doc.dropoff_total_weight) {
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
						frm.set_value('dropoff_date', r.message.dropoff_date);

						// Check for purchase_order
						if (r.message.purchase_order) {
							frm.set_value('purchase_order', r.message.purchase_order);
						}
					}
				}
			});
		}
	}
});

function show_summary_stats(frm) {
	if (!frm.doc.dropoff) return;

	let html = `
		<div style="padding: 15px; background: #f9f9f9; border-radius: 5px; margin-top: 10px;">
			<h4 style="margin-top: 0;">${__('Summary')}</h4>
			<table class="table table-bordered" style="margin-bottom: 0;">
				<tr>
					<th style="width: 50%;">${__('Metric')}</th>
					<th style="text-align: right;">${__('Value')}</th>
				</tr>
				<tr>
					<td>${__('Dropoff Total Weight')}</td>
					<td style="text-align: right;"><strong>${flt(frm.doc.dropoff_total_weight).toFixed(3)} kg</strong></td>
				</tr>
				<tr style="background: #e8f5e9;">
					<td>${__('Total Good Weight (Payable)')}</td>
					<td style="text-align: right; color: green;"><strong>${flt(frm.doc.total_good_weight).toFixed(3)} kg</strong></td>
				</tr>
				<tr style="background: #ffebee;">
					<td>${__('Total Unwanted Weight (Returned)')}</td>
					<td style="text-align: right; color: red;"><strong>${flt(frm.doc.total_unwanted_weight).toFixed(3)} kg</strong></td>
				</tr>
				<tr>
					<td>${__('Total Verified Weight')}</td>
					<td style="text-align: right;"><strong>${flt(frm.doc.total_verified_weight).toFixed(3)} kg</strong></td>
				</tr>
				<tr ${Math.abs(frm.doc.weight_variance) > 0.1 ? 'style="background: #fff3cd;"' : ''}>
					<td>${__('Weight Variance')}</td>
					<td style="text-align: right;">${flt(frm.doc.weight_variance).toFixed(3)} kg (${flt(frm.doc.variance_percent).toFixed(2)}%)</td>
				</tr>
				<tr>
					<td>${__('Net Payable Percentage')}</td>
					<td style="text-align: right; font-size: 1.2em;">
						<strong style="color: ${frm.doc.variance_ok ? 'green' : 'orange'};">
							${((frm.doc.total_good_weight / frm.doc.dropoff_total_weight) * 100).toFixed(2)}%
						</strong>
					</td>
				</tr>
			</table>
		</div>
	`;

	frm.set_df_property('section_verification', 'description', html);
}
