// Copyright (c) 2026, Scrap Metal Suite and contributors
// For license information, please see license.txt

frappe.ui.form.on("Scrap Weight Container", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}

		const status = frm.doc.status;

		if (status === "Active") {
			// Reweigh
			frm.add_custom_button(__("Reweigh"), () => {
				frappe.prompt(
					[
						{
							fieldname: "new_weight",
							label: __("New Net Weight (kg)"),
							fieldtype: "Float",
							reqd: 1,
						},
						{
							fieldname: "reason",
							label: __("Reason"),
							fieldtype: "Small Text",
							reqd: 1,
						},
					],
					(values) => {
						frappe.call({
							method: "scrap_metal_suite.api.v1.dropoff.reweigh_container",
							args: {
								container: frm.doc.name,
								net_weight: values.new_weight,
								reason: values.reason,
							},
							callback: () => frm.reload_doc(),
						});
					},
					__("Reweigh Container"),
					__("Save")
				);
			});

			// Void
			frm.add_custom_button(__("Void"), () => {
				frappe.prompt(
					[
						{
							fieldname: "reason",
							label: __("Reason"),
							fieldtype: "Small Text",
							reqd: 1,
						},
					],
					(values) => {
						frappe.call({
							method: "scrap_metal_suite.api.v1.dropoff.void_container",
							args: {
								container: frm.doc.name,
								reason: values.reason,
							},
							callback: () => frm.reload_doc(),
						});
					},
					__("Void Container"),
					__("Confirm")
				);
			});

			// Print Thermal
			frm.add_custom_button(
				__("Print Thermal"),
				() => {
					const url =
						"/printview?doctype=Scrap%20Weight%20Container" +
						"&name=" +
						encodeURIComponent(frm.doc.name) +
						"&format=Scrap%20Weight%20Container%20Thermal" +
						"&no_letterhead=1";
					window.open(url, "_blank");
				},
				__("Print")
			);

			// Print Sticker
			frm.add_custom_button(
				__("Print Sticker"),
				() => {
					const url =
						"/printview?doctype=Scrap%20Weight%20Container" +
						"&name=" +
						encodeURIComponent(frm.doc.name) +
						"&format=Scrap%20Weight%20Container%20Sticker" +
						"&no_letterhead=1";
					window.open(url, "_blank");
				},
				__("Print")
			);
		}

		// Approve Deviation — visible when deviation exists and is not yet approved
		if (frm.doc.is_deviation && !frm.doc.deviation_approved_by) {
			frm.add_custom_button(__("Approve Deviation"), () => {
				frappe.prompt(
					[
						{
							fieldname: "reason",
							label: __("Reason (optional)"),
							fieldtype: "Small Text",
						},
					],
					(values) => {
						frappe.call({
							method: "scrap_metal_suite.api.v1.dropoff.approve_container_deviation",
							args: {
								container: frm.doc.name,
								reason: values.reason || "",
							},
							callback: () => frm.reload_doc(),
						});
					},
					__("Approve Deviation"),
					__("Approve")
				);
			});
		}
	},
});
